"""Test MainAgent feedback loop by simulating task completion.

This script simulates worker task completion and verifies that MainAgent:
1. Processes worker_task_completed events
2. Updates workflow metrics
3. Checks stage completion
4. Makes LLM decisions
5. Progresses to next stage
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from datetime import datetime
from uuid import uuid4, UUID

from sqlmodel import Session, select

from app.config import settings
from app.infra.db.connection import engine
from app.infra.db.models import Event, Agent
from app.domain.types import EventType, EventSource
from app.domain.workflow.models import WorkflowExecution, Workflow
from app.domain.tasks.models import WorkerTask, TaskStatus
from app.domain.agents.orchestrator import Orchestrator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


def find_active_workflow_execution(session: Session):
    """Find an active workflow execution with pending tasks."""
    stmt = (
        select(WorkflowExecution)
        .where(WorkflowExecution.status == "running")
        .order_by(WorkflowExecution.created_at.desc())
    )
    executions = session.exec(stmt).all()

    for execution in executions:
        # Check if there are pending tasks
        task_stmt = select(WorkerTask).where(
            WorkerTask.workflow_execution_id == execution.id,
            WorkerTask.status == TaskStatus.PENDING
        )
        tasks = list(session.exec(task_stmt).all())

        if tasks:
            return execution, tasks

    return None, []


def simulate_task_completion(session: Session, task: WorkerTask):
    """Simulate a worker task completion."""
    logger.info(f"Simulating completion of task {task.id}")
    logger.info(f"  Task type: {task.task_type}")
    logger.info(f"  Consumer: {task.consumer_id}")
    logger.info(f"  Workflow execution: {task.workflow_execution_id}")

    # Update task status to completed
    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.utcnow()
    task.result = {
        "sent": True,
        "message_id": f"msg_{uuid4().hex[:8]}",
        "task_type": task.task_type,
        "timestamp": datetime.utcnow().isoformat()
    }

    session.add(task)
    session.commit()
    session.refresh(task)

    logger.info(f"✅ Task {task.id} marked as completed")

    # Create worker_task_completed event
    event = Event(
        creator_id=UUID(task.task_payload["creator_id"]),
        consumer_id=task.consumer_id,
        type=EventType.WORKER_TASK_COMPLETED,
        source=EventSource.SYSTEM,
        timestamp=datetime.utcnow(),
        payload={
            "task_id": str(task.id),
            "agent_id": str(task.assigned_agent_id),
            "result": task.result,
            "missing_tools": [],
            "execution_time_ms": 150.5,
            "workflow_execution_id": str(task.workflow_execution_id)
        }
    )

    session.add(event)
    session.commit()
    session.refresh(event)

    logger.info(f"✅ Created worker_task_completed event: {event.id}")

    return event


def trigger_main_agent(session: Session, event: Event):
    """Trigger MainAgent to process the event."""
    logger.info("=" * 80)
    logger.info("Triggering MainAgent feedback loop...")
    logger.info("=" * 80)

    orchestrator = Orchestrator(session)

    try:
        invocation_ids = orchestrator.process_event_agents(
            creator_id=event.creator_id,
            consumer_id=event.consumer_id,
            event_id=event.id
        )

        logger.info(f"✅ MainAgent triggered - {len(invocation_ids)} invocations")

        return invocation_ids

    except Exception as e:
        logger.error(f"Failed to trigger MainAgent: {e}", exc_info=True)
        raise


def verify_workflow_progression(session: Session, execution_id: UUID):
    """Verify that workflow execution was updated."""
    logger.info("=" * 80)
    logger.info("Verifying workflow progression...")
    logger.info("=" * 80)

    # Refresh execution
    execution = session.get(WorkflowExecution, execution_id)

    if not execution:
        logger.error(f"WorkflowExecution {execution_id} not found!")
        return False

    logger.info(f"\n✅ Workflow Execution {execution.id}:")
    logger.info(f"  Current stage: {execution.current_stage}")
    logger.info(f"  Status: {execution.status}")
    logger.info(f"  Metrics: {execution.metrics}")
    logger.info(f"  Decisions log: {len(execution.decisions_log)} decisions")
    logger.info(f"  Tool usage log: {len(execution.tool_usage_log)} tool calls")
    logger.info(f"  Missing tool attempts: {len(execution.missing_tool_attempts)}")

    # Show decision log
    if execution.decisions_log:
        logger.info("\n  Recent decisions:")
        for decision in execution.decisions_log[-3:]:
            logger.info(f"    - {decision}")

    # Check if metrics were updated
    metrics_updated = len(execution.metrics) > 0
    if metrics_updated:
        logger.info("\n✅ Metrics were updated!")
    else:
        logger.warning("\n⚠️  No metrics updates found")

    # Check if decisions were logged
    decisions_logged = len(execution.decisions_log) > 0
    if decisions_logged:
        logger.info("✅ Decisions were logged!")
    else:
        logger.warning("⚠️  No decisions logged")

    return metrics_updated and decisions_logged


def main():
    """Main test function."""
    logger.info("=" * 80)
    logger.info("MainAgent Feedback Loop Test")
    logger.info("=" * 80)
    logger.info(f"Database: {settings.database_url}\n")

    with Session(engine) as session:
        # Step 1: Find active workflow with pending tasks
        logger.info("Step 1: Finding active workflow with pending tasks...")
        execution, tasks = find_active_workflow_execution(session)

        if not execution:
            logger.error("No active workflow executions with pending tasks found!")
            logger.error("Run test_creator_onboarded.py first to create a workflow")
            return

        logger.info(f"✅ Found workflow execution: {execution.id}")
        logger.info(f"  Current stage: {execution.current_stage}")
        logger.info(f"  Pending tasks: {len(tasks)}")

        # Step 2: Simulate completion of first task
        logger.info("\nStep 2: Simulating task completion...")
        task = tasks[0]
        event = simulate_task_completion(session, task)

        # Step 3: Trigger MainAgent
        logger.info("\nStep 3: Triggering MainAgent...")
        invocation_ids = trigger_main_agent(session, event)

        # Step 4: Verify workflow progression
        logger.info("\nStep 4: Verifying workflow progression...")
        success = verify_workflow_progression(session, execution.id)

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("Test Summary")
        logger.info("=" * 80)
        logger.info(f"Workflow execution: {execution.id}")
        logger.info(f"Task completed: {task.id}")
        logger.info(f"Event created: {event.id}")
        logger.info(f"MainAgent invocations: {len(invocation_ids)}")
        logger.info(f"Feedback loop working: {'✅ YES' if success else '❌ NO'}")
        logger.info("=" * 80)


if __name__ == "__main__":
    main()
