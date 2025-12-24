"""Redpanda event producer for event streaming."""
import json
import logging
from typing import Optional
from uuid import UUID

from confluent_kafka import Producer, KafkaError

logger = logging.getLogger(__name__)


class RedpandaProducer:
    """Produces events to Redpanda topics."""

    def __init__(self, bootstrap_servers: str = "redpanda:9092"):
        """Initialize Redpanda producer.

        Args:
            bootstrap_servers: Comma-separated list of Redpanda brokers
        """
        self.bootstrap_servers = bootstrap_servers

        # Resolve advertised listener issue for local development
        # If using localhost, also resolve shared-redpanda to localhost
        broker_address_family = "v4"
        if "localhost" in bootstrap_servers or "127.0.0.1" in bootstrap_servers:
            # For local development, use IP resolution
            broker_address_family = "v4"

        self.producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "client.id": "creator-agents-producer",
                "acks": "all",  # Wait for all replicas
                "retries": 3,
                "retry.backoff.ms": 100,
                "broker.address.family": broker_address_family,
                # Increase timeout for local development
                "socket.timeout.ms": 60000,
                "request.timeout.ms": 60000,
            }
        )

        logger.info(f"Initialized Redpanda producer: {bootstrap_servers}")

    def _delivery_report(self, err, msg):
        """Delivery report callback for produced messages."""
        if err is not None:
            logger.error(f"Message delivery failed: {err} [Topic: {msg.topic()}]")
        else:
            logger.debug(
                f"Message delivered to {msg.topic()} "
                f"[Partition: {msg.partition()}, Offset: {msg.offset()}]"
            )

    def publish_event(
        self,
        topic: str,
        creator_id: UUID,
        consumer_id: UUID,
        event_type: str,
        payload: dict,
        event_id: Optional[UUID] = None,
        idempotency_key: Optional[str] = None,
    ) -> bool:
        """Publish event to Redpanda topic.

        Args:
            topic: Topic name (e.g., 'events')
            creator_id: Creator UUID
            consumer_id: Consumer UUID
            event_type: Type of event
            payload: Event payload
            event_id: Optional event ID
            idempotency_key: Optional idempotency key for deduplication

        Returns:
            True if published successfully, False otherwise
        """
        try:
            message = {
                "event_id": str(event_id) if event_id else None,
                "creator_id": str(creator_id),
                "consumer_id": str(consumer_id),
                "event_type": event_type,
                "payload": payload,
                "idempotency_key": idempotency_key,
            }

            # Use idempotency_key or event_id as partition key for ordering
            key = (idempotency_key or str(event_id)).encode("utf-8") if idempotency_key or event_id else None

            self.producer.produce(
                topic,
                key=key,
                value=json.dumps(message).encode("utf-8"),
                callback=self._delivery_report,
            )

            # Don't wait for all messages, let batch send
            self.producer.poll(0)

            logger.info(
                f"Published event to {topic}: "
                f"{event_type} (consumer: {str(consumer_id)[:8]}...)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish event to {topic}: {str(e)}")
            return False

    def publish_agent_invocation(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        event_id: UUID,
        invocation_id: UUID,
        agent_id: UUID,
        context: dict,
    ) -> bool:
        """Publish agent invocation event.

        Args:
            creator_id: Creator UUID
            consumer_id: Consumer UUID
            event_id: Event that triggered invocation
            invocation_id: Invocation UUID
            agent_id: Agent UUID
            context: Execution context

        Returns:
            True if published successfully, False otherwise
        """
        try:
            message = {
                "invocation_id": str(invocation_id),
                "event_id": str(event_id),
                "creator_id": str(creator_id),
                "consumer_id": str(consumer_id),
                "agent_id": str(agent_id),
                "context": context,
            }

            self.producer.produce(
                "agent-invocations",
                key=str(invocation_id).encode("utf-8"),
                value=json.dumps(message).encode("utf-8"),
                callback=self._delivery_report,
            )

            self.producer.poll(0)

            logger.info(
                f"Published agent invocation: {str(invocation_id)[:8]}... "
                f"(agent: {str(agent_id)[:8]}...)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish agent invocation: {str(e)}")
            return False

    def publish_action(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        invocation_id: UUID,
        action_id: UUID,
        action_type: str,
        channel: str,
        payload: dict,
    ) -> bool:
        """Publish action execution event.

        Args:
            creator_id: Creator UUID
            consumer_id: Consumer UUID
            invocation_id: Parent invocation UUID
            action_id: Action UUID
            action_type: Type of action
            channel: Execution channel (email, whatsapp, call, payment)
            payload: Action payload

        Returns:
            True if published successfully, False otherwise
        """
        try:
            message = {
                "action_id": str(action_id),
                "invocation_id": str(invocation_id),
                "creator_id": str(creator_id),
                "consumer_id": str(consumer_id),
                "action_type": action_type,
                "channel": channel,
                "payload": payload,
            }

            self.producer.produce(
                "actions",
                key=str(action_id).encode("utf-8"),
                value=json.dumps(message).encode("utf-8"),
                callback=self._delivery_report,
            )

            self.producer.poll(0)

            logger.info(
                f"Published action: {str(action_id)[:8]}... "
                f"(type: {action_type}, channel: {channel})"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to publish action: {str(e)}")
            return False

    def produce(self, topic: str, key: str, value: str) -> bool:
        """Generic produce method for publishing to any topic.

        Args:
            topic: Topic name
            key: Message key (for partitioning)
            value: Message value (JSON string)

        Returns:
            True if published successfully, False otherwise
        """
        try:
            self.producer.produce(
                topic,
                key=key.encode("utf-8") if key else None,
                value=value.encode("utf-8") if isinstance(value, str) else value,
                callback=self._delivery_report,
            )

            self.producer.poll(0)

            logger.info(f"Published message to {topic} with key {key[:8] if key else 'None'}...")
            return True

        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {str(e)}")
            return False

    def flush(self, timeout_ms: int = 5000) -> int:
        """Flush pending messages to Redpanda.

        Args:
            timeout_ms: Timeout in milliseconds

        Returns:
            Number of messages still pending after flush
        """
        remaining = self.producer.flush(timeout_ms)
        if remaining == 0:
            logger.info("All messages flushed successfully")
        else:
            logger.warning(f"{remaining} messages still in queue after flush")
        return remaining

    def close(self):
        """Close producer and flush all messages."""
        self.flush()
        self.producer = None
        logger.info("Redpanda producer closed")


# Global producer instance
_producer: Optional[RedpandaProducer] = None


def get_producer(bootstrap_servers: str = "redpanda:9092") -> RedpandaProducer:
    """Get or create global Redpanda producer instance.

    Args:
        bootstrap_servers: Comma-separated list of Redpanda brokers

    Returns:
        RedpandaProducer instance
    """
    global _producer
    if _producer is None:
        _producer = RedpandaProducer(bootstrap_servers)
    return _producer


def close_producer():
    """Close global producer instance."""
    global _producer
    if _producer is not None:
        _producer.close()
        _producer = None
