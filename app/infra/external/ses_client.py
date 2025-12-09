"""AWS SES client for sending emails."""
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class SESClient:
    """Client for AWS Simple Email Service."""

    def __init__(self):
        self.client = boto3.client(
            "ses",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        self.default_from_email = settings.ses_sender_email

    def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> str:
        """Send an email via SES.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body_html: HTML body content
            body_text: Plain text body (optional)
            from_email: Sender email (optional, uses default if not provided)

        Returns:
            Message ID from SES

        Raises:
            ClientError if sending fails
        """
        sender = from_email or self.default_from_email
        if not sender:
            raise ValueError("No sender email configured")

        message = {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": body_html, "Charset": "UTF-8"},
            },
        }

        if body_text:
            message["Body"]["Text"] = {"Data": body_text, "Charset": "UTF-8"}

        try:
            response = self.client.send_email(
                Source=sender,
                Destination={"ToAddresses": [to_email]},
                Message=message,
            )
            message_id = response["MessageId"]
            logger.info(f"Email sent successfully to {to_email}, MessageId: {message_id}")
            return message_id

        except ClientError as e:
            logger.error(f"Failed to send email to {to_email}: {e.response['Error']['Message']}")
            raise
