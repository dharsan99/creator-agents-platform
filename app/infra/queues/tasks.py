"""Background tasks for RQ workers."""
import logging
from uuid import UUID

from sqlmodel import Session

from app.infra.db.connection import engine
from app.domain.agents.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


def process_agent_invocations(
    creator_id: str,
    consumer_id: str,
    event_id: str,
    event_type: str,
) -> list[str]:
    """Process agent invocations for an event.

    This is the main background task that gets enqueued when events are recorded.

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
            logger.error(f"Failed to process agent invocations: {str(e)}")
            raise


def execute_scheduled_actions() -> int:
    """Execute all actions whose send_at time has passed.

    This should be run periodically (e.g., every minute) by a scheduler.

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
            logger.error(f"Failed to execute scheduled actions: {str(e)}")
            raise


def enqueue_agent_invocations(
    creator_id: str,
    consumer_id: str,
    event_id: str,
    event_type: str,
) -> None:
    """Enqueue agent invocation processing.

    This is called by the event handler to queue the background job.
    """
    from app.infra.queues.connection import agents_queue

    job = agents_queue.enqueue(
        process_agent_invocations,
        creator_id,
        consumer_id,
        event_id,
        event_type,
        job_timeout="5m",
    )

    logger.info(f"Enqueued agent invocation job {job.id} for event {event_id}")
