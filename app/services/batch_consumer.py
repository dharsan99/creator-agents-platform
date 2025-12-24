"""Batch consumer service for scheduled jobs and low-priority events.

This service consumes low-priority events from Redpanda for batch processing:
- Analytics events (metrics aggregation, reporting)
- Scheduled tasks (periodic jobs, cleanup)
- Audit logs (compliance, security)

Consumer Group: batch-processing-group
Topics: analytics_events, scheduled_tasks, audit_events
Concurrency: 2 concurrent workers (lower priority)
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
from app.infra.events.consumer import RedpandaConsumer

logger = logging.getLogger(__name__)


class BatchConsumerService:
    """Service for consuming and processing batch/low-priority events.

    This service runs as a long-lived background process that:
    1. Consumes low-priority events from batch topics
    2. Processes analytics, scheduled tasks, and audit logs
    3. Runs with lower concurrency to not interfere with high-priority events

    Usage:
        service = BatchConsumerService()
        await service.run()
    """

    def __init__(self):
        """Initialize batch consumer."""
        self.running = False
        self.consumer: Optional[RedpandaConsumer] = None

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Batch processing topics
        self.topics = [
            "analytics_events",
            "scheduled_tasks",
            "audit_events",
        ]

        logger.info(
            "BatchConsumerService initialized",
            extra={
                "consumer_group": "batch-processing-group",
                "topics": self.topics,
                "concurrency": 2,
            }
        )

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False

    async def process_analytics_event(
        self,
        event_data: Dict[str, Any],
        session: Session
    ) -> bool:
        """Process analytics event for metrics aggregation.

        Args:
            event_data: Analytics event data
            session: Database session

        Returns:
            True if successfully processed, False otherwise
        """
        try:
            logger.info(
                f"Processing analytics event: {event_data.get('metric_type')}",
                extra={
                    "metric_type": event_data.get("metric_type"),
                    "metric_value": event_data.get("metric_value"),
                }
            )

            # TODO: Implement analytics aggregation
            # - Update metrics tables
            # - Calculate rolling averages
            # - Update dashboards

            return True

        except Exception as e:
            logger.error(
                f"Failed to process analytics event: {e}",
                exc_info=True,
                extra={"event_data": event_data}
            )
            return False

    async def process_scheduled_task(
        self,
        event_data: Dict[str, Any],
        session: Session
    ) -> bool:
        """Process scheduled task (cron-like jobs).

        Args:
            event_data: Scheduled task data
            session: Database session

        Returns:
            True if successfully processed, False otherwise
        """
        try:
            logger.info(
                f"Processing scheduled task: {event_data.get('task_name')}",
                extra={
                    "task_name": event_data.get("task_name"),
                    "schedule": event_data.get("schedule"),
                }
            )

            # TODO: Implement scheduled task execution
            # - Execute periodic cleanup jobs
            # - Generate scheduled reports
            # - Run maintenance tasks

            return True

        except Exception as e:
            logger.error(
                f"Failed to process scheduled task: {e}",
                exc_info=True,
                extra={"event_data": event_data}
            )
            return False

    async def process_audit_event(
        self,
        event_data: Dict[str, Any],
        session: Session
    ) -> bool:
        """Process audit event for compliance logging.

        Args:
            event_data: Audit event data
            session: Database session

        Returns:
            True if successfully processed, False otherwise
        """
        try:
            logger.info(
                f"Processing audit event: {event_data.get('action')}",
                extra={
                    "actor_id": event_data.get("actor_id"),
                    "action": event_data.get("action"),
                    "resource_type": event_data.get("resource_type"),
                }
            )

            # TODO: Implement audit logging
            # - Store in audit_logs table
            # - Check compliance rules
            # - Alert on suspicious activity

            return True

        except Exception as e:
            logger.error(
                f"Failed to process audit event: {e}",
                exc_info=True,
                extra={"event_data": event_data}
            )
            return False

    async def process_batch_event(
        self,
        event_data: Dict[str, Any],
        session: Session
    ) -> bool:
        """Route batch event to appropriate handler.

        Args:
            event_data: Event data
            session: Database session

        Returns:
            True if successfully processed, False otherwise
        """
        try:
            event_type = event_data.get("event_type", "")

            if event_type == "analytics_event":
                return await self.process_analytics_event(event_data, session)
            elif event_type == "scheduled_task":
                return await self.process_scheduled_task(event_data, session)
            elif event_type == "audit_event":
                return await self.process_audit_event(event_data, session)
            else:
                logger.warning(f"Unknown batch event type: {event_type}")
                return False

        except Exception as e:
            logger.error(
                f"Failed to process batch event: {e}",
                exc_info=True,
                extra={"event_data": event_data}
            )
            return False

    async def consume_batch(
        self,
        timeout_ms: int = 1000,
        max_messages: int = 5
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
            # Consume messages - use 1ms timeout for non-blocking behavior
            messages = self.consumer.consume(
                timeout_ms=1,  # Non-blocking
                max_messages=max_messages
            )

            if not messages:
                return 0

            logger.info(f"Consumed {len(messages)} batch messages")

            processed_count = 0

            for message in messages:
                try:
                    # Message is already parsed JSON dict
                    event_data = message

                    # Process with database session
                    session = next(get_session())
                    success = await self.process_batch_event(event_data, session)
                    session.close()

                    if success:
                        processed_count += 1

                except Exception as e:
                    logger.error(
                        f"Failed to process message: {e}",
                        exc_info=True
                    )
                    continue

            logger.info(
                f"Processed {processed_count}/{len(messages)} batch messages"
            )

            return processed_count

        except Exception as e:
            logger.error(
                f"Failed to consume batch: {e}",
                exc_info=True
            )
            return 0

    async def run(self):
        """Run the batch consumer service.

        This is the main loop that continuously consumes and processes
        batch/low-priority events from Redpanda.

        The loop runs until:
        - SIGINT (Ctrl+C) received
        - SIGTERM received
        - Fatal error occurs
        """
        logger.info("Starting BatchConsumerService...")

        try:
            # Create consumer
            self.consumer = RedpandaConsumer(
                topics=self.topics,
                group_id="batch-processing-group",
                bootstrap_servers=settings.redpanda_brokers,
            )

            self.running = True

            logger.info(
                "BatchConsumerService running",
                extra={
                    "topics": self.topics,
                    "group_id": "batch-processing-group",
                }
            )

            # Main consumption loop
            iteration = 0
            while self.running:
                try:
                    iteration += 1
                    if iteration % 10 == 1:
                        logger.info(f"Batch consumption loop iteration {iteration}")

                    # Process batch of messages (lower concurrency than high-priority)
                    processed = await self.consume_batch(
                        timeout_ms=1000,
                        max_messages=5
                    )

                    # Sleep longer if no messages (batch processing can wait)
                    if processed == 0:
                        await asyncio.sleep(1.0)  # 1 second sleep for batch jobs

                except Exception as e:
                    logger.error(
                        f"Error in consumption loop iteration {iteration}: {e}",
                        exc_info=True
                    )
                    await asyncio.sleep(5)  # Back off on error

        except Exception as e:
            logger.error(
                f"Fatal error in BatchConsumerService: {e}",
                exc_info=True
            )
            raise

        finally:
            # Cleanup
            if self.consumer:
                self.consumer.close()
                logger.info("Consumer closed")

            logger.info("BatchConsumerService stopped")


async def main():
    """Main entry point for batch consumer service.

    This function is called when running the service as a standalone process:
        python -m app.services.batch_consumer
    """
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger.info("=" * 60)
    logger.info("Batch Consumer Service")
    logger.info("=" * 60)

    # Create and run service
    service = BatchConsumerService()

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
