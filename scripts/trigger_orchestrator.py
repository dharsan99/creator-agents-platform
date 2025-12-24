"""Trigger orchestrator to process creator_onboarded event."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.infra.db.connection import engine
from app.infra.db.models import Event, Creator
from app.domain.agents.orchestrator import Orchestrator

with Session(engine) as session:
    # Get ajay_shenoy creator
    creator = session.exec(select(Creator).where(Creator.email == "bastyajay@gmail.com")).first()
    
    if not creator:
        print("Creator not found!")
        sys.exit(1)
    
    # Get the creator_onboarded event
    event = session.exec(
        select(Event).where(
            Event.creator_id == creator.id,
            Event.type == "creator_onboarded"
        ).order_by(Event.created_at.desc())
    ).first()
    
    if not event:
        print("Event not found!")
        sys.exit(1)
    
    print(f"Processing event: {event.id}")
    print(f"Creator: {creator.name} ({creator.id})")
    print(f"Event type: {event.type}")
    
    # Process event through orchestrator
    orchestrator = Orchestrator(session)
    
    try:
        invocation_ids = orchestrator.process_event_agents(
            creator_id=event.creator_id,
            consumer_id=event.consumer_id,
            event_id=event.id
        )
        
        print(f"\n✅ Created {len(invocation_ids)} invocations")
        
        # Check if workflow was created
        from app.domain.workflow.models import Workflow
        workflows = session.exec(select(Workflow).where(Workflow.creator_id == creator.id)).all()
        
        print(f"\n✅ Workflows: {len(workflows)}")
        for wf in workflows:
            print(f"  - {wf.id}")
            print(f"    Purpose: {wf.purpose}")
            print(f"    Type: {wf.workflow_type}")
            print(f"    Goal: {wf.goal}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
