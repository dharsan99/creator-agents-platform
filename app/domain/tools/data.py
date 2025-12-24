"""
Data Tools - Query and update system data

These tools allow agents to read and write data during execution.
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import datetime
from sqlmodel import Session, select

from app.domain.tools.base import BaseTool, ToolResult, ToolCategory
from app.domain.tools.registry import get_registry
from app.infra.db.models import ConsumerContext, Consumer
from app.domain.context.service import ConsumerContextService

logger = logging.getLogger(__name__)


class GetConsumerContextTool(BaseTool):
    """
    Fetch consumer context from database

    Returns complete consumer context including:
    - Stage (new, interested, engaged, converted, churned)
    - Metrics (page_views, emails_sent, bookings, etc.)
    - Contact info (name, email, whatsapp)
    - Attributes (custom data)

    Parameters:
    - consumer_id: UUID of the consumer
    - creator_id: UUID of the creator (required for context lookup)
    """

    name = "get_consumer_context"
    description = "Get complete consumer context including stage, metrics, and contact info"
    category = ToolCategory.DATA
    timeout_seconds = 10
    retry_on_timeout = False
    max_retries = 0

    schema = {
        "type": "object",
        "properties": {
            "consumer_id": {
                "type": "string",
                "format": "uuid",
                "description": "Consumer UUID"
            },
            "creator_id": {
                "type": "string",
                "format": "uuid",
                "description": "Creator UUID"
            }
        },
        "required": ["consumer_id", "creator_id"]
    }

    def __init__(self, session: Optional[Session] = None):
        """Initialize with optional database session"""
        self.session = session
        super().__init__()

    def check_availability(self) -> bool:
        """Data tools are always available (database is core dependency)"""
        return True

    def execute(
        self,
        consumer_id: str,
        creator_id: str,
        **kwargs
    ) -> ToolResult:
        """
        Fetch consumer context

        Args:
            consumer_id: Consumer UUID (string)
            creator_id: Creator UUID (string)

        Returns:
            ToolResult with consumer context data
        """
        start_time = datetime.utcnow()

        try:
            # Convert string UUIDs to UUID objects
            consumer_uuid = UUID(consumer_id)
            creator_uuid = UUID(creator_id)

            # Get database session
            if self.session is None:
                from app.infra.db.connection import get_session
                session = next(get_session())
            else:
                session = self.session

            # Get consumer context
            context_service = ConsumerContextService(session)
            context = context_service.get_or_create_context(creator_uuid, consumer_uuid)

            # Also get consumer basic info
            consumer = session.exec(
                select(Consumer).where(Consumer.id == consumer_uuid)
            ).first()

            # Build result data
            result_data = {
                "consumer_id": str(consumer_uuid),
                "creator_id": str(creator_uuid),
                "stage": context.stage,
                "last_seen_at": context.last_seen_at.isoformat() if context.last_seen_at else None,
                "metrics": context.metrics,
                "attributes": context.attributes,
                "consumer_info": {
                    "name": consumer.name if consumer else None,
                    "email": consumer.email if consumer else None,
                    "whatsapp": consumer.whatsapp if consumer else None,
                } if consumer else {}
            }

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.debug(
                f"Retrieved consumer context",
                extra={
                    "consumer_id": consumer_id,
                    "creator_id": creator_id,
                    "stage": context.stage,
                    "execution_time_ms": execution_time
                }
            )

            return ToolResult(
                success=True,
                data=result_data,
                error=None,
                execution_time_ms=execution_time,
                tool_name=self.name,
                timestamp=start_time
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"Failed to get consumer context: {e}", exc_info=True)

            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                execution_time_ms=execution_time,
                tool_name=self.name,
                timestamp=start_time
            )


class UpdateConsumerStageTool(BaseTool):
    """
    Update consumer stage in the database

    Stages: new, interested, engaged, converted, churned

    Parameters:
    - consumer_id: UUID of the consumer
    - creator_id: UUID of the creator
    - stage: New stage value
    """

    name = "update_consumer_stage"
    description = "Update the stage of a consumer (new, interested, engaged, converted, churned)"
    category = ToolCategory.DATA
    timeout_seconds = 10
    retry_on_timeout = False
    max_retries = 0

    schema = {
        "type": "object",
        "properties": {
            "consumer_id": {
                "type": "string",
                "format": "uuid",
                "description": "Consumer UUID"
            },
            "creator_id": {
                "type": "string",
                "format": "uuid",
                "description": "Creator UUID"
            },
            "stage": {
                "type": "string",
                "enum": ["new", "interested", "engaged", "converted", "churned"],
                "description": "New stage for the consumer"
            }
        },
        "required": ["consumer_id", "creator_id", "stage"]
    }

    def __init__(self, session: Optional[Session] = None):
        """Initialize with optional database session"""
        self.session = session
        super().__init__()

    def check_availability(self) -> bool:
        """Data tools are always available"""
        return True

    def execute(
        self,
        consumer_id: str,
        creator_id: str,
        stage: str,
        **kwargs
    ) -> ToolResult:
        """
        Update consumer stage

        Args:
            consumer_id: Consumer UUID (string)
            creator_id: Creator UUID (string)
            stage: New stage value

        Returns:
            ToolResult with updated context
        """
        start_time = datetime.utcnow()

        try:
            # Validate stage
            valid_stages = ["new", "interested", "engaged", "converted", "churned"]
            if stage not in valid_stages:
                raise ValueError(f"Invalid stage '{stage}'. Must be one of: {valid_stages}")

            # Convert string UUIDs
            consumer_uuid = UUID(consumer_id)
            creator_uuid = UUID(creator_id)

            # Get database session
            if self.session is None:
                from app.infra.db.connection import get_session
                session = next(get_session())
            else:
                session = self.session

            # Get or create context
            context_service = ConsumerContextService(session)
            context = context_service.get_or_create_context(creator_uuid, consumer_uuid)

            # Update stage
            old_stage = context.stage
            context.stage = stage
            context.updated_at = datetime.utcnow()

            session.add(context)
            session.commit()
            session.refresh(context)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.info(
                f"Updated consumer stage",
                extra={
                    "consumer_id": consumer_id,
                    "creator_id": creator_id,
                    "old_stage": old_stage,
                    "new_stage": stage,
                    "execution_time_ms": execution_time
                }
            )

            return ToolResult(
                success=True,
                data={
                    "consumer_id": str(consumer_uuid),
                    "creator_id": str(creator_uuid),
                    "old_stage": old_stage,
                    "new_stage": stage,
                    "updated_at": context.updated_at.isoformat()
                },
                error=None,
                execution_time_ms=execution_time,
                tool_name=self.name,
                timestamp=start_time
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"Failed to update consumer stage: {e}", exc_info=True)

            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                execution_time_ms=execution_time,
                tool_name=self.name,
                timestamp=start_time
            )


class SearchFAQTool(BaseTool):
    """
    Search knowledge base / FAQ for answers

    NOTE: This is a STUB implementation for Phase 1.
    In future phases, this will integrate with:
    - Vector database (Pinecone, Weaviate)
    - Creator-specific knowledge bases
    - LLM-powered semantic search

    Parameters:
    - query: Search query
    - creator_id: UUID of the creator (for creator-specific FAQs)
    - limit: Maximum number of results (default: 5)
    """

    name = "search_faq"
    description = "Search FAQ/knowledge base for answers (STUB - to be implemented)"
    category = ToolCategory.KNOWLEDGE
    timeout_seconds = 10
    retry_on_timeout = False
    max_retries = 0

    schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "creator_id": {
                "type": "string",
                "format": "uuid",
                "description": "Creator UUID"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum results to return",
                "default": 5
            }
        },
        "required": ["query", "creator_id"]
    }

    def check_availability(self) -> bool:
        """
        FAQ search is not yet implemented

        Returns False so agents know this tool is unavailable.
        Agents will log missing tool requests when they try to use it.
        """
        return False

    def execute(
        self,
        query: str,
        creator_id: str,
        limit: int = 5,
        **kwargs
    ) -> ToolResult:
        """
        STUB: Search FAQ (not implemented yet)

        Args:
            query: Search query
            creator_id: Creator UUID
            limit: Max results

        Returns:
            ToolResult indicating tool is not available
        """
        start_time = datetime.utcnow()

        # This is a stub - return empty results
        logger.warning(
            f"search_faq called but not implemented",
            extra={"query": query, "creator_id": creator_id}
        )

        return ToolResult(
            success=False,
            data=None,
            error="search_faq tool is not yet implemented. "
                  "This will be available in a future release with vector search integration.",
            execution_time_ms=0,
            tool_name=self.name,
            timestamp=start_time
        )


# Register tools on module import
_registry = get_registry()
_registry.register_tool(GetConsumerContextTool())
_registry.register_tool(UpdateConsumerStageTool())
_registry.register_tool(SearchFAQTool())

logger.info("Data tools registered")
