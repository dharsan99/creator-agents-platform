"""Create database tables using SQLModel."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import SQLModel, create_engine
from app.config import settings

# Import all models to ensure they're registered with SQLModel
from app.infra.db.models import (
    Creator,
    Consumer,
    Product,
    Event,
    ConsumerContext,
    Agent,
    AgentTrigger,
    AgentInvocation,
    Action,
    PolicyRule,
)
from app.infra.db.creator_profile_models import CreatorProfile, OnboardingLog

def create_tables():
    """Create all database tables."""
    print(f"Creating tables in database: {settings.database_url}")

    engine = create_engine(settings.database_url, echo=True)

    # Create all tables
    SQLModel.metadata.create_all(engine)

    print("\n✅ All tables created successfully!")

if __name__ == "__main__":
    create_tables()
