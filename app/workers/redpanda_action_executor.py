"""Redpanda consumer worker for executing action events."""
import asyncio
import logging
import sys
from datetime import datetime
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


class ActionExecutorWorker:
    """Worker that executes actions from Redpanda."""

    def __init__(self, bootstrap_servers: str = "redpanda:9092"):
        """Initialize action executor worker.

        Args:
            bootstrap_servers: Redpanda bootstrap servers
        """
        self.bootstrap_servers = bootstrap_servers
        self.consumer = RedpandaConsumer(
            topics=["actions"],
            group_id="action-executors",
            bootstrap_servers=bootstrap_servers,
            auto_offset_reset="earliest",
        )
        self.executed_count = 0
        self.error_count = 0

    def execute_action(self, message: dict) -> bool:
        """Execute a single action.

        Args:
            message: Action message from Redpanda

        Returns:
            True if executed successfully, False otherwise
        """
        try:
            # Extract action data
            action_id = message.get("action_id")
            creator_id = message.get("creator_id")
            consumer_id = message.get("consumer_id")
            action_type = message.get("action_type")
            channel = message.get("channel")
            payload = message.get("payload", {})

            if not all([action_id, creator_id, consumer_id, action_type, channel]):
                logger.error(f"Missing required fields in action: {message}")
                return False

            logger.info(
                f"Executing action: {action_type} on {channel} "
                f"(action_id: {str(action_id)[:8]}..., "
                f"consumer: {str(consumer_id)[:8]}...)"
            )

            # Process with orchestrator
            with Session(engine) as session:
                orchestrator = Orchestrator(session)

                try:
                    # Execute the action
                    result = orchestrator.execute_pending_actions()

                    logger.info(
                        f"Executed {result} actions (including action {str(action_id)[:8]}...)"
                    )
                    self.executed_count += 1
                    return True

                except Exception as e:
                    logger.error(f"Failed to execute action: {str(e)}", exc_info=True)
                    self.error_count += 1
                    return False

        except Exception as e:
            logger.error(f"Unexpected error executing action: {str(e)}", exc_info=True)
            self.error_count += 1
            return False

    async def run(self):
        """Main worker loop."""
        logger.info("🚀 Starting Redpanda Action Executor Worker")
        logger.info(f"Bootstrap servers: {self.bootstrap_servers}")
        logger.info("Listening on topic: actions")
        logger.info("Consumer group: action-executors")

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

                        self.execute_action(message)

                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}", exc_info=True)

                # Log stats every 100 messages
                if self.executed_count % 100 == 0 and self.executed_count > 0:
                    logger.info(
                        f"📊 Stats: Executed={self.executed_count}, "
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
                f"Worker stopped. Total: Executed={self.executed_count}, "
                f"Errors={self.error_count}"
            )


def main():
    """Main entry point."""
    bootstrap_servers = "redpanda:9092"

    worker = ActionExecutorWorker(bootstrap_servers)

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
