"""Redpanda channel for publishing events."""
import logging
from typing import Any, Dict
from uuid import UUID

from app.domain.channels.base import ChannelTool
from app.infra.events.producer import RedpandaProducer

logger = logging.getLogger(__name__)


class RedpandaChannel(ChannelTool):
    """Channel for publishing events to Redpanda topics."""

    def __init__(self, producer: RedpandaProducer):
        """Initialize Redpanda channel.

        Args:
            producer: RedpandaProducer instance
        """
        self.producer = producer

    def validate_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate Redpanda payload has required fields.

        Args:
            payload: Action payload

        Returns:
            True if valid, False otherwise
        """
        required_fields = ["topic", "value"]

        if not all(field in payload for field in required_fields):
            logger.error(f"Missing required fields in Redpanda payload: {required_fields}")
            return False

        return True

    def execute(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Publish event to Redpanda topic.

        Args:
            creator_id: ID of the creator
            consumer_id: ID of the consumer
            payload: Action payload containing:
                - topic: Topic name to publish to
                - key: Optional message key (defaults to consumer_id)
                - value: Message value (JSON string)

        Returns:
            Result dictionary with execution details

        Raises:
            ValueError if payload is invalid
            Exception if publish fails
        """
        if not self.validate_payload(payload):
            raise ValueError("Invalid Redpanda payload")

        topic = payload["topic"]
        key = payload.get("key", str(consumer_id))
        value = payload["value"]

        logger.info(
            f"Publishing to Redpanda topic: {topic}",
            extra={
                "topic": topic,
                "key": key[:8] if key else "None",
                "consumer_id": str(consumer_id),
            }
        )

        try:
            # Publish to Redpanda
            success = self.producer.produce(
                topic=topic,
                key=key,
                value=value
            )

            if not success:
                raise Exception("Failed to publish to Redpanda")

            # Flush to ensure message is sent
            remaining = self.producer.flush(timeout_ms=5000)

            if remaining > 0:
                logger.warning(f"{remaining} messages still pending after flush")

            logger.info(
                f"Successfully published to {topic}",
                extra={
                    "topic": topic,
                    "consumer_id": str(consumer_id),
                }
            )

            return {
                "status": "success",
                "topic": topic,
                "key": key,
                "timestamp": str(logger.makeRecord(
                    name=__name__,
                    level=logging.INFO,
                    fn="",
                    lno=0,
                    msg="",
                    args=(),
                    exc_info=None
                ).created)
            }

        except Exception as e:
            logger.error(
                f"Failed to publish to Redpanda: {str(e)}",
                exc_info=True,
                extra={
                    "topic": topic,
                    "consumer_id": str(consumer_id),
                }
            )
            raise
