"""
SuprSend Client - Transactional email and notification service

SuprSend is a unified API for multi-channel notifications (email, SMS, WhatsApp, push).
This client handles email sending via SuprSend workflows.

Docs: https://docs.suprsend.com/
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid

logger = logging.getLogger(__name__)


class SuprSendClient:
    """
    Client for SuprSend API

    Handles transactional emails via SuprSend workflows.
    Uses workflow API for better deliverability and tracking.
    """

    def __init__(
        self,
        workspace_key: str,
        workspace_secret: str,
        is_staging: bool = False
    ):
        """
        Initialize SuprSend client

        Args:
            workspace_key: SuprSend workspace key
            workspace_secret: SuprSend workspace secret
            is_staging: Whether to use staging environment
        """
        try:
            from suprsend import Suprsend, Workflow

            self.workspace_key = workspace_key
            self.workspace_secret = workspace_secret
            self.is_staging = is_staging
            self.client = Suprsend(workspace_key, workspace_secret)
            self.Workflow = Workflow

            logger.info(
                f"SuprSend client initialized",
                extra={
                    "environment": "staging" if is_staging else "production",
                    "has_credentials": bool(workspace_key and workspace_secret)
                }
            )

        except ImportError:
            logger.error("suprsend package not installed. Install with: pip install suprsend")
            raise

    def send_transactional_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = "Creator Agents Platform",
        html: bool = True,
        idempotency_key: Optional[str] = None,
        workflow_name: str = "developer-testing-aiagents-aiagents-transactional",
        template_slug: str = "aiagents-transactional",
        notification_category: str = "transactional"
    ) -> Dict[str, Any]:
        """
        Send transactional email via SuprSend workflow

        Args:
            to_email: Recipient email address
            subject: Email subject line
            body: Email body (HTML or plain text)
            from_email: Optional sender email (uses default if not provided)
            from_name: Optional sender name
            html: Whether body is HTML (default: True)
            idempotency_key: Optional unique key for deduplication
            workflow_name: SuprSend workflow name (default: developer-testing-aiagents-aiagents-transactional)
            template_slug: SuprSend template slug (default: aiagents-transactional)
            notification_category: Notification category (default: transactional)

        Returns:
            dict: Response with message_id, status, etc.

        Raises:
            Exception: If email sending fails
        """
        try:
            # Generate idempotency key if not provided
            if idempotency_key is None:
                idempotency_key = f"email_{uuid.uuid4()}"

            # Generate unique distinct_id for recipient
            distinct_id = f"email_{to_email.replace('@', '_at_').replace('.', '_')}"

            # Prepare workflow data using new SDK format
            workflow_data = {
                "name": workflow_name,
                "template": template_slug,
                "notification_category": notification_category,
                "users": [
                    {
                        "distinct_id": distinct_id,
                        "$email": [to_email]
                    }
                ],
                "data": {
                    "subject": subject,
                    "body": body,
                    "from_email": from_email or "noreply@creatoragents.ai",
                    "from_name": from_name,
                    "is_html": html
                }
            }

            # Create workflow instance
            workflow = self.Workflow(
                body=workflow_data,
                idempotency_key=idempotency_key
            )

            # Trigger workflow
            response = self.client.workflows.trigger(workflow)

            logger.info(
                f"Email sent via SuprSend",
                extra={
                    "to": to_email,
                    "subject": subject[:50],
                    "idempotency_key": idempotency_key,
                    "response_status": response.get("status")
                }
            )

            return {
                "success": True,
                "message_id": idempotency_key,
                "status": response.get("status", "sent"),
                "to": to_email,
                "subject": subject,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "response": response
            }

        except Exception as e:
            logger.error(
                f"SuprSend email failed: {e}",
                extra={"to": to_email, "subject": subject[:50]},
                exc_info=True
            )
            raise

    def send_workflow(
        self,
        workflow_name: str,
        recipient_email: str,
        data: Dict[str, Any],
        template_slug: str,
        notification_category: str = "transactional",
        idempotency_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send email using custom SuprSend workflow template

        Args:
            workflow_name: SuprSend workflow name
            recipient_email: Recipient email
            data: Data to pass to workflow template
            template_slug: SuprSend template slug
            notification_category: Notification category (default: transactional)
            idempotency_key: Optional unique key for deduplication

        Returns:
            dict: Response with message_id, status, etc.
        """
        try:
            if idempotency_key is None:
                idempotency_key = f"workflow_{workflow_name}_{uuid.uuid4()}"

            # Generate unique distinct_id for recipient
            distinct_id = f"email_{recipient_email.replace('@', '_at_').replace('.', '_')}"

            workflow_data = {
                "name": workflow_name,
                "template": template_slug,
                "notification_category": notification_category,
                "users": [
                    {
                        "distinct_id": distinct_id,
                        "$email": [recipient_email]
                    }
                ],
                "data": data
            }

            workflow = self.Workflow(
                body=workflow_data,
                idempotency_key=idempotency_key
            )

            response = self.client.workflows.trigger(workflow)

            logger.info(
                f"Workflow '{workflow_name}' sent via SuprSend",
                extra={
                    "workflow": workflow_name,
                    "to": recipient_email,
                    "idempotency_key": idempotency_key
                }
            )

            return {
                "success": True,
                "message_id": idempotency_key,
                "workflow": workflow_name,
                "status": response.get("status", "sent"),
                "response": response
            }

        except Exception as e:
            logger.error(
                f"SuprSend workflow '{workflow_name}' failed: {e}",
                extra={"workflow": workflow_name, "to": recipient_email},
                exc_info=True
            )
            raise

    def create_user(
        self,
        distinct_id: str,
        email: str,
        phone: Optional[str] = None,
        name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create or update user in SuprSend

        Args:
            distinct_id: Unique user identifier (consumer_id)
            email: User email
            phone: Optional phone number (with country code)
            name: Optional user name

        Returns:
            dict: Response from SuprSend
        """
        try:
            user = self.client.user.get_instance(distinct_id=str(distinct_id))
            user.add_email(email)

            if phone:
                user.add_whatsapp(phone)
                user.add_sms(phone)

            if name:
                user.append("$name", name)

            response = user.save()

            logger.info(
                f"User created/updated in SuprSend",
                extra={
                    "distinct_id": distinct_id,
                    "email": email,
                    "has_phone": bool(phone)
                }
            )

            return response

        except Exception as e:
            logger.error(
                f"SuprSend user creation failed: {e}",
                extra={"distinct_id": distinct_id, "email": email},
                exc_info=True
            )
            raise

    @staticmethod
    def from_settings():
        """
        Create SuprSend client from application settings

        Returns:
            SuprSendClient instance

        Raises:
            ValueError: If credentials not configured
        """
        from app.config import settings

        workspace_key = getattr(settings, "SUPRSEND_WORKSPACE_KEY", None)
        workspace_secret = getattr(settings, "SUPRSEND_WORKSPACE_SECRET", None)
        is_staging = getattr(settings, "IS_STAGING_ENV", False)

        if not workspace_key or not workspace_secret:
            raise ValueError(
                "SuprSend credentials not configured. "
                "Set SUPRSEND_WORKSPACE_KEY and SUPRSEND_WORKSPACE_SECRET environment variables."
            )

        return SuprSendClient(
            workspace_key=workspace_key,
            workspace_secret=workspace_secret,
            is_staging=is_staging
        )
