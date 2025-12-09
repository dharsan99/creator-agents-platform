"""Test onboarding with Ajay Shenoy."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, create_engine
from app.config import settings
from app.domain.onboarding.service import OnboardingService

def test_onboarding():
    """Test onboarding Ajay Shenoy."""
    print("="*60)
    print("Testing Onboarding for Ajay Shenoy")
    print("="*60)

    # Create engine and session
    engine = create_engine(settings.database_url)
    session = Session(engine)

    try:
        # Create onboarding service
        service = OnboardingService(session)

        # Onboard Ajay Shenoy
        print("\n📥 Fetching Ajay Shenoy's data from Topmate API...")
        creator, profile = service.onboard_creator(
            external_username="ajay_shenoy"
        )

        print("\n✅ Onboarding successful!")
        print(f"\n📋 Creator Details:")
        print(f"   ID: {creator.id}")
        print(f"   Name: {creator.name}")
        print(f"   Email: {creator.email}")

        print(f"\n📋 Profile Highlights:")
        print(f"   External Username: {profile.external_username}")
        print(f"   Services: {len(profile.services)} service(s)")
        print(f"   Value Propositions: {len(profile.value_propositions)}")

        print(f"\n📝 LLM Summary (first 500 chars):")
        print(f"   {profile.llm_summary[:500]}...")

        print(f"\n💡 Sales Pitch (first 500 chars):")
        print(f"   {profile.sales_pitch[:500]}...")

        print(f"\n🎯 Target Audience:")
        print(f"   {profile.target_audience_description[:500]}...")

        print(f"\n✨ Value Propositions:")
        for i, vp in enumerate(profile.value_propositions[:5], 1):
            print(f"   {i}. {vp}")

        print(f"\n💼 Services:")
        for i, service in enumerate(profile.services[:3], 1):
            print(f"   {i}. {service.get('name', 'Unknown')}")
            print(f"      Type: {service.get('type', 'N/A')}")
            print(f"      Price: {service.get('pricing', 'N/A')}")

        print(f"\n🤖 Agent Instructions (first 300 chars):")
        print(f"   {profile.agent_instructions[:300]}...")

        print(f"\n🛡️  Objection Handling:")
        for i, (objection, response) in enumerate(list(profile.objection_handling.items())[:2], 1):
            print(f"   {i}. Objection: {objection}")
            print(f"      Response: {response[:200]}...")

        print(f"\n⭐ Ratings:")
        print(f"   {profile.ratings}")

        print(f"\n👥 Social Proof:")
        print(f"   {profile.social_proof}")

        print("\n" + "="*60)
        print("✅ Test completed successfully!")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Error during onboarding: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    test_onboarding()
