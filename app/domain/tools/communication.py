"""
Communication Tools - Send messages via email, WhatsApp, SMS

These tools integrate with external services (SES, Twilio) to send messages.
"""

import logging
from typing import Optional
from datetime import datetime
from app.domain.tools.base import BaseTool, ToolResult, ToolCategory
from app.domain.tools.registry import get_registry
from app.config import settings

logger = logging.getLogger(__name__)


class SendEmailTool(BaseTool):
    """
    Send email via SuprSend (primary) or AWS SES (fallback)

    Parameters:
    - to: Recipient email address
    - subject: Email subject line
    - body: Email body (plain text or HTML)
    - from_email: Optional sender email (uses default if not provided)
    - from_name: Optional sender name (default: "Creator Agents Platform")
    - html: Whether body is HTML (default: True)
    """

    name = "send_email"
    description = "Send transactional email to a consumer via SuprSend or AWS SES"
    category = ToolCategory.COMMUNICATION
    timeout_seconds = 30
    retry_on_timeout = True
    max_retries = 2

    schema = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "format": "email",
                "description": "Recipient email address"
            },
            "subject": {
                "type": "string",
                "description": "Email subject line"
            },
            "body": {
                "type": "string",
                "description": "Email body content (plain text or HTML)"
            },
            "from_email": {
                "type": "string",
                "format": "email",
                "description": "Sender email address (optional, uses default)"
            },
            "from_name": {
                "type": "string",
                "description": "Sender name (optional, default: Creator Agents Platform)"
            },
            "html": {
                "type": "boolean",
                "description": "Whether body is HTML",
                "default": True
            }
        },
        "required": ["to", "subject", "body"]
    }

    def check_availability(self) -> bool:
        """Check if SuprSend or SES credentials are configured"""
        try:
            # Check if SuprSend is available (preferred)
            has_suprsend_key = bool(getattr(settings, "SUPRSEND_WORKSPACE_KEY", None))
            has_suprsend_secret = bool(getattr(settings, "SUPRSEND_WORKSPACE_SECRET", None))

            # Check if SES is available (fallback)
            has_aws_key = bool(getattr(settings, "AWS_ACCESS_KEY_ID", None))
            has_ses_sender = bool(getattr(settings, "SES_SENDER_EMAIL", None))

            # Available if either SuprSend or SES is configured
            return (has_suprsend_key and has_suprsend_secret) or (has_aws_key and has_ses_sender)
        except Exception:
            return False

    def execute(
        self,
        to: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
        from_name: Optional[str] = "Creator Agents Platform",
        html: bool = True,
        **kwargs
    ) -> ToolResult:
        """
        Execute email sending via SuprSend (primary) or SES (fallback)

        Args:
            to: Recipient email
            subject: Subject line
            body: Email content
            from_email: Optional sender email
            from_name: Optional sender name
            html: Whether body is HTML

        Returns:
            ToolResult with message_id if successful
        """
        start_time = datetime.utcnow()

        try:
            # Try SuprSend first (preferred)
            has_suprsend = bool(
                getattr(settings, "SUPRSEND_WORKSPACE_KEY", None) and
                getattr(settings, "SUPRSEND_WORKSPACE_SECRET", None)
            )

            if has_suprsend:
                try:
                    from app.infra.external.suprsend_client import SuprSendClient

                    # Create SuprSend client
                    suprsend_client = SuprSendClient.from_settings()

                    # Send email
                    response = suprsend_client.send_transactional_email(
                        to_email=to,
                        subject=subject,
                        body=body,
                        from_email=from_email,
                        from_name=from_name,
                        html=html
                    )

                    execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                    logger.info(
                        f"Email sent successfully via SuprSend",
                        extra={
                            "to": to,
                            "subject": subject[:50],
                            "message_id": response["message_id"],
                            "provider": "suprsend",
                            "execution_time_ms": execution_time
                        }
                    )

                    return ToolResult(
                        success=True,
                        data={
                            "message_id": response["message_id"],
                            "to": to,
                            "subject": subject,
                            "sent_at": response["sent_at"],
                            "provider": "suprsend",
                            "status": response.get("status", "sent")
                        },
                        error=None,
                        execution_time_ms=execution_time,
                        tool_name=self.name,
                        timestamp=start_time
                    )

                except Exception as suprsend_error:
                    logger.warning(
                        f"SuprSend failed, falling back to SES: {suprsend_error}",
                        extra={"to": to}
                    )
                    # Fall through to SES fallback

            # Fallback to SES
            from app.infra.external.ses_client import SESClient

            ses_client = SESClient()

            # Use default sender if not provided
            if from_email is None:
                from_email = getattr(settings, "SES_SENDER_EMAIL", "noreply@example.com")

            # Send email
            message_id = ses_client.send_email(
                to_email=to,
                subject=subject,
                body=body,
                from_email=from_email,
                html=html
            )

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.info(
                f"Email sent successfully via SES",
                extra={
                    "to": to,
                    "subject": subject[:50],
                    "message_id": message_id,
                    "provider": "ses",
                    "execution_time_ms": execution_time
                }
            )

            return ToolResult(
                success=True,
                data={
                    "message_id": message_id,
                    "to": to,
                    "subject": subject,
                    "sent_at": start_time.isoformat(),
                    "provider": "ses"
                },
                error=None,
                execution_time_ms=execution_time,
                tool_name=self.name,
                timestamp=start_time
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"Email sending failed (all providers): {e}", exc_info=True)

            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                execution_time_ms=execution_time,
                tool_name=self.name,
                timestamp=start_time
            )


