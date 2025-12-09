"""Database connection and session management."""
from sqlmodel import Session, create_engine
from app.config import settings

# Create engine with connection pooling
engine = create_engine(
    settings.database_url,
    echo=settings.env == "development",
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
)


def get_session():
    """Dependency for getting database session."""
    with Session(engine) as session:
        yield session
