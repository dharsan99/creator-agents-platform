"""
Missing Tool Logger - Tracks requests for tools that don't exist yet

When agents need tools that aren't implemented, we log the request
so we can prioritize implementation based on actual usage patterns.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Session, select
from enum import Enum


class ToolPriority(str, Enum):
    """Priority levels for missing tool requests"""
    CRITICAL = "critical"  # Blocks critical workflows
    HIGH = "high"  # Requested frequently
    MEDIUM = "medium"  # Nice to have
    LOW = "low"  # Rare use case


class MissingToolRequest(SQLModel, table=True):
    """
    Database model for tracking missing tool requests

    This helps us understand what tools agents need most.
    """
    __tablename__ = "missing_tool_requests"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tool_name: str = Field(index=True)  # e.g., "generate_video", "send_telegram"
    category: Optional[str] = None  # e.g., "content", "communication"
    use_case: str  # Why the agent needed this tool
    agent_id: Optional[UUID] = Field(default=None, index=True)
    creator_id: Optional[UUID] = Field(default=None, index=True)
    workflow_id: Optional[UUID] = Field(default=None, index=True)
    priority: ToolPriority = Field(default=ToolPriority.MEDIUM)
    request_count: int = Field(default=1)  # How many times requested
    first_requested_at: datetime = Field(default_factory=datetime.utcnow)
    last_requested_at: datetime = Field(default_factory=datetime.utcnow)
    implemented: bool = Field(default=False)  # Has tool been implemented?
    implemented_at: Optional[datetime] = None
    notes: Optional[str] = None  # Additional context


class MissingToolLogger:
    """
    Service for logging and querying missing tool requests

    Usage:
        logger = MissingToolLogger(session)
        logger.log_missing_tool(
            tool_name="send_telegram",
            use_case="Need to send Telegram message for creator campaign",
            agent_id=agent.id,
            priority=ToolPriority.HIGH
        )
    """

    def __init__(self, session: Session):
        self.session = session

    def log_missing_tool(
        self,
        tool_name: str,
        use_case: str,
        agent_id: Optional[UUID] = None,
        creator_id: Optional[UUID] = None,
        workflow_id: Optional[UUID] = None,
        priority: ToolPriority = ToolPriority.MEDIUM,
        category: Optional[str] = None,
        notes: Optional[str] = None
    ) -> MissingToolRequest:
        """
        Log a request for a tool that doesn't exist

        Args:
            tool_name: Name of the requested tool
            use_case: Description of why the tool is needed
            agent_id: Which agent requested it
            creator_id: Which creator's workflow needed it
            workflow_id: Which workflow execution needed it
            priority: Urgency level
            category: Tool category (communication, data, etc.)
            notes: Additional context

        Returns:
            MissingToolRequest: Created or updated request
        """
        # Check if we already have a request for this tool
        existing = self.session.exec(
            select(MissingToolRequest)
            .where(MissingToolRequest.tool_name == tool_name)
            .where(MissingToolRequest.implemented == False)
        ).first()

        if existing:
            # Update existing request
            existing.request_count += 1
            existing.last_requested_at = datetime.utcnow()

            # Upgrade priority if needed
            priority_order = {
                ToolPriority.LOW: 0,
                ToolPriority.MEDIUM: 1,
                ToolPriority.HIGH: 2,
                ToolPriority.CRITICAL: 3
            }
            if priority_order[priority] > priority_order[existing.priority]:
                existing.priority = priority

            # Append to notes if provided
            if notes:
                existing.notes = f"{existing.notes}\n---\n{notes}" if existing.notes else notes

            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing

        # Create new request
        request = MissingToolRequest(
            tool_name=tool_name,
            category=category,
            use_case=use_case,
            agent_id=agent_id,
            creator_id=creator_id,
            workflow_id=workflow_id,
            priority=priority,
            notes=notes
        )

        self.session.add(request)
        self.session.commit()
        self.session.refresh(request)
        return request

    def get_top_requested_tools(self, limit: int = 10) -> list[MissingToolRequest]:
        """
        Get most frequently requested missing tools

        Args:
            limit: Number of tools to return

        Returns:
            List of MissingToolRequest ordered by request_count
        """
        return list(self.session.exec(
            select(MissingToolRequest)
            .where(MissingToolRequest.implemented == False)
            .order_by(MissingToolRequest.request_count.desc())  # type: ignore
            .limit(limit)
        ))

    def get_high_priority_tools(self) -> list[MissingToolRequest]:
        """Get all high-priority and critical missing tools"""
        return list(self.session.exec(
            select(MissingToolRequest)
            .where(MissingToolRequest.implemented == False)
            .where(
                (MissingToolRequest.priority == ToolPriority.HIGH) |
                (MissingToolRequest.priority == ToolPriority.CRITICAL)
            )
            .order_by(MissingToolRequest.priority.desc())  # type: ignore
        ))

    def mark_tool_implemented(self, tool_name: str) -> None:
        """
        Mark a tool as implemented

        Args:
            tool_name: Name of the tool that was implemented
        """
        requests = self.session.exec(
            select(MissingToolRequest)
            .where(MissingToolRequest.tool_name == tool_name)
            .where(MissingToolRequest.implemented == False)
        ).all()

        for request in requests:
            request.implemented = True
            request.implemented_at = datetime.utcnow()
            self.session.add(request)

        self.session.commit()

    def get_summary_by_category(self) -> dict[str, int]:
        """
        Get count of missing tools by category

        Returns:
            Dict mapping category → count
        """
        requests = self.session.exec(
            select(MissingToolRequest)
            .where(MissingToolRequest.implemented == False)
        ).all()

        summary: dict[str, int] = {}
        for request in requests:
            category = request.category or "uncategorized"
            summary[category] = summary.get(category, 0) + request.request_count

        return summary
