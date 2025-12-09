"""
Simple Agent Interface Demo - No Dependencies Required
This demonstrates the agent concept with plain Python
"""
from datetime import datetime, timedelta
from abc import ABC, abstractmethod


# ==================== Simplified Types ====================

class PlannedAction:
    """Represents a planned action."""
    def __init__(self, action_type, channel, payload, send_at, priority=1.0):
        self.action_type = action_type
        self.channel = channel
        self.payload = payload
        self.send_at = send_at
        self.priority = priority

    def __repr__(self):
        return f"PlannedAction({self.action_type}, {self.channel})"


class ConsumerContext:
    """Simplified consumer context."""
    def __init__(self, stage, metrics):
        self.stage = stage
        self.metrics = metrics


class Event:
    """Simplified event."""
    def __init__(self, event_type, payload):
        self.type = event_type
        self.payload = payload


# ==================== Base Agent Interface ====================

class BaseAgent(ABC):
    """Simple base class for creating custom agents."""

    def __init__(self, config):
        self.config = config

    @abstractmethod
    def should_act(self, context, event) -> bool:
        """Return True to act, False to skip"""
        pass

    @abstractmethod
    def plan_actions(self, context, event) -> list:
        """Return list of actions to take"""
        pass

    # Helper methods
    def is_new_lead(self, context):
        return context.stage == "new"

    def is_engaged(self, context):
        return context.stage == "engaged"

    def get_page_views(self, context):
        return context.metrics.get("page_views", 0)

    def get_emails_sent(self, context):
        return context.metrics.get("emails_sent", 0)

    def get_event_payload(self, event, key, default=None):
        return event.payload.get(key, default)

    def send_email(self, to, subject, body, delay_minutes=0, priority=1.0):
        return PlannedAction(
            action_type="send_email",
            channel="email",
            payload={"to": to, "subject": subject, "body": body},
            send_at=datetime.utcnow() + timedelta(minutes=delay_minutes),
            priority=priority
        )

    def send_whatsapp(self, to, message, delay_minutes=0, priority=1.0):
        return PlannedAction(
            action_type="send_whatsapp",
            channel="whatsapp",
            payload={"to": to, "message": message},
            send_at=datetime.utcnow() + timedelta(minutes=delay_minutes),
            priority=priority
        )


# ==================== Example Agent ====================

class WelcomeAgent(BaseAgent):
    """Welcomes new leads on their first visit."""

    def should_act(self, context, event) -> bool:
        """Act on first page view for new leads."""
        return (
            event.type == "page_view" and
            self.get_page_views(context) == 1 and
            self.is_new_lead(context)
        )

    def plan_actions(self, context, event):
        """Send welcome message."""
        actions = []

        whatsapp = self.get_event_payload(event, "whatsapp")
        email = self.get_event_payload(event, "email")

        if whatsapp:
            actions.append(
                self.send_whatsapp(
                    to=whatsapp,
                    message="Hey! 👋 Welcome! I'm here if you have questions.",
                    delay_minutes=2,
                )
            )

        if email:
            actions.append(
                self.send_email(
                    to=email,
                    subject="Welcome! 🎉",
                    body="<html><body><h2>Thanks for visiting!</h2></body></html>",
                    delay_minutes=5,
                )
            )

        return actions


class FollowUpAgent(BaseAgent):
    """Follows up with engaged leads."""

    def should_act(self, context, event) -> bool:
        """Act on email opens from engaged leads."""
        return (
            event.type == "email_opened" and
            self.is_engaged(context) and
            self.get_emails_sent(context) < 3
        )

    def plan_actions(self, context, event):
        """Send personalized follow-up."""
        email = self.get_event_payload(event, "email")

        # Calculate engagement
        engagement_score = (
            self.get_page_views(context) * 1 +
            context.metrics.get("emails_opened", 0) * 2
        )

        if engagement_score >= 5:
            subject = "Let's schedule a call?"
            message = "You seem really interested! Want to chat?"
        else:
            subject = "Have questions?"
            message = "Just checking in. Any questions?"

        return [
            self.send_email(
                to=email,
                subject=subject,
                body=f"<html><body><p>{message}</p></body></html>",
                delay_minutes=30,
            )
        ]


# ==================== Demo Scenarios ====================

