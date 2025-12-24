"""Conversation API endpoints for human-in-loop dashboard integration.

These endpoints allow humans to view and respond to escalated conversations
through a dashboard interface.

Endpoints:
- GET /conversations - List threads waiting for human
- GET /conversations/{thread_id} - Get thread details
- GET /conversations/{thread_id}/messages - Get messages
- POST /conversations/{thread_id}/messages - Human sends message
- POST /conversations/{thread_id}/resolve - Mark resolved, resume workflow
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.infra.db.connection import get_session
from app.domain.conversations.models import (
    ConversationThread,
    Message,
    ThreadStatus,
    SenderType,
)
from app.domain.workflow.service import WorkflowService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])


# Request/Response Models

class CreateMessageRequest(BaseModel):
    """Request to create a message in a thread."""
    sender_id: UUID = Field(description="UUID of the human sender (user_id)")
    content: str = Field(description="Message content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional metadata")


class ResolveThreadRequest(BaseModel):
    """Request to resolve a conversation thread."""
    resolution: Dict[str, Any] = Field(description="Resolution details and next steps")
    resume_workflow: bool = Field(default=True, description="Whether to resume workflow")
    resolved_by: UUID = Field(description="UUID of the human who resolved (user_id)")


class ThreadResponse(BaseModel):
    """Response model for conversation thread."""
    id: UUID
    creator_id: UUID
    consumer_id: UUID
    workflow_execution_id: Optional[UUID]
    agent_id: Optional[UUID]
    status: str
    escalation_reason: str
    context: Dict[str, Any]
    resolution: Optional[Dict[str, Any]]
    created_at: datetime
    resolved_at: Optional[datetime]
    resumed_at: Optional[datetime]
    message_count: int = 0

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Response model for message."""
    id: UUID
    thread_id: UUID
    sender_type: str
    sender_id: UUID
    content: str
    metadata: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


# API Endpoints

