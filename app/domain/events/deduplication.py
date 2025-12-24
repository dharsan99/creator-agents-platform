"""Event deduplication logic to prevent duplicate processing."""
import hashlib
import json
import logging
from typing import Optional
from uuid import UUID

from sqlmodel import Session, select

from app.infra.db.models import Event

logger = logging.getLogger(__name__)


class EventDeduplicator:
    """Handles event deduplication using idempotency keys."""

    @staticmethod
    def generate_idempotency_key(
        creator_id: UUID,
        consumer_id: UUID,
        event_type: str,
        payload: dict
    ) -> str:
        """Generate a consistent idempotency key for an event.

        This creates a hash-based key from event attributes to prevent
        duplicate processing of the same logical event.

        Args:
            creator_id: UUID of the creator
            consumer_id: UUID of the consumer
            event_type: Type of event (page_view, booking, etc.)
            payload: Event payload dictionary

        Returns:
            Hexadecimal hash string suitable for use as idempotency key
        """
        # Create a deterministic representation
        data = {
            "creator_id": str(creator_id),
            "consumer_id": str(consumer_id),
            "event_type": event_type,
            "payload": payload,
        }

        # Convert to JSON with sorted keys for consistency
        json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))

        # Create SHA256 hash
        return hashlib.sha256(json_str.encode()).hexdigest()

    @staticmethod
    def is_duplicate(
        session: Session,
        creator_id: UUID,
        consumer_id: UUID,
        event_type: str,
        payload: dict,
        idempotency_key: Optional[str] = None
    ) -> bool:
        """Check if an event is a duplicate based on idempotency key.

        Args:
            session: Database session
            creator_id: UUID of the creator
            consumer_id: UUID of the consumer
            event_type: Type of event
            payload: Event payload dictionary
            idempotency_key: Optional explicit idempotency key

        Returns:
            True if a matching event already exists, False otherwise
        """
        # Generate key if not provided
        if not idempotency_key:
            idempotency_key = EventDeduplicator.generate_idempotency_key(
                creator_id, consumer_id, event_type, payload
            )

        # Query for existing event with same idempotency key
        stmt = select(Event).where(Event.idempotency_key == idempotency_key)
        existing = session.exec(stmt).first()

        if existing:
            logger.info(
                f"Duplicate event detected: {event_type} for consumer {consumer_id} "
                f"(key: {idempotency_key[:16]}...)"
            )
            return True

        return False

    @staticmethod
    def get_existing_event(
        session: Session,
        idempotency_key: str
    ) -> Optional[Event]:
        """Retrieve an existing event by its idempotency key.

        Args:
            session: Database session
            idempotency_key: The idempotency key to look up

        Returns:
            The existing Event if found, None otherwise
        """
        stmt = select(Event).where(Event.idempotency_key == idempotency_key)
        return session.exec(stmt).first()

    @staticmethod
    def mark_event_with_key(
        event: Event,
        creator_id: UUID,
        consumer_id: UUID,
        event_type: str,
        payload: dict,
        idempotency_key: Optional[str] = None
    ) -> str:
        """Mark an event with its idempotency key.

        Args:
            event: The Event instance to mark
            creator_id: UUID of the creator
            consumer_id: UUID of the consumer
            event_type: Type of event
            payload: Event payload dictionary
            idempotency_key: Optional explicit idempotency key

        Returns:
            The idempotency key assigned to the event
        """
        if not idempotency_key:
            idempotency_key = EventDeduplicator.generate_idempotency_key(
                creator_id, consumer_id, event_type, payload
            )

        event.idempotency_key = idempotency_key
        logger.debug(f"Marked event with idempotency key: {idempotency_key[:16]}...")

        return idempotency_key


# Convenience function for external use
def check_event_duplicate(
    session: Session,
    creator_id: UUID,
    consumer_id: UUID,
    event_type: str,
    payload: dict,
    idempotency_key: Optional[str] = None
) -> bool:
    """Convenience function to check if an event is a duplicate.

    Args:
        session: Database session
        creator_id: UUID of the creator
        consumer_id: UUID of the consumer
        event_type: Type of event
        payload: Event payload dictionary
        idempotency_key: Optional explicit idempotency key

    Returns:
        True if duplicate, False otherwise
    """
    return EventDeduplicator.is_duplicate(
        session, creator_id, consumer_id, event_type, payload, idempotency_key
    )


def generate_event_idempotency_key(
    creator_id: UUID,
    consumer_id: UUID,
    event_type: str,
    payload: dict
) -> str:
    """Convenience function to generate an idempotency key.

    Args:
        creator_id: UUID of the creator
        consumer_id: UUID of the consumer
        event_type: Type of event
        payload: Event payload dictionary

    Returns:
        The generated idempotency key
    """
    return EventDeduplicator.generate_idempotency_key(
        creator_id, consumer_id, event_type, payload
    )
