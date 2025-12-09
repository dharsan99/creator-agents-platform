"""Database models for creator profiles and onboarding."""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Column, Field, JSON, SQLModel, Text


class CreatorProfile(SQLModel, table=True):
    """Enhanced creator profile with LLM-generated content."""
    __tablename__ = "creator_profiles"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    creator_id: UUID = Field(foreign_key="creators.id", unique=True, index=True)

    # External data
    external_user_id: Optional[int] = Field(default=None, index=True)
    external_username: Optional[str] = Field(default=None, index=True)

    # Raw data from external API
    raw_data: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # LLM-generated content
    llm_summary: str = Field(sa_column=Column(Text))  # Comprehensive summary for LLM
    sales_pitch: str = Field(sa_column=Column(Text))  # Optimized sales pitch
    target_audience_description: str = Field(sa_column=Column(Text))
    value_propositions: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Structured service data
    services: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    pricing_info: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # Reputation data
    ratings: dict = Field(default_factory=dict, sa_column=Column(JSON))
    social_proof: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # Agent instructions
    agent_instructions: str = Field(sa_column=Column(Text))  # How agents should sell
    objection_handling: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # Metadata
    last_synced_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OnboardingLog(SQLModel, table=True):
    """Log of creator onboarding attempts."""
    __tablename__ = "onboarding_logs"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    creator_id: Optional[UUID] = Field(foreign_key="creators.id", default=None)
    external_username: str = Field(index=True)

    status: str  # pending, processing, completed, failed
    external_api_response: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    llm_response: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    error_message: Optional[str] = None

    processing_time_seconds: Optional[float] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
