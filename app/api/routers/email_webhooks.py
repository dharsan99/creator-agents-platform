"""
Email Webhook Endpoints

Receives email status updates from email-services mock or SuprSend webhooks
and processes them to update consumer context and trigger agent actions.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlmodel import Session, select
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
import logging

from app.infra.db.connection import get_session
from app.infra.db.models import Consumer
from app.domain.context.service import ConsumerContextService
from app.domain.events.service import EventService
from app.domain.types import EventType, EventSource
from app.domain.schemas import EventCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/email", tags=["Email Webhooks"])


class EmailStatusWebhook(BaseModel):
    """Email status update from email-services or SuprSend"""

    # Email identification
    distinct_id: Optional[str] = None
    recipient_email: Optional[str] = None
    message_id: Optional[str] = None

    # Status information
    status: str  # delivered, unread, read, replied, click_cta, booking_click, booking_done
    previous_status: Optional[str] = None

    # Email metadata
    subject: Optional[str] = None
    body: Optional[str] = None  # Email body content
    from_email: Optional[str] = None
    template_name: Optional[str] = None
    workflow_name: Optional[str] = None

    # Timing
    timestamp: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    cta_clicked_at: Optional[datetime] = None
    booking_clicked_at: Optional[datetime] = None
    booking_completed_at: Optional[datetime] = None

    # Additional data
    simulated: bool = False
    raw_data: Optional[Dict[str, Any]] = None


class SuprSendWebhook(BaseModel):
    """SuprSend native webhook format"""

    event: str  # $notification_delivered, $notification_opened, $notification_clicked, etc.
    env: str
    tenant_id: Optional[str] = None

    # User data
    distinct_id: str

    # Event data
    body: Dict[str, Any]

    # Timestamps
    created_on: str  # ISO format


@router.post("/status", response_model=Dict[str, Any])
async def receive_email_status(
    webhook: EmailStatusWebhook,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    Receive email status updates from email-services mock

    Processes status updates and:
    1. Creates/updates events in the system
    2. Updates consumer context with email engagement
    3. Triggers follow-up agents based on engagement
    """
    logger.info(
        f"Received email status webhook: status={webhook.status}, recipient={webhook.recipient_email}, distinct_id={webhook.distinct_id}"
    )

    try:
        # Initialize services
        event_service = EventService(session)
        context_service = ConsumerContextService(session)

        # Resolve consumer_id and creator_id
        consumer_id = None
        creator_id = None
        consumer = None

        # Strategy 1: Try to parse distinct_id as UUID (consumer_id)
        if webhook.distinct_id:
            try:
                consumer_id = UUID(webhook.distinct_id)
                consumer = session.get(Consumer, consumer_id)
                if consumer:
                    creator_id = consumer.creator_id
                    logger.info(f"✅ Resolved consumer {consumer_id} -> creator {creator_id} via distinct_id")
                else:
                    logger.warning(f"⚠️ Consumer not found: {consumer_id}")
                    consumer_id = None
            except ValueError:
                # Not a UUID, try other strategies
                pass

        # Strategy 2: If distinct_id is email-like format
        if not consumer_id and webhook.distinct_id and webhook.distinct_id.startswith("email_"):
            email_part = webhook.distinct_id.replace("email_", "").replace("_at_", "@").replace("_", ".")
            statement = select(Consumer).where(Consumer.email == email_part)
            consumer = session.exec(statement).first()
            if consumer:
                consumer_id = consumer.id
                creator_id = consumer.creator_id
                logger.info(f"✅ Resolved consumer by email pattern {email_part} -> {consumer_id}")

        # Strategy 3: Try recipient_email directly
        if not consumer_id and webhook.recipient_email:
            statement = select(Consumer).where(Consumer.email == webhook.recipient_email)
            consumer = session.exec(statement).first()
            if consumer:
                consumer_id = consumer.id
                creator_id = consumer.creator_id
                logger.info(f"✅ Resolved consumer by recipient_email {webhook.recipient_email} -> {consumer_id}")

        # Map status to event type
        event_type_map = {
            "delivered": EventType.EMAIL_DELIVERED,
            "unread": EventType.EMAIL_DELIVERED,
            "read": EventType.EMAIL_OPENED,
            "opened": EventType.EMAIL_OPENED,
            "replied": EventType.EMAIL_REPLIED,
            "click_cta": EventType.EMAIL_CLICKED,
            "clicked": EventType.EMAIL_CLICKED,
            "booking_click": EventType.EMAIL_CLICKED,
            "booking_done": EventType.BOOKING_CREATED,
        }

        event_type = event_type_map.get(webhook.status.lower(), EventType.EMAIL_DELIVERED)

        # Create event payload
        event_payload = {
            "status": webhook.status,
            "previous_status": webhook.previous_status,
            "recipient_email": webhook.recipient_email,
            "subject": webhook.subject,
            "body": webhook.body,  # Include email body
            "template_name": webhook.template_name,
            "workflow_name": webhook.workflow_name,
            "simulated": webhook.simulated,
            "timestamp": webhook.timestamp.isoformat() if webhook.timestamp else None,
        }

        # Add timing data
        if webhook.read_at:
            event_payload["read_at"] = webhook.read_at.isoformat()
        if webhook.replied_at:
            event_payload["replied_at"] = webhook.replied_at.isoformat()
        if webhook.cta_clicked_at:
            event_payload["cta_clicked_at"] = webhook.cta_clicked_at.isoformat()
        if webhook.booking_clicked_at:
            event_payload["booking_clicked_at"] = webhook.booking_clicked_at.isoformat()
        if webhook.booking_completed_at:
            event_payload["booking_completed_at"] = webhook.booking_completed_at.isoformat()

        # If we have consumer_id and creator_id, create event
        if consumer_id and creator_id:
            event_data = EventCreate(
                consumer_id=consumer_id,
                type=event_type,
                source=EventSource.WEBHOOK,
                payload=event_payload
            )
            event = event_service.create_event(
                creator_id=creator_id,
                data=event_data
            )

            logger.info(f"✅ Created event {event.id} for consumer {consumer_id}, type: {event_type}, status: {webhook.status}")

            # Update consumer context based on engagement
            context = context_service.get_or_create_context(creator_id, consumer_id)

            # Update engagement metrics
            if webhook.status in ["read", "opened"]:
                context.metrics["email_opens"] = context.metrics.get("email_opens", 0) + 1
            elif webhook.status == "replied":
                context.metrics["email_replies"] = context.metrics.get("email_replies", 0) + 1
            elif webhook.status in ["click_cta", "booking_click", "clicked"]:
                context.metrics["email_clicks"] = context.metrics.get("email_clicks", 0) + 1
            elif webhook.status == "booking_done":
                context.metrics["bookings_completed"] = context.metrics.get("bookings_completed", 0) + 1
                context.stage = "converted"

            # Save updated context
            context.updated_at = datetime.utcnow()
            session.add(context)
            session.commit()

            logger.info(f"✅ Updated consumer context for {consumer_id}")

            return {
                "success": True,
                "message": "Email status processed successfully",
                "status": webhook.status,
                "event_created": True,
                "event_id": str(event.id),
                "consumer_id": str(consumer_id),
                "creator_id": str(creator_id)
            }
        else:
            logger.warning(
                f"❌ Could not resolve consumer_id or creator_id from webhook - distinct_id: {webhook.distinct_id}, email: {webhook.recipient_email}"
            )
            return {
                "success": False,
                "message": "Could not resolve consumer",
                "status": webhook.status,
                "event_created": False,
                "distinct_id": webhook.distinct_id,
                "recipient_email": webhook.recipient_email
            }

    except Exception as e:
        logger.error(f"❌ Error processing email status webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/suprsend", response_model=Dict[str, Any])
