"""Deploy WorkerAgent for processing supervisor task assignments.

This script deploys a single global WorkerAgent that:
- Listens for worker_task_assigned events
- Executes delegated tasks from MainAgent
- Publishes results back to task_results topic
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from sqlmodel import Session, select

from app.infra.db.connection import engine
from app.infra.db.models import Agent, AgentTrigger
from app.domain.types import EventType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def deploy_worker_agent(session: Session) -> Agent:
    """Deploy global WorkerAgent.

    Returns:
        Agent: The deployed WorkerAgent instance
    """
    # Check if WorkerAgent already exists
    stmt = select(Agent).where(Agent.name == "WorkerAgent")
    existing = session.exec(stmt).first()

    if existing:
        logger.info(f"WorkerAgent already deployed: {existing.id}")
        return existing

    logger.info("Deploying WorkerAgent...")

    # Create WorkerAgent
    agent = Agent(
        creator_id=None,  # Global agent (no specific creator)
        name="WorkerAgent",
        implementation="simple",
        config={
            "agent_class": "app.agents.worker_agent:WorkerAgent",
            "description": "Generic worker agent that executes tasks delegated by MainAgent",
        },
        enabled=True
    )

    session.add(agent)
    session.flush()  # Get agent.id

    # Create trigger for worker_task_assigned events
    trigger = AgentTrigger(
        agent_id=agent.id,
        event_type=EventType.WORKER_TASK_ASSIGNED.value,
        filter={}  # No filter - process all worker task assignments
    )

    session.add(trigger)
    session.commit()
    session.refresh(agent)

    logger.info(f"✅ WorkerAgent deployed: {agent.id}")
    logger.info(f"   Triggers: {EventType.WORKER_TASK_ASSIGNED.value}")

    return agent


def main():
    """Main deployment function."""
    logger.info("=" * 60)
    logger.info("WorkerAgent Deployment")
    logger.info("=" * 60)

    with Session(engine) as session:
        agent = deploy_worker_agent(session)

        logger.info("")
        logger.info("=" * 60)
        logger.info("Deployment Complete!")
        logger.info("=" * 60)
        logger.info(f"WorkerAgent ID: {agent.id}")
        logger.info("")
        logger.info("The WorkerAgent is now ready to:")
        logger.info("  - Consume worker_task_assigned events")
        logger.info("  - Execute tasks delegated by MainAgent")
        logger.info("  - Publish results to task_results topic")
        logger.info("=" * 60)


if __name__ == "__main__":
    main()