def demo_scenario_1():
    """Demo: First-time visitor triggers welcome agent."""
    print("\n" + "="*70)
    print("📋 SCENARIO 1: First-Time Visitor")
    print("="*70)

    # Create agent
    agent = WelcomeAgent({"name": "Welcome Agent"})

    # Create mock data
    context = ConsumerContext(
        stage="new",
        metrics={"page_views": 1, "emails_sent": 0}
    )

    event = Event(
        event_type="page_view",
        payload={
            "page_url": "https://example.com/cohort",
            "whatsapp": "+1234567890",
            "email": "newuser@example.com"
        }
    )

    # Test the agent
    print(f"\n🔍 Input:")
    print(f"   Consumer Stage: {context.stage}")
    print(f"   Page Views: {context.metrics['page_views']}")
    print(f"   Event Type: {event.type}")

    should_act = agent.should_act(context, event)
    print(f"\n🤔 Agent Decision: {'✅ ACT' if should_act else '❌ SKIP'}")

    if should_act:
        actions = agent.plan_actions(context, event)
        print(f"\n📤 Actions Planned ({len(actions)} total):")
        for i, action in enumerate(actions, 1):
            print(f"   {i}. {action.action_type.upper()} via {action.channel}")
            print(f"      → {list(action.payload.keys())}")
            print(f"      → Priority: {action.priority}, Delay: {(action.send_at - datetime.utcnow()).seconds // 60}min")


def demo_scenario_2():
    """Demo: Returning visitor - agent should NOT act."""
    print("\n" + "="*70)
    print("📋 SCENARIO 2: Returning Visitor (Should Skip)")
    print("="*70)

    agent = WelcomeAgent({"name": "Welcome Agent"})

    context = ConsumerContext(
        stage="interested",
        metrics={"page_views": 5, "emails_sent": 1}
    )

    event = Event(
        event_type="page_view",
        payload={"page_url": "https://example.com/pricing"}
    )

    print(f"\n🔍 Input:")
    print(f"   Consumer Stage: {context.stage}")
    print(f"   Page Views: {context.metrics['page_views']}")
    print(f"   Event Type: {event.type}")

    should_act = agent.should_act(context, event)
    print(f"\n🤔 Agent Decision: {'✅ ACT' if should_act else '❌ SKIP'}")
    print(f"   ✓ Agent correctly skipped (not first visit)")


def demo_scenario_3():
    """Demo: Follow-up agent with engaged lead."""
    print("\n" + "="*70)
    print("📋 SCENARIO 3: Engaged Lead Opens Email")
    print("="*70)

    agent = FollowUpAgent({"name": "Follow-Up Agent"})

    context = ConsumerContext(
        stage="engaged",
        metrics={
            "page_views": 8,
            "emails_sent": 2,
            "emails_opened": 3
        }
    )

    event = Event(
        event_type="email_opened",
        payload={"email": "engaged@example.com"}
    )

    print(f"\n🔍 Input:")
    print(f"   Consumer Stage: {context.stage}")
    print(f"   Page Views: {context.metrics['page_views']}")
    print(f"   Emails Opened: {context.metrics['emails_opened']}")
    print(f"   Event Type: {event.type}")

    # Calculate engagement score
    engagement_score = (
        context.metrics['page_views'] * 1 +
        context.metrics['emails_opened'] * 2
    )
    print(f"   Engagement Score: {engagement_score}")

    should_act = agent.should_act(context, event)
    print(f"\n🤔 Agent Decision: {'✅ ACT' if should_act else '❌ SKIP'}")

    if should_act:
        actions = agent.plan_actions(context, event)
        print(f"\n📤 Actions Planned ({len(actions)} total):")
        for i, action in enumerate(actions, 1):
            print(f"   {i}. {action.action_type.upper()} via {action.channel}")
            print(f"      → Subject: {action.payload.get('subject')}")


def show_interface():
    """Show the simple interface code."""
    print("\n" + "="*70)
    print("💡 THE SIMPLE INTERFACE")
    print("="*70)
    print("""
Just implement 2 methods:

class MyAgent(BaseAgent):
    def should_act(self, context, event) -> bool:
        \"\"\"Return True to act, False to skip\"\"\"
        return event.type == "page_view" and self.is_new_lead(context)

    def plan_actions(self, context, event):
        \"\"\"Return list of actions\"\"\"
        return [
            self.send_whatsapp(to="...", message="Welcome!")
        ]

That's it! 🎉
""")


# ==================== Main ====================

def main():
    """Run the demo."""
    print("\n" + "🚀" * 35)
    print("🚀    SIMPLE AGENT INTERFACE - DEMO    🚀")
    print("🚀" * 35)

    show_interface()
    demo_scenario_1()
    demo_scenario_2()
    demo_scenario_3()

    print("\n" + "="*70)
    print("✅ DEMO COMPLETE!")
    print("="*70)
    print("""
🎯 What you just saw:

1. ✅ Simple 2-method interface (should_act + plan_actions)
2. ✅ Rich helper methods (is_new_lead, get_page_views, etc.)
3. ✅ Easy action creation (send_email, send_whatsapp)
4. ✅ Clear decision logic (when to act, when to skip)
5. ✅ Personalized actions based on engagement

📖 Next Steps:

1. Create your agent in app/agents/my_agent.py
2. Register it via API with implementation: "simple"
3. Record events to trigger it
4. Watch it automate! 🤖

📚 Read AGENT_GUIDE.md for complete tutorial with examples!
    """)


if __name__ == "__main__":
    main()
