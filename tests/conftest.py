"""Test configuration and fixtures."""
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.infra.db.models import *  # Import all models


@pytest.fixture(name="session")
def session_fixture():
    """Create test database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture(name="creator")
def creator_fixture(session: Session):
    """Create a test creator."""
    from app.domain.creators.service import CreatorService
    from app.domain.schemas import CreatorCreate

    service = CreatorService(session)
    creator = service.create_creator(
        CreatorCreate(
            name="Test Creator",
            email="test@example.com",
            settings={"brand_voice": "friendly"},
        )
    )
    return creator


@pytest.fixture(name="consumer")
def consumer_fixture(session: Session, creator):
    """Create a test consumer."""
    from app.domain.consumers.service import ConsumerService
    from app.domain.schemas import ConsumerCreate

    service = ConsumerService(session)
    consumer = service.create_consumer(
        creator.id,
        ConsumerCreate(
            email="consumer@example.com",
            whatsapp="+1234567890",
            name="Test Consumer",
            timezone="America/New_York",
            consent={"email": True, "whatsapp": True},
        ),
    )
    return consumer
