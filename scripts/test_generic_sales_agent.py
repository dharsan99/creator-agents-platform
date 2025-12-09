"""Test the generic sales agent with a creator's profile."""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, create_engine, select
from app.config import settings
from app.infra.db.models import Creator, Consumer, Event, ConsumerContext
from app.infra.db.creator_profile_models import CreatorProfile
from app.agents.generic_sales_agent import GenericSalesAgent


def test_generic_sales_agent():
    """Test generic sales agent with Ajay Shenoy's profile."""
    print("="*70)
    print("Testing Generic Sales Agent with Creator Profile")
    print("="*70)

    # Create engine and session
    engine = create_engine(settings.database_url)
    session = Session(engine)

    try:
        # Step 1: Get Ajay Shenoy's creator and profile from database
        print("\n📥 Fetching creator profile from database...")

        creator_stmt = select(Creator).where(Creator.email == "ajay_shenoy@topmate.io")
        creator = session.exec(creator_stmt).first()

        if not creator:
            print("❌ Creator not found. Please run test_onboarding.py first!")
            return

        profile_stmt = select(CreatorProfile).where(CreatorProfile.creator_id == creator.id)
        profile = session.exec(profile_stmt).first()

        if not profile:
            print("❌ Creator profile not found!")
            return

        print(f"✅ Found creator: {creator.name}")
        print(f"✅ Found profile with {len(profile.services)} service(s)")

        # Step 2: Prepare creator profile data for agent
        creator_profile_data = {
            "creator_name": creator.name,
            "creator_id": str(creator.id),
            "sales_pitch": profile.sales_pitch,
            "agent_instructions": profile.agent_instructions,
            "services": profile.services,
            "value_propositions": profile.value_propositions,
            "objection_handling": profile.objection_handling,
            "target_audience": profile.target_audience_description,
        }

        # Step 3: Create agent configuration with profile
        agent_config = {
            "agent_class": "GenericSalesAgent",
            "creator_profile": creator_profile_data,
            "enabled": True,
        }

        # Step 4: Create test consumer
        print("\n👤 Creating test consumer...")
        consumer = Consumer(
            id=uuid4(),
            creator_id=creator.id,
            name="Test Lead",
            email="test@example.com",
            whatsapp="+919876543210",
        )

        # Step 5: Create consumer context (include consumer contact info in metrics)
        context = ConsumerContext(
            creator_id=creator.id,
            consumer_id=consumer.id,
            stage="new",
            last_seen_at=datetime.utcnow(),
            metrics={
                "page_views": 0,
                "service_clicks": 0,
                "enrolled": False,
                # Add consumer contact info for agent access
                "name": consumer.name,
                "email": consumer.email,
                "whatsapp": consumer.whatsapp,
            },
        )

        # Step 6: Initialize agent
        print("\n🤖 Initializing Generic Sales Agent...")
        agent = GenericSalesAgent(agent_config)
        print(f"   Agent configured with profile for: {creator.name}")

        # Test Scenario 1: First page view (new lead)
        print("\n" + "="*70)
        print("SCENARIO 1: New Lead - First Page View")
        print("="*70)

        event1 = Event(
            id=uuid4(),
            creator_id=creator.id,
            consumer_id=consumer.id,
            type="page_view",
            source="website",
            timestamp=datetime.utcnow(),
            payload={"page": "creator_profile", "url": f"https://topmate.io/{creator.name}"},
        )

        context.metrics["page_views"] = 1

        should_act = agent.should_act(context, event1)
        print(f"\n❓ Should agent act? {should_act}")

        if should_act:
            actions = agent.plan_actions(context, event1)
            print(f"\n✅ Agent planned {len(actions)} action(s):")
            for i, action in enumerate(actions, 1):
                print(f"\n   Action {i}:")
                print(f"   📱 Channel: {action.channel}")
                print(f"   📧 To: {action.payload.get('to', 'N/A')}")
                # Calculate delay from send_at
                delay_seconds = (action.send_at - datetime.utcnow()).total_seconds()
                delay_minutes = int(delay_seconds / 60)
                print(f"   ⏰ Delay: ~{delay_minutes} minutes")
                print(f"   📝 Message Preview:")
                message = action.payload.get("message", "")
                print(f"      {message[:300]}...")

        # Test Scenario 2: Returning lead
        print("\n" + "="*70)
        print("SCENARIO 2: Returning Lead - Multiple Page Views")
        print("="*70)

        event2 = Event(
            id=uuid4(),
            creator_id=creator.id,
            consumer_id=consumer.id,
            type="page_view",
            source="website",
            timestamp=datetime.utcnow(),
            payload={"page": "creator_profile"},
        )

        context.metrics["page_views"] = 3
        context.last_seen_at = datetime.utcnow() - timedelta(hours=30)

        should_act = agent.should_act(context, event2)
        print(f"\n❓ Should agent act? {should_act}")

        if should_act:
            actions = agent.plan_actions(context, event2)
            print(f"\n✅ Agent planned {len(actions)} action(s):")
            for i, action in enumerate(actions, 1):
                print(f"\n   Action {i}:")
                print(f"   📱 Channel: {action.channel}")
                delay_seconds = (action.send_at - datetime.utcnow()).total_seconds()
                delay_minutes = int(delay_seconds / 60)
                print(f"   ⏰ Delay: ~{delay_minutes} minutes")
                print(f"   📝 Message Preview:")
                message = action.payload.get("message", "")
                print(f"      {message[:300]}...")

        # Test Scenario 3: Service click
        print("\n" + "="*70)
        print("SCENARIO 3: Lead Clicks on Service")
        print("="*70)

        service_id = profile.services[0].get("id") if profile.services else None

        event3 = Event(
            id=uuid4(),
            creator_id=creator.id,
            consumer_id=consumer.id,
            type="service_click",
            source="website",
            timestamp=datetime.utcnow(),
            payload={"service_id": service_id},
        )

        context.metrics["service_clicks"] = 1

        should_act = agent.should_act(context, event3)
        print(f"\n❓ Should agent act? {should_act}")

        if should_act:
            actions = agent.plan_actions(context, event3)
            print(f"\n✅ Agent planned {len(actions)} action(s):")
            for i, action in enumerate(actions, 1):
                print(f"\n   Action {i}:")
                print(f"   📱 Channel: {action.channel}")
                delay_seconds = (action.send_at - datetime.utcnow()).total_seconds()
                delay_minutes = int(delay_seconds / 60)
                print(f"   ⏰ Delay: ~{delay_minutes} minutes")
                print(f"   📝 Message Preview:")
                message = action.payload.get("message", "")
                print(f"      {message[:300]}...")

        # Summary
        print("\n" + "="*70)
        print("✅ Test Complete - Key Insights:")
        print("="*70)
        print(f"\n✨ This Generic Sales Agent can work with ANY creator!")
        print(f"\n   • Takes creator profile as context")
        print(f"   • Uses LLM-generated sales pitch & instructions")
        print(f"   • Adapts messages to creator's services")
        print(f"   • Handles objections using creator's guidelines")
        print(f"\n💡 To use with different creator:")
        print(f"   1. Onboard the creator (generates profile)")
        print(f"   2. Pass their profile to agent config")
        print(f"   3. Agent automatically uses their context!")
        print("\n" + "="*70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    test_generic_sales_agent()
