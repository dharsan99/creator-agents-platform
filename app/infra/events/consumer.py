"""Redpanda event consumer for streaming event processing."""
import json
import logging
from typing import Callable, List, Optional
from uuid import UUID

from confluent_kafka import Consumer, KafkaError

logger = logging.getLogger(__name__)


class RedpandaConsumer:
    """Consumes events from Redpanda topics."""

    def __init__(
        self,
        topics: List[str],
        group_id: str,
        bootstrap_servers: str = "redpanda:9092",
        auto_offset_reset: str = "earliest",
    ):
        """Initialize Redpanda consumer.

        Args:
            topics: List of topic names to subscribe to
            group_id: Consumer group ID
            bootstrap_servers: Comma-separated list of Redpanda brokers
            auto_offset_reset: Where to start reading ('earliest' or 'latest')
        """
        self.topics = topics
        self.group_id = group_id
        self.bootstrap_servers = bootstrap_servers

        self.consumer = Consumer(
            {
                "bootstrap.servers": bootstrap_servers,
                "group.id": group_id,
                "auto.offset.reset": auto_offset_reset,
                "enable.auto.commit": True,
                "session.timeout.ms": 6000,
                "max.poll.interval.ms": 300000,
            }
        )

        self.consumer.subscribe(topics)
        logger.info(
            f"Initialized Redpanda consumer: group={group_id}, topics={topics}, "
            f"servers={bootstrap_servers}"
        )

    def consume(
        self,
        timeout_ms: int = 1000,
        max_messages: int = 100,
    ) -> List[dict]:
        """Consume messages from subscribed topics.

        Args:
            timeout_ms: Timeout in milliseconds
            max_messages: Maximum number of messages to consume

        Returns:
            List of parsed message dictionaries
        """
        messages = []

        try:
            while len(messages) < max_messages:
                msg = self.consumer.poll(timeout_ms)

                if msg is None:
                    break

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        logger.debug("Reached end of partition")
                    else:
                        logger.error(f"Consumer error: {msg.error()}")
                    break

                try:
                    value = json.loads(msg.value().decode("utf-8"))
                    value["_metadata"] = {
                        "topic": msg.topic(),
                        "partition": msg.partition(),
                        "offset": msg.offset(),
                        "timestamp": msg.timestamp(),
                    }
                    messages.append(value)
                    logger.debug(
                        f"Consumed message from {msg.topic()} "
                        f"[Partition: {msg.partition()}, Offset: {msg.offset()}]"
                    )
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {e}")

        except Exception as e:
            logger.error(f"Error consuming messages: {str(e)}")

        return messages

    def consume_single(self, timeout_ms: int = 1000) -> Optional[dict]:
        """Consume a single message from subscribed topics.

        Args:
            timeout_ms: Timeout in milliseconds

        Returns:
            Parsed message dictionary or None if no message
        """
        try:
            msg = self.consumer.poll(timeout_ms)

            if msg is None:
                return None

            if msg.error():
                logger.error(f"Consumer error: {msg.error()}")
                return None

            value = json.loads(msg.value().decode("utf-8"))
            value["_metadata"] = {
                "topic": msg.topic(),
                "partition": msg.partition(),
                "offset": msg.offset(),
                "timestamp": msg.timestamp(),
            }
            return value

        except Exception as e:
            logger.error(f"Error consuming message: {str(e)}")
            return None

    def commit(self):
        """Commit current offsets to Kafka."""
        try:
            self.consumer.commit(asynchronous=False)
            logger.debug("Committed offsets")
        except Exception as e:
            logger.error(f"Error committing offsets: {str(e)}")

    def close(self):
        """Close consumer and commit offsets."""
        try:
            self.consumer.close()
            logger.info("Redpanda consumer closed")
        except Exception as e:
            logger.error(f"Error closing consumer: {str(e)}")


class EventConsumerHandler:
    """Handler for consuming and processing events from Redpanda."""

    def __init__(
        self,
        topics: List[str],
        group_id: str,
        bootstrap_servers: str = "redpanda:9092",
        auto_offset_reset: str = "earliest",
    ):
        """Initialize event consumer handler.

        Args:
            topics: List of topic names
            group_id: Consumer group ID
            bootstrap_servers: Redpanda bootstrap servers
            auto_offset_reset: Offset reset strategy
        """
        self.consumer = RedpandaConsumer(
            topics, group_id, bootstrap_servers, auto_offset_reset
        )
        self.handlers: dict[str, Callable] = {}

    def register_handler(self, topic: str, handler: Callable):
        """Register a handler for a specific topic.

        Args:
            topic: Topic name
            handler: Callable that processes messages from this topic
        """
        self.handlers[topic] = handler
        logger.info(f"Registered handler for topic: {topic}")

    async def process_messages(
        self,
        timeout_ms: int = 1000,
        max_batch_size: int = 100,
    ):
        """Process messages from all subscribed topics.

        Args:
            timeout_ms: Timeout per consume call
            max_batch_size: Maximum messages per batch
        """
        messages = self.consumer.consume(timeout_ms, max_batch_size)

        for message in messages:
            topic = message.get("_metadata", {}).get("topic")

            if topic and topic in self.handlers:
                try:
                    handler = self.handlers[topic]
                    # Support both sync and async handlers
                    import inspect
                    if inspect.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)

                    logger.debug(f"Successfully processed message from {topic}")
                except Exception as e:
                    logger.error(f"Error processing message from {topic}: {str(e)}")

    def close(self):
        """Close the consumer."""
        self.consumer.close()


# Topic definitions
TOPICS = {
    "events": {
        "name": "events",
        "partitions": 3,
        "replication_factor": 1,
        "description": "All consumer events (page_view, booking, etc.)",
    },
    "agent-invocations": {
        "name": "agent-invocations",
        "partitions": 3,
        "replication_factor": 1,
        "description": "Agent execution invocations",
    },
    "actions": {
        "name": "actions",
        "partitions": 3,
        "replication_factor": 1,
        "description": "Planned actions for execution",
    },
    "dlq-agents": {
        "name": "dlq-agents",
        "partitions": 1,
        "replication_factor": 1,
        "description": "Dead letter queue for agent invocation failures",
    },
    "dlq-actions": {
        "name": "dlq-actions",
        "partitions": 1,
        "replication_factor": 1,
        "description": "Dead letter queue for action execution failures",
    },
}
