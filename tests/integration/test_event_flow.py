"""Integration test for end-to-end event flow."""
import pytest
from datetime import datetime

from app.domain.events.service import EventService
from app.domain.context.service import ConsumerContextService
from app.domain.schemas import EventCreate
from app.domain.types import EventType, EventSource, ConsumerStage


def test_event_creates_and_updates_context(session, creator, consumer):
    """Test that creating an event updates consumer context."""
    # Arrange
    event_service = EventService(session)
    context_service = ConsumerContextService(session)

    # Act - Create a page view event
    event = event_service.create_event(
        creator.id,
        EventCreate(
            consumer_id=consumer.id,
            type=EventType.PAGE_VIEW,
            source=EventSource.API,
            timestamp=datetime.utcnow(),
            payload={"page_url": "https://example.com/cohort"},
        ),
    )

    # Get or create context (simulating what event handler does)
    context = context_service.update_context_from_event(event)

    # Assert
    assert event.id is not None
    assert event.creator_id == creator.id
    assert event.consumer_id == consumer.id
    assert event.type == EventType.PAGE_VIEW.value

    assert context is not None
    assert context.creator_id == creator.id
    assert context.consumer_id == consumer.id
    assert context.metrics["page_views"] == 1
    assert context.last_seen_at is not None


def test_multiple_events_update_stage(session, creator, consumer):
    """Test that multiple events progress consumer through stages."""
    # Arrange
    event_service = EventService(session)
    context_service = ConsumerContextService(session)

    # Act - Create multiple events
    # 1. Page view
    event1 = event_service.create_event(
        creator.id,
        EventCreate(
            consumer_id=consumer.id,
            type=EventType.PAGE_VIEW,
            source=EventSource.API,
            payload={},
        ),
    )
    context = context_service.update_context_from_event(event1)
    assert context.stage == ConsumerStage.NEW.value

    # 2. Email opened
    event2 = event_service.create_event(
        creator.id,
        EventCreate(
            consumer_id=consumer.id,
            type=EventType.EMAIL_OPENED,
            source=EventSource.WEBHOOK,
            payload={},
        ),
    )
    context = context_service.update_context_from_event(event2)

    # 3. Another page view
    event3 = event_service.create_event(
        creator.id,
        EventCreate(
            consumer_id=consumer.id,
            type=EventType.PAGE_VIEW,
            source=EventSource.API,
            payload={},
        ),
    )
    context = context_service.update_context_from_event(event3)

    # Assert - Should have progressed to INTERESTED stage
    assert context.metrics["page_views"] == 2
    assert context.metrics["emails_opened"] == 1
    assert context.stage in [ConsumerStage.INTERESTED.value, ConsumerStage.ENGAGED.value]


def test_payment_event_marks_converted(session, creator, consumer):
    """Test that payment event marks consumer as converted."""
    # Arrange
    event_service = EventService(session)
    context_service = ConsumerContextService(session)

    # Act - Create payment event
    event = event_service.create_event(
        creator.id,
        EventCreate(
            consumer_id=consumer.id,
            type=EventType.PAYMENT_SUCCESS,
            source=EventSource.WEBHOOK,
            payload={"amount_cents": 50000, "currency": "USD"},
        ),
    )
    context = context_service.update_context_from_event(event)

    # Assert
    assert context.stage == ConsumerStage.CONVERTED.value
    assert context.metrics["revenue_cents"] == 50000


def test_consumer_timeline(session, creator, consumer):
    """Test retrieving consumer timeline."""
    # Arrange
    event_service = EventService(session)

    # Create multiple events
    for i in range(5):
        event_service.create_event(
            creator.id,
            EventCreate(
                consumer_id=consumer.id,
                type=EventType.PAGE_VIEW,
                source=EventSource.API,
                payload={"page": i},
            ),
        )

    # Act
    timeline = event_service.get_consumer_timeline(creator.id, consumer.id, limit=10)

    # Assert
    assert len(timeline) == 5
    # Should be ordered by timestamp descending
    assert timeline[0].payload["page"] == 4
    assert timeline[-1].payload["page"] == 0
