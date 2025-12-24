"""Event consumer service for processing Redpanda events.

This service consumes events from Redpanda topics and routes them to
appropriate handlers based on event type and priority.

Architecture:
- Multiple consumer groups run independently
- Each group subscribes to specific topics
- Priority-based routing ensures urgent events processed first
- Handlers are pluggable and event-type specific
"""

import asyncio
import json
import logging
import signal
from typing import Any, Callable, Dict, Optional
from uuid import UUID

from app.infra.events.consumer import RedpandaConsumer
from app.infra.events.consumer_groups import (
    HIGH_PRIORITY_GROUP,
    ConsumerGroupConfig,
    get_consumer_group,
)
from app.infra.events.schemas import (
    BaseEvent,
    CreatorOnboardedEvent,
    WorkerTaskEvent,
    deserialize_event,
)

logger = logging.getLogger(__name__)


class EventHandler:
    """Base class for event handlers.

    Handlers process specific event types and are registered with
    the EventConsumerService.
    """

    def __init__(self):
        self.name = self.__class__.__name__

    async def handle(self, event: BaseEvent) -> bool:
        """Handle an event.

        Args:
            event: The event to process

        Returns:
            True if handled successfully, False otherwise
        """
        raise NotImplementedError


class CreatorOnboardedHandler(EventHandler):
    """Handler for creator_onboarded events.

    Processes new creator onboarding by:
    1. Creating a system event in the database
    2. Triggering MainAgent to create workflow
    3. MainAgent delegates initial tasks to worker agents
    """

    def __init__(self):
        super().__init__()
        from app.infra.db.connection import get_session
        self.session_factory = get_session

    async def handle(self, event: CreatorOnboardedEvent) -> bool:
        """Handle creator onboarded event.

        Args:
            event: CreatorOnboardedEvent instance

        Returns:
            True if successful
        """
        try:
            logger.info(
                f"Processing creator_onboarded event",
                extra={
                    "event_id": str(event.event_id),
                    "creator_id": str(event.creator_id),
                    "worker_agents": len(event.worker_agent_ids),
                    "consumers": len(event.consumers),
                    "purpose": event.purpose,
                }
            )

            # Create database session
            session = next(self.session_factory())

            try:
                # Convert Redpanda event to database Event for MainAgent
                from app.infra.db.models import Event
                from app.domain.types import EventType, EventSource

                db_event = Event(
                    creator_id=event.creator_id,
                    consumer_id=event.creator_id,  # Use creator_id as consumer_id for creator-level events (db constraint)
                    type=EventType.CREATOR_ONBOARDED,
                    source=EventSource.SYSTEM,
                    timestamp=event.timestamp,
                    payload={
                        "creator_id": str(event.creator_id),
                        "worker_agent_ids": [str(aid) for aid in event.worker_agent_ids],
                        "consumers": [str(cid) for cid in event.consumers],
                        "purpose": event.purpose,
                        "start_date": event.start_date.isoformat(),
                        "end_date": event.end_date.isoformat(),
                        "goal": event.goal,
                        "config": event.config,
                    }
                )

                session.add(db_event)
                session.commit()
                session.refresh(db_event)

                logger.info(
                    f"Created database event for creator_onboarded",
                    extra={"event_id": str(db_event.id), "creator_id": str(event.creator_id)}
                )

                # Initialize ConsumerContext for all consumers in the cohort
                # This is REQUIRED for worker agents to execute tasks
                from app.infra.db.models import Consumer, ConsumerContext

                contexts_created = 0
                for consumer_id in event.consumers:
                    # Check if ConsumerContext already exists
                    existing_context = session.query(ConsumerContext).filter(
                        ConsumerContext.creator_id == event.creator_id,
                        ConsumerContext.consumer_id == consumer_id
                    ).first()

                    if not existing_context:
                        # Verify consumer exists
                        consumer = session.get(Consumer, consumer_id)
                        if not consumer:
                            logger.warning(
                                f"Consumer {consumer_id} not found in database, skipping context creation",
                                extra={"consumer_id": str(consumer_id)}
                            )
                            continue

                        # Create ConsumerContext with initial state
                        consumer_context = ConsumerContext(
                            creator_id=event.creator_id,
                            consumer_id=consumer_id,
                            stage="onboarding",  # Initial stage for new cohort
                            last_seen_at=event.timestamp,
                            metrics={},  # Empty metrics initially
                            updated_at=event.timestamp
                        )
                        session.add(consumer_context)
                        contexts_created += 1

                session.commit()

                logger.info(
                    f"✅ Initialized {contexts_created} ConsumerContext records",
                    extra={
                        "creator_id": str(event.creator_id),
                        "total_consumers": len(event.consumers),
                        "contexts_created": contexts_created
                    }
                )

                # Trigger MainAgent
                from app.agents.main_agent import MainAgent

                # MainAgent config (minimal - it's purpose-agnostic)
                agent_config = {
                    "agent_class": "app.agents.main_agent:MainAgent",
                    "type": "supervisor",
                }

                main_agent = MainAgent(agent_config=agent_config, session=session)

                # Create a minimal ConsumerContext for MainAgent
                # (MainAgent doesn't need consumer context for creator_onboarded events)
                from app.infra.db.models import ConsumerContext
                dummy_context = ConsumerContext(
                    creator_id=event.creator_id,
                    consumer_id=event.creator_id,  # Use creator_id as placeholder
                    stage="onboarding",
                    metrics={},
                    attributes={},
                )

                # Check if MainAgent should act
                if main_agent.should_act(dummy_context, db_event):
                    logger.info(
                        f"MainAgent triggered for creator_onboarded",
                        extra={"event_id": str(db_event.id)}
                    )

                    # Plan actions (creates workflow, delegates tasks)
                    actions = main_agent.plan_actions(dummy_context, db_event)

                    logger.info(
                        f"MainAgent planned {len(actions)} actions",
                        extra={
                            "event_id": str(db_event.id),
                            "actions_count": len(actions),
                        }
                    )

                    # Actions are published to Redpanda by MainAgent internally
                    # No need to execute them here

                session.commit()

                logger.info(
                    f"Successfully processed creator_onboarded event",
                    extra={
                        "event_id": str(event.event_id),
                        "creator_id": str(event.creator_id),
                        "purpose": event.purpose,
                        "goal": event.goal,
                    }
                )

                return True

            finally:
                session.close()

        except Exception as e:
            logger.error(
                f"Failed to handle creator_onboarded event: {e}",
                extra={"event_id": str(event.event_id)},
                exc_info=True
            )
            return False


