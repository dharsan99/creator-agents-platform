"""Create consumer contexts for ajay_shenoy's consumers."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.infra.db.connection import engine
from app.infra.db.models import Creator, Consumer
from app.domain.context.service import ConsumerContextService

with Session(engine) as session:
    # Get ajay_shenoy creator
    creator = session.exec(select(Creator).where(Creator.email == "bastyajay@gmail.com")).first()
    
    if not creator:
        print("Creator not found!")
        sys.exit(1)
    
    # Get all consumers for this creator
    consumers = session.exec(select(Consumer).where(Consumer.creator_id == creator.id)).all()
    
    print(f"Creating contexts for {len(consumers)} consumers...")
    
    context_service = ConsumerContextService(session)
    
    for consumer in consumers:
        context = context_service.get_or_create_context(creator.id, consumer.id)
        print(f"✅ Context created for {consumer.name} ({consumer.email})")
        print(f"   Stage: {context.stage}, Metrics: {context.metrics}")
    
    print(f"\n✅ Created {len(consumers)} consumer contexts")
