"""Agent service for managing agents and their execution."""
import logging
from typing import List, Optional
from uuid import UUID
from sqlmodel import Session, select

from app.infra.db.models import Agent, AgentTrigger, AgentInvocation
from app.domain.schemas import AgentCreate, AgentInput, AgentOutput
from app.domain.agents.runtime import AgentRuntimeFactory
from app.domain.types import AgentImplementation, EventType, InvocationStatus

logger = logging.getLogger(__name__)


class AgentService:
    """Service for managing agents."""

    def __init__(self, session: Session):
        self.session = session

    def create_agent(
        self, creator_id: Optional[UUID], data: AgentCreate
    ) -> Agent:
        """Create a new agent with triggers."""
        agent = Agent(
            creator_id=creator_id,
            name=data.name,
            implementation=data.implementation,
            config=data.config,
            enabled=data.enabled,
        )
        self.session.add(agent)
        self.session.flush()  # Get agent ID

        # Create triggers
        for trigger_data in data.triggers:
            trigger = AgentTrigger(
                agent_id=agent.id,
                event_type=trigger_data["event_type"],
                filter=trigger_data.get("filter", {}),
            )
            self.session.add(trigger)

        self.session.commit()
        self.session.refresh(agent)
        return agent

    def get_agent(self, agent_id: UUID) -> Optional[Agent]:
        """Get agent by ID."""
        return self.session.get(Agent, agent_id)

    def list_agents(
        self,
        creator_id: Optional[UUID] = None,
        enabled_only: bool = True,
    ) -> List[Agent]:
        """List agents, optionally filtered by creator."""
        statement = select(Agent)

        if creator_id:
            statement = statement.where(Agent.creator_id == creator_id)

        if enabled_only:
            statement = statement.where(Agent.enabled == True)

        return list(self.session.exec(statement).all())

    def get_agents_for_event(
        self,
        creator_id: UUID,
        event_type: EventType,
    ) -> List[Agent]:
        """Get all agents that should be triggered for an event type."""
        # Get creator-specific agents
        statement = (
            select(Agent)
            .join(AgentTrigger, Agent.id == AgentTrigger.agent_id)
            .where(Agent.creator_id == creator_id)
            .where(Agent.enabled == True)
            .where(AgentTrigger.event_type == event_type.value)
        )
        creator_agents = list(self.session.exec(statement).all())

        # Get global agents (creator_id = None)
        statement = (
            select(Agent)
            .join(AgentTrigger, Agent.id == AgentTrigger.agent_id)
            .where(Agent.creator_id == None)
            .where(Agent.enabled == True)
            .where(AgentTrigger.event_type == event_type.value)
        )
        global_agents = list(self.session.exec(statement).all())

        return creator_agents + global_agents

    def execute_agent(
        self,
        agent: Agent,
        input_data: AgentInput,
        invocation_id: UUID,
    ) -> AgentOutput:
        """Execute an agent and return planned actions."""
        logger.info(f"Executing agent {agent.id} ({agent.name})")

        try:
            # Update invocation status to running
            invocation = self.session.get(AgentInvocation, invocation_id)
            if invocation:
                invocation.status = InvocationStatus.RUNNING.value
                self.session.add(invocation)
                self.session.commit()

            # Get appropriate runtime
            implementation = AgentImplementation(agent.implementation)
            runtime = AgentRuntimeFactory.create(implementation, self.session)

            # Execute agent
            output = runtime.execute(agent.config, input_data)

            # Update invocation with result
            if invocation:
                invocation.status = InvocationStatus.COMPLETED.value
                invocation.result = {
                    "actions_count": len(output.actions),
                    "reasoning": output.reasoning,
                    "metadata": output.metadata,
                }
                self.session.add(invocation)
                self.session.commit()

            logger.info(
                f"Agent {agent.id} completed successfully, "
                f"generated {len(output.actions)} actions"
            )
            return output

        except Exception as e:
            logger.error(f"Agent {agent.id} execution failed: {str(e)}")

            # Update invocation with error
            invocation = self.session.get(AgentInvocation, invocation_id)
            if invocation:
                invocation.status = InvocationStatus.FAILED.value
                invocation.error = str(e)
                self.session.add(invocation)
                self.session.commit()

            raise

    def disable_agent(self, agent_id: UUID) -> Agent:
        """Disable an agent."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        agent.enabled = False
        self.session.add(agent)
        self.session.commit()
        self.session.refresh(agent)
        return agent

    def enable_agent(self, agent_id: UUID) -> Agent:
        """Enable an agent."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        agent.enabled = True
        self.session.add(agent)
        self.session.commit()
        self.session.refresh(agent)
        return agent
