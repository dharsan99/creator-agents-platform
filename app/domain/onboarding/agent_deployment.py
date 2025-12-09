"""Service for deploying agents for onboarded creators."""
import logging
from uuid import UUID
from sqlmodel import Session

from app.infra.db.models import Agent, AgentTrigger, Creator
from app.infra.db.creator_profile_models import CreatorProfile
from app.domain.types import AgentImplementation, EventType
from app.domain.schemas import AgentCreate

logger = logging.getLogger(__name__)


class AgentDeploymentService:
    """Service for deploying GenericSalesAgent for creators."""

    def __init__(self, session: Session):
        self.session = session

    def deploy_sales_agent(
        self,
        creator: Creator,
        profile: CreatorProfile,
    ) -> Agent:
        """Deploy a GenericSalesAgent for a creator.

        Args:
            creator: Creator instance
            profile: CreatorProfile with LLM-generated content

        Returns:
            Created Agent instance
        """
        logger.info(f"Deploying GenericSalesAgent for creator {creator.id}")

        # Prepare creator profile data for agent context
        creator_profile_data = {
            "creator_name": creator.name,
            "creator_id": str(creator.id),
            "sales_pitch": profile.sales_pitch,
            "agent_instructions": profile.agent_instructions,
            "services": profile.services,
            "value_propositions": profile.value_propositions,
            "objection_handling": profile.objection_handling,
            "target_audience": profile.target_audience_description,
        }

        # Create agent configuration
        agent_config = {
            "agent_class": "app.agents.generic_sales_agent:GenericSalesAgent",
            "creator_profile": creator_profile_data,
        }

        # Create the agent
        agent = Agent(
            creator_id=creator.id,
            name=f"{creator.name} - Sales Agent",
            implementation=AgentImplementation.SIMPLE.value,
            config=agent_config,
            enabled=True,
        )

        self.session.add(agent)
        self.session.flush()  # Get agent ID

        # Create triggers for relevant events
        triggers = [
            AgentTrigger(
                agent_id=agent.id,
                event_type=EventType.PAGE_VIEW.value,
                filter={},  # No filter - trigger on all page views
            ),
            AgentTrigger(
                agent_id=agent.id,
                event_type=EventType.SERVICE_CLICK.value,
                filter={},  # No filter - trigger on all service clicks
            ),
        ]

        for trigger in triggers:
            self.session.add(trigger)

        self.session.commit()
        self.session.refresh(agent)

        logger.info(
            f"Successfully deployed agent {agent.id} for creator {creator.id} "
            f"with {len(triggers)} triggers"
        )

        return agent

    def get_creator_agents(self, creator_id: UUID) -> list[Agent]:
        """Get all agents for a creator.

        Args:
            creator_id: Creator ID

        Returns:
            List of Agent instances
        """
        from sqlmodel import select

        statement = select(Agent).where(Agent.creator_id == creator_id)
        return list(self.session.exec(statement).all())

    def update_agent_profile(
        self,
        agent: Agent,
        profile: CreatorProfile,
    ) -> Agent:
        """Update an existing agent with new profile data.

        Args:
            agent: Agent instance
            profile: Updated CreatorProfile

        Returns:
            Updated Agent instance
        """
        logger.info(f"Updating agent {agent.id} with new profile data")

        # Get creator from agent
        creator = self.session.get(Creator, agent.creator_id)
        if not creator:
            raise ValueError(f"Creator {agent.creator_id} not found")

        # Update creator profile data in config
        creator_profile_data = {
            "creator_name": creator.name,
            "creator_id": str(creator.id),
            "sales_pitch": profile.sales_pitch,
            "agent_instructions": profile.agent_instructions,
            "services": profile.services,
            "value_propositions": profile.value_propositions,
            "objection_handling": profile.objection_handling,
            "target_audience": profile.target_audience_description,
        }

        # Update agent config
        agent.config["creator_profile"] = creator_profile_data

        self.session.add(agent)
        self.session.commit()
        self.session.refresh(agent)

        logger.info(f"Successfully updated agent {agent.id}")

        return agent
