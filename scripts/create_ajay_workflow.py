"""Create workflow for ajay_shenoy."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from sqlmodel import Session, select

from app.config import settings
from app.infra.db.connection import engine
from app.infra.db.models import Creator, Consumer, Event, Agent
from app.infra.db.creator_profile_models import CreatorProfile
from app.domain.agents.orchestrator import Orchestrator
from app.infra.logging import setup_logging, set_correlation_id

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
setup_logging(use_json=False)
logger = logging.getLogger(__name__)

def main():
    logger.info("Creating workflow for ajay_shenoy...")
    
    with Session(engine) as session:
        # Check if ajay_shenoy exists
        stmt = select(CreatorProfile).where(CreatorProfile.external_username == "ajay_shenoy")
        profile = session.exec(stmt).first()
        
        if profile:
            logger.info(f"Found existing creator profile: {profile.creator_id}")
            creator = session.get(Creator, profile.creator_id)
        else:
            logger.info("Creating ajay_shenoy from eden_gardens_gcp...")
            import httpx
            
            base_url = "https://gcp.galactus.run"
            creator_data = httpx.get(f"{base_url}/creator-agents/agentscreatordetails/", params={"username": "ajay_shenoy"}, timeout=30.0).json()
            product_data = httpx.get(f"{base_url}/creator-agents/agentsproductdetails/", params={"username": "ajay_shenoy"}, timeout=30.0).json()
            
            creator = Creator(name=creator_data.get("display_name", "Ajay Shenoy"), email=creator_data.get("email"), settings={})
            session.add(creator)
            session.commit()
            session.refresh(creator)
            logger.info(f"Created creator: {creator.id}")
            
            profile = CreatorProfile(
                creator_id=creator.id,
                external_user_id=creator_data.get("user_id"),
                external_username="ajay_shenoy",
                raw_data={"creator": creator_data, "products": product_data},
                llm_summary=creator_data.get("description", ""),
                sales_pitch="AI/ML Expert with 14+ years experience, PhD from IISc, 14,616 sessions delivered",
                services=product_data.get("services", [])[:10],
                last_synced_at=datetime.utcnow(),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(profile)
            session.commit()
            logger.info(f"Created profile: {profile.id}")
        
        # Create test consumers
        consumers = []
        for i, email in enumerate(["rahul@test.com", "priya@test.com", "amit@test.com"]):
            consumer = session.exec(select(Consumer).where(Consumer.creator_id == creator.id, Consumer.email == email)).first()
            if not consumer:
                consumer = Consumer(creator_id=creator.id, name=f"Test User {i+1}", email=email, whatsapp=f"+9187654321{i}")
                session.add(consumer)
                consumers.append(consumer)
            else:
                consumers.append(consumer)
        session.commit()
        logger.info(f"Ensured {len(consumers)} consumers exist")
        
        # Get MainAgent
        agent = session.exec(select(Agent).where(Agent.name == "MainAgent")).first()
        if not agent:
            agent = Agent(name="MainAgent", implementation="simple", config={"agent_class": "app.agents.main_agent:MainAgent"}, enabled=True)
            session.add(agent)
            session.commit()
            session.refresh(agent)
            logger.info(f"Created MainAgent: {agent.id}")
        
        # Create event
        event = Event(
            creator_id=creator.id,
            consumer_id=consumers[0].id,
            type="creator_onboarded",
            source="api",
            timestamp=datetime.utcnow(),
            payload={
                "creator_id": str(creator.id),
                "worker_agent_ids": [str(agent.id)],
                "consumers": [str(c.id) for c in consumers],
                "purpose": "sales",
                "start_date": datetime.utcnow().isoformat(),
                "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                "goal": "Convert consumers through freemium funnel",
                "config": {"creator_name": "Ajay Shenoy", "campaign_type": "freemium_conversion"}
            }
        )
        session.add(event)
        session.commit()
        logger.info(f"Created event: {event.id}")
        
        # Trigger MainAgent
        logger.info("Triggering MainAgent...")
        orchestrator = Orchestrator(session)
        invocation_ids = orchestrator.process_event_agents(creator_id=event.creator_id, consumer_id=event.consumer_id, event_id=event.id)
        logger.info(f"Created {len(invocation_ids)} invocations")
        
        # Show workflow
        from app.domain.workflow.models import Workflow
        workflows = session.exec(select(Workflow).where(Workflow.creator_id == creator.id)).all()
        logger.info(f"\nWorkflows created: {len(workflows)}")
        for wf in workflows:
            logger.info(f"  - {wf.id}: {wf.purpose} ({wf.workflow_type})")
            logger.info(f"    Goal: {wf.goal}")
            logger.info(f"    Stages: {list(wf.stages.keys()) if wf.stages else []}")
        
        logger.info(f"\n✅ Workflow creation completed for ajay_shenoy!")
        logger.info(f"Creator ID: {creator.id}")

if __name__ == "__main__":
    main()