@router.get("", response_model=List[ThreadResponse])
async def list_conversations(
    status: Optional[str] = Query(None, description="Filter by status"),
    creator_id: Optional[UUID] = Query(None, description="Filter by creator"),
    limit: int = Query(100, le=500, description="Max threads to return"),
    session: Session = Depends(get_session)
):
    """List conversation threads, optionally filtered.

    By default, returns threads waiting for human intervention.

    Args:
        status: Optional status filter (active, waiting_human, resolved, etc.)
        creator_id: Optional creator filter
        limit: Maximum number of threads to return (default 100, max 500)

    Returns:
        List of conversation threads with message counts
    """
    try:
        # Build query
        statement = select(ConversationThread).order_by(
            ConversationThread.created_at.desc()
        ).limit(limit)

        # Apply filters
        if status:
            statement = statement.where(ConversationThread.status == status)
        elif not creator_id:
            # Default: show threads waiting for human
            statement = statement.where(
                ConversationThread.status.in_([
                    ThreadStatus.ACTIVE,
                    ThreadStatus.WAITING_HUMAN
                ])
            )

        if creator_id:
            statement = statement.where(ConversationThread.creator_id == creator_id)

        threads = list(session.exec(statement).all())

        # Get message counts for each thread
        thread_responses = []
        for thread in threads:
            message_count_stmt = select(Message).where(
                Message.thread_id == thread.id
            )
            message_count = len(list(session.exec(message_count_stmt).all()))

            thread_response = ThreadResponse.model_validate(thread)
            thread_response.message_count = message_count
            thread_responses.append(thread_response)

        logger.info(
            f"Retrieved {len(thread_responses)} conversation threads",
            extra={
                "status_filter": status,
                "creator_filter": str(creator_id) if creator_id else None
            }
        )

        return thread_responses

    except Exception as e:
        logger.error(f"Failed to list conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_conversation(
    thread_id: UUID,
    session: Session = Depends(get_session)
):
    """Get conversation thread details by ID.

    Args:
        thread_id: Thread UUID

    Returns:
        Conversation thread with message count

    Raises:
        404: Thread not found
    """
    try:
        thread = session.get(ConversationThread, thread_id)

        if not thread:
            raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")

        # Get message count
        message_count_stmt = select(Message).where(Message.thread_id == thread.id)
        message_count = len(list(session.exec(message_count_stmt).all()))

        thread_response = ThreadResponse.model_validate(thread)
        thread_response.message_count = message_count

        return thread_response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{thread_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    thread_id: UUID,
    limit: int = Query(100, le=500, description="Max messages to return"),
    session: Session = Depends(get_session)
):
    """Get messages in a conversation thread.

    Args:
        thread_id: Thread UUID
        limit: Maximum number of messages to return (default 100, max 500)

    Returns:
        List of messages ordered by creation time

    Raises:
        404: Thread not found
    """
    try:
        # Verify thread exists
        thread = session.get(ConversationThread, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")

        # Get messages
        statement = (
            select(Message)
            .where(Message.thread_id == thread_id)
            .order_by(Message.created_at)
            .limit(limit)
        )

        messages = list(session.exec(statement).all())

        logger.info(
            f"Retrieved {len(messages)} messages for thread {thread_id}",
            extra={"thread_id": str(thread_id)}
        )

        return [MessageResponse.model_validate(msg) for msg in messages]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{thread_id}/messages", response_model=MessageResponse)
async def create_message(
    thread_id: UUID,
    request: CreateMessageRequest,
    session: Session = Depends(get_session)
):
    """Human sends a message in a conversation thread.

    Args:
        thread_id: Thread UUID
        request: Message creation request

    Returns:
        Created message

    Raises:
        404: Thread not found
        400: Thread is resolved or closed
    """
    try:
        # Verify thread exists and is active
        thread = session.get(ConversationThread, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")

        if thread.status in [ThreadStatus.RESOLVED, ThreadStatus.RESUMED, ThreadStatus.ABANDONED]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot send message to {thread.status} thread"
            )

        # Create message
        message = Message(
            thread_id=thread_id,
            sender_type=SenderType.HUMAN,
            sender_id=request.sender_id,
            content=request.content,
            metadata=request.metadata
        )

        session.add(message)

        # Update thread status to waiting_consumer
        thread.status = ThreadStatus.WAITING_CONSUMER

        session.add(thread)
        session.commit()
        session.refresh(message)

        logger.info(
            f"Human message created in thread {thread_id}",
            extra={
                "thread_id": str(thread_id),
                "sender_id": str(request.sender_id),
                "message_preview": request.content[:100]
            }
        )

        return MessageResponse.model_validate(message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create message: {e}", exc_info=True)
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{thread_id}/resolve")
async def resolve_conversation(
    thread_id: UUID,
    request: ResolveThreadRequest,
    session: Session = Depends(get_session)
):
    """Mark conversation thread as resolved and optionally resume workflow.

    Args:
        thread_id: Thread UUID
        request: Resolution request

    Returns:
        Resolution status

    Raises:
        404: Thread not found
        400: Thread already resolved
    """
    try:
        # Get thread
        thread = session.get(ConversationThread, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")

        if thread.status in [ThreadStatus.RESOLVED, ThreadStatus.RESUMED]:
            raise HTTPException(
                status_code=400,
                detail=f"Thread already {thread.status}"
            )

        # Update thread
        thread.status = ThreadStatus.RESOLVED
        thread.resolution = request.resolution
        thread.resolved_at = datetime.utcnow()

        session.add(thread)

        # Resume workflow if requested
        workflow_resumed = False
        if request.resume_workflow and thread.workflow_execution_id:
            workflow_service = WorkflowService(session)
            workflow_service.resume_workflow(
                thread.workflow_execution_id,
                reason=f"Human resolved escalation: {thread.escalation_reason}"
            )

            thread.status = ThreadStatus.RESUMED
            thread.resumed_at = datetime.utcnow()
            workflow_resumed = True

        session.add(thread)
        session.commit()

        logger.info(
            f"Thread {thread_id} resolved",
            extra={
                "thread_id": str(thread_id),
                "resolved_by": str(request.resolved_by),
                "workflow_resumed": workflow_resumed
            }
        )

        return {
            "success": True,
            "thread_id": str(thread_id),
            "status": thread.status,
            "workflow_resumed": workflow_resumed,
            "resolved_at": thread.resolved_at.isoformat() if thread.resolved_at else None,
            "resumed_at": thread.resumed_at.isoformat() if thread.resumed_at else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve conversation: {e}", exc_info=True)
        session.rollback()
        raise HTTPException(status_code=500, detail=str(e))
