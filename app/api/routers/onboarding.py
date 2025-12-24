"""API router for creator onboarding and agent management.

UPDATED FOR SUPERVISOR-WORKER ARCHITECTURE:
- Creator onboarding happens in creator-onboarding-service (external)
- This service receives creator_onboarded events via Redpanda
- MainAgent is global (deployed once, works for all creators)
- Creator profiles fetched on-demand from onboarding service
"""
import logging
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.dependencies import get_session
from app.infra.external.onboarding_client import get_onboarding_client, OnboardingServiceClient
from app.infra.db.models import Agent
from app.domain.schemas import AgentResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

SessionDep = Annotated[Session, Depends(get_session)]


# Response Models

class CreatorProfileResponse(BaseModel):
    """Response model for creator profile (proxied from onboarding service)."""
    creator_id: UUID
    external_username: str
    name: Optional[str] = None
    email: Optional[str] = None
    services: list = Field(default_factory=list)
    sales_pitch: Optional[str] = None
    target_audience: Optional[str] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class MainAgentDeploymentResponse(BaseModel):
    """Response for MainAgent deployment."""
    success: bool
    message: str
    agent_id: UUID
    agent_name: str
    enabled: bool
    triggers: list[str]
    created_at: str


# API Endpoints

@router.get("/profile/{creator_id}", response_model=CreatorProfileResponse)
async def get_creator_profile(
    creator_id: UUID,
    session: SessionDep,
):
    """Get creator profile by ID (proxied from onboarding service).

    This endpoint fetches creator profile data on-demand from the
    creator-onboarding-service. No local database sync.

    Args:
        creator_id: Creator UUID

    Returns:
        Creator profile data

    Raises:
        404: Creator profile not found
        503: Onboarding service unavailable
    """
    try:
        client = get_onboarding_client()
        profile = client.get_creator_profile(creator_id)

        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Creator profile not found: {creator_id}"
            )

        logger.info(f"Retrieved creator profile: {creator_id}")

        return CreatorProfileResponse(
            creator_id=creator_id,
            external_username=profile.external_username,
            name=profile.name,
            email=profile.email,
            services=profile.services,
            sales_pitch=profile.sales_pitch,
            target_audience=profile.target_audience,
            created_at=profile.created_at.isoformat() if profile.created_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get creator profile: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Onboarding service unavailable"
        )


@router.get("/agents/{creator_id}", response_model=list[AgentResponse])
async def list_creator_agents(
    creator_id: UUID,
    session: SessionDep,
):
    """List all agents for a creator.

    In the new architecture, this returns:
    - Worker agents specific to this creator (if any)
    - The global MainAgent (supervisor for all creators)

    Args:
        creator_id: Creator UUID

    Returns:
        List of agents
    """
    try:
        # Get creator-specific agents
        statement = select(Agent).where(Agent.creator_id == creator_id)
        creator_agents = list(session.exec(statement).all())

        # Get global MainAgent
        main_agent_stmt = select(Agent).where(
            Agent.creator_id.is_(None),
            Agent.name == "MainAgent"
        )
        main_agent = session.exec(main_agent_stmt).first()

        agents = creator_agents
        if main_agent:
            agents.append(main_agent)

        logger.info(
            f"Retrieved {len(agents)} agents for creator {creator_id}",
            extra={
                "creator_agents": len(creator_agents),
                "has_main_agent": main_agent is not None
            }
        )

        return [AgentResponse.model_validate(agent) for agent in agents]

    except Exception as e:
        logger.error(f"Failed to list creator agents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/admin/deploy-main-agent", response_model=MainAgentDeploymentResponse)
async def deploy_main_agent(
    session: SessionDep,
):
    """Deploy the global MainAgent (supervisor).

    This is an admin-only endpoint that deploys the single global
    MainAgent that orchestrates workflows for ALL creators.

    The MainAgent:
    - Is NOT tied to a specific creator (creator_id = None)
    - Handles creator_onboarded events
    - Plans workflows dynamically using LLM
    - Delegates tasks to worker agents
    - Monitors metrics and adjusts workflows

    This endpoint should only be called once during initial setup.

    Returns:
        Deployment status

    Raises:
        409: MainAgent already exists
        500: Deployment failed
    """
    try:
        # Check if MainAgent already exists
        statement = select(Agent).where(
            Agent.creator_id.is_(None),
            Agent.name == "MainAgent"
        )
        existing = session.exec(statement).first()

        if existing:
            logger.warning("MainAgent already exists")
            return MainAgentDeploymentResponse(
                success=True,
                message="MainAgent already deployed",
                agent_id=existing.id,
                agent_name=existing.name,
                enabled=existing.enabled,
                triggers=[],
                created_at=existing.created_at.isoformat() if existing.created_at else "",
            )

        # Deploy MainAgent using the deployment script logic
        from app.infra.db.models import AgentTrigger
        from datetime import datetime

        logger.info("Deploying global MainAgent...")

        # Create MainAgent
        main_agent = Agent(
            creator_id=None,  # Global agent
            name="MainAgent",
            implementation="simple",
            config={
                "agent_class": "app.agents.main_agent:MainAgent",
                "description": "Global supervisor agent for workflow orchestration",
                "purpose": "orchestration",
                "capabilities": [
                    "workflow_planning",
                    "tool_discovery",
                    "task_delegation",
                    "metric_monitoring",
                    "dynamic_adjustment"
                ]
            },
            enabled=True,
        )

        session.add(main_agent)
        session.flush()

        # Create triggers for orchestration events
        orchestration_events = [
            "creator_onboarded",
            "workflow_metric_update",
            "worker_task_completed",
            "workflow_state_change",
        ]

        for event_type in orchestration_events:
            trigger = AgentTrigger(
                agent_id=main_agent.id,
                event_type=event_type,
                filter=None,
            )
            session.add(trigger)

        session.commit()
        session.refresh(main_agent)

        logger.info(
            f"MainAgent deployed successfully",
            extra={
                "agent_id": str(main_agent.id),
                "triggers": len(orchestration_events),
            }
        )

        return MainAgentDeploymentResponse(
            success=True,
            message="MainAgent deployed successfully",
            agent_id=main_agent.id,
            agent_name=main_agent.name,
            enabled=main_agent.enabled,
            triggers=orchestration_events,
            created_at=main_agent.created_at.isoformat() if main_agent.created_at else "",
        )

    except Exception as e:
        logger.error(f"Failed to deploy MainAgent: {e}", exc_info=True)
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MainAgent deployment failed: {str(e)}"
        )
