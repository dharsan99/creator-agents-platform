"""Domain types and enums for type safety."""
from enum import Enum


class EventType(str, Enum):
    """Types of events in the system."""
    PAGE_VIEW = "page_view"
    SERVICE_CLICK = "service_click"
    BOOKING_CREATED = "booking_created"
    BOOKING_CANCELLED = "booking_cancelled"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    EMAIL_SENT = "email_sent"
    EMAIL_OPENED = "email_opened"
    EMAIL_CLICKED = "email_clicked"
    EMAIL_REPLIED = "email_replied"
    WHATSAPP_MESSAGE_SENT = "whatsapp_message_sent"
    WHATSAPP_MESSAGE_RECEIVED = "whatsapp_message_received"
    CALL_SCHEDULED = "call_scheduled"
    CALL_COMPLETED = "call_completed"
    AGENT_ACTION = "agent_action"


class EventSource(str, Enum):
    """Source of the event."""
    SYSTEM = "system"
    WEBHOOK = "webhook"
    API = "api"
    AGENT = "agent"


class ProductType(str, Enum):
    """Types of products creators can offer."""
    COHORT = "cohort"
    ONE_ON_ONE = "one_on_one"
    SUBSCRIPTION = "subscription"


class ConsumerStage(str, Enum):
    """Funnel stages for consumers."""
    NEW = "new"
    INTERESTED = "interested"
    ENGAGED = "engaged"
    CONVERTED = "converted"
    CHURNED = "churned"


class Channel(str, Enum):
    """Communication channels."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    CALL = "call"
    PAYMENT = "payment"


class ActionType(str, Enum):
    """Types of actions agents can take."""
    SEND_EMAIL = "send_email"
    SEND_WHATSAPP = "send_whatsapp"
    SCHEDULE_CALL = "schedule_call"
    SEND_PAYMENT_LINK = "send_payment_link"


class ActionStatus(str, Enum):
    """Status of an action."""
    PLANNED = "planned"
    APPROVED = "approved"
    DENIED = "denied"
    EXECUTING = "executing"
    EXECUTED = "executed"
    FAILED = "failed"


class AgentImplementation(str, Enum):
    """Agent implementation types."""
    SIMPLE = "simple"
    LANGGRAPH = "langgraph"
    EXTERNAL_HTTP = "external_http"


class InvocationStatus(str, Enum):
    """Agent invocation status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ConsentType(str, Enum):
    """Types of consent."""
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    CALL = "call"


class PolicyKey(str, Enum):
    """Policy rule keys."""
    RATE_LIMIT_EMAIL_WEEKLY = "rate_limit_email_weekly"
    RATE_LIMIT_EMAIL_DAILY = "rate_limit_email_daily"
    RATE_LIMIT_WHATSAPP_DAILY = "rate_limit_whatsapp_daily"
    RATE_LIMIT_WHATSAPP_WEEKLY = "rate_limit_whatsapp_weekly"
    RATE_LIMIT_CALL_WEEKLY = "rate_limit_call_weekly"
    QUIET_HOURS_START = "quiet_hours_start"
    QUIET_HOURS_END = "quiet_hours_end"
    REQUIRE_CONSENT = "require_consent"
