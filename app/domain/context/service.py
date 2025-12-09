"""Consumer context service for maintaining materialized state."""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select

from app.infra.db.models import ConsumerContext, Event
from app.domain.types import ConsumerStage, EventType


class ConsumerContextService:
    """Service for managing consumer context (materialized view)."""

    def __init__(self, session: Session):
        self.session = session

    def get_context(
        self, creator_id: UUID, consumer_id: UUID
    ) -> Optional[ConsumerContext]:
        """Get consumer context."""
        statement = (
            select(ConsumerContext)
            .where(ConsumerContext.creator_id == creator_id)
            .where(ConsumerContext.consumer_id == consumer_id)
        )
        return self.session.exec(statement).first()

    def get_or_create_context(
        self, creator_id: UUID, consumer_id: UUID
    ) -> ConsumerContext:
        """Get or create consumer context."""
        context = self.get_context(creator_id, consumer_id)
        if context:
            return context

        context = ConsumerContext(
            creator_id=creator_id,
            consumer_id=consumer_id,
            stage=ConsumerStage.NEW.value,
            metrics={
                "page_views": 0,
                "emails_sent": 0,
                "emails_opened": 0,
                "whatsapp_messages_sent": 0,
                "whatsapp_messages_received": 0,
                "bookings": 0,
                "revenue_cents": 0,
                "last_page_view": None,
                "last_email_sent": None,
                "last_whatsapp_sent": None,
            },
        )
        self.session.add(context)
        self.session.commit()
        self.session.refresh(context)
        return context

    def update_context_from_event(self, event: Event) -> ConsumerContext:
        """Update context based on a new event."""
        context = self.get_or_create_context(event.creator_id, event.consumer_id)

        # Update last_seen_at
        if event.timestamp:
            if not context.last_seen_at or event.timestamp > context.last_seen_at:
                context.last_seen_at = event.timestamp

        # Update metrics based on event type
        metrics = context.metrics
        event_type = EventType(event.type)

        if event_type == EventType.PAGE_VIEW:
            metrics["page_views"] = metrics.get("page_views", 0) + 1
            metrics["last_page_view"] = event.timestamp.isoformat()
            self._update_stage_from_engagement(context)

        elif event_type == EventType.EMAIL_SENT:
            metrics["emails_sent"] = metrics.get("emails_sent", 0) + 1
            metrics["last_email_sent"] = event.timestamp.isoformat()

        elif event_type == EventType.EMAIL_OPENED:
            metrics["emails_opened"] = metrics.get("emails_opened", 0) + 1
            self._update_stage_from_engagement(context)

        elif event_type == EventType.WHATSAPP_MESSAGE_SENT:
            metrics["whatsapp_messages_sent"] = metrics.get("whatsapp_messages_sent", 0) + 1
            metrics["last_whatsapp_sent"] = event.timestamp.isoformat()

        elif event_type == EventType.WHATSAPP_MESSAGE_RECEIVED:
            metrics["whatsapp_messages_received"] = (
                metrics.get("whatsapp_messages_received", 0) + 1
            )
            self._update_stage_from_engagement(context)

        elif event_type == EventType.BOOKING_CREATED:
            metrics["bookings"] = metrics.get("bookings", 0) + 1
            context.stage = ConsumerStage.ENGAGED.value

        elif event_type == EventType.PAYMENT_SUCCESS:
            amount_cents = event.payload.get("amount_cents", 0)
            metrics["revenue_cents"] = metrics.get("revenue_cents", 0) + amount_cents
            context.stage = ConsumerStage.CONVERTED.value

        context.metrics = metrics
        context.updated_at = datetime.utcnow()

        self.session.add(context)
        self.session.commit()
        self.session.refresh(context)
        return context

    def _update_stage_from_engagement(self, context: ConsumerContext) -> None:
        """Update stage based on engagement signals."""
        metrics = context.metrics

        # If already converted or churned, don't downgrade
        if context.stage in [ConsumerStage.CONVERTED.value, ConsumerStage.CHURNED.value]:
            return

        page_views = metrics.get("page_views", 0)
        emails_opened = metrics.get("emails_opened", 0)
        whatsapp_received = metrics.get("whatsapp_messages_received", 0)

        # Simple heuristic: if they have multiple touchpoints, mark as interested
        engagement_score = page_views + emails_opened * 2 + whatsapp_received * 3

        if engagement_score >= 5:
            context.stage = ConsumerStage.ENGAGED.value
        elif engagement_score >= 2:
            context.stage = ConsumerStage.INTERESTED.value

    def compute_engagement_score(
        self, creator_id: UUID, consumer_id: UUID
    ) -> float:
        """Compute engagement score for a consumer."""
        context = self.get_context(creator_id, consumer_id)
        if not context:
            return 0.0

        metrics = context.metrics
        score = (
            metrics.get("page_views", 0) * 1
            + metrics.get("emails_opened", 0) * 2
            + metrics.get("emails_replied", 0) * 5
            + metrics.get("whatsapp_messages_received", 0) * 3
            + metrics.get("bookings", 0) * 10
        )
        return float(score)

    def is_recently_active(
        self, creator_id: UUID, consumer_id: UUID, days: int = 7
    ) -> bool:
        """Check if consumer has been active recently."""
        context = self.get_context(creator_id, consumer_id)
        if not context or not context.last_seen_at:
            return False

        threshold = datetime.utcnow() - timedelta(days=days)
        return context.last_seen_at >= threshold
