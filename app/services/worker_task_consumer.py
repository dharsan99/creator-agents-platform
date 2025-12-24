"""Worker task consumer service.

This service consumes from TWO Redpanda topics:
1. supervisor_tasks - Worker task assignments from MainAgent
2. task_results - Worker task completion results

Architecture:
- MainAgent publishes WorkerTaskEvent → supervisor_tasks topic
- This consumer reads supervisor_tasks → Creates DB event → Triggers WorkerAgent
- WorkerAgent executes task → Publishes WorkerTaskCompletedEvent → task_results topic
- This consumer reads task_results → Creates DB event → Triggers MainAgent
- MainAgent processes result → Updates workflow

Consumer Group: worker-task-consumer-group
Topics: supervisor_tasks, task_results
Concurrency: 8 concurrent workers
"""

import asyncio
import logging
import signal
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from sqlmodel import Session

from app.config import settings
from app.infra.db.connection import get_session
from app.infra.events.producer import RedpandaProducer
from app.infra.events.consumer import RedpandaConsumer
from app.infra.events.schemas import WorkerTaskEvent, WorkerTaskCompletedEvent, EventPriority
from app.infra.events.consumer_groups import WORKER_TASK_GROUP
from app.domain.agents.orchestrator import Orchestrator
from app.domain.events.service import EventService
from app.domain.schemas import EventCreate
from app.domain.types import EventType, EventSource
# Import workflow models to ensure SQLAlchemy metadata includes them
from app.domain.workflow.models import Workflow, WorkflowExecution, WorkflowVersion
from app.domain.tasks.models import WorkerTask

logger = logging.getLogger(__name__)


