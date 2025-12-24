"""Creator domain service."""
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select

from app.infra.db.models import Creator
from app.domain.schemas import CreatorCreate, CreatorResponse


class CreatorService:
    """Service for managing creator accounts."""

    def __init__(self, session: Session):
        self.session = session

    def create_creator(self, data: CreatorCreate) -> Creator:
        """Create a new creator account."""
        creator = Creator(
            name=data.name,
            email=data.email,
            settings=data.settings,
        )
        self.session.add(creator)
        self.session.commit()
        self.session.refresh(creator)
        return creator

    def get_creator(self, creator_id: UUID) -> Optional[Creator]:
        """Get creator by ID."""
        return self.session.get(Creator, creator_id)

    def get_creator_by_email(self, email: str) -> Optional[Creator]:
        """Get creator by email."""
        statement = select(Creator).where(Creator.email == email)
        return self.session.exec(statement).first()

    def list_creators(self) -> list[Creator]:
        """List all creators."""
        statement = select(Creator).order_by(Creator.created_at.desc())
        return list(self.session.exec(statement).all())

    def update_settings(self, creator_id: UUID, settings: dict) -> Creator:
        """Update creator settings."""
        creator = self.get_creator(creator_id)
        if not creator:
            raise ValueError(f"Creator {creator_id} not found")

        creator.settings = {**creator.settings, **settings}
        self.session.add(creator)
        self.session.commit()
        self.session.refresh(creator)
        return creator

    def get_setting(self, creator_id: UUID, key: str, default=None):
        """Get a specific setting value."""
        creator = self.get_creator(creator_id)
        if not creator:
            return default
        return creator.settings.get(key, default)

    def has_channel_configured(self, creator_id: UUID, channel: str) -> bool:
        """Check if creator has a channel configured."""
        creator = self.get_creator(creator_id)
        if not creator:
            return False

        channel_config = creator.settings.get("channels", {}).get(channel, {})
        return channel_config.get("enabled", False)