async def receive_suprsend_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    Receive native SuprSend webhooks

    SuprSend sends webhooks for various notification events.
    This endpoint normalizes them and processes via the standard flow.
    """
    try:
        # Get raw body
        body = await request.json()

        logger.info(
            f"Received SuprSend webhook",
            extra={"event": body.get("event"), "distinct_id": body.get("distinct_id")}
        )

        # Map SuprSend event to our status
        event_status_map = {
            "$notification_delivered": "delivered",
            "$notification_opened": "read",
            "$notification_clicked": "click_cta",
            "$notification_replied": "replied",
        }

        suprsend_event = body.get("event", "")
        status = event_status_map.get(suprsend_event, "delivered")

        # Extract email from body
        notification_body = body.get("body", {})
        recipient_email = notification_body.get("$email", [None])[0] if isinstance(notification_body.get("$email"), list) else notification_body.get("$email")

        # Create normalized webhook
        normalized = EmailStatusWebhook(
            distinct_id=body.get("distinct_id"),
            recipient_email=recipient_email,
            status=status,
            timestamp=datetime.fromisoformat(body.get("created_on", "").replace("Z", "+00:00")) if body.get("created_on") else datetime.utcnow(),
            simulated=False,
            raw_data=body
        )

        # Process via standard handler
        return await receive_email_status(normalized, background_tasks, session)

    except Exception as e:
        logger.error(f"Error processing SuprSend webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoint"""
    return {
        "status": "healthy",
        "service": "email-webhooks",
        "timestamp": datetime.utcnow().isoformat()
    }
