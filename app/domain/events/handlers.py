"""Event handlers for triggering side effects."""
from uuid import UUID
from sqlmodel import Session

from app.infra.db.models import Event
from app.domain.context.service import ConsumerContextService
from app.domain.types import EventType


class EventHandler:
    """Handles event side effects like context updates and agent triggers."""

    def __init__(self, session: Session):
        self.session = session
        self.context_service = ConsumerContextService(session)

    def handle_event(self, event: Event) -> None:
        """Process event and trigger appropriate handlers."""
        # Always update consumer context
        self.context_service.update_context_from_event(event)

        # Trigger agent invocations (will be queued to background workers)
        self._trigger_agents(event)

    def _trigger_agents(self, event: Event) -> None:
        """Queue agent invocations for this event.

        In v1, this enqueues background jobs via RQ.
        In future versions, this could publish to a message bus.
        """
        from app.infra.queues.tasks import enqueue_agent_invocations

        enqueue_agent_invocations(
            creator_id=str(event.creator_id),
            consumer_id=str(event.consumer_id),
            event_id=str(event.id),
            event_type=event.type,
        )


# Event subscribers registry
# In v1, we call handlers synchronously within the transaction
# In future versions, this could be replaced with pub/sub
EVENT_HANDLERS: dict[str, list[callable]] = {}


def register_handler(event_type: EventType, handler: callable) -> None:
    """Register a handler for an event type."""
    if event_type.value not in EVENT_HANDLERS:
        EVENT_HANDLERS[event_type.value] = []
    EVENT_HANDLERS[event_type.value].append(handler)


def handle_event(session: Session, event: Event) -> None:
    """Execute all registered handlers for an event."""
    handler = EventHandler(session)
    handler.handle_event(event)

    # Execute custom handlers if any
    for custom_handler in EVENT_HANDLERS.get(event.type, []):
        custom_handler(session, event)
