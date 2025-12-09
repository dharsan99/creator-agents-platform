"""Twilio client for WhatsApp messaging."""
import logging
from typing import Optional

from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

from app.config import settings

logger = logging.getLogger(__name__)


class TwilioClient:
    """Client for Twilio WhatsApp API."""

    def __init__(self):
        if not settings.twilio_account_sid or not settings.twilio_auth_token:
            logger.warning("Twilio credentials not configured")
            self.client = None
        else:
            self.client = Client(
                settings.twilio_account_sid,
                settings.twilio_auth_token,
            )
        self.from_whatsapp = settings.twilio_whatsapp_from

    def send_whatsapp(
        self,
        to_number: str,
        message: str,
        template: Optional[str] = None,
    ) -> str:
        """Send a WhatsApp message via Twilio.

        Args:
            to_number: Recipient WhatsApp number (format: whatsapp:+1234567890)
            message: Message content
            template: Optional template name for WhatsApp Business API

        Returns:
            Message SID from Twilio

        Raises:
            TwilioRestException if sending fails
        """
        if not self.client:
            raise ValueError("Twilio client not configured")

        if not self.from_whatsapp:
            raise ValueError("Twilio WhatsApp sender number not configured")

        # Ensure number is in WhatsApp format
        if not to_number.startswith("whatsapp:"):
            to_number = f"whatsapp:{to_number}"

        try:
            message_obj = self.client.messages.create(
                from_=self.from_whatsapp,
                to=to_number,
                body=message,
            )

            logger.info(
                f"WhatsApp message sent successfully to {to_number}, SID: {message_obj.sid}"
            )
            return message_obj.sid

        except TwilioRestException as e:
            logger.error(f"Failed to send WhatsApp message to {to_number}: {e.msg}")
            raise