class WorkerTaskConsumerService:
    """Service for consuming and processing worker tasks and results.

    This service runs as a long-lived background process that:
    1. Consumes WorkerTaskEvent from supervisor_tasks topic
       → Creates DB event → Triggers WorkerAgent
    2. Consumes WorkerTaskCompletedEvent from task_results topic
       → Creates DB event → Triggers MainAgent
    3. Enables bidirectional communication: MainAgent ↔ WorkerAgent

    Usage:
        service = WorkerTaskConsumerService()
        await service.run()
    """

    def __init__(self):
        """Initialize worker task consumer."""
        self.running = False
        self.consumer: Optional[RedpandaConsumer] = None

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(
            "WorkerTaskConsumerService initialized",
            extra={
                "consumer_group": WORKER_TASK_GROUP.group_id,
                "topics": WORKER_TASK_GROUP.topics,
                "concurrency": WORKER_TASK_GROUP.concurrency,
            }
        )

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    async def process_worker_task(
        self,
        event_data: Dict[str, Any],
        session: Session
    ) -> bool:
        """Process a single worker task event.

        Args:
            event_data: Parsed WorkerTaskEvent data
            session: Database session

        Returns:
            True if successfully processed, False otherwise
        """
        try:
            # Parse event
            task_event = WorkerTaskEvent(**event_data)

            logger.info(
                f"Processing worker task {task_event.task_id}",
                extra={
                    "task_id": str(task_event.task_id),
                    "agent_id": str(task_event.agent_id),
                    "consumer_id": str(task_event.consumer_id),
                    "task_type": task_event.task_type,
                }
            )

            # Create event in database for tracking
            event_service = EventService(session)

            # Get creator_id from task payload (MainAgent includes it)
            creator_id = UUID(task_event.task_payload.get("creator_id"))

            event_create = EventCreate(
                consumer_id=task_event.consumer_id,
                type=EventType.WORKER_TASK_ASSIGNED,
                source=EventSource.SYSTEM,
                payload={
                    "task_id": str(task_event.task_id),
                    "agent_id": str(task_event.agent_id),
                    "task_type": task_event.task_type,
                    "workflow_execution_id": str(task_event.workflow_execution_id),
                }
            )

            db_event = event_service.create_event(
                creator_id=creator_id,
                data=event_create
            )

            # Trigger worker agent via orchestrator
            orchestrator = Orchestrator(session)
            invocation_ids = orchestrator.process_event_agents(
                creator_id=creator_id,
                consumer_id=task_event.consumer_id,
                event_id=db_event.id
            )

            if invocation_ids:
                logger.info(
                    f"Worker task {task_event.task_id} triggered {len(invocation_ids)} agents",
                    extra={
                        "task_id": str(task_event.task_id),
                        "invocation_ids": [str(id) for id in invocation_ids],
                    }
                )
                return True
            else:
                logger.warning(
                    f"No agents triggered for worker task {task_event.task_id}",
                    extra={"task_id": str(task_event.task_id)}
                )
                return False

        except Exception as e:
            logger.error(
                f"Failed to process worker task: {e}",
                exc_info=True,
                extra={"event_data": event_data}
            )
            return False

    async def process_task_result(
        self,
        event_data: Dict[str, Any],
        session: Session
    ) -> bool:
        """Process worker task completion result.

        Args:
            event_data: Task completion event data
            session: Database session

        Returns:
            True if successfully processed, False otherwise
        """
        try:
            # Parse WorkerTaskCompletedEvent
            task_result = WorkerTaskCompletedEvent(**event_data)

            logger.info(
                f"Processing task result for task {task_result.task_id}",
                extra={
                    "task_id": str(task_result.task_id),
                    "event_type": task_result.event_type,
                }
            )

            # Get WorkerTask from database to find creator_id
            worker_task = session.get(WorkerTask, task_result.task_id)
            if not worker_task:
                logger.error(
                    f"WorkerTask not found: {task_result.task_id}",
                    extra={"task_id": str(task_result.task_id)}
                )
                return False

            # Get creator_id from task payload
            creator_id = UUID(worker_task.task_payload.get("creator_id"))

            # Create event in database for tracking
            event_service = EventService(session)

            event_create = EventCreate(
                consumer_id=task_result.consumer_id,
                type=EventType.WORKER_TASK_COMPLETED,
                source=EventSource.SYSTEM,
                payload={
                    "task_id": str(task_result.task_id),
                    "agent_id": str(task_result.agent_id),
                    "result": task_result.result,
                    "missing_tools": task_result.missing_tools,
                    "execution_time_ms": task_result.execution_time_ms,
                    "workflow_execution_id": str(task_result.workflow_execution_id),
                }
            )

            db_event = event_service.create_event(
                creator_id=creator_id,
                data=event_create
            )

            # Trigger MainAgent via orchestrator
            orchestrator = Orchestrator(session)
            invocation_ids = orchestrator.process_event_agents(
                creator_id=creator_id,
                consumer_id=task_result.consumer_id,
                event_id=db_event.id
            )

            if invocation_ids:
                logger.info(
                    f"Task result {task_result.task_id} triggered {len(invocation_ids)} agents",
                    extra={
                        "task_id": str(task_result.task_id),
                        "invocation_ids": [str(id) for id in invocation_ids],
                    }
                )
                return True
            else:
                logger.warning(
                    f"No agents triggered for task result {task_result.task_id}",
                    extra={"task_id": str(task_result.task_id)}
                )
                return False

        except Exception as e:
            logger.error(
                f"Failed to process task result: {e}",
                exc_info=True,
                extra={"event_data": event_data}
            )
            return False

    async def consume_batch(
        self,
        timeout_ms: int = 1000,
        max_messages: int = 10
    ) -> int:
        """Consume and process a batch of messages.

        Args:
            timeout_ms: Timeout for consuming messages
            max_messages: Maximum messages to consume per batch

        Returns:
            Number of messages successfully processed
        """
        if not self.consumer:
            logger.warning("Consumer not initialized!")
            return 0

        try:
            # Consume messages - use 1ms timeout for truly non-blocking behavior
            logger.info(f"Attempting to consume up to {max_messages} messages...")

            # Use 1ms timeout to make it effectively non-blocking
            messages = self.consumer.consume(
                timeout_ms=1,  # 1ms = effectively non-blocking
                max_messages=max_messages
            )

            if not messages:
                logger.debug("No messages consumed")
                return 0

            logger.info(f"Consumed {len(messages)} worker task messages")

            processed_count = 0

            for message in messages:
                try:
                    # Message is already parsed JSON dict
                    event_data = message

                    # Route based on event type
                    event_type = event_data.get("event_type", "")

                    # Process with database session
                    session = next(get_session())

                    if event_type == "worker_task_assigned":
                        success = await self.process_worker_task(event_data, session)
                    elif event_type == "worker_task_completed":
                        success = await self.process_task_result(event_data, session)
                    else:
                        logger.warning(
                            f"Unknown event type: {event_type}",
                            extra={"event_data": event_data}
                        )
                        success = False

                    session.close()

                    if success:
                        processed_count += 1

                    # Note: Consumer auto-commits offsets (enable.auto.commit=True)

                except Exception as e:
                    logger.error(
                        f"Failed to process message: {e}",
                        exc_info=True
                    )
                    # Don't commit offset - message will be reprocessed
                    continue

            logger.info(
                f"Processed {processed_count}/{len(messages)} worker task messages"
            )

            return processed_count

        except Exception as e:
            logger.error(
                f"Failed to consume batch: {e}",
                exc_info=True
            )
            return 0

    async def run(self):
        """Run the consumer service.

        This is the main loop that continuously consumes and processes
        worker task assignments from Redpanda.

        The loop runs until:
        - SIGINT (Ctrl+C) received
        - SIGTERM received
        - Fatal error occurs
        """
        logger.info("Starting WorkerTaskConsumerService...")

        try:
            # Create consumer
            self.consumer = RedpandaConsumer(
                topics=WORKER_TASK_GROUP.topics,
                group_id=WORKER_TASK_GROUP.group_id,
                bootstrap_servers=settings.redpanda_brokers,
            )

            self.running = True

            logger.info(
                "WorkerTaskConsumerService running",
                extra={
                    "topics": WORKER_TASK_GROUP.topics,
                    "group_id": WORKER_TASK_GROUP.group_id,
                }
            )

            # Main consumption loop
            logger.info("Starting main consumption loop...")
            iteration = 0
            while self.running:
                try:
                    iteration += 1
                    if iteration % 10 == 1:  # Log every 10 iterations
                        logger.info(f"Consumption loop iteration {iteration}")

                    # Process batch of messages
                    processed = await self.consume_batch(
                        timeout_ms=1000,
                        max_messages=WORKER_TASK_GROUP.concurrency
                    )

                    # Short sleep if no messages to avoid tight loop
                    if processed == 0:
                        await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(
                        f"Error in consumption loop iteration {iteration}: {e}",
                        exc_info=True
                    )
                    await asyncio.sleep(1)  # Back off on error

        except Exception as e:
            logger.error(
                f"Fatal error in WorkerTaskConsumerService: {e}",
                exc_info=True
            )
            raise

        finally:
            # Cleanup
            if self.consumer:
                self.consumer.close()
                logger.info("Consumer closed")

            logger.info("WorkerTaskConsumerService stopped")


async def main():
    """Main entry point for worker task consumer service.

    This function is called when running the service as a standalone process:
        python -m app.services.worker_task_consumer
    """
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("=" * 60)
    logger.info("Worker Task Consumer Service")
    logger.info("=" * 60)

    # Create and run service
    service = WorkerTaskConsumerService()

    try:
        await service.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Service failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    """Run the service when executed directly."""
    asyncio.run(main())
