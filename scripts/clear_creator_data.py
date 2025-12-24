"""
Clear all data for a specific creator (for E2E testing)

This script removes all associated data for a creator:
- Consumer contexts
- Events
- Actions and agent invocations
- Agent triggers and agents
- Consumers
- Creator profile and onboarding logs
- Creator record
"""

import os
import sys
from pathlib import Path
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlmodel import Session, select

from app.infra.db.models import (
    Creator, Consumer, Event, Agent, AgentTrigger,
    AgentInvocation, Action, ConsumerContext
)
from app.infra.db.creator_profile_models import CreatorProfile, OnboardingLog

# Load environment variables
load_dotenv()


def clear_creator_data(creator_id: str):
    """Clear all data for a specific creator"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable not set")

    engine = create_engine(database_url, echo=False)

    with Session(engine) as session:
        creator_uuid = UUID(creator_id)

        # Check if creator exists
        creator = session.get(Creator, creator_uuid)
        if not creator:
            print(f"❌ Creator {creator_id} not found")
            return False

        print(f"🔍 Found creator: {creator.name} ({creator.email})")
        print(f"⚠️  This will DELETE ALL data for this creator!\n")

        # Get consumer IDs first (needed for cascade deletion)
        consumers = session.exec(
            select(Consumer).where(Consumer.creator_id == creator_uuid)
        ).all()
        consumer_ids = [c.id for c in consumers]

        print(f"📊 Data to be deleted:")
        print(f"  - Consumers: {len(consumer_ids)}")

        # Count related records
        if consumer_ids:
            events_count = session.exec(
                select(Event).where(Event.consumer_id.in_(consumer_ids))
            ).all()
            print(f"  - Events: {len(events_count)}")

            contexts_count = session.exec(
                select(ConsumerContext).where(
                    ConsumerContext.consumer_id.in_(consumer_ids)
                )
            ).all()
            print(f"  - Consumer contexts: {len(contexts_count)}")

        agents = session.exec(
            select(Agent).where(Agent.creator_id == creator_uuid)
        ).all()
        print(f"  - Agents: {len(agents)}")

        profiles = session.exec(
            select(CreatorProfile).where(CreatorProfile.creator_id == creator_uuid)
        ).all()
        print(f"  - Creator profiles: {len(profiles)}")

        logs = session.exec(
            select(OnboardingLog).where(OnboardingLog.creator_id == creator_uuid)
        ).all()
        print(f"  - Onboarding logs: {len(logs)}")

        print("\n" + "="*60)

        try:
            # Delete in order (respecting foreign keys)
            # Order: actions → invocations → events → triggers → agents → contexts → consumers → profiles → logs → creator

            # 1. Delete actions (references invocations)
            print("🗑️  Deleting actions...")
            all_invocations = session.exec(
                select(AgentInvocation).where(AgentInvocation.creator_id == creator_uuid)
            ).all()

            if all_invocations:
                invocation_ids = [inv.id for inv in all_invocations]
                actions = session.exec(
                    select(Action).where(Action.agent_invocation_id.in_(invocation_ids))
                ).all()
                for action in actions:
                    session.delete(action)

            # 2. Delete agent invocations (references events and agents)
            print("🗑️  Deleting agent invocations...")
            for invocation in all_invocations:
                session.delete(invocation)

            # 3. Delete events (now safe - no FK references)
            if consumer_ids:
                print("🗑️  Deleting events...")
                events = session.exec(
                    select(Event).where(Event.consumer_id.in_(consumer_ids))
                ).all()
                for event in events:
                    session.delete(event)

            # 4. Delete consumer contexts
            if consumer_ids:
                print("🗑️  Deleting consumer contexts...")
                contexts = session.exec(
                    select(ConsumerContext).where(
                        ConsumerContext.consumer_id.in_(consumer_ids)
                    )
                ).all()
                for context in contexts:
                    session.delete(context)

            # 5. Delete agent triggers
            if agents:
                print("🗑️  Deleting agent triggers...")
                for agent in agents:
                    triggers = session.exec(
                        select(AgentTrigger).where(AgentTrigger.agent_id == agent.id)
                    ).all()
                    for trigger in triggers:
                        session.delete(trigger)

            # 6. Delete agents
            print("🗑️  Deleting agents...")
            for agent in agents:
                session.delete(agent)

            # 7. Delete worker tasks (references consumers)
            if consumer_ids:
                print("🗑️  Deleting worker tasks...")
                # Use raw SQL to avoid model foreign key validation issues
                consumer_id_strs = [str(cid) for cid in consumer_ids]
                for consumer_id in consumer_id_strs:
                    session.execute(
                        text("DELETE FROM worker_tasks WHERE consumer_id = :consumer_id"),
                        {"consumer_id": consumer_id}
                    )

            # 8. Delete consumers
            print("🗑️  Deleting consumers...")
            for consumer in consumers:
                session.delete(consumer)

            # 9. Delete creator profiles
            print("🗑️  Deleting creator profiles...")
            for profile in profiles:
                session.delete(profile)

            # 10. Delete onboarding logs
            print("🗑️  Deleting onboarding logs...")
            for log in logs:
                session.delete(log)

            # 11. Delete creator
            print("🗑️  Deleting creator...")
            session.delete(creator)

            # Commit all deletions
            session.commit()

            print("\n" + "="*60)
            print(f"✅ Successfully cleared all data for creator: {creator.name}")
            print("="*60 + "\n")

            return True

        except Exception as e:
            session.rollback()
            print(f"\n❌ Error clearing creator data: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python clear_creator_data.py <creator_id>")
        print("\nExample:")
        print("  python clear_creator_data.py 81fc4c5c-9e9e-4c44-9260-ccd468d9d1a3")
        sys.exit(1)

    creator_id = sys.argv[1]

    print("\n" + "="*60)
    print("CLEAR CREATOR DATA - E2E TESTING")
    print("="*60 + "\n")

    success = clear_creator_data(creator_id)
    sys.exit(0 if success else 1)
