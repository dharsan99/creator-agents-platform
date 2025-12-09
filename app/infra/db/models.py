"""SQLModel database models for all entities."""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Column, Field, JSON, Relationship, SQLModel, Text
from sqlalchemy import Index

# Import creator profile models
from app.infra.db.creator_profile_models import CreatorProfile, OnboardingLog


# ==================== Base Models ====================

class TimestampMixin(SQLModel):
    """Mixin for created_at and updated_at timestamps."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ==================== Creator ====================

class Creator(SQLModel, table=True):
    """Creator account with brand voice and integration settings."""
    __tablename__ = "creators"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    email: str = Field(unique=True, index=True)
    settings: dict = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    consumers: list["Consumer"] = Relationship(back_populates="creator")
    products: list["Product"] = Relationship(back_populates="creator")
    agents: list["Agent"] = Relationship(back_populates="creator")
    events: list["Event"] = Relationship(back_populates="creator")


# ==================== Consumer ====================

class Consumer(SQLModel, table=True):
    """Lead/consumer per creator."""
    __tablename__ = "consumers"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    creator_id: UUID = Field(foreign_key="creators.id", index=True)

    # Identity
    email: Optional[str] = Field(default=None, index=True)
    phone: Optional[str] = Field(default=None)
    whatsapp: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    timezone: Optional[str] = Field(default=None)

    # Preferences and consent
    preferences: dict = Field(default_factory=dict, sa_column=Column(JSON))
    consent: dict = Field(default_factory=dict, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    creator: Creator = Relationship(back_populates="consumers")
    events: list["Event"] = Relationship(back_populates="consumer")
    contexts: list["ConsumerContext"] = Relationship(back_populates="consumer")


# ==================== Product ====================

class Product(SQLModel, table=True):
    """Creator offerings: cohorts, 1:1, subscriptions."""
    __tablename__ = "products"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    creator_id: UUID = Field(foreign_key="creators.id", index=True)

    name: str
    type: str = Field(index=True)  # cohort, one_on_one, subscription
    price_cents: int
    currency: str = Field(default="USD")
    meta: dict = Field(default_factory=dict, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    creator: Creator = Relationship(back_populates="products")


# ==================== Event ====================

class Event(SQLModel, table=True):
    """Unified event model for all consumer interactions."""
    __tablename__ = "events"
    __table_args__ = (
        Index("idx_events_consumer_time", "creator_id", "consumer_id", "timestamp"),
        Index("idx_events_type", "creator_id", "type", "timestamp"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    creator_id: UUID = Field(foreign_key="creators.id", index=True)
    consumer_id: UUID = Field(foreign_key="consumers.id", index=True)

    type: str = Field(index=True)  # page_view, booking, payment, email_sent, etc.
    source: str  # system, webhook, api
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    payload: dict = Field(sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    creator: Creator = Relationship(back_populates="events")
    consumer: Consumer = Relationship(back_populates="events")


# ==================== Consumer Context ====================

class ConsumerContext(SQLModel, table=True):
    """Materialized consumer state snapshot."""
    __tablename__ = "consumer_contexts"

    creator_id: UUID = Field(foreign_key="creators.id", primary_key=True)
    consumer_id: UUID = Field(foreign_key="consumers.id", primary_key=True)

    stage: str  # new, interested, engaged, converted, churned
    last_seen_at: Optional[datetime] = None
    metrics: dict = Field(default_factory=dict, sa_column=Column(JSON))

    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    consumer: Consumer = Relationship(back_populates="contexts")


# ==================== Agent ====================

class Agent(SQLModel, table=True):
    """Agent configuration and metadata."""
    __tablename__ = "agents"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    creator_id: Optional[UUID] = Field(foreign_key="creators.id", default=None, index=True)

    name: str
    implementation: str  # langgraph, external_http
    config: dict = Field(sa_column=Column(JSON))
    enabled: bool = Field(default=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    creator: Optional[Creator] = Relationship(back_populates="agents")
    triggers: list["AgentTrigger"] = Relationship(back_populates="agent")
    invocations: list["AgentInvocation"] = Relationship(back_populates="agent")


# ==================== Agent Trigger ====================

class AgentTrigger(SQLModel, table=True):
    """Defines which events trigger an agent."""
    __tablename__ = "agent_triggers"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    agent_id: UUID = Field(foreign_key="agents.id", index=True)

    event_type: str = Field(index=True)
    filter: dict = Field(default_factory=dict, sa_column=Column(JSON))

    # Relationships
    agent: Agent = Relationship(back_populates="triggers")


# ==================== Agent Invocation ====================

class AgentInvocation(SQLModel, table=True):
    """Tracks agent execution instances."""
    __tablename__ = "agent_invocations"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    agent_id: UUID = Field(foreign_key="agents.id", index=True)
    creator_id: UUID = Field(foreign_key="creators.id", index=True)
    consumer_id: UUID = Field(foreign_key="consumers.id", index=True)
    trigger_event_id: UUID = Field(foreign_key="events.id", index=True)

    status: str  # pending, running, completed, failed
    result: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    error: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    agent: Agent = Relationship(back_populates="invocations")
    actions: list["Action"] = Relationship(back_populates="invocation")


# ==================== Action ====================

class Action(SQLModel, table=True):
    """Planned or executed actions by agents."""
    __tablename__ = "actions"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    agent_invocation_id: UUID = Field(foreign_key="agent_invocations.id", index=True)
    creator_id: UUID = Field(foreign_key="creators.id", index=True)
    consumer_id: UUID = Field(foreign_key="consumers.id", index=True)

    action_type: str  # send_email, send_whatsapp, schedule_call, send_payment_link
    channel: str  # email, whatsapp, call, payment
    payload: dict = Field(sa_column=Column(JSON))

    send_at: datetime  # Scheduled time
    priority: float = Field(default=0.0)

    status: str  # planned, approved, denied, executing, executed, failed
    policy_decision: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    invocation: AgentInvocation = Relationship(back_populates="actions")


# ==================== Policy Rule ====================

class PolicyRule(SQLModel, table=True):
    """Guardrail rules per creator."""
    __tablename__ = "policy_rules"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    creator_id: UUID = Field(foreign_key="creators.id", index=True)

    key: str  # rate_limit_email_weekly, quiet_hours_start, etc.
    value: dict = Field(sa_column=Column(JSON))