class SendWhatsAppTool(BaseTool):
    """
    Send WhatsApp message via Twilio

    Parameters:
    - to: Recipient phone number (with country code, e.g., +919876543210)
    - message: Message content (text)
    - from_number: Optional Twilio WhatsApp number (uses default if not provided)
    """

    name = "send_whatsapp"
    description = "Send a WhatsApp message to a consumer via Twilio"
    category = ToolCategory.COMMUNICATION
    timeout_seconds = 30
    retry_on_timeout = True
    max_retries = 2

    schema = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient phone number with country code (e.g., +919876543210)"
            },
            "message": {
                "type": "string",
                "description": "Message content (text only, no media yet)"
            },
            "from_number": {
                "type": "string",
                "description": "Twilio WhatsApp number (optional, uses default)"
            }
        },
        "required": ["to", "message"]
    }

    def check_availability(self) -> bool:
        """Check if Twilio credentials are configured"""
        try:
            # settings already imported at module level
            has_account_sid = bool(getattr(settings, "TWILIO_ACCOUNT_SID", None))
            has_auth_token = bool(getattr(settings, "TWILIO_AUTH_TOKEN", None))
            has_whatsapp_from = bool(getattr(settings, "TWILIO_WHATSAPP_FROM", None))
            return has_account_sid and has_auth_token and has_whatsapp_from
        except Exception:
            return False

    def execute(
        self,
        to: str,
        message: str,
        from_number: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Execute WhatsApp message sending

        Args:
            to: Recipient phone number
            message: Message content
            from_number: Optional Twilio WhatsApp number

        Returns:
            ToolResult with message SID if successful
        """
        start_time = datetime.utcnow()

        try:
            # Import Twilio client
            from app.infra.external.twilio_client import TwilioClient
            from app.config import settings

            # settings already imported at module level
            twilio_client = TwilioClient()

            # Use default WhatsApp number if not provided
            if from_number is None:
                from_number = settings.TWILIO_WHATSAPP_FROM

            # Ensure numbers are in WhatsApp format
            if not to.startswith("whatsapp:"):
                to = f"whatsapp:{to}"

            if not from_number.startswith("whatsapp:"):
                from_number = f"whatsapp:{from_number}"

            # Send WhatsApp message
            message_sid = twilio_client.send_message(
                to=to,
                body=message,
                from_=from_number
            )

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.info(
                f"WhatsApp message sent successfully",
                extra={
                    "to": to,
                    "message_preview": message[:50],
                    "message_sid": message_sid,
                    "execution_time_ms": execution_time
                }
            )

            return ToolResult(
                success=True,
                data={
                    "message_sid": message_sid,
                    "to": to,
                    "message_preview": message[:100],
                    "sent_at": start_time.isoformat()
                },
                error=None,
                execution_time_ms=execution_time,
                tool_name=self.name,
                timestamp=start_time
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"WhatsApp sending failed: {e}", exc_info=True)

            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                execution_time_ms=execution_time,
                tool_name=self.name,
                timestamp=start_time
            )


class SendSMSTool(BaseTool):
    """
    Send SMS via Twilio

    Parameters:
    - to: Recipient phone number (with country code)
    - message: Message content (text, max 160 chars recommended)
    - from_number: Optional Twilio phone number (uses default if not provided)
    """

    name = "send_sms"
    description = "Send an SMS to a consumer via Twilio"
    category = ToolCategory.COMMUNICATION
    timeout_seconds = 30
    retry_on_timeout = True
    max_retries = 2

    schema = {
        "type": "object",
        "properties": {
            "to": {
                "type": "string",
                "description": "Recipient phone number with country code (e.g., +919876543210)"
            },
            "message": {
                "type": "string",
                "description": "SMS message content (keep under 160 chars for single SMS)",
                "maxLength": 1600  # Twilio limit
            },
            "from_number": {
                "type": "string",
                "description": "Twilio phone number (optional, uses default)"
            }
        },
        "required": ["to", "message"]
    }

    def check_availability(self) -> bool:
        """Check if Twilio credentials and SMS number are configured"""
        try:
            # settings already imported at module level
            has_account_sid = bool(getattr(settings, "TWILIO_ACCOUNT_SID", None))
            has_auth_token = bool(getattr(settings, "TWILIO_AUTH_TOKEN", None))
            has_phone_from = bool(getattr(settings, "TWILIO_PHONE_FROM", None))
            return has_account_sid and has_auth_token and has_phone_from
        except Exception:
            return False

    def execute(
        self,
        to: str,
        message: str,
        from_number: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Execute SMS sending

        Args:
            to: Recipient phone number
            message: SMS content
            from_number: Optional Twilio phone number

        Returns:
            ToolResult with message SID if successful
        """
        start_time = datetime.utcnow()

        try:
            # Import Twilio client
            from app.infra.external.twilio_client import TwilioClient
            from app.config import settings

            # settings already imported at module level
            twilio_client = TwilioClient()

            # Use default phone number if not provided
            if from_number is None:
                from_number = getattr(settings, "TWILIO_PHONE_FROM", None)

            if from_number is None:
                raise ValueError("No Twilio SMS number configured")

            # Send SMS
            message_sid = twilio_client.send_message(
                to=to,
                body=message,
                from_=from_number
            )

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            logger.info(
                f"SMS sent successfully",
                extra={
                    "to": to,
                    "message_preview": message[:50],
                    "message_sid": message_sid,
                    "execution_time_ms": execution_time
                }
            )

            return ToolResult(
                success=True,
                data={
                    "message_sid": message_sid,
                    "to": to,
                    "message_preview": message[:100],
                    "sent_at": start_time.isoformat(),
                    "sms_count": (len(message) // 160) + 1  # Estimate SMS count
                },
                error=None,
                execution_time_ms=execution_time,
                tool_name=self.name,
                timestamp=start_time
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"SMS sending failed: {e}", exc_info=True)

            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                execution_time_ms=execution_time,
                tool_name=self.name,
                timestamp=start_time
            )


class EscalateToHumanTool(BaseTool):
    """
    Escalate consumer conversation to human intervention

    Parameters:
    - creator_id: Creator UUID
    - consumer_id: Consumer UUID
    - workflow_execution_id: Optional workflow execution UUID
    - agent_id: Agent UUID that is escalating
    - reason: Escalation reason (complex_question, complaint, etc.)
    - context: Full context at time of escalation
    - consumer_message: Optional consumer message that triggered escalation
    """

    name = "escalate_to_human"
    description = "Escalate consumer to human when question/issue is too complex for agent"
    category = ToolCategory.COMMUNICATION
    timeout_seconds = 15
    retry_on_timeout = False
    max_retries = 0

    schema = {
        "type": "object",
        "properties": {
            "creator_id": {
                "type": "string",
                "format": "uuid",
                "description": "Creator UUID"
            },
            "consumer_id": {
                "type": "string",
                "format": "uuid",
                "description": "Consumer UUID"
            },
            "workflow_execution_id": {
                "type": "string",
                "format": "uuid",
                "description": "Optional workflow execution UUID"
            },
            "agent_id": {
                "type": "string",
                "format": "uuid",
                "description": "Agent UUID that is escalating"
            },
            "reason": {
                "type": "string",
                "description": "Escalation reason: complex_question, complaint, negotiation, etc."
            },
            "context": {
                "type": "object",
                "description": "Full context at time of escalation"
            },
            "consumer_message": {
                "type": "string",
                "description": "Optional consumer message that triggered escalation"
            }
        },
        "required": ["creator_id", "consumer_id", "agent_id", "reason", "context"]
    }

    def check_availability(self) -> bool:
        """Check if escalation is available (always available)."""
        return True

    def execute(self, **kwargs) -> ToolResult:
        """
        Execute escalation to human.

        This creates a ConversationThread, pauses the workflow for this consumer,
        and sends notification to dashboard.

        Returns:
            ToolResult with thread_id and status
        """
        from uuid import UUID
        from sqlmodel import Session
        from app.infra.db.connection import get_session
        from app.domain.conversations.models import ConversationThread, Message, SenderType
        from app.domain.workflow.service import WorkflowService

        start_time = datetime.utcnow()

        try:
            # Extract parameters
            creator_id = UUID(kwargs["creator_id"])
            consumer_id = UUID(kwargs["consumer_id"])
            agent_id = UUID(kwargs["agent_id"])
            reason = kwargs["reason"]
            context = kwargs["context"]
            workflow_execution_id = kwargs.get("workflow_execution_id")
            consumer_message = kwargs.get("consumer_message")

            if workflow_execution_id:
                workflow_execution_id = UUID(workflow_execution_id)

            logger.info(
                f"Escalating consumer {consumer_id} to human",
                extra={
                    "creator_id": str(creator_id),
                    "consumer_id": str(consumer_id),
                    "reason": reason,
                }
            )

            # Get database session
            session = next(get_session())

            try:
                # Create ConversationThread
                thread = ConversationThread(
                    creator_id=creator_id,
                    consumer_id=consumer_id,
                    workflow_execution_id=workflow_execution_id,
                    agent_id=agent_id,
                    status="waiting_human",
                    escalation_reason=reason,
                    context=context,
                )

                session.add(thread)
                session.commit()
                session.refresh(thread)

                # If consumer message provided, add it as first message
                if consumer_message:
                    message = Message(
                        thread_id=thread.id,
                        sender_type=SenderType.CONSUMER,
                        sender_id=consumer_id,
                        content=consumer_message,
                        metadata={
                            "is_escalation_trigger": True
                        }
                    )
                    session.add(message)

                # Add agent's escalation note
                agent_note = Message(
                    thread_id=thread.id,
                    sender_type=SenderType.AGENT,
                    sender_id=agent_id,
                    content=f"Escalated to human: {reason}",
                    metadata={
                        "escalation_context": context
                    }
                )
                session.add(agent_note)
                session.commit()

                # Pause workflow if execution_id provided
                if workflow_execution_id:
                    workflow_service = WorkflowService(session)
                    workflow_service.pause_workflow(
                        workflow_execution_id,
                        reason=f"Escalated to human: {reason}"
                    )

                # TODO: Send notification to dashboard (webhook/email)
                # This would integrate with the creator dashboard to notify humans

                session.close()

                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                logger.info(
                    f"Escalation successful",
                    extra={
                        "thread_id": str(thread.id),
                        "consumer_id": str(consumer_id),
                        "reason": reason,
                    }
                )

                return ToolResult(
                    success=True,
                    data={
                        "thread_id": str(thread.id),
                        "status": "escalated",
                        "workflow_paused": workflow_execution_id is not None,
                        "messages_created": 2 if consumer_message else 1,
                        "next_steps": "Human will be notified via dashboard",
                    },
                    error=None,
                    execution_time_ms=execution_time,
                    tool_name=self.name,
                    timestamp=start_time
                )

            finally:
                session.close()

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"Escalation failed: {e}", exc_info=True)

            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                execution_time_ms=execution_time,
                tool_name=self.name,
                timestamp=start_time
            )


# Register tools on module import
_registry = get_registry()
_registry.register_tool(SendEmailTool())
_registry.register_tool(SendWhatsAppTool())
_registry.register_tool(SendSMSTool())
_registry.register_tool(EscalateToHumanTool())

logger.info("Communication tools registered")
