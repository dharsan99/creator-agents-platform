"""Domain schemas for API requests and responses."""
from datetime import datetime
from typing import Any, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

from app.domain.types import (
    ActionStatus,
    ActionType,
    Channel,
    ConsumerStage,
    EventSource,
    EventType,
    ProductType,
)


# ==================== Base Schemas ====================

class TimestampSchema(BaseModel):
    """Mixin for timestamp fields."""
    created_at: datetime
    updated_at: datetime


# ==================== Creator Schemas ====================

class CreatorCreate(BaseModel):
    """Schema for creating a creator."""
    name: str
    email: EmailStr
    settings: dict = Field(default_factory=dict)


class CreatorResponse(BaseModel):
    """Schema for creator response."""
    id: UUID
    name: str
    email: EmailStr
    settings: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# ==================== Consumer Schemas ====================

class ConsumerCreate(BaseModel):
    """Schema for creating a consumer."""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    whatsapp: Optional[str] = None
    name: Optional[str] = None
    timezone: Optional[str] = None
    preferences: dict = Field(default_factory=dict)
    consent: dict = Field(default_factory=dict)


class ConsumerResponse(BaseModel):
    """Schema for consumer response."""
    id: UUID
    creator_id: UUID
    email: Optional[EmailStr]
    phone: Optional[str]
    whatsapp: Optional[str]
    name: Optional[str]
    timezone: Optional[str]
    preferences: dict
    consent: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# ==================== Product Schemas ====================

class ProductCreate(BaseModel):
    """Schema for creating a product."""
    name: str
    type: ProductType
    price_cents: int
    currency: str = "USD"
    meta: dict = Field(default_factory=dict)


class ProductResponse(BaseModel):
    """Schema for product response."""
    id: UUID
    creator_id: UUID
    name: str
    type: ProductType
    price_cents: int
    currency: str
    meta: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# ==================== Event Schemas ====================

class EventCreate(BaseModel):
    """Schema for creating an event."""
    consumer_id: UUID
    type: EventType
    source: EventSource = EventSource.API
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    payload: dict = Field(default_factory=dict)


class EventResponse(BaseModel):
    """Schema for event response."""
    id: UUID
    creator_id: UUID
    consumer_id: UUID
    type: EventType
    source: EventSource
    timestamp: datetime
    payload: dict
    created_at: datetime

    model_config = {"from_attributes": True}


# ==================== Consumer Context Schemas ====================

class ConsumerContextResponse(BaseModel):
    """Schema for consumer context response."""
    creator_id: UUID
    consumer_id: UUID
    stage: ConsumerStage
    last_seen_at: Optional[datetime]
    metrics: dict
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==================== Agent Schemas ====================

class AgentCreate(BaseModel):
    """Schema for creating an agent."""
    name: str
    implementation: str
    config: dict
    enabled: bool = True
    triggers: list[dict] = Field(default_factory=list)


class AgentResponse(BaseModel):
    """Schema for agent response."""
    id: UUID
    creator_id: Optional[UUID]
    name: str
    implementation: str
    config: dict
    enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ==================== Action Schemas ====================

class PlannedAction(BaseModel):
    """Schema for a planned action from an agent."""
    action_type: ActionType
    channel: Channel
    payload: dict
    send_at: datetime
    priority: float = 0.0


class ActionResponse(BaseModel):
    """Schema for action response."""
    id: UUID
    agent_invocation_id: UUID
    creator_id: UUID
    consumer_id: UUID
    action_type: ActionType
    channel: Channel
    payload: dict
    send_at: datetime
    priority: float
    status: ActionStatus
    policy_decision: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ==================== Policy Schemas ====================

class PolicyDecision(BaseModel):
    """Schema for policy decision result."""
    approved: bool
    reason: Optional[str] = None
    violations: list[str] = Field(default_factory=list)


# ==================== Agent Runtime Schemas ====================

class AgentInput(BaseModel):
    """Input to agent runtime."""
    creator_id: UUID
    consumer_id: UUID
    event: EventResponse
    context: ConsumerContextResponse
    tools: list[str]


class AgentOutput(BaseModel):
    """Output from agent runtime."""
    actions: list[PlannedAction]
    reasoning: Optional[str] = None
    metadata: dict = Field(default_factory=dict)


# ==================== Onboarding Schemas ====================

class OnboardingRequest(BaseModel):
    """Request schema for creator onboarding."""
    username: str
    name: Optional[str] = None
    email: Optional[EmailStr] = None


class OnboardingResponse(BaseModel):
    """Response schema for creator onboarding."""
    success: bool
    message: str
    creator_id: UUID
    profile_id: UUID
    external_username: str
    processing_time_seconds: float

    # Profile highlights
    llm_summary: str
    sales_pitch: str
    services: list[dict]
    value_propositions: list[str]

    model_config = {"from_attributes": True}


class CreatorProfileResponse(BaseModel):
    """Schema for creator profile response."""
    id: UUID
    creator_id: UUID
    external_username: Optional[str]
    llm_summary: str
    sales_pitch: str
    target_audience_description: str
    value_propositions: list[str]
    services: list[dict]
    pricing_info: dict
    ratings: dict
    social_proof: dict
    agent_instructions: str
    objection_handling: dict
    last_synced_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class SyncProfileRequest(BaseModel):
    """Request schema for syncing creator profile."""
    creator_id: UUID


class SyncProfileResponse(BaseModel):
    """Response schema for profile sync."""
    success: bool
    message: str
    profile: CreatorProfileResponse

    model_config = {"from_attributes": True}
