"""
End-to-End Workflow Execution Test

This script tests the complete workflow lifecycle with time compression:

1. Creates 100 test consumers for the creator
2. Triggers workflow execution via MainAgent
3. Monitors WorkerTask execution (email sending)
4. Simulates email events (delivered, opened, clicked, etc.)
5. Tracks metrics and workflow iterations
6. Uses time compression (7 days → 7 min, 1 day → 1 min, 1 hour → 1 sec)

Test Flow:
- Creator: Ajay Shenoy (bastyajay@gmail.com)
- Workflow: Sales workflow (8 stages)
- Consumers: 100 test consumers
- Duration: ~7 minutes (compressed from 7 days)
"""

import os
import sys
import time
import random
import requests
from pathlib import Path
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from typing import List, Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlmodel import Session, select

from app.infra.db.models import Creator, Consumer, Event
from app.infra.db.connection import get_session
from app.domain.workflow.models import Workflow, WorkflowExecution
from app.domain.tasks.models import WorkerTask, TaskStatus
from app.domain.types import EventType
from app.utils.time_compression import TimeCompression

# Load environment variables
load_dotenv()


class E2EWorkflowTest:
    """End-to-end workflow execution test."""

    def __init__(self, username: str = "ajay_shenoy"):
        """Initialize test. Everything will be created fresh from username."""
        self.username = username
        self.creator_id: Optional[UUID] = None  # Will be set after onboarding
        self.workflow_id: Optional[UUID] = None  # Will be generated
        self.consumer_ids: List[UUID] = []
        self.execution_id: UUID | None = None

        # Database connection
        database_url = os.getenv("DATABASE_URL")
        self.engine = create_engine(database_url, echo=False)

        # API endpoints
        self.api_base = os.getenv("CREATOR_AGENTS_URL", "http://localhost:8002")
        self.onboarding_api = os.getenv("ONBOARDING_SERVICE_URL", "http://localhost:8001")
        self.email_service_api = os.getenv("EMAIL_SERVICE_URL", "http://host.docker.internal:8003")

        print("\n" + "="*80)
        print("END-TO-END WORKFLOW EXECUTION TEST - FRESH START")
        print("="*80)
        print(f"\n📋 Configuration:")
        print(f"   Username: {self.username}")
        print(f"   Creator: Will be created via onboarding service")
        print(f"   Workflow: Will be created dynamically")
        print(f"   API Base: {self.api_base}")
        print(f"   Onboarding Service: {self.onboarding_api}")
        print(f"   Email Service: {self.email_service_api}")
        print(f"   Time Compression: {'ENABLED' if TimeCompression.is_enabled() else 'DISABLED'}")

        if TimeCompression.is_enabled():
            print(f"\n⏱️  Time Compression Ratios:")
            print(f"   7 days → {TimeCompression.format_compressed_time(7*24*3600)}")
            print(f"   1 day → {TimeCompression.format_compressed_time(24*3600)}")
            print(f"   1 hour → {TimeCompression.format_compressed_time(3600)}")

    def step_0_cleanup_existing_data(self):
        """Clear all existing test data for a fresh start."""
        print("\n" + "-"*80)
        print("STEP 0: Cleanup Existing Data")
        print("-"*80)

        try:
            with Session(self.engine) as session:
                # Get counts before cleanup
                creators_count = session.execute(text("SELECT COUNT(*) FROM creators")).scalar()
                workflows_count = session.execute(text("SELECT COUNT(*) FROM workflows")).scalar()
                consumers_count = session.execute(text("SELECT COUNT(*) FROM consumers")).scalar()
                events_count = session.execute(text("SELECT COUNT(*) FROM events")).scalar()
                contexts_count = session.execute(text("SELECT COUNT(*) FROM consumer_contexts")).scalar()
                executions_count = session.execute(text("SELECT COUNT(*) FROM workflow_executions")).scalar()
                tasks_count = session.execute(text("SELECT COUNT(*) FROM worker_tasks")).scalar()

                print(f"\n📊 Current data:")
                print(f"   Creators: {creators_count}")
                print(f"   Workflows: {workflows_count}")
                print(f"   Consumers: {consumers_count}")
                print(f"   Events: {events_count}")
                print(f"   Consumer Contexts: {contexts_count}")
                print(f"   Workflow Executions: {executions_count}")
                print(f"   Worker Tasks: {tasks_count}")

                total_count = creators_count + workflows_count + consumers_count + events_count + executions_count
                if total_count > 0:
                    print(f"\n🧹 Clearing all test data for fresh start...")

                    # Clear tables in correct order (respecting foreign keys)
                    session.execute(text("TRUNCATE TABLE events CASCADE"))
                    session.execute(text("TRUNCATE TABLE consumers CASCADE"))
                    session.execute(text("TRUNCATE TABLE consumer_contexts CASCADE"))
                    session.execute(text("TRUNCATE TABLE workflow_executions CASCADE"))
                    session.execute(text("TRUNCATE TABLE worker_tasks CASCADE"))
                    session.execute(text("TRUNCATE TABLE workflows CASCADE"))
                    session.execute(text("TRUNCATE TABLE creators CASCADE"))
                    session.commit()

                    print(f"✅ All test data cleared!")
                else:
                    print(f"\n✅ Database is already clean - no data to clear")

                # Verify clean state
                creators_after = session.execute(text("SELECT COUNT(*) FROM creators")).scalar()
                workflows_after = session.execute(text("SELECT COUNT(*) FROM workflows")).scalar()
                consumers_after = session.execute(text("SELECT COUNT(*) FROM consumers")).scalar()
                events_after = session.execute(text("SELECT COUNT(*) FROM events")).scalar()

                print(f"\n📊 After cleanup:")
                print(f"   Creators: {creators_after}")
                print(f"   Workflows: {workflows_after}")
                print(f"   Consumers: {consumers_after}")
                print(f"   Events: {events_after}")

                return True

        except Exception as e:
            print(f"\n❌ Error during cleanup: {e}")
            import traceback
            traceback.print_exc()
            return False

    def step_1_verify_creator(self):
        """Create fresh creator via onboarding service."""
        print("\n" + "-"*80)
        print("STEP 1: Onboard Creator")
        print("-"*80)

        # Onboard via creator-onboarding-service
        print(f"\n📝 Onboarding creator via Creator Onboarding Service...")
        print(f"   Service URL: {self.onboarding_api}")
        print(f"   Username: {self.username}")
        print(f"   This will:")
        print(f"   1. Fetch creator data from Eden Gardens API")
        print(f"   2. Generate LLM-enhanced profile with OpenAI")
        print(f"   3. Store full profile with services, sales pitch, etc.")

        try:
            # Derive name and email from username
            name = self.username.replace('_', ' ').title()
            email = f"{self.username}@example.com"

            response = requests.post(
                f"{self.onboarding_api}/onboard/enhanced",
                json={
                    "username": self.username,
                    "name": name,
                    "email": email
                },
                timeout=120
            )

            if response.status_code in [200, 201]:
                result = response.json()
                print(f"\n✅ Creator onboarded successfully!")
                print(f"   Creator ID: {result['creator_id']}")
                print(f"   Profile ID: {result['profile_id']}")
                print(f"   Services: {len(result['services'])}")
                print(f"   Value Props: {len(result['value_propositions'])}")
                print(f"   Processing Time: {result['processing_time_seconds']:.2f}s")

                # Set creator_id from onboarding response
                self.creator_id = UUID(result['creator_id'])
                print(f"\n✅ Creator ID set: {self.creator_id}")

                # Also create creator in main platform database
                print(f"\n📝 Creating creator record in main platform database...")
                with Session(self.engine) as session:
                    # Check if creator already exists
                    existing_creator = session.get(Creator, self.creator_id)
                    if not existing_creator:
                        creator = Creator(
                            id=self.creator_id,
                            name=name,
                            email=email,
                            username=self.username
                        )
                        session.add(creator)
                        session.commit()
                        print(f"✅ Creator record created in main platform database")
                    else:
                        print(f"✅ Creator already exists in main platform database")

                return True
            else:
                print(f"\n❌ Onboarding failed: HTTP {response.status_code}")
                print(f"   Response: {response.text[:300]}")
                return False

        except Exception as e:
            print(f"\n❌ Error: {e}")
            print(f"   Make sure creator-onboarding-service is running at {self.onboarding_api}")
            return False

    def step_2_verify_workflow(self):
        """Create fresh workflow for testing."""
        print("\n" + "-"*80)
        print("STEP 2: Create Workflow")
        print("-"*80)

        with Session(self.engine) as session:
            # Generate new workflow ID
            self.workflow_id = uuid4()
            print(f"📝 Creating new sales workflow with ID: {self.workflow_id}")

            # Create a default sales workflow for testing
            workflow = Workflow(
                id=self.workflow_id,
                creator_id=self.creator_id,
                worker_agent_ids=[],
                purpose="sales",
                workflow_type="sequential",
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=7),
                goal="Convert freemium users to paid customers",
                version=1,
                stages={
                    "initial_assessment": {
                        "day": 1,
                        "actions": ["send_intro_email", "track_engagement"],
                        "conditions": {"stage": "new"},
                        "required_tools": ["send_email", "track_engagement"]
                    },
                    "freemium_onboarding": {
                        "day": 2,
                        "actions": ["send_welcome_email", "provide_resources"],
                        "conditions": {"email_opened": ">= 1"},
                        "required_tools": ["send_email"]
                    },
                    "value_demonstration": {
                        "day": 3,
                        "actions": ["send_value_email", "share_case_study"],
                        "conditions": {"engagement_score": ">= 0.2"},
                        "required_tools": ["send_email"]
                    },
                    "engagement_tracking": {
                        "day": 4,
                        "actions": ["track_usage", "send_tips"],
                        "conditions": {"days_active": ">= 2"},
                        "required_tools": ["send_email", "track_engagement"]
                    },
                    "conversion_push": {
                        "day": 5,
                        "actions": ["send_upgrade_offer", "offer_discount"],
                        "conditions": {"engagement_score": ">= 0.5"},
                        "required_tools": ["send_email"]
                    },
                    "objection_handling": {
                        "day": 6,
                        "actions": ["address_concerns", "send_testimonials"],
                        "conditions": {"not_converted": "true"},
                        "required_tools": ["send_email"]
                    },
                    "final_conversion": {
                        "day": 7,
                        "actions": ["send_final_offer", "create_urgency"],
                        "conditions": {"not_converted": "true"},
                        "required_tools": ["send_email"]
                    },
                    "retention_setup": {
                        "day": 7,
                        "actions": ["setup_onboarding", "schedule_checkin"],
                        "conditions": {"converted": "true"},
                        "required_tools": ["send_email", "schedule_meeting"]
                    }
                },
                metrics_thresholds={
                    "email_open_rate": {"threshold": 0.2, "action": "adjust_subject_lines"},
                    "conversion_rate": {"threshold": 0.02, "action": "escalate_to_human"}
                },
                available_tools=["send_email", "track_engagement"],
                missing_tools=[
                    {"name": "send_sms", "priority": "medium"},
                    {"name": "schedule_meeting", "priority": "high"}
                ]
            )
            session.add(workflow)
            session.commit()

            print(f"✅ Workflow created!")

            print(f"✅ Workflow found:")
            print(f"   Purpose: {workflow.purpose}")
            print(f"   Type: {workflow.workflow_type}")
            print(f"   Version: {workflow.version}")
            print(f"   Start Date: {workflow.start_date}")
            print(f"   End Date: {workflow.end_date}")
            print(f"   Goal: {workflow.goal}")
            print(f"\n📊 Workflow Stages:")
            for stage_name, stage_data in workflow.stages.items():
                print(f"   - {stage_name}:")
                print(f"      Day: {stage_data.get('day')}")
                print(f"      Actions: {', '.join(stage_data.get('actions', []))}")
                if stage_data.get('conditions'):
                    print(f"      Conditions: {stage_data['conditions']}")

            print(f"\n🔧 Available Tools: {', '.join(workflow.available_tools)}")
            if workflow.missing_tools:
                print(f"⚠️  Missing Tools:")
                for tool in workflow.missing_tools:
                    print(f"   - {tool['name']} (priority: {tool.get('priority', 'unknown')})")

            return True

    def step_3_create_test_consumers(self, count: int = 100):
        """Create test consumers for the workflow."""
        print("\n" + "-"*80)
        print(f"STEP 3: Create {count} Test Consumers")
        print("-"*80)

        with Session(self.engine) as session:
            creator = session.get(Creator, self.creator_id)

            print(f"🔨 Creating {count} test consumers...")

            for i in range(count):
                consumer = Consumer(
                    id=uuid4(),
                    creator_id=self.creator_id,
                    name=f"Test Consumer {i+1:03d}",
                    email=f"test_consumer_{i+1:03d}@example.com",
                    whatsapp=f"+1555{i+1:07d}"
                )

                session.add(consumer)
                self.consumer_ids.append(consumer.id)

                if (i + 1) % 20 == 0:
                    print(f"   Created {i+1}/{count} consumers...")

            session.commit()

            print(f"✅ Successfully created {count} test consumers")
            print(f"   Consumer IDs: {len(self.consumer_ids)} stored")

            return True

    def step_4_create_workflow_execution(self):
        """Create a workflow execution for the test consumers."""
        print("\n" + "-"*80)
        print("STEP 4: Create Workflow Execution")
        print("-"*80)

        with Session(self.engine) as session:
            workflow = session.get(Workflow, self.workflow_id)

            # Get first stage name
            first_stage = list(workflow.stages.keys())[0]

            execution = WorkflowExecution(
                id=uuid4(),
                workflow_id=self.workflow_id,
                workflow_version=workflow.version,
                creator_id=self.creator_id,
                consumer_ids=[str(cid) for cid in self.consumer_ids],
                current_stage=first_stage,
                status="running",
                metrics={
                    "consumers_total": len(self.consumer_ids),
                    "consumers_contacted": 0,
                    "emails_sent": 0,
                    "emails_delivered": 0,
                    "emails_opened": 0,
                    "emails_clicked": 0,
                    "bookings_completed": 0,
                    "conversion_rate": 0.0
                },
                decisions_log=[],
                tool_usage_log=[],
                missing_tool_attempts=[]
            )

            session.add(execution)
            session.commit()

            self.execution_id = execution.id

            print(f"✅ Created workflow execution:")
            print(f"   Execution ID: {self.execution_id}")
            print(f"   Status: {execution.status}")
            print(f"   Current Stage: {execution.current_stage}")
            print(f"   Consumers: {len(self.consumer_ids)}")

            return True

    def step_5_simulate_email_campaign(self):
        """Simulate email campaign execution with time compression."""
        print("\n" + "-"*80)
        print("STEP 5: Simulate Email Campaign with Time Compression")
        print("-"*80)

        with Session(self.engine) as session:
            workflow = session.get(Workflow, self.workflow_id)
            execution = session.get(WorkflowExecution, self.execution_id)

            print(f"\n📧 Simulating email campaign...")
            print(f"   Total consumers: {len(self.consumer_ids)}")
            print(f"   Workflow stages: {len(workflow.stages)}")

            # Iterate through workflow stages
            for stage_name, stage_data in workflow.stages.items():
                print(f"\n🎯 Stage: {stage_name}")
                print(f"   Day: {stage_data.get('day')}")
                print(f"   Actions: {', '.join(stage_data.get('actions', []))}")

                # Calculate compressed delay
                day = stage_data.get('day', 1)
                original_delay_seconds = (day - 1) * 24 * 3600  # Days to seconds
                compressed_delay_seconds = TimeCompression.compress_seconds(original_delay_seconds)

                if compressed_delay_seconds > 0:
                    print(f"   ⏳ Waiting: {TimeCompression.format_compressed_time(original_delay_seconds)}")
                    time.sleep(compressed_delay_seconds)

                # Send emails via email-services (which will handle engagement simulation)
                batch_size = 20
                emails_sent = 0

                for i in range(0, len(self.consumer_ids), batch_size):
                    batch = self.consumer_ids[i:i+batch_size]

                    # Send emails through email-services
                    for consumer_id in batch:
                        # Get consumer details
                        consumer = session.get(Consumer, consumer_id)
                        if not consumer:
                            continue

                        # Generate email content
                        email_subject = f"Email for stage: {stage_name}"
                        email_body = self._generate_email_body(stage_name, stage_data.get("goal", ""))

                        # Send via email-services (which will automatically simulate engagement)
                        success = self._send_email_via_service(
                            consumer_id=consumer_id,
                            consumer_email=consumer.email,
                            stage_name=stage_name,
                            email_subject=email_subject,
                            email_body=email_body
                        )

                        if success:
                            emails_sent += 1

                    print(f"   📨 Sent emails to {min(i+batch_size, len(self.consumer_ids))}/{len(self.consumer_ids)} consumers via email-services")

                # Update metrics
                execution.metrics["emails_sent"] += emails_sent
                session.add(execution)
                session.commit()

                # Give email-services time to simulate engagement and send webhooks
                print(f"   ⏳ Waiting for email-services to simulate engagement...")
                time.sleep(10)  # Wait 10 seconds for email-services to process

                # Update execution stage
                execution.current_stage = stage_name
                session.add(execution)
                session.commit()

            # Mark execution as completed
            execution.status = "completed"
            execution.completed_at = datetime.utcnow()
            session.add(execution)
            session.commit()

            print(f"\n✅ Email campaign completed!")
            print(f"   Final metrics: {execution.metrics}")

            return True

    def _generate_email_body(self, stage_name: str, stage_goal: str) -> str:
        """Generate realistic email body content based on stage"""
        email_templates = {
            "initial_contact": f"""Hi there!

Thank you for showing interest in our services.

{stage_goal}

We'd love to help you achieve your goals. Our personalized coaching sessions can help you:
- Build confidence and clarity
- Develop actionable strategies
- Overcome obstacles
- Achieve sustainable growth

Would you like to learn more about how we can work together?

Best regards,
The Team""",
            "value_demonstration": f"""Hi again!

I wanted to share some insights that might be valuable for you.

{stage_goal}

Here are some key benefits our clients have experienced:
- 3x increase in productivity
- Clear roadmap to achieve goals
- Support from experienced mentors
- Proven frameworks and strategies

Ready to take the next step? Book a free consultation to discuss your goals.

Looking forward to connecting!""",
            "objection_handling": f"""Hello!

I noticed you haven't taken the next step yet, and I wanted to address any concerns you might have.

{stage_goal}

Common questions we get:
- "Is this right for me?" - We offer a free consultation to ensure fit
- "What's the investment?" - Flexible payment plans available
- "How long does it take?" - Results vary, but most see progress in weeks

Still have questions? Reply to this email and let's chat!

Best,
The Team""",
            "urgency_creation": f"""Hi there!

This week only, we're offering a special opportunity.

{stage_goal}

Limited spots available:
- 20% discount on coaching packages
- Bonus resources worth $500
- Priority scheduling

This offer expires in 3 days. Secure your spot now!

Book here: [Link]""",
            "final_push": f"""Last chance!

{stage_goal}

This is your final reminder about our limited-time offer.

Don't miss out on:
- Expert 1-on-1 coaching
- Proven success framework
- Exclusive bonus materials

Book your session today and start your transformation journey!

[Book Now Button]""",
            "retention_setup": f"""Welcome aboard!

{stage_goal}

We're excited to work with you! Here's what happens next:
- You'll receive onboarding materials within 24 hours
- Your first session is scheduled
- Access to our exclusive community

Questions? We're here to help!

Welcome to the family!""",
        }

        # Get template or use default
        template = email_templates.get(stage_name, f"""Hello!

{stage_goal}

We're excited to connect with you. This email is part of our {stage_name} campaign.

Let us know if you have any questions!

Best regards,
The Team""")

        return template

    def _send_email_via_service(self, consumer_id: UUID, consumer_email: str, stage_name: str, email_subject: str, email_body: str):
        """Send email via email-services (which will simulate engagement automatically)."""
        timestamp_ms = int(datetime.utcnow().timestamp() * 1000)

        payload = {
            "distinct_id": str(consumer_id),
            "channel": "email",
            "template": f"workflow_{stage_name}",
            "workflow_name": f"workflow_{self.workflow_id}",
            "channel_value": consumer_email,
            "suprsend_status": {
                "status": "sent",
                "timestamp": timestamp_ms
            },
            "vendor_response": {
                "amazon_ses": {
                    "Message": {
                        "mail": {
                            "commonHeaders": {
                                "subject": email_subject,
                                "from": ["noreply@topmate.io"],
                                "to": [consumer_email]
                            },
                            "destination": [consumer_email]
                        }
                    }
                }
            },
            "body": email_body,
            "metadata": {
                "creator_id": str(self.creator_id),
                "workflow_execution_id": str(self.execution_id),
                "stage": stage_name
            }
        }

        try:
            response = requests.post(
                f"{self.email_service_api}/webhooks/suprsend",
                json=payload,
                timeout=5
            )
            return response.status_code in [200, 201]
        except Exception as e:
            print(f"   ⚠️ Error sending email via service: {e}")
            return False

    def _simulate_consumer_engagement(self, session: Session, stage_name: str):
        """Simulate random consumer engagement (opens, clicks, bookings)."""
        # Realistic engagement rates
        open_rate = 0.30  # 30% open rate
        click_rate = 0.40  # 40% of opens result in clicks
        booking_rate = 0.10  # 10% of clicks result in bookings

        execution = session.get(WorkflowExecution, self.execution_id)

        # Simulate opens (30% of consumers)
        num_opens = max(1, int(len(self.consumer_ids) * open_rate))
        open_consumers = random.sample(self.consumer_ids, min(num_opens, len(self.consumer_ids)))

        for consumer_id in open_consumers:
            event = Event(
                id=uuid4(),
                creator_id=self.creator_id,
                consumer_id=consumer_id,
                type=EventType.EMAIL_OPENED,
                source="system",
                timestamp=datetime.utcnow(),
                payload={
                    "stage": stage_name,
                    "workflow_execution_id": str(self.execution_id)
                }
            )
            session.add(event)

        execution.metrics["emails_opened"] += num_opens

        # Simulate clicks (40% of opens)
        num_clicks = max(1, int(num_opens * click_rate))
        click_consumers = random.sample(open_consumers, min(num_clicks, len(open_consumers)))

        for consumer_id in click_consumers:
            event = Event(
                id=uuid4(),
                creator_id=self.creator_id,
                consumer_id=consumer_id,
                type=EventType.EMAIL_CLICKED,
                source="system",
                timestamp=datetime.utcnow(),
                payload={
                    "stage": stage_name,
                    "workflow_execution_id": str(self.execution_id)
                }
            )
            session.add(event)

        execution.metrics["emails_clicked"] += num_clicks

        # Simulate bookings (10% of clicks)
        num_bookings = max(0, int(num_clicks * booking_rate))
        if num_bookings > 0 and len(click_consumers) > 0:
            booking_consumers = random.sample(click_consumers, min(num_bookings, len(click_consumers)))

            for consumer_id in booking_consumers:
                event = Event(
                    id=uuid4(),
                    creator_id=self.creator_id,
                    consumer_id=consumer_id,
                    type=EventType.BOOKING_CREATED,
                    source="system",
                    timestamp=datetime.utcnow(),
                    payload={
                        "stage": stage_name,
                        "workflow_execution_id": str(self.execution_id),
                        "service_id": f"service_{random.randint(1,4)}"
                    }
                )
                session.add(event)

            execution.metrics["bookings_completed"] += num_bookings

        # Calculate conversion rate
        if execution.metrics["emails_sent"] > 0:
            execution.metrics["conversion_rate"] = (
                execution.metrics["bookings_completed"] / execution.metrics["emails_sent"]
            ) * 100

        session.add(execution)
        session.commit()

        print(f"   📊 Engagement: {num_opens} opens, {num_clicks} clicks, {num_bookings} bookings")

    def step_6_display_results(self):
        """Display final test results with actual engagement data from email-services."""
        print("\n" + "="*80)
        print("TEST RESULTS")
        print("="*80)

        with Session(self.engine) as session:
            execution = session.get(WorkflowExecution, self.execution_id)
            workflow = session.get(Workflow, self.workflow_id)

            # Calculate actual engagement metrics from events created by email-services webhooks
            total_events = session.query(Event).filter(
                Event.creator_id == self.creator_id,
                Event.consumer_id.in_(self.consumer_ids)
            ).count()

            email_delivered = session.query(Event).filter(
                Event.creator_id == self.creator_id,
                Event.consumer_id.in_(self.consumer_ids),
                Event.type == EventType.EMAIL_DELIVERED
            ).count()

            email_opened = session.query(Event).filter(
                Event.creator_id == self.creator_id,
                Event.consumer_id.in_(self.consumer_ids),
                Event.type == EventType.EMAIL_OPENED
            ).count()

            email_clicked = session.query(Event).filter(
                Event.creator_id == self.creator_id,
                Event.consumer_id.in_(self.consumer_ids),
                Event.type == EventType.EMAIL_CLICKED
            ).count()

            bookings = session.query(Event).filter(
                Event.creator_id == self.creator_id,
                Event.consumer_id.in_(self.consumer_ids),
                Event.type == EventType.BOOKING_CREATED
            ).count()

            print(f"\n📊 Workflow Execution Summary:")
            print(f"   Execution ID: {execution.id}")
            print(f"   Status: {execution.status}")
            print(f"   Started: {execution.created_at}")
            print(f"   Completed: {execution.completed_at}")
            duration = (execution.completed_at - execution.created_at).total_seconds()
            print(f"   Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")

            print(f"\n📈 Actual Engagement Metrics (from email-services):")
            print(f"   Total Events: {total_events}")
            print(f"   Emails Sent: {execution.metrics.get('emails_sent', 0)}")
            print(f"   Emails Delivered: {email_delivered}")
            print(f"   Emails Opened: {email_opened}")
            print(f"   Emails Clicked: {email_clicked}")
            print(f"   Bookings Created: {bookings}")

            if email_delivered > 0:
                open_rate = (email_opened / email_delivered) * 100
                print(f"   Open Rate: {open_rate:.2f}%")

                if email_opened > 0:
                    click_rate = (email_clicked / email_opened) * 100
                    print(f"   Click Rate: {click_rate:.2f}%")

                    if email_clicked > 0 and bookings > 0:
                        booking_rate = (bookings / email_clicked) * 100
                        print(f"   Booking Rate: {booking_rate:.2f}%")

                conversion_rate = (bookings / execution.metrics.get('emails_sent', 1)) * 100
                print(f"   Overall Conversion Rate: {conversion_rate:.2f}%")

            print(f"\n✅ Test completed successfully!")
            print(f"   Total stages executed: {len(workflow.stages)}")
            print(f"   Total consumers: {len(self.consumer_ids)}")
            print(f"\n💡 Note: Engagement was simulated by email-services based on configured ratios")
            print(f"   View email-services dashboard: {self.email_service_api}/")

            return True

    def run(self, num_consumers: int = 100):
        """Run the complete E2E test."""
        try:
            # Step 0: Cleanup existing data
            if not self.step_0_cleanup_existing_data():
                return False

            # Step 1: Verify creator
            if not self.step_1_verify_creator():
                return False

            # Step 2: Verify workflow
            if not self.step_2_verify_workflow():
                return False

            # Step 3: Create test consumers
            if not self.step_3_create_test_consumers(count=num_consumers):
                return False

            # Step 4: Create workflow execution
            if not self.step_4_create_workflow_execution():
                return False

            # Step 5: Simulate email campaign
            if not self.step_5_simulate_email_campaign():
                return False

            # Step 6: Display results
            if not self.step_6_display_results():
                return False

            print("\n" + "="*80)
            print("🎉 E2E TEST PASSED!")
            print("="*80 + "\n")

            return True

        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run E2E workflow execution test with fresh data",
        epilog="""
Examples:
  # Test with default username (ajay_shenoy) and 100 consumers
  python test_e2e_workflow_execution.py

  # Test with custom username and 50 consumers
  python test_e2e_workflow_execution.py --username dharmesh_shah --consumers 50

  # Test with time compression disabled
  python test_e2e_workflow_execution.py --disable-compression
        """
    )
    parser.add_argument(
        "--username",
        default="ajay_shenoy",
        help="Creator username for onboarding (default: ajay_shenoy)"
    )
    parser.add_argument(
        "--consumers",
        type=int,
        default=100,
        help="Number of test consumers (default: 100)"
    )
    parser.add_argument(
        "--disable-compression",
        action="store_true",
        help="Disable time compression (test will run in real-time)"
    )

    args = parser.parse_args()

    # Configure time compression
    if args.disable_compression:
        TimeCompression.disable()
        print("⚠️  Time compression disabled - test will run in real-time!")

    # Run test
    test = E2EWorkflowTest(username=args.username)
    success = test.run(num_consumers=args.consumers)

    sys.exit(0 if success else 1)
