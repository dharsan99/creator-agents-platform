"""Redpanda consumer worker for processing agent invocation events."""
import asyncio
import logging
import sys
from uuid import UUID

from sqlmodel import Session

from app.infra.db.connection import engine
from app.infra.events.consumer import RedpandaConsumer, TOPICS
from app.domain.agents.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


class AgentProcessorWorker:
    """Worker that processes agent-invocations from Redpanda."""

    def __init__(self, bootstrap_servers: str = "redpanda:9092"):
        """Initialize agent processor worker.

        Args:
            bootstrap_servers: Redpanda bootstrap servers
        """
        self.bootstrap_servers = bootstrap_servers
        self.consumer = RedpandaConsumer(
            topics=["events"],
            group_id="agent-processors",
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset="earliest",
        )
        self.processed_count = 0
        self.error_count = 0

    def process_event(self, message: dict) -> bool:
        """Process a single event and trigger agents.

        Args:
            message: Event message from Redpanda

        Returns:
            True if processed successfully, False otherwise
        """
        try:
            # Extract event data
            creator_id = message.get("creator_id")
            consumer_id = message.get("consumer_id")
            event_id = message.get("event_id")
            event_type = message.get("event_type")

            if not all([creator_id, consumer_id, event_id, event_type]):
                logger.error(f"Missing required fields in event: {message}")
                return False

            logger.info(
                f"Processing event: {event_type} "
                f"(event_id: {str(event_id)[:8]}..., "
                f"consumer: {str(consumer_id)[:8]}...)"
            )

            # Process with orchestrator
            with Session(engine) as session:
                orchestrator = Orchestrator(session)

                try:
                    invocation_ids = orchestrator.process_event_agents(
                        creator_id=UUID(creator_id),
                        consumer_id=UUID(consumer_id),
                        event_id=UUID(event_id),
                    )

                    logger.info(
                        f"Created {len(invocation_ids)} invocations for event {event_id}"
                    )
                    self.processed_count += 1
                    return True

                except Exception as e:
                    logger.error(f"Failed to process event: {str(e)}", exc_info=True)
                    self.error_count += 1
                    return False

        except Exception as e:
            logger.error(f"Unexpected error processing event: {str(e)}", exc_info=True)
            self.error_count += 1
            return False

    async def run(self):
        """Main worker loop."""
        logger.info("🚀 Starting Redpanda Agent Processor Worker")
        logger.info(f"Bootstrap servers: {self.bootstrap_servers}")
        logger.info("Listening on topic: events")
        logger.info("Consumer group: agent-processors")

        try:
            while True:
                # Consume messages
                messages = self.consumer.consume(timeout_ms=1000, max_messages=100)

                if not messages:
                    logger.debug("No messages to process")
                    continue

                logger.info(f"Processing batch of {len(messages)} messages")

                for message in messages:
                    try:
                        # Skip metadata
                        if "_metadata" in message:
                            del message["_metadata"]

                        self.process_event(message)

                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}", exc_info=True)

                # Log stats every 100 messages
                if self.processed_count % 100 == 0 and self.processed_count > 0:
                    logger.info(
                        f"📊 Stats: Processed={self.processed_count}, "
                        f"Errors={self.error_count}"
                    )

        except KeyboardInterrupt:
            logger.info("Shutting down gracefully...")
        except Exception as e:
            logger.error(f"Worker error: {str(e)}", exc_info=True)
            raise
        finally:
            self.consumer.close()
            logger.info(
                f"Worker stopped. Total: Processed={self.processed_count}, "
                f"Errors={self.error_count}"
            )


def main():
    """Main entry point."""
    bootstrap_servers = "redpanda:9092"

    worker = AgentProcessorWorker(bootstrap_servers)

    try:
        asyncio.run(worker.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
