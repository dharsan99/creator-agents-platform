"""Agents API router."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import CreatorIdDep, SessionDep
from app.domain.agents.service import AgentService
from app.domain.schemas import AgentCreate, AgentResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    creator_id: CreatorIdDep,
    session: SessionDep,
    agent_data: AgentCreate,
) -> AgentResponse:
    """Create a new agent for the creator."""
    service = AgentService(session)
    agent = service.create_agent(creator_id, agent_data)
    return AgentResponse.model_validate(agent)


@router.get("", response_model=list[AgentResponse])
def list_agents(
    creator_id: CreatorIdDep,
    session: SessionDep,
    enabled_only: bool = Query(True),
) -> list[AgentResponse]:
    """List all agents for the creator."""
    service = AgentService(session)
    agents = service.list_agents(creator_id, enabled_only)
    return [AgentResponse.model_validate(agent) for agent in agents]


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    creator_id: CreatorIdDep,
    session: SessionDep,
    agent_id: UUID,
) -> AgentResponse:
    """Get a specific agent."""
    service = AgentService(session)
    agent = service.get_agent(agent_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    # Verify agent belongs to creator (or is global)
    if agent.creator_id and agent.creator_id != creator_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    return AgentResponse.model_validate(agent)


@router.post("/{agent_id}/enable", response_model=AgentResponse)
def enable_agent(
    creator_id: CreatorIdDep,
    session: SessionDep,
    agent_id: UUID,
) -> AgentResponse:
    """Enable an agent."""
    service = AgentService(session)
    agent = service.get_agent(agent_id)

    if not agent or (agent.creator_id and agent.creator_id != creator_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    agent = service.enable_agent(agent_id)
    return AgentResponse.model_validate(agent)


@router.post("/{agent_id}/disable", response_model=AgentResponse)
def disable_agent(
    creator_id: CreatorIdDep,
    session: SessionDep,
    agent_id: UUID,
) -> AgentResponse:
    """Disable an agent."""
    service = AgentService(session)
    agent = service.get_agent(agent_id)

    if not agent or (agent.creator_id and agent.creator_id != creator_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )

    agent = service.disable_agent(agent_id)
    return AgentResponse.model_validate(agent)
