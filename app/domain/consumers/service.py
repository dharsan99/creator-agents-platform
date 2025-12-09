"""Consumer domain service."""
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select

from app.infra.db.models import Consumer
from app.domain.schemas import ConsumerCreate
from app.domain.types import ConsentType


class ConsumerService:
    """Service for managing consumers (leads)."""

    def __init__(self, session: Session):
        self.session = session

    def create_consumer(self, creator_id: UUID, data: ConsumerCreate) -> Consumer:
        """Create a new consumer."""
        consumer = Consumer(
            creator_id=creator_id,
            email=data.email,
            phone=data.phone,
            whatsapp=data.whatsapp,
            name=data.name,
            timezone=data.timezone,
            preferences=data.preferences,
            consent=data.consent,
        )
        self.session.add(consumer)
        self.session.commit()
        self.session.refresh(consumer)
        return consumer

    def get_consumer(self, consumer_id: UUID) -> Optional[Consumer]:
        """Get consumer by ID."""
        return self.session.get(Consumer, consumer_id)

    def get_consumer_by_email(
        self, creator_id: UUID, email: str
    ) -> Optional[Consumer]:
        """Get consumer by email for a specific creator."""
        statement = (
            select(Consumer)
            .where(Consumer.creator_id == creator_id)
            .where(Consumer.email == email)
        )
        return self.session.exec(statement).first()

    def update_consumer(
        self, consumer_id: UUID, **kwargs
    ) -> Consumer:
        """Update consumer attributes."""
        consumer = self.get_consumer(consumer_id)
        if not consumer:
            raise ValueError(f"Consumer {consumer_id} not found")

        for key, value in kwargs.items():
            if hasattr(consumer, key) and value is not None:
                setattr(consumer, key, value)

        self.session.add(consumer)
        self.session.commit()
        self.session.refresh(consumer)
        return consumer

    def has_consent(self, consumer_id: UUID, consent_type: ConsentType) -> bool:
        """Check if consumer has given consent for a channel."""
        consumer = self.get_consumer(consumer_id)
        if not consumer:
            return False

        return consumer.consent.get(consent_type.value, False)

    def grant_consent(self, consumer_id: UUID, consent_type: ConsentType) -> Consumer:
        """Grant consent for a channel."""
        consumer = self.get_consumer(consumer_id)
        if not consumer:
            raise ValueError(f"Consumer {consumer_id} not found")

        consumer.consent[consent_type.value] = True
        self.session.add(consumer)
        self.session.commit()
        self.session.refresh(consumer)
        return consumer

    def revoke_consent(self, consumer_id: UUID, consent_type: ConsentType) -> Consumer:
        """Revoke consent for a channel."""
        consumer = self.get_consumer(consumer_id)
        if not consumer:
            raise ValueError(f"Consumer {consumer_id} not found")

        consumer.consent[consent_type.value] = False
        self.session.add(consumer)
        self.session.commit()
        self.session.refresh(consumer)
        return consumer

    def update_preferences(self, consumer_id: UUID, preferences: dict) -> Consumer:
        """Update consumer preferences."""
        consumer = self.get_consumer(consumer_id)
        if not consumer:
            raise ValueError(f"Consumer {consumer_id} not found")

        consumer.preferences = {**consumer.preferences, **preferences}
        self.session.add(consumer)
        self.session.commit()
        self.session.refresh(consumer)
        return consumer

    def get_timezone(self, consumer_id: UUID) -> Optional[str]:
        """Get consumer timezone."""
        consumer = self.get_consumer(consumer_id)
        return consumer.timezone if consumer else None
