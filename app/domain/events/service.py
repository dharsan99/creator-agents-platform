"""Event domain service."""
from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select

from app.infra.db.models import Event
from app.domain.schemas import EventCreate, EventResponse
from app.domain.types import EventType


class EventService:
    """Service for managing events."""

    def __init__(self, session: Session):
        self.session = session

    def create_event(self, creator_id: UUID, data: EventCreate) -> Event:
        """Create and persist an event."""
        event = Event(
            creator_id=creator_id,
            consumer_id=data.consumer_id,
            type=data.type.value,
            source=data.source.value,
            timestamp=data.timestamp,
            payload=data.payload,
        )
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        return event

    def get_event(self, event_id: UUID) -> Optional[Event]:
        """Get event by ID."""
        return self.session.get(Event, event_id)

    def list_events(
        self,
        creator_id: UUID,
        consumer_id: Optional[UUID] = None,
        event_type: Optional[EventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[Event]:
        """List events with optional filters."""
        statement = select(Event).where(Event.creator_id == creator_id)

        if consumer_id:
            statement = statement.where(Event.consumer_id == consumer_id)

        if event_type:
            statement = statement.where(Event.type == event_type.value)

        if start_time:
            statement = statement.where(Event.timestamp >= start_time)

        if end_time:
            statement = statement.where(Event.timestamp <= end_time)

        statement = statement.order_by(Event.timestamp.desc()).limit(limit)

        return list(self.session.exec(statement).all())

    def get_consumer_timeline(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        limit: int = 100,
    ) -> list[Event]:
        """Get complete event timeline for a consumer."""
        return self.list_events(
            creator_id=creator_id,
            consumer_id=consumer_id,
            limit=limit,
        )
