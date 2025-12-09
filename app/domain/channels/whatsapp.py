"""WhatsApp channel implementation using Twilio."""
import logging
from typing import Any, Dict
from uuid import UUID

from app.domain.channels.base import ChannelTool
from app.infra.external.twilio_client import TwilioClient

logger = logging.getLogger(__name__)


class WhatsAppChannel(ChannelTool):
    """WhatsApp channel using Twilio."""

    def __init__(self, twilio_client: TwilioClient):
        self.twilio_client = twilio_client

    def validate_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate WhatsApp payload."""
        required_fields = ["to_number", "message"]
        return all(field in payload for field in required_fields)

    def execute(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send WhatsApp message via Twilio."""
        if not self.validate_payload(payload):
            raise ValueError("Invalid WhatsApp payload")

        to_number = payload["to_number"]
        message = payload["message"]
        template = payload.get("template")  # Optional template for Business API

        logger.info(
            f"Sending WhatsApp message to {to_number} for creator {creator_id}, consumer {consumer_id}"
        )

        try:
            message_sid = self.twilio_client.send_whatsapp(
                to_number=to_number,
                message=message,
                template=template,
            )

            return {
                "success": True,
                "message_sid": message_sid,
                "provider": "twilio",
            }

        except Exception as e:
            logger.error(f"Failed to send WhatsApp message: {str(e)}")
            raise
