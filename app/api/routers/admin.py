"""Admin API endpoints for dashboard."""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Query
from sqlmodel import select, func

from app.api.dependencies import SessionDep
from app.infra.db.models import Creator, Agent, Consumer, Event
from app.domain.schemas import EventResponse

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def get_dashboard_stats(session: SessionDep) -> dict:
    """Get dashboard statistics (unauthenticated for development)."""
    total_creators = session.exec(select(func.count(Creator.id))).one()
    total_agents = session.exec(select(func.count(Agent.id))).one()
    total_consumers = session.exec(select(func.count(Consumer.id))).one()
    total_events = session.exec(select(func.count(Event.id))).one()

    return {
        "creators": total_creators,
        "agents": total_agents,
        "consumers": total_consumers,
        "events": total_events,
    }


@router.get("/events")
def list_all_events(
    session: SessionDep,
    creator_id: Optional[UUID] = Query(None),
    limit: int = Query(20, le=1000),
    skip: int = Query(0),
) -> dict:
    """List all events across all creators (admin endpoint for dashboard)."""
    statement = select(Event).order_by(Event.timestamp.desc())

    if creator_id:
        statement = statement.where(Event.creator_id == creator_id)

    # Get total count
    total_statement = select(func.count(Event.id))
    if creator_id:
        total_statement = total_statement.where(Event.creator_id == creator_id)
    total = session.exec(total_statement).one()

    # Get paginated events
    statement = statement.offset(skip).limit(limit)
    events = session.exec(statement).all()

    return {
        "items": [EventResponse.model_validate(event) for event in events],
        "total": total,
        "limit": limit,
        "skip": skip,
    }
