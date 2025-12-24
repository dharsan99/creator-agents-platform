"""Conversation models for human-in-loop escalations.

These models track conversations between consumers, agents, and humans
when agents escalate complex scenarios that require human intervention.

Workflow:
1. Agent encounters complex scenario (question, complaint, negotiation)
2. Agent creates ConversationThread and escalates to human
3. Human receives notification via dashboard
4. Human and consumer exchange messages through thread
5. Human resolves thread and resumes workflow
6. Agent continues with workflow based on resolution
"""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from sqlmodel import Column, Field, JSON, SQLModel


class ConversationThread(SQLModel, table=True):
    """Conversation thread for human-in-loop escalations.

    Represents a conversation that has been escalated to a human
    for intervention. Tracks the full context, participants, and
    resolution status.

    Lifecycle:
    - active: Thread created, waiting for human response
    - waiting_human: Consumer replied, awaiting human
    - waiting_consumer: Human replied, awaiting consumer
    - resolved: Human resolved the issue
    - resumed: Workflow resumed after resolution
    - abandoned: Thread abandoned without resolution

    Attributes:
        id: Thread UUID
        creator_id: Creator UUID (owner of the workflow)
        consumer_id: Consumer UUID (who is being helped)
        workflow_execution_id: Optional workflow execution this thread belongs to
        agent_id: Agent that created the escalation
        status: Thread status
        escalation_reason: Why this was escalated (complex_question, complaint, etc.)
        context: Full context at time of escalation
        resolution: How the issue was resolved
        created_at: When thread was created
        resolved_at: When thread was resolved
        resumed_at: When workflow was resumed
    """

    __tablename__ = "conversation_threads"

    # Identity
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    creator_id: UUID = Field(
        foreign_key="creators.id",
        index=True,
        description="Creator who owns this workflow"
    )
    consumer_id: UUID = Field(
        foreign_key="consumers.id",
        index=True,
        description="Consumer in this conversation"
    )
    workflow_execution_id: Optional[UUID] = Field(
        default=None,
        foreign_key="workflow_executions.id",
        index=True,
        description="Workflow execution (if escalated from workflow)"
    )
    agent_id: Optional[UUID] = Field(
        default=None,
        foreign_key="agents.id",
        index=True,
        description="Agent that created the escalation"
    )

    # Thread Status
    status: str = Field(
        default="active",
        index=True,
        description="active, waiting_human, waiting_consumer, resolved, resumed, abandoned"
    )

    # Escalation Details
    escalation_reason: str = Field(
        description="Why escalated: complex_question, complaint, negotiation, etc."
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Full context at time of escalation (workflow state, metrics, etc.)"
    )

    # Resolution
    resolution: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="How the issue was resolved, next steps, etc."
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When thread was created"
    )
    resolved_at: Optional[datetime] = Field(
        default=None,
        description="When thread was resolved"
    )
    resumed_at: Optional[datetime] = Field(
        default=None,
        description="When workflow was resumed after resolution"
    )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "creator_id": "789e0123-e89b-12d3-a456-426614174000",
                "consumer_id": "456e7890-e89b-12d3-a456-426614174000",
                "workflow_execution_id": "321e6543-e89b-12d3-a456-426614174000",
                "agent_id": "111e1111-e89b-12d3-a456-426614174000",
                "status": "active",
                "escalation_reason": "complex_question",
                "context": {
                    "workflow_id": "321e6543-e89b-12d3-a456-426614174000",
                    "current_stage": "followup",
                    "consumer_question": "Can I get a custom payment plan?",
                    "agent_attempted_response": "I don't have authority to customize pricing",
                },
                "resolution": None,
            }
        }


class Message(SQLModel, table=True):
    """Individual message in a conversation thread.

    Represents a single message from a consumer, agent, or human
    within a conversation thread.

    Attributes:
        id: Message UUID
        thread_id: Conversation thread UUID
        sender_type: Who sent this message (consumer, agent, human)
        sender_id: UUID of the sender (consumer, agent, or user)
        content: Message content (text)
        message_metadata: Additional message metadata
        created_at: When message was sent
    """

    __tablename__ = "messages"

    # Identity
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    thread_id: UUID = Field(
        foreign_key="conversation_threads.id",
        index=True,
        description="Conversation thread this message belongs to"
    )

    # Sender Info
    sender_type: str = Field(
        description="consumer, agent, human"
    )
    sender_id: UUID = Field(
        description="UUID of sender (consumer_id, agent_id, or user_id)"
    )

    # Content
    content: str = Field(
        description="Message content (text)"
    )
    message_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON),
        description="Additional metadata: attachments, mentions, formatting, etc."
    )

    # Timestamp
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When message was sent"
    )

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "thread_id": "789e0123-e89b-12d3-a456-426614174000",
                "sender_type": "consumer",
                "sender_id": "456e7890-e89b-12d3-a456-426614174000",
                "content": "Can I get a custom payment plan for your coaching program?",
                "message_metadata": {
                    "channel": "email",
                    "original_message_id": "msg_abc123"
                },
            }
        }


class ThreadStatus:
    """Conversation thread status constants."""
    ACTIVE = "active"
    WAITING_HUMAN = "waiting_human"
    WAITING_CONSUMER = "waiting_consumer"
    RESOLVED = "resolved"
    RESUMED = "resumed"
    ABANDONED = "abandoned"


class SenderType:
    """Message sender type constants."""
    CONSUMER = "consumer"
    AGENT = "agent"
    HUMAN = "human"


class EscalationReason:
    """Common escalation reason constants."""
    COMPLEX_QUESTION = "complex_question"
    COMPLAINT = "complaint"
    SPECIAL_REQUEST = "special_request"
    PRICING_NEGOTIATION = "pricing_negotiation"
    TECHNICAL_ISSUE = "technical_issue"
    URGENT_MATTER = "urgent_matter"
    UNCLEAR_INTENT = "unclear_intent"
    AGENT_UNCERTAIN = "agent_uncertain"
