"""Test script for creator_onboarded event with MainAgent.

This script simulates a creator_onboarded event and triggers the MainAgent
to create a workflow and delegate tasks to worker agents.

Usage:
    python scripts/test_creator_onboarded.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from datetime import datetime, timedelta
from uuid import uuid4

from sqlmodel import Session, select

from app.config import settings
from app.infra.db.connection import engine
from app.infra.db.models import Creator, Consumer, Event, Agent
from app.infra.db.creator_profile_models import CreatorProfile
from app.domain.agents.orchestrator import Orchestrator
from app.infra.logging import setup_logging, set_correlation_id

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
setup_logging(use_json=False)

logger = logging.getLogger(__name__)


def create_test_data(session: Session):
    """Create test creator and consumers."""
    logger.info("Creating test data...")

    # Check if test creator already exists
    from sqlmodel import select
    stmt = select(Creator).where(Creator.email == "test@example.com")
    creator = session.exec(stmt).first()

    if creator:
        logger.info(f"Using existing creator: {creator.id} - {creator.name}")
    else:
        # Create test creator
        creator = Creator(
            name="Test Creator",
            email="test@example.com",
            settings={}
        )
        session.add(creator)
        session.commit()
        session.refresh(creator)
        logger.info(f"Created creator: {creator.id} - {creator.name}")

    # Get or create test consumers
    consumers = []
    test_emails = [f"consumer{i+1}@example.com" for i in range(3)]

    # Check existing consumers
    stmt = select(Consumer).where(
        Consumer.creator_id == creator.id,
        Consumer.email.in_(test_emails)
    )
    existing_consumers = list(session.exec(stmt).all())

    if len(existing_consumers) >= 3:
        consumers = existing_consumers[:3]
        logger.info(f"Using {len(consumers)} existing consumers")
    else:
        # Create missing consumers
        for i in range(3):
            email = f"consumer{i+1}@example.com"
            # Check if this specific consumer exists
            existing = next((c for c in existing_consumers if c.email == email), None)
            if existing:
                consumers.append(existing)
            else:
                consumer = Consumer(
                    creator_id=creator.id,
                    name=f"Test Consumer {i+1}",
                    email=email,
                    whatsapp=f"+1415555000{i}",
                    preferences={"cohort": "test_cohort"},
                    consent={}
                )
                session.add(consumer)
                consumers.append(consumer)

        session.commit()
        for consumer in consumers:
            session.refresh(consumer)
            if consumer.id not in [c.id for c in existing_consumers]:
                logger.info(f"Created consumer: {consumer.id} - {consumer.name}")
            else:
                logger.info(f"Using existing consumer: {consumer.id} - {consumer.name}")

    # Create or get consumer contexts
    from app.domain.context.service import ConsumerContextService
    context_service = ConsumerContextService(session)

    for consumer in consumers:
        # Get or create context
        context = context_service.get_or_create_context(creator.id, consumer.id)
        if context.stage:  # Context already existed
            logger.info(f"Ensured context exists for consumer: {consumer.id}")

    return creator, consumers


def get_main_agent(session: Session) -> Agent:
    """Get the deployed MainAgent."""
    stmt = select(Agent).where(Agent.name == "MainAgent")
    agent = session.exec(stmt).first()

    if not agent:
        logger.error("MainAgent not found! Run: python scripts/deploy_main_agent.py")
        sys.exit(1)

    logger.info(f"Found MainAgent: {agent.id}")
    return agent


def create_creator_onboarded_event(
    session: Session,
    creator: Creator,
    consumers: list,
    agent: Agent
) -> Event:
    """Create a creator_onboarded event."""
    logger.info("Creating creator_onboarded event...")

    # Calculate campaign dates
    start_date = datetime.utcnow()
    end_date = start_date + timedelta(days=7)

    event = Event(
        creator_id=creator.id,
        consumer_id=consumers[0].id,  # Use first consumer as event source
        type="creator_onboarded",
        source="api",
        timestamp=datetime.utcnow(),
        payload={
            "creator_id": str(creator.id),
            "worker_agent_ids": [str(agent.id)],  # In real scenario, these would be worker agents
            "consumers": [str(c.id) for c in consumers],
            "purpose": "cohort_conversion",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "goal": "Convert test cohort consumers",
            "config": {
                "creator_name": creator.name,
                "cohort_name": "Test Cohort",
                "product_name": "Test Product",
                "product_price": "$999",
                "campaign_type": "cohort_sales"
            }
        }
    )

    session.add(event)
    session.commit()
    session.refresh(event)

    logger.info(f"Created event: {event.id} - {event.type}")
    logger.info(f"Event payload: {event.payload}")

    return event


def trigger_main_agent(session: Session, event: Event):
    """Trigger MainAgent to process the event."""
    logger.info("=" * 80)
    logger.info("Triggering MainAgent...")
    logger.info("=" * 80)

    # Set correlation ID for tracing
    correlation_id = set_correlation_id()
    logger.info(f"Correlation ID: {correlation_id}")

    # Use orchestrator to process event
    orchestrator = Orchestrator(session)

    try:
        invocation_ids = orchestrator.process_event_agents(
            creator_id=event.creator_id,
            consumer_id=event.consumer_id,
            event_id=event.id
        )

        logger.info("=" * 80)
        logger.info(f"✅ MainAgent processing completed!")
        logger.info(f"Created {len(invocation_ids)} agent invocations")
        logger.info("=" * 80)

        # Show results
        for inv_id in invocation_ids:
            from app.infra.db.models import AgentInvocation
            invocation = session.get(AgentInvocation, inv_id)
            if invocation:
                logger.info(f"\nInvocation {invocation.id}:")
                logger.info(f"  Agent: {invocation.agent_id}")
                logger.info(f"  Status: {invocation.status}")
                if invocation.result:
                    logger.info(f"  Result: {invocation.result}")
                if invocation.error:
                    logger.error(f"  Error: {invocation.error}")

        return invocation_ids

    except Exception as e:
        logger.error(f"Failed to process event: {e}", exc_info=True)
        raise


def check_workflow_created(session: Session, creator_id):
    """Check if a workflow was created."""
    from app.domain.workflow.models import Workflow, WorkflowExecution

    logger.info("\n" + "=" * 80)
    logger.info("Checking created workflows...")
    logger.info("=" * 80)

    # Get workflows for creator
    stmt = select(Workflow).where(Workflow.creator_id == creator_id)
    workflows = session.exec(stmt).all()

    if not workflows:
        logger.warning("No workflows created yet")
        return

    for workflow in workflows:
        logger.info(f"\n✅ Workflow {workflow.id}:")
        logger.info(f"  Purpose: {workflow.purpose}")
        logger.info(f"  Type: {workflow.workflow_type}")
        logger.info(f"  Version: {workflow.version}")
        logger.info(f"  Goal: {workflow.goal}")
        logger.info(f"  Stages: {list(workflow.stages.keys()) if workflow.stages else []}")
        logger.info(f"  Available tools: {workflow.available_tools}")
        logger.info(f"  Missing tools: {len(workflow.missing_tools)} tools")

        # Get executions
        exec_stmt = select(WorkflowExecution).where(
            WorkflowExecution.workflow_id == workflow.id
        )
        executions = session.exec(exec_stmt).all()

        logger.info(f"\n  Executions: {len(executions)}")
        for execution in executions:
            logger.info(f"    - {execution.id}: {execution.status} (stage: {execution.current_stage})")


def check_worker_tasks(session: Session, creator_id):
    """Check if worker tasks were created."""
    from app.domain.tasks.models import WorkerTask

    logger.info("\n" + "=" * 80)
    logger.info("Checking worker tasks...")
    logger.info("=" * 80)

    # Get tasks for workflows owned by creator
    from app.domain.workflow.models import Workflow, WorkflowExecution

    stmt = select(Workflow).where(Workflow.creator_id == creator_id)
    workflows = session.exec(stmt).all()

    if not workflows:
        logger.warning("No workflows found")
        return

    total_tasks = 0
    for workflow in workflows:
        exec_stmt = select(WorkflowExecution).where(
            WorkflowExecution.workflow_id == workflow.id
        )
        executions = session.exec(exec_stmt).all()

        for execution in executions:
            task_stmt = select(WorkerTask).where(
                WorkerTask.workflow_execution_id == execution.id
            )
            tasks = session.exec(task_stmt).all()

            if tasks:
                logger.info(f"\n✅ Tasks for execution {execution.id}:")
                for task in tasks:
                    total_tasks += 1
                    logger.info(f"  - Task {task.id}:")
                    logger.info(f"      Type: {task.task_type}")
                    logger.info(f"      Status: {task.status}")
                    logger.info(f"      Consumer: {task.consumer_id}")

    if total_tasks == 0:
        logger.warning("No worker tasks created yet")
    else:
        logger.info(f"\n✅ Total worker tasks: {total_tasks}")


def main():
    """Main test function."""
    logger.info("=" * 80)
    logger.info("Creator Onboarded Event Test")
    logger.info("=" * 80)
    logger.info(f"Database: {settings.database_url}")
    logger.info("")

    with Session(engine) as session:
        # Step 1: Create test data
        creator, consumers = create_test_data(session)

        # Step 2: Get MainAgent
        main_agent = get_main_agent(session)

        # Step 3: Create creator_onboarded event
        event = create_creator_onboarded_event(session, creator, consumers, main_agent)

        # Step 4: Trigger MainAgent
        invocation_ids = trigger_main_agent(session, event)

        # Step 5: Check results
        check_workflow_created(session, creator.id)
        check_worker_tasks(session, creator.id)

        logger.info("\n" + "=" * 80)
        logger.info("Test completed!")
        logger.info("=" * 80)
        logger.info(f"Creator ID: {creator.id}")
        logger.info(f"Event ID: {event.id}")
        logger.info(f"Invocations: {len(invocation_ids)}")
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Check the logs above for workflow and task creation")
        logger.info("2. Query the database to see workflows and tasks")
        logger.info("3. Start consumer services to process events from Redpanda")
        logger.info("=" * 80)


if __name__ == "__main__":
    main()
