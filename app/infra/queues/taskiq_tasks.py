"""Taskiq async tasks for background job processing with retry logic."""
import logging
from uuid import UUID
from datetime import datetime, timedelta

from sqlmodel import Session

from app.infra.db.connection import engine
from app.infra.queues.taskiq_broker import broker
from app.domain.agents.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


@broker.task(max_retries=3)
async def process_agent_invocations(
    creator_id: str,
    consumer_id: str,
    event_id: str,
    event_type: str,
) -> list[str]:
    """Process agent invocations for an event with exponential backoff retry.

    This is the main background task that gets enqueued when events are recorded.
    Features:
    - Automatic retry with exponential backoff (max 3 retries)
    - Comprehensive error logging
    - Task metrics tracking

    Args:
        creator_id: UUID string of creator
        consumer_id: UUID string of consumer
        event_id: UUID string of event
        event_type: Type of event

    Returns:
        List of invocation IDs created
    """
    logger.info(
        f"Processing agent invocations for event {event_id} "
        f"(type: {event_type}, creator: {creator_id}, consumer: {consumer_id})"
    )

    with Session(engine) as session:
        orchestrator = Orchestrator(session)

        try:
            invocation_ids = orchestrator.process_event_agents(
                creator_id=UUID(creator_id),
                consumer_id=UUID(consumer_id),
                event_id=UUID(event_id),
            )

            logger.info(f"Created {len(invocation_ids)} invocations for event {event_id}")
            return [str(inv_id) for inv_id in invocation_ids]

        except Exception as e:
            logger.error(f"Failed to process agent invocations: {str(e)}", exc_info=True)
            raise


@broker.task(max_retries=3)
async def execute_scheduled_actions() -> int:
    """Execute all actions whose send_at time has passed with retry logic.

    This should be run periodically (e.g., every minute) by a scheduler.
    Features:
    - Automatic retry with exponential backoff
    - Detailed execution logging
    - Transactional safety

    Returns:
        Number of actions executed
    """
    logger.info("Executing scheduled actions")

    with Session(engine) as session:
        orchestrator = Orchestrator(session)

        try:
            count = orchestrator.execute_pending_actions()
            logger.info(f"Executed {count} scheduled actions")
            return count

        except Exception as e:
            logger.error(f"Failed to execute scheduled actions: {str(e)}", exc_info=True)
            raise


@broker.task(max_retries=1)
async def process_dead_letter_queue_task() -> int:
    """Process and retry failed tasks from the dead letter queue.

    This task handles recovery of failed background jobs with a simpler retry strategy.
    It re-enqueues failed tasks with reduced retry counts to avoid infinite loops.

    Returns:
        Number of tasks reprocessed
    """
    from app.infra.queues.dlq_service import DLQService

    logger.info("Processing dead letter queue")

    with Session(engine) as session:
        try:
            dlq_service = DLQService(session)

            # Get unprocessed DLQ entries (limit to 10 per batch)
            dlq_entries = dlq_service.get_unprocessed_entries(limit=10)

            if not dlq_entries:
                logger.info("No unprocessed DLQ entries found")
                return 0

            reprocessed_count = 0

            for entry in dlq_entries:
                try:
                    logger.info(
                        f"Reprocessing DLQ entry {entry.id}: {entry.task_name} "
                        f"(retry #{entry.retry_count + 1})"
                    )

                    # Skip if already retried too many times from DLQ
                    if entry.retry_count >= 3:
                        logger.warning(
                            f"DLQ entry {entry.id} has been retried {entry.retry_count} times, "
                            f"marking as processed without retry"
                        )
                        dlq_service.mark_processed(entry.id)
                        continue

                    # Re-enqueue the task based on task name
                    if entry.task_name == "process_agent_invocations":
                        # Extract args from payload
                        args = entry.payload.get("args", [])
                        if len(args) >= 4:
                            await broker.send_task(
                                "app.infra.queues.taskiq_tasks.process_agent_invocations",
                                args=tuple(args),
                                labels={"dlq_retry": True, "max_retries": 1}  # Reduced retries
                            )
                            reprocessed_count += 1
                        else:
                            logger.error(f"Invalid payload for DLQ entry {entry.id}")

                    elif entry.task_name == "execute_scheduled_actions":
                        await broker.send_task(
                            "app.infra.queues.taskiq_tasks.execute_scheduled_actions",
                            args=(),
                            labels={"dlq_retry": True, "max_retries": 1}
                        )
                        reprocessed_count += 1

                    else:
                        logger.warning(
                            f"Unknown task name in DLQ entry {entry.id}: {entry.task_name}"
                        )

                    # Mark as processed
                    dlq_service.mark_processed(entry.id)

                except Exception as e:
                    logger.error(
                        f"Failed to reprocess DLQ entry {entry.id}: {str(e)}",
                        exc_info=True
                    )
                    session.rollback()
                    continue  # Continue with next entry

            logger.info(f"Reprocessed {reprocessed_count} tasks from DLQ")
            return reprocessed_count

        except Exception as e:
            logger.error(f"Failed to process DLQ: {str(e)}", exc_info=True)
            raise


async def enqueue_agent_invocations(
    creator_id: str,
    consumer_id: str,
    event_id: str,
    event_type: str,
) -> str:
    """Enqueue agent invocation processing via Taskiq.

    This is called by the event handler to queue the background job.

    Args:
        creator_id: UUID string of creator
        consumer_id: UUID string of consumer
        event_id: UUID string of event
        event_type: Type of event

    Returns:
        Task ID for tracking
    """
    task_id = await broker.send_task(
        "app.infra.queues.taskiq_tasks.process_agent_invocations",
        args=(creator_id, consumer_id, event_id, event_type),
    )

    logger.info(f"Enqueued agent invocation task {task_id.task_id} for event {event_id}")
    return task_id.task_id


async def enqueue_scheduled_actions() -> str:
    """Enqueue scheduled actions execution via Taskiq.

    Returns:
        Task ID for tracking
    """
    task_id = await broker.send_task(
        "app.infra.queues.taskiq_tasks.execute_scheduled_actions",
        args=(),
    )

    logger.info(f"Enqueued scheduled actions task {task_id.task_id}")
    return task_id.task_id
