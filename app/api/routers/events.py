"""Events API router."""
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CreatorIdDep, SessionDep
from app.domain.events.service import EventService
from app.domain.events.handlers import handle_event
from app.domain.schemas import EventCreate, EventResponse
from app.domain.types import EventType

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    creator_id: CreatorIdDep,
    session: SessionDep,
    event_data: EventCreate,
) -> EventResponse:
    """Record a new event.

    This is the main ingestion endpoint. When an event is recorded:
    1. Event is persisted to database
    2. Consumer context is updated
    3. Agent invocations are queued as background jobs
    """
    service = EventService(session)

    # Create event
    event = service.create_event(creator_id, event_data)

    # Trigger event handlers (context update + agent invocations)
    # This happens within the same transaction
    handle_event(session, event)

    return EventResponse.model_validate(event)


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    creator_id: CreatorIdDep,
    session: SessionDep,
    event_id: UUID,
) -> EventResponse:
    """Get a specific event by ID."""
    service = EventService(session)
    event = service.get_event(event_id)

    if not event or event.creator_id != creator_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )

    return EventResponse.model_validate(event)


@router.get("", response_model=list[EventResponse])
def list_events(
    creator_id: CreatorIdDep,
    session: SessionDep,
    consumer_id: Optional[UUID] = Query(None),
    event_type: Optional[EventType] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(100, le=1000),
) -> list[EventResponse]:
    """List events with optional filters."""
    service = EventService(session)

    events = service.list_events(
        creator_id=creator_id,
        consumer_id=consumer_id,
        event_type=event_type,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )

    return [EventResponse.model_validate(event) for event in events]


@router.get("/consumer/{consumer_id}/timeline", response_model=list[EventResponse])
def get_consumer_timeline(
    creator_id: CreatorIdDep,
    session: SessionDep,
    consumer_id: UUID,
    limit: int = Query(100, le=1000),
) -> list[EventResponse]:
    """Get complete event timeline for a consumer."""
    service = EventService(session)

    events = service.get_consumer_timeline(
        creator_id=creator_id,
        consumer_id=consumer_id,
        limit=limit,
    )

    return [EventResponse.model_validate(event) for event in events]
