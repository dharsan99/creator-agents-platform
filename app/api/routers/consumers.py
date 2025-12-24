"""Consumers API router."""
from uuid import UUID
from typing import List, Optional
from sqlmodel import select, func
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel

from app.api.dependencies import CreatorIdDep, SessionDep
from app.domain.consumers.service import ConsumerService
from app.domain.context.service import ConsumerContextService
from app.domain.schemas import ConsumerCreate, ConsumerResponse, ConsumerContextResponse
from app.infra.db.models import Consumer, ConsumerContext, Event

router = APIRouter(prefix="/consumers", tags=["consumers"])


class ConsumerMetrics(BaseModel):
    """Consumer with engagement metrics"""
    id: UUID
    name: Optional[str]
    email: Optional[str]
    stage: str
    emails_delivered: int
    emails_opened: int
    emails_clicked: int
    bookings: int
    last_activity: Optional[datetime]
    created_at: datetime


class ConsumerMetricsResponse(BaseModel):
    """Response with consumer metrics"""
    consumers: List[ConsumerMetrics]
    total: int
    page: int
    page_size: int


@router.get("", response_model=ConsumerMetricsResponse)
def list_consumers_with_metrics(
    creator_id: CreatorIdDep,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> ConsumerMetricsResponse:
    """List all consumers for a creator with their engagement metrics"""
    from sqlalchemy import text

    # Calculate offset
    offset = (page - 1) * page_size

    # Raw SQL query for better performance with aggregations
    query = text("""
        SELECT
            c.id,
            c.name,
            c.email,
            c.created_at,
            COALESCE(cc.stage, 'new') as stage,
            COUNT(DISTINCT e.id) FILTER (WHERE e.type = 'email_delivered') as emails_delivered,
            COUNT(DISTINCT e.id) FILTER (WHERE e.type = 'email_opened') as emails_opened,
            COUNT(DISTINCT e.id) FILTER (WHERE e.type = 'email_clicked') as emails_clicked,
            COUNT(DISTINCT e.id) FILTER (WHERE e.type = 'booking_created') as bookings,
            MAX(e.timestamp) as last_activity
        FROM consumers c
        LEFT JOIN consumer_contexts cc ON c.id = cc.consumer_id
        LEFT JOIN events e ON c.id = e.consumer_id
        WHERE c.creator_id = :creator_id
        GROUP BY c.id, c.name, c.email, c.created_at, cc.stage
        ORDER BY last_activity DESC NULLS LAST, c.created_at DESC
        LIMIT :limit OFFSET :offset
    """)

    count_query = text("""
        SELECT COUNT(*) FROM consumers WHERE creator_id = :creator_id
    """)

    # Execute queries
    result = session.execute(query, {"creator_id": str(creator_id), "limit": page_size, "offset": offset})
    rows = result.fetchall()

    total_result = session.execute(count_query, {"creator_id": str(creator_id)})
    total = total_result.scalar()

    # Convert to ConsumerMetrics objects
    consumers = []
    for row in rows:
        consumers.append(ConsumerMetrics(
            id=row.id,
            name=row.name,
            email=row.email,
            stage=row.stage,
            emails_delivered=row.emails_delivered or 0,
            emails_opened=row.emails_opened or 0,
            emails_clicked=row.emails_clicked or 0,
            bookings=row.bookings or 0,
            last_activity=row.last_activity,
            created_at=row.created_at
        ))

    return ConsumerMetricsResponse(
        consumers=consumers,
        total=total or 0,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=ConsumerResponse, status_code=status.HTTP_201_CREATED)
def create_consumer(
    creator_id: CreatorIdDep,
    session: SessionDep,
    consumer_data: ConsumerCreate,
) -> ConsumerResponse:
    """Create a new consumer (lead)."""
    service = ConsumerService(session)

    # Check if consumer with email already exists
    if consumer_data.email:
        existing = service.get_consumer_by_email(creator_id, consumer_data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Consumer with this email already exists",
            )

    consumer = service.create_consumer(creator_id, consumer_data)
    return ConsumerResponse.model_validate(consumer)


@router.get("/{consumer_id}", response_model=ConsumerResponse)
def get_consumer(
    creator_id: CreatorIdDep,
    session: SessionDep,
    consumer_id: UUID,
) -> ConsumerResponse:
    """Get a specific consumer."""
    service = ConsumerService(session)
    consumer = service.get_consumer(consumer_id)

    if not consumer or consumer.creator_id != creator_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consumer not found",
        )

    return ConsumerResponse.model_validate(consumer)


@router.get("/{consumer_id}/context", response_model=ConsumerContextResponse)
def get_consumer_context(
    creator_id: CreatorIdDep,
    session: SessionDep,
    consumer_id: UUID,
) -> ConsumerContextResponse:
    """Get consumer context (materialized state)."""
    # Verify consumer belongs to creator
    consumer_service = ConsumerService(session)
    consumer = consumer_service.get_consumer(consumer_id)

    if not consumer or consumer.creator_id != creator_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consumer not found",
        )

    # Get context
    context_service = ConsumerContextService(session)
    context = context_service.get_or_create_context(creator_id, consumer_id)

    return ConsumerContextResponse.model_validate(context)


@router.patch("/{consumer_id}", response_model=ConsumerResponse)
def update_consumer(
    creator_id: CreatorIdDep,
    session: SessionDep,
    consumer_id: UUID,
    updates: dict,
) -> ConsumerResponse:
    """Update consumer attributes."""
    service = ConsumerService(session)
    consumer = service.get_consumer(consumer_id)

    if not consumer or consumer.creator_id != creator_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consumer not found",
        )

    consumer = service.update_consumer(consumer_id, **updates)
    return ConsumerResponse.model_validate(consumer)