class WorkerTaskHandler(EventHandler):
    """Handler for worker_task_assigned events.

    Processes task assignments by:
    1. Finding the appropriate worker agent
    2. Executing the task
    3. Reporting results back to MainAgent
    """

    async def handle(self, event: WorkerTaskEvent) -> bool:
        """Handle worker task event.

        Args:
            event: WorkerTaskEvent instance

        Returns:
            True if successful
        """
        try:
            logger.info(
                f"Processing worker_task_assigned event",
                extra={
                    "event_id": str(event.event_id),
                    "task_id": str(event.task_id),
                    "agent_id": str(event.agent_id),
                    "task_type": event.task_type,
                }
            )

            # TODO: Phase 4 - Execute worker task
            # from app.domain.tasks.service import TaskService
            # task_service = TaskService(...)
            # task_service.execute_task(event.task_id)

            logger.info(
                f"Worker task assigned: {event.task_id}, "
                f"type: {event.task_type}"
            )

            return True

        except Exception as e:
            logger.error(
                f"Failed to handle worker_task_assigned event: {e}",
                extra={"event_id": str(event.event_id)},
                exc_info=True
            )
            return False


class EventConsumerService:
    """Service for consuming and processing Redpanda events.

    This service runs as a long-running background process that:
    - Consumes events from Redpanda topics
    - Deserializes events to typed event objects
    - Routes events to appropriate handlers
    - Handles errors and retries
    - Supports graceful shutdown

    Usage:
        service = EventConsumerService(HIGH_PRIORITY_GROUP)
        service.register_handler("creator_onboarded", CreatorOnboardedHandler())
        await service.run()
    """

    def __init__(self, consumer_group: ConsumerGroupConfig):
        """Initialize event consumer service.

        Args:
            consumer_group: Configuration for this consumer group
        """
        from app.config import settings

        self.consumer_group = consumer_group
        self.consumer = RedpandaConsumer(
            topics=consumer_group.topics,
            group_id=consumer_group.group_id,
            bootstrap_servers=settings.redpanda_brokers,
        )
        self.handlers: Dict[str, EventHandler] = {}
        self.running = False
        self.shutdown_event = asyncio.Event()

        logger.info(
            f"EventConsumerService initialized",
            extra={
                "group_id": consumer_group.group_id,
                "topics": consumer_group.topics,
                "concurrency": consumer_group.concurrency,
                "brokers": settings.redpanda_brokers,
            }
        )

    def register_handler(self, event_type: str, handler: EventHandler):
        """Register an event handler for a specific event type.

        Args:
            event_type: Type of event (e.g., "creator_onboarded")
            handler: EventHandler instance
        """
        self.handlers[event_type] = handler
        logger.info(f"Registered handler {handler.name} for event type '{event_type}'")

    async def process_event(self, event_data: Dict[str, Any]) -> bool:
        """Process a single event.

        Args:
            event_data: Raw event data from Redpanda

        Returns:
            True if processed successfully
        """
        try:
            # Deserialize event
            event = deserialize_event(event_data)

            logger.debug(
                f"Processing event",
                extra={
                    "event_id": str(event.event_id),
                    "event_type": event.event_type,
                    "priority": event.priority,
                    "source": event.source,
                }
            )

            # Find handler for this event type
            handler = self.handlers.get(event.event_type)

            if not handler:
                logger.warning(
                    f"No handler registered for event type: {event.event_type}",
                    extra={"event_id": str(event.event_id)}
                )
                return False

            # Execute handler
            success = await handler.handle(event)

            if success:
                logger.info(
                    f"Successfully processed event",
                    extra={
                        "event_id": str(event.event_id),
                        "event_type": event.event_type,
                        "handler": handler.name,
                    }
                )
            else:
                logger.error(
                    f"Handler failed to process event",
                    extra={
                        "event_id": str(event.event_id),
                        "event_type": event.event_type,
                        "handler": handler.name,
                    }
                )

            return success

        except Exception as e:
            logger.error(
                f"Failed to process event: {e}",
                extra={"event_data": event_data},
                exc_info=True
            )
            return False

    async def consume_batch(self, timeout_ms: int = 1000, max_messages: int = 10):
        """Consume and process a batch of messages.

        Args:
            timeout_ms: Poll timeout in milliseconds
            max_messages: Maximum messages per batch
        """
        try:
            messages = self.consumer.consume(
                timeout_ms=timeout_ms,
                max_messages=max_messages
            )

            for message in messages:
                try:
                    # Message is already a parsed dict from RedpandaConsumer.consume()
                    # Extract metadata for logging
                    metadata = message.get("_metadata", {})
                    topic = metadata.get("topic", "unknown")
                    partition = metadata.get("partition", -1)
                    offset = metadata.get("offset", -1)

                    logger.debug(
                        f"Processing message from {topic} [partition={partition}, offset={offset}]"
                    )

                    # Process event (message is already the event_data dict)
                    await self.process_event(message)

                except Exception as e:
                    logger.error(
                        f"Error processing message: {e}",
                        extra={"message": message},
                        exc_info=True
                    )

            # Commit offsets after processing batch
            if messages:
                self.consumer.commit()
                logger.debug(f"Committed {len(messages)} messages")

        except Exception as e:
            logger.error(f"Error consuming batch: {e}", exc_info=True)

    async def run(self):
        """Run the event consumer service.

        This is a long-running coroutine that continuously consumes
        and processes events until shutdown is signaled.
        """
        self.running = True
        logger.info(
            f"Starting event consumer service",
            extra={"group_id": self.consumer_group.group_id}
        )

        try:
            while self.running and not self.shutdown_event.is_set():
                await self.consume_batch(
                    timeout_ms=1000,
                    max_messages=self.consumer_group.max_poll_records
                )

                # Small delay to prevent tight loop
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info("Event consumer service cancelled")
        except Exception as e:
            logger.error(f"Event consumer service error: {e}", exc_info=True)
        finally:
            self.running = False
            logger.info("Event consumer service stopped")

    def shutdown(self):
        """Signal shutdown to the consumer service."""
        logger.info("Shutting down event consumer service")
        self.running = False
        self.shutdown_event.set()
        self.consumer.close()


async def run_high_priority_consumer():
    """Run the high-priority event consumer.

    This is the main entry point for the high-priority consumer service.
    It handles CRITICAL and HIGH priority events including creator_onboarded.
    """
    service = EventConsumerService(HIGH_PRIORITY_GROUP)

    # Register handlers
    service.register_handler("creator_onboarded", CreatorOnboardedHandler())
    # Add more handlers as needed

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        service.shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the service
    await service.run()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Run the high-priority consumer
    asyncio.run(run_high_priority_consumer())
