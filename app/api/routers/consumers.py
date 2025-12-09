"""Consumers API router."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CreatorIdDep, SessionDep
from app.domain.consumers.service import ConsumerService
from app.domain.context.service import ConsumerContextService
from app.domain.schemas import ConsumerCreate, ConsumerResponse, ConsumerContextResponse

router = APIRouter(prefix="/consumers", tags=["consumers"])


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
