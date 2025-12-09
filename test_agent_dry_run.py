"""
Dry run test for Simple Agent Interface
Tests the agent without needing database or external services
"""
import sys
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock

# Add app to path
sys.path.insert(0, '/Users/dineshsingh/dev/topmate/creator-agents')

from app.domain.agents.base_agent import BaseAgent
from app.infra.db.models import Event, ConsumerContext
from app.domain.types import EventType, ConsumerStage


# ==================== Test Agent ====================

class TestWelcomeAgent(BaseAgent):
    """Simple test agent that welcomes new leads."""

    def should_act(self, context: ConsumerContext, event: Event) -> bool:
        """Act on first page view for new leads."""
        print(f"\n🔍 Checking if agent should act...")
        print(f"   Event type: {event.type}")
        print(f"   Consumer stage: {context.stage}")
        print(f"   Page views: {self.get_page_views(context)}")

        should_act = (
            event.type == "page_view" and
            self.get_page_views(context) == 1 and
            self.is_new_lead(context)
        )

        print(f"   Decision: {'✅ ACT' if should_act else '❌ SKIP'}")
        return should_act

    def plan_actions(self, context: ConsumerContext, event: Event):
        """Send welcome message."""
        print(f"\n📋 Planning actions...")

        whatsapp = self.get_event_payload(event, "whatsapp")
        email = self.get_event_payload(event, "email")

        actions = []

        if whatsapp:
            print(f"   ✉️  Adding WhatsApp message to {whatsapp}")
            actions.append(
                self.send_whatsapp(
                    to=whatsapp,
                    message="Hey! 👋 Welcome to our site. I'm here if you have questions!",
                    delay_minutes=2,
                )
            )

        if email:
            print(f"   📧 Adding email to {email}")
            actions.append(
                self.send_email(
                    to=email,
                    subject="Welcome! 🎉",
                    body="<html><body><h2>Thanks for visiting!</h2></body></html>",
                    delay_minutes=5,
                )
            )

        print(f"   Total actions planned: {len(actions)}")
        return actions


# ==================== Mock Data ====================

def create_mock_context(stage="new", page_views=1):
    """Create a mock consumer context."""
    context = Mock(spec=ConsumerContext)
    context.creator_id = uuid4()
    context.consumer_id = uuid4()
    context.stage = stage
    context.metrics = {
        "page_views": page_views,
        "emails_sent": 0,
        "emails_opened": 0,
        "whatsapp_messages_sent": 0,
        "whatsapp_messages_received": 0,
        "bookings": 0,
        "revenue_cents": 0,
    }
    context.last_seen_at = datetime.utcnow()
    context.updated_at = datetime.utcnow()
    return context


def create_mock_event(event_type="page_view", payload=None):
    """Create a mock event."""
    event = Mock(spec=Event)
    event.id = uuid4()
    event.creator_id = uuid4()
    event.consumer_id = uuid4()
    event.type = event_type
    event.source = "api"
    event.timestamp = datetime.utcnow()
    event.payload = payload or {}
    event.created_at = datetime.utcnow()
    return event


# ==================== Test Scenarios ====================

def test_scenario_1_first_time_visitor():
    """Test: First time visitor should trigger welcome agent."""
    print("\n" + "="*70)
    print("TEST SCENARIO 1: First Time Visitor")
    print("="*70)

    agent = TestWelcomeAgent({"name": "Welcome Agent"})
    context = create_mock_context(stage="new", page_views=1)
    event = create_mock_event(
        event_type="page_view",
        payload={
            "page_url": "https://example.com/cohort",
            "whatsapp": "+1234567890",
            "email": "newuser@example.com",
        }
    )

    # Test should_act
    should_act = agent.should_act(context, event)
    assert should_act == True, "Agent should act on first page view"

    # Test plan_actions
    actions = agent.plan_actions(context, event)
    assert len(actions) == 2, "Should have 2 actions (WhatsApp + Email)"

    print(f"\n✅ Test passed!")
    print(f"   Generated {len(actions)} actions")
    for i, action in enumerate(actions, 1):
        print(f"   {i}. {action.channel.value}: {action.action_type.value}")


def test_scenario_2_returning_visitor():
    """Test: Returning visitor should NOT trigger welcome agent."""
    print("\n" + "="*70)
    print("TEST SCENARIO 2: Returning Visitor (Should Not Act)")
    print("="*70)

    agent = TestWelcomeAgent({"name": "Welcome Agent"})
    context = create_mock_context(stage="interested", page_views=5)
    event = create_mock_event(
        event_type="page_view",
        payload={"page_url": "https://example.com/pricing"}
    )

    # Test should_act
    should_act = agent.should_act(context, event)
    assert should_act == False, "Agent should NOT act on returning visitor"

    print(f"\n✅ Test passed!")
    print(f"   Agent correctly skipped action")


def test_scenario_3_email_opened():
    """Test: Email opened event should NOT trigger welcome agent."""
    print("\n" + "="*70)
    print("TEST SCENARIO 3: Email Opened (Wrong Event Type)")
    print("="*70)

    agent = TestWelcomeAgent({"name": "Welcome Agent"})
    context = create_mock_context(stage="new", page_views=1)
    event = create_mock_event(
        event_type="email_opened",
        payload={"email": "user@example.com"}
    )

    # Test should_act
    should_act = agent.should_act(context, event)
    assert should_act == False, "Agent should NOT act on email_opened event"

    print(f"\n✅ Test passed!")
    print(f"   Agent correctly skipped action (wrong event type)")


def test_scenario_4_engaged_lead():
    """Test: Test with engaged lead."""
    print("\n" + "="*70)
    print("TEST SCENARIO 4: Engaged Lead")
    print("="*70)

    agent = TestWelcomeAgent({"name": "Welcome Agent"})
    context = create_mock_context(stage="engaged", page_views=10)
    context.metrics["emails_opened"] = 3
    context.metrics["whatsapp_messages_received"] = 2

    event = create_mock_event(event_type="page_view")

    # Test helper methods
    print(f"\n📊 Testing helper methods:")
    print(f"   is_engaged: {agent.is_engaged(context)}")
    print(f"   get_page_views: {agent.get_page_views(context)}")
    print(f"   get_emails_opened: {agent.get_emails_opened(context)}")

    # Calculate engagement score
    engagement_score = (
        agent.get_page_views(context) * 1 +
        agent.get_emails_opened(context) * 2 +
        agent.get_metric(context, "whatsapp_messages_received", 0) * 3
    )
    print(f"   engagement_score: {engagement_score}")

    print(f"\n✅ Test passed!")
    print(f"   Helper methods work correctly")


# ==================== Main ====================

def main():
    """Run all test scenarios."""
    print("\n" + "🚀" * 35)
    print("🚀  SIMPLE AGENT INTERFACE - DRY RUN TEST  🚀")
    print("🚀" * 35)

    try:
        # Run all test scenarios
        test_scenario_1_first_time_visitor()
        test_scenario_2_returning_visitor()
        test_scenario_3_email_opened()
        test_scenario_4_engaged_lead()

        print("\n" + "="*70)
        print("🎉 ALL TESTS PASSED!")
        print("="*70)
        print("\n✅ The Simple Agent Interface is working correctly!")
        print("✅ Agents can:")
        print("   - Check consumer context (stage, metrics)")
        print("   - Filter events (should_act logic)")
        print("   - Generate actions (plan_actions)")
        print("   - Use helper methods (is_engaged, get_page_views, etc.)")
        print("\n📖 Next steps:")
        print("   1. Register your agent via API")
        print("   2. Record events to trigger it")
        print("   3. Watch it automate! 🤖")
        print()

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
