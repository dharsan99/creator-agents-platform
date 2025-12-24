"""Deploy MainAgent - Global Supervisor Agent.

This script deploys a single global MainAgent that orchestrates workflows
for all creators, regardless of purpose.

Usage:
    python scripts/deploy_main_agent.py

What it does:
1. Checks if MainAgent already exists
2. Creates MainAgent with appropriate triggers
3. Enables MainAgent for orchestration events
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select

from app.infra.db.connection import get_session
from app.infra.db.models import Agent, AgentTrigger


def deploy_main_agent(session: Session) -> Agent:
    """Deploy or update the global MainAgent.

    Args:
        session: Database session

    Returns:
        MainAgent instance
    """
    # Check if MainAgent already exists
    statement = select(Agent).where(Agent.name == "MainAgent")
    existing = session.exec(statement).first()

    if existing:
        print(f"✓ MainAgent already exists (ID: {existing.id})")
        print(f"  Enabled: {existing.enabled}")
        print(f"  Created: {existing.created_at}")
        return existing

    # Create MainAgent
    print("Creating global MainAgent...")

    main_agent = Agent(
        creator_id=None,  # Global agent (not tied to specific creator)
        name="MainAgent",
        implementation="simple",
        config={
            "agent_class": "app.agents.main_agent:MainAgent",
            "description": "Global supervisor agent for workflow orchestration",
            "purpose": "orchestration",
            "capabilities": [
                "workflow_planning",
                "tool_discovery",
                "task_delegation",
                "metric_monitoring",
                "dynamic_adjustment"
            ]
        },
        enabled=True,
    )

    session.add(main_agent)
    session.flush()  # Get ID before creating triggers

    # Create triggers for orchestration events
    orchestration_events = [
        "creator_onboarded",       # Initialize workflow for new creator
        "workflow_metric_update",  # Adjust workflow based on metrics
        "worker_task_completed",   # Check if stage is complete
        "workflow_state_change",   # Handle state transitions
    ]

    for event_type in orchestration_events:
        trigger = AgentTrigger(
            agent_id=main_agent.id,
            event_type=event_type,
            filter=None,  # No filter - MainAgent sees all orchestration events
        )
        session.add(trigger)
        print(f"  ✓ Created trigger for: {event_type}")

    session.commit()
    session.refresh(main_agent)

    print(f"\n✅ MainAgent deployed successfully!")
    print(f"   ID: {main_agent.id}")
    print(f"   Triggers: {len(orchestration_events)}")
    print(f"   Status: {'Enabled' if main_agent.enabled else 'Disabled'}")

    return main_agent


def main():
    """Main entry point."""
    print("=" * 60)
    print("MainAgent Deployment Script")
    print("=" * 60)
    print()

    try:
        # Get database session
        session = next(get_session())

        # Deploy MainAgent
        main_agent = deploy_main_agent(session)

        # Summary
        print("\n" + "=" * 60)
        print("Deployment Summary")
        print("=" * 60)
        print(f"MainAgent ID: {main_agent.id}")
        print(f"Implementation: {main_agent.implementation}")
        print(f"Agent Class: {main_agent.config['agent_class']}")
        print(f"Enabled: {main_agent.enabled}")
        print()
        print("MainAgent is ready to orchestrate workflows!")
        print()
        print("Next steps:")
        print("1. Ensure Redpanda consumer services are running")
        print("2. Monitor logs for MainAgent activity")
        print("3. Test with a creator_onboarded event")
        print()

    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
