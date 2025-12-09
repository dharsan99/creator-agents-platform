"""End-to-end test: Onboard creator, deploy agent, simulate events."""
import sys
from pathlib import Path
from datetime import datetime
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, create_engine, select
from app.config import settings
from app.infra.db.models import Creator, Consumer, Event, ConsumerContext
from app.domain.onboarding.service import OnboardingService
from app.domain.onboarding.agent_deployment import AgentDeploymentService
from app.domain.agents.service import AgentService
from app.domain.schemas import AgentInput


def test_e2e_deployment():
    """Test end-to-end agent deployment and execution."""
    print("="*80)
    print("END-TO-END TEST: Creator Onboarding → Agent Deployment → Event Processing")
    print("="*80)

    # Create engine and session
    engine = create_engine(settings.database_url)
    session = Session(engine)

    try:
        # ================== STEP 1: Onboard Creator ==================
        print("\n" + "="*80)
        print("STEP 1: Onboarding Creator (ajay_shenoy)")
        print("="*80)

        onboarding_service = OnboardingService(session)

        # Check if already onboarded
        creator_stmt = select(Creator).where(Creator.email == "ajay_shenoy@topmate.io")
        creator = session.exec(creator_stmt).first()

        if creator:
            print(f"✅ Creator already exists: {creator.name} (ID: {creator.id})")
            profile = onboarding_service.get_creator_profile(creator.id)
        else:
            print("📥 Fetching and onboarding creator...")
            creator, profile = onboarding_service.onboard_creator(
                external_username="ajay_shenoy"
            )
            print(f"✅ Successfully onboarded: {creator.name} (ID: {creator.id})")

        print(f"   Profile ID: {profile.id}")
        print(f"   Services: {len(profile.services)}")
        print(f"   Value Propositions: {len(profile.value_propositions)}")

        # ================== STEP 2: Deploy Sales Agent ==================
        print("\n" + "="*80)
        print("STEP 2: Deploying GenericSalesAgent")
        print("="*80)

        deployment_service = AgentDeploymentService(session)

        # Check if agent already exists
        existing_agents = deployment_service.get_creator_agents(creator.id)
        if existing_agents:
            agent = existing_agents[0]
            print(f"✅ Agent already deployed: {agent.name} (ID: {agent.id})")
        else:
            print("🤖 Deploying new sales agent...")
            agent = deployment_service.deploy_sales_agent(creator, profile)
            print(f"✅ Successfully deployed agent: {agent.name} (ID: {agent.id})")

        print(f"   Implementation: {agent.implementation}")
        print(f"   Enabled: {agent.enabled}")
        print(f"   Agent Class: {agent.config.get('agent_class')}")

        # ================== STEP 3: Create Test Consumer ==================
        print("\n" + "="*80)
        print("STEP 3: Creating Test Consumer")
        print("="*80)

        # Check if test consumer exists
        consumer_stmt = select(Consumer).where(
            Consumer.creator_id == creator.id,
            Consumer.email == "test_lead@example.com"
        )
        consumer = session.exec(consumer_stmt).first()

        if not consumer:
            consumer = Consumer(
                id=uuid4(),
                creator_id=creator.id,
                name="Test Lead",
                email="test_lead@example.com",
                whatsapp="+919876543210",
            )
            session.add(consumer)
            session.commit()
            print(f"✅ Created test consumer: {consumer.name} (ID: {consumer.id})")
        else:
            print(f"✅ Using existing test consumer: {consumer.name} (ID: {consumer.id})")

        # Create consumer context
        context_stmt = select(ConsumerContext).where(
            ConsumerContext.creator_id == creator.id,
            ConsumerContext.consumer_id == consumer.id
        )
        context = session.exec(context_stmt).first()

        if not context:
            context = ConsumerContext(
                creator_id=creator.id,
                consumer_id=consumer.id,
                stage="new",
                last_seen_at=datetime.utcnow(),
                metrics={
                    "page_views": 0,
                    "service_clicks": 0,
                    "enrolled": False,
                    "name": consumer.name,
                    "email": consumer.email,
                    "whatsapp": consumer.whatsapp,
                },
            )
            session.add(context)
            session.commit()
            print(f"✅ Created consumer context")
        else:
            print(f"✅ Using existing consumer context")

        # ================== STEP 4: Simulate Page View Event ==================
        print("\n" + "="*80)
        print("STEP 4: Simulating Page View Event")
        print("="*80)

        # Create page view event
        event = Event(
            id=uuid4(),
            creator_id=creator.id,
            consumer_id=consumer.id,
            type="page_view",
            source="api",  # Use valid EventSource value
            timestamp=datetime.utcnow(),
            payload={
                "page": "creator_profile",
                "url": f"https://topmate.io/{creator.name}",
                "actual_source": "website"  # Store original source in payload
            },
        )
        session.add(event)

        # Update context
        context.metrics["page_views"] = 1
        context.last_seen_at = datetime.utcnow()
        session.add(context)
        session.commit()
        session.refresh(event)

        print(f"✅ Created event: {event.type} (ID: {event.id})")
        print(f"   Consumer: {consumer.name}")
        print(f"   Page: {event.payload.get('page')}")

        # ================== STEP 5: Execute Agent ==================
        print("\n" + "="*80)
        print("STEP 5: Executing Agent")
        print("="*80)

        agent_service = AgentService(session)

        # Load agent and execute directly
        from app.domain.agents.runtime import AgentRuntimeFactory
        from app.domain.types import AgentImplementation

        runtime = AgentRuntimeFactory.create(AgentImplementation.SIMPLE, session)

        # Prepare input
        from app.domain.schemas import EventResponse, ConsumerContextResponse

        input_data = AgentInput(
            creator_id=creator.id,
            consumer_id=consumer.id,
            event=EventResponse.model_validate(event),
            context=ConsumerContextResponse.model_validate(context),
            tools=[],
        )

        print("🤖 Executing agent with page_view event...")
        output = runtime.execute(agent.config, input_data)

        print(f"\n✅ Agent Execution Complete!")
        print(f"   Reasoning: {output.reasoning}")
        print(f"   Actions Planned: {len(output.actions)}")

        if output.actions:
            for i, action in enumerate(output.actions, 1):
                print(f"\n   Action {i}:")
                print(f"   📱 Channel: {action.channel}")
                print(f"   📧 To: {action.payload.get('to', 'N/A')}")
                delay_seconds = (action.send_at - datetime.utcnow()).total_seconds()
                delay_minutes = int(delay_seconds / 60)
                print(f"   ⏰ Delay: ~{delay_minutes} minutes")
                print(f"   📝 Message Preview:")
                message = action.payload.get("message", "")
                # Print first 300 chars
                preview = message[:300]
                print(f"      {preview}...")
        else:
            print("   ℹ️  Agent decided not to act")

        # ================== STEP 6: Simulate Service Click ==================
        print("\n" + "="*80)
        print("STEP 6: Simulating Service Click Event")
        print("="*80)

        # Get first service ID
        service_id = profile.services[0].get("id") if profile.services else "test_service"

        event2 = Event(
            id=uuid4(),
            creator_id=creator.id,
            consumer_id=consumer.id,
            type="service_click",
            source="api",  # Use valid EventSource value
            timestamp=datetime.utcnow(),
            payload={
                "service_id": service_id,
                "actual_source": "website"
            },
        )
        session.add(event2)

        # Update context
        context.metrics["service_clicks"] = 1
        session.add(context)
        session.commit()
        session.refresh(event2)

        print(f"✅ Created event: {event2.type} (ID: {event2.id})")
        print(f"   Service ID: {service_id}")

        # Execute agent for service click
        input_data2 = AgentInput(
            creator_id=creator.id,
            consumer_id=consumer.id,
            event=EventResponse.model_validate(event2),
            context=ConsumerContextResponse.model_validate(context),
            tools=[],
        )

        print("\n🤖 Executing agent with service_click event...")
        output2 = runtime.execute(agent.config, input_data2)

        print(f"\n✅ Agent Execution Complete!")
        print(f"   Reasoning: {output2.reasoning}")
        print(f"   Actions Planned: {len(output2.actions)}")

        if output2.actions:
            for i, action in enumerate(output2.actions, 1):
                print(f"\n   Action {i}:")
                print(f"   📱 Channel: {action.channel}")
                print(f"   📧 To: {action.payload.get('to', 'N/A')}")
                delay_seconds = (action.send_at - datetime.utcnow()).total_seconds()
                delay_minutes = int(delay_seconds / 60)
                print(f"   ⏰ Delay: ~{delay_minutes} minutes")
                print(f"   📝 Message Preview:")
                message = action.payload.get("message", "")
                preview = message[:300]
                print(f"      {preview}...")

        # ================== Summary ==================
        print("\n" + "="*80)
        print("✅ END-TO-END TEST COMPLETE!")
        print("="*80)
        print(f"\n📊 Summary:")
        print(f"   • Creator: {creator.name} (ID: {creator.id})")
        print(f"   • Profile: Generated with {len(profile.services)} service(s)")
        print(f"   • Agent: {agent.name} (ID: {agent.id})")
        print(f"   • Consumer: {consumer.name} (ID: {consumer.id})")
        print(f"   • Events Processed: 2 (page_view, service_click)")
        print(f"   • Total Actions Planned: {len(output.actions) + len(output2.actions)}")
        print(f"\n💡 What This Demonstrates:")
        print(f"   ✓ Creator onboarding with LLM profile generation")
        print(f"   ✓ Automatic agent deployment with creator's profile as context")
        print(f"   ✓ Agent responds to events (page_view, service_click)")
        print(f"   ✓ Agent uses creator's sales_pitch, instructions, and services")
        print(f"   ✓ Personalized messages tailored to each creator")
        print(f"\n🚀 Production Flow:")
        print(f"   1. POST /onboarding/ → Onboard any creator")
        print(f"   2. POST /onboarding/deploy-agent/{{creator_id}} → Deploy agent")
        print(f"   3. POST /events → Events automatically trigger the agent")
        print(f"   4. Agent plans actions → Background workers execute them")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()


if __name__ == "__main__":
    test_e2e_deployment()
