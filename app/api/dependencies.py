"""API dependencies for dependency injection."""
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session

from app.infra.db.connection import get_session
from app.domain.creators.service import CreatorService


def get_creator_id_from_header(
    x_creator_id: Annotated[str, Header()],
) -> UUID:
    """Extract and validate creator ID from header."""
    try:
        return UUID(x_creator_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid creator ID format",
        )


def verify_creator_exists(
    creator_id: Annotated[UUID, Depends(get_creator_id_from_header)],
    session: Annotated[Session, Depends(get_session)],
) -> UUID:
    """Verify that creator exists in database."""
    service = CreatorService(session)
    creator = service.get_creator(creator_id)

    if not creator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Creator not found",
        )

    return creator_id


# Type alias for creator ID dependency
CreatorIdDep = Annotated[UUID, Depends(verify_creator_exists)]
SessionDep = Annotated[Session, Depends(get_session)]
