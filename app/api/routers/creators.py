"""Creators API router."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import CreatorIdDep, SessionDep
from app.domain.creators.service import CreatorService
from app.domain.schemas import CreatorCreate, CreatorResponse

router = APIRouter(prefix="/creators", tags=["creators"])


@router.post("", response_model=CreatorResponse, status_code=status.HTTP_201_CREATED)
def create_creator(
    session: SessionDep,
    creator_data: CreatorCreate,
) -> CreatorResponse:
    """Create a new creator account."""
    service = CreatorService(session)

    # Check if email already exists
    existing = service.get_creator_by_email(creator_data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Creator with this email already exists",
        )

    creator = service.create_creator(creator_data)
    return CreatorResponse.model_validate(creator)


@router.get("", response_model=list[CreatorResponse])
def list_creators(
    session: SessionDep,
) -> list[CreatorResponse]:
    """List all creators (admin endpoint for dashboard)."""
    service = CreatorService(session)
    creators = service.list_creators()
    return [CreatorResponse.model_validate(creator) for creator in creators]


@router.get("/me", response_model=CreatorResponse)
def get_current_creator(
    creator_id: CreatorIdDep,
    session: SessionDep,
) -> CreatorResponse:
    """Get current creator details."""
    service = CreatorService(session)
    creator = service.get_creator(creator_id)

    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator not found",
        )

    return CreatorResponse.model_validate(creator)


@router.patch("/me/settings", response_model=CreatorResponse)
def update_creator_settings(
    creator_id: CreatorIdDep,
    session: SessionDep,
    settings: dict,
) -> CreatorResponse:
    """Update creator settings."""
    service = CreatorService(session)
    creator = service.update_settings(creator_id, settings)
    return CreatorResponse.model_validate(creator)
