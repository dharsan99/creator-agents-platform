"""Email channel implementation using AWS SES."""
import logging
from typing import Any, Dict
from uuid import UUID

from app.domain.channels.base import ChannelTool
from app.infra.external.ses_client import SESClient

logger = logging.getLogger(__name__)


class EmailChannel(ChannelTool):
    """Email channel using AWS SES."""

    def __init__(self, ses_client: SESClient):
        self.ses_client = ses_client

    def validate_payload(self, payload: Dict[str, Any]) -> bool:
        """Validate email payload."""
        required_fields = ["to_email", "subject", "body"]
        return all(field in payload for field in required_fields)

    def execute(
        self,
        creator_id: UUID,
        consumer_id: UUID,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send email via SES."""
        if not self.validate_payload(payload):
            raise ValueError("Invalid email payload")

        to_email = payload["to_email"]
        subject = payload["subject"]
        body = payload["body"]
        from_email = payload.get("from_email")  # Optional, uses default if not provided

        logger.info(
            f"Sending email to {to_email} for creator {creator_id}, consumer {consumer_id}"
        )

        try:
            message_id = self.ses_client.send_email(
                to_email=to_email,
                subject=subject,
                body_html=body,
                from_email=from_email,
            )

            return {
                "success": True,
                "message_id": message_id,
                "provider": "ses",
            }

        except Exception as e:
            logger.error(f"Failed to send email: {str(e)}")
            raise
