"""Simple base interface for creating custom agents.

To create a new agent, simply inherit from BaseAgent and implement:
1. should_act() - Decide if the agent should take action
2. plan_actions() - Generate the list of actions to take

That's it! The framework handles everything else.
"""
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime

from app.domain.schemas import PlannedAction
from app.infra.db.models import Event, ConsumerContext


class BaseAgent(ABC):
    """Simple base class for creating custom agents.

    Example:
        class MyAgent(BaseAgent):
            def should_act(self, context, event):
                # Only act on new leads who viewed the pricing page
                return (
                    context.stage == "new" and
                    event.type == "page_view" and
                    "pricing" in event.payload.get("page_url", "")
                )

            def plan_actions(self, context, event):
                return [
                    self.send_email(
                        to=event.payload.get("email"),
                        subject="Questions about pricing?",
                        body="<html>...</html>",
                    )
                ]
    """

    def __init__(self, agent_config: dict):
        """Initialize agent with configuration.

        Args:
            agent_config: Configuration dict from agent.config field
        """
        self.config = agent_config
        self.name = agent_config.get("name", self.__class__.__name__)

    @abstractmethod
    def should_act(self, context: ConsumerContext, event: Event) -> bool:
        """Decide if this agent should take action.

        This is your filtering logic. Return True if the agent should
        generate actions for this event and consumer context.

        Args:
            context: Consumer's current state (stage, metrics, etc.)
            event: The event that triggered this agent

        Returns:
            True if agent should act, False otherwise

        Example:
            def should_act(self, context, event):
                # Only act on page views for new leads
                return (
                    event.type == "page_view" and
                    context.stage == "new" and
                    context.metrics.get("page_views", 0) == 1
                )
        """
        pass

    @abstractmethod
    def plan_actions(
        self,
        context: ConsumerContext,
        event: Event
    ) -> list[PlannedAction]:
        """Generate actions to take.

        Return a list of actions you want to execute. Use the helper
        methods below to create common actions easily.

        Args:
            context: Consumer's current state
            event: The triggering event

        Returns:
            List of PlannedAction objects

        Example:
            def plan_actions(self, context, event):
                return [
                    self.send_whatsapp(
                        to="+1234567890",
                        message="Hey! Saw you checked out our program..."
                    ),
                    self.send_email(
                        to="user@example.com",
                        subject="Welcome!",
                        body="<html>...</html>"
                    )
                ]
        """
        pass

    def analyze(self, context: ConsumerContext, event: Event) -> dict:
        """Optional: Perform custom analysis.

        Override this if you need to do complex analysis before
        deciding on actions. The result is stored in action metadata.

        Args:
            context: Consumer's current state
            event: The triggering event

        Returns:
            Dictionary with your analysis results
        """
        return {}

    # ==================== Tool Calling ====================
    # NEW: Call tools during agent execution (not just plan actions)

    def call_tool(
        self,
        tool_name: str,
        creator_id: Optional["UUID"] = None,
        consumer_id: Optional["UUID"] = None,
        **kwargs
    ):
        """
        Call a tool during agent execution (Phase 1: Dynamic Tool Calling)

        This is NEW functionality that allows agents to execute tools
        during reasoning, not just plan actions for later.

        Args:
            tool_name: Name of the tool (e.g., "send_email", "get_consumer_context")
            creator_id: Optional creator context for policy validation
            consumer_id: Optional consumer context for policy validation
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with success status, data, error, and metadata

        Example:
            # Get consumer context during execution
            result = self.call_tool(
                "get_consumer_context",
                consumer_id=consumer.id,
                creator_id=creator.id
            )
            if result.success:
                stage = result.data["stage"]
                metrics = result.data["metrics"]

            # Send email immediately
            result = self.call_tool(
                "send_email",
                creator_id=creator.id,
                consumer_id=consumer.id,
                to="user@example.com",
                subject="Hello",
                body="Welcome to our platform!"
            )

        Note:
            - Tools execute with 30-second timeout by default
            - Policy validation applied (rate limits, consent)
            - Tool usage logged for analytics
            - If tool unavailable, MissingToolLogger tracks the need
        """
        from app.domain.tools.executor import ToolExecutor
        from app.domain.tools.missing_tools import MissingToolLogger
        from app.domain.tools.registry import get_registry
        from app.infra.db.connection import get_session
        from uuid import UUID as UUIDType
        import logging

        logger = logging.getLogger(__name__)

        # Get database session
        try:
            session = next(get_session())
        except:
            logger.error("Failed to get database session for tool call")
            from app.domain.tools.base import ToolResult
            from datetime import datetime
            return ToolResult(
                success=False,
                data=None,
                error="Database session unavailable",
                execution_time_ms=0,
                tool_name=tool_name,
                timestamp=datetime.utcnow()
            )

        # Check if tool exists
        registry = get_registry()
        tool = registry.get_tool(tool_name)

        if tool is None:
            # Tool doesn't exist - log for future implementation
            logger.warning(f"Agent requested non-existent tool: {tool_name}")

            missing_logger = MissingToolLogger(session)
            missing_logger.log_missing_tool(
                tool_name=tool_name,
                use_case=f"Called by {self.name} agent",
                agent_id=self.config.get("agent_id"),
                creator_id=creator_id,
                priority="medium",
                category=kwargs.get("category", "unknown")
            )

            from app.domain.tools.base import ToolResult
            from datetime import datetime
            return ToolResult(
                success=False,
                data=None,
                error=f"Tool '{tool_name}' not found. Request logged for future implementation.",
                execution_time_ms=0,
                tool_name=tool_name,
                timestamp=datetime.utcnow()
            )

        if not tool.is_available:
            # Tool exists but unavailable - log it
            logger.warning(f"Agent requested unavailable tool: {tool_name}")

            missing_logger = MissingToolLogger(session)
            missing_logger.log_missing_tool(
                tool_name=tool_name,
                use_case=f"Tool exists but unavailable for {self.name} agent",
                agent_id=self.config.get("agent_id"),
                creator_id=creator_id,
                priority="high",  # Higher priority since it's registered but broken
                category=tool.category,
                notes="Tool is registered but check_availability() returned False"
            )

        # Execute tool via ToolExecutor
        try:
            from app.domain.policy.service import PolicyService

            policy_service = PolicyService(session) if creator_id and consumer_id else None

            executor = ToolExecutor(
                session=session,
                policy_service=policy_service,
                registry=registry
            )

            result = executor.execute(
                tool_name=tool_name,
                creator_id=creator_id,
                consumer_id=consumer_id,
                agent_id=self.config.get("agent_id"),
                **kwargs
            )

            return result

        except Exception as e:
            logger.error(f"Tool execution error: {e}", exc_info=True)

            from app.domain.tools.base import ToolResult
            from datetime import datetime
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                execution_time_ms=0,
                tool_name=tool_name,
                timestamp=datetime.utcnow()
            )

    # ==================== Helper Methods ====================
    # Use these to easily create actions in plan_actions()

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        delay_minutes: int = 0,
        priority: float = 1.0,
    ) -> PlannedAction:
        """Create an email action.

        Args:
            to: Recipient email address
            subject: Email subject line
            body: HTML email body
            from_email: Optional sender email (uses default if not provided)
            delay_minutes: Delay before sending (default: immediate)
            priority: Action priority (higher = more important)

        Returns:
            PlannedAction for sending an email
        """
        from datetime import timedelta
        from app.domain.types import ActionType, Channel

        send_at = datetime.utcnow() + timedelta(minutes=delay_minutes)

        payload = {
            "to_email": to,
            "subject": subject,
            "body": body,
        }
        if from_email:
            payload["from_email"] = from_email

        return PlannedAction(
            action_type=ActionType.SEND_EMAIL,
            channel=Channel.EMAIL,
            payload=payload,
            send_at=send_at,
            priority=priority,
        )

    def send_whatsapp(
        self,
        to: str,
        message: str,
        template: Optional[str] = None,
        delay_minutes: int = 0,
        priority: float = 1.0,
    ) -> PlannedAction:
        """Create a WhatsApp message action.

        Args:
            to: WhatsApp number (format: +1234567890 or whatsapp:+1234567890)
            message: Message content
            template: Optional WhatsApp Business template name
            delay_minutes: Delay before sending
            priority: Action priority

        Returns:
            PlannedAction for sending a WhatsApp message
        """
        from datetime import timedelta
        from app.domain.types import ActionType, Channel

        send_at = datetime.utcnow() + timedelta(minutes=delay_minutes)

        payload = {
            "to_number": to if to.startswith("whatsapp:") else f"whatsapp:{to}",
            "message": message,
        }
        if template:
            payload["template"] = template

        return PlannedAction(
            action_type=ActionType.SEND_WHATSAPP,
            channel=Channel.WHATSAPP,
            payload=payload,
            send_at=send_at,
            priority=priority,
        )

    def schedule_call(
        self,
        phone: str,
        scheduled_time: datetime,
        call_type: str = "scheduled",
        priority: float = 1.0,
    ) -> PlannedAction:
        """Create a call scheduling action.

        Args:
            phone: Phone number to call
            scheduled_time: When to schedule the call
            call_type: "scheduled" or "immediate"
            priority: Action priority

        Returns:
            PlannedAction for scheduling a call
        """
        from app.domain.types import ActionType, Channel

        return PlannedAction(
            action_type=ActionType.SCHEDULE_CALL,
            channel=Channel.CALL,
            payload={
                "phone_number": phone,
                "scheduled_time": scheduled_time.isoformat(),
                "type": call_type,
            },
            send_at=scheduled_time,
            priority=priority,
        )

    def send_payment_link(
        self,
        product_id: str,
        custom_amount_cents: Optional[int] = None,
        message: Optional[str] = None,
        delay_minutes: int = 0,
        priority: float = 1.0,
    ) -> PlannedAction:
        """Create a payment link action.

        Args:
            product_id: UUID of the product
            custom_amount_cents: Optional custom amount (overrides product price)
            message: Optional message to include with payment link
            delay_minutes: Delay before sending
            priority: Action priority

        Returns:
            PlannedAction for sending a payment link
        """
        from datetime import timedelta
        from app.domain.types import ActionType, Channel

        send_at = datetime.utcnow() + timedelta(minutes=delay_minutes)

        payload = {"product_id": product_id}
        if custom_amount_cents:
            payload["amount_cents"] = custom_amount_cents
        if message:
            payload["message"] = message

        return PlannedAction(
            action_type=ActionType.SEND_PAYMENT_LINK,
            channel=Channel.PAYMENT,
            payload=payload,
            send_at=send_at,
            priority=priority,
        )

    # ==================== Context Helper Methods ====================

    def get_stage(self, context: ConsumerContext) -> str:
        """Get consumer's current stage."""
        return context.stage

    def get_metric(self, context: ConsumerContext, metric_name: str, default=0):
        """Get a specific metric value."""
        return context.metrics.get(metric_name, default)

    def is_new_lead(self, context: ConsumerContext) -> bool:
        """Check if consumer is a new lead."""
        from app.domain.types import ConsumerStage
        return context.stage == ConsumerStage.NEW.value

    def is_engaged(self, context: ConsumerContext) -> bool:
        """Check if consumer is engaged."""
        from app.domain.types import ConsumerStage
        return context.stage == ConsumerStage.ENGAGED.value

    def is_converted(self, context: ConsumerContext) -> bool:
        """Check if consumer has converted."""
        from app.domain.types import ConsumerStage
        return context.stage == ConsumerStage.CONVERTED.value

    def get_total_revenue(self, context: ConsumerContext) -> int:
        """Get total revenue from this consumer in cents."""
        return self.get_metric(context, "revenue_cents", 0)

    def get_page_views(self, context: ConsumerContext) -> int:
        """Get number of page views."""
        return self.get_metric(context, "page_views", 0)

    def get_emails_sent(self, context: ConsumerContext) -> int:
        """Get number of emails sent to consumer."""
        return self.get_metric(context, "emails_sent", 0)

    def get_emails_opened(self, context: ConsumerContext) -> int:
        """Get number of emails opened by consumer."""
        return self.get_metric(context, "emails_opened", 0)

    # ==================== Event Helper Methods ====================

    def is_event_type(self, event: Event, event_type: str) -> bool:
        """Check if event is of a specific type."""
        return event.type == event_type

    def get_event_payload(self, event: Event, key: str, default=None):
        """Get a value from event payload."""
        return event.payload.get(key, default)
