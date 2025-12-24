"""WorkerAgent - Base class for worker agents that execute delegated tasks.

Worker agents receive tasks from MainAgent via Redpanda, execute them
using available tools, and report results back.

Architecture:
- MainAgent delegates tasks → Redpanda supervisor_tasks topic
- WorkerAgent consumes tasks → Executes with tools → Reports completion
- Task results published → Redpanda task_results topic
- MainAgent receives results → Updates workflow

Key Features:
- Task routing based on task_type
- Tool calling for execution
- LLM-based content generation
- Error handling with retry logic
- Escalation to human when needed
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlmodel import Session

from app.domain.agents.base_agent import BaseAgent
from app.domain.schemas import PlannedAction
from app.domain.tasks.models import WorkerTask, TaskStatus
from app.domain.tasks.service import TaskService
from app.domain.tools.registry import get_registry
from app.domain.types import Channel, ActionType
from app.infra.db.models import ConsumerContext, Event

logger = logging.getLogger(__name__)


class WorkerAgent(BaseAgent):
    """Base class for worker agents that execute delegated tasks.

    Worker agents are specialized agents that receive task assignments
    from MainAgent and execute them using available tools. Each worker
    can be specialized for different channels or capabilities:

    - EmailWorker: Email campaigns and follow-ups
    - WhatsAppWorker: WhatsApp messaging
    - AnalyticsWorker: Metrics collection and reporting
    - ContentWorker: Content generation and scheduling

    The worker handles:
    1. Receiving tasks from Redpanda
    2. Routing to task-specific handlers
    3. Executing tasks with tools
    4. Reporting completion/failure
    5. Escalating complex scenarios to humans

    Usage:
        class EmailWorker(WorkerAgent):
            def handle_create_intro_email(self, task: WorkerTask):
                # Custom email logic
                ...

        worker = EmailWorker(config, session)
        actions = worker.plan_actions(context, task_assigned_event)
    """

    def __init__(self, agent_config: dict, session: Session):
        """Initialize worker agent.

        Args:
            agent_config: Agent configuration
            session: Database session
        """
        super().__init__(agent_config)
        self.session = session
        self.task_service = TaskService(session)
        self.tool_registry = get_registry()
        self.llm = ChatOpenAI(model="gpt-4-turbo-preview", temperature=0.8)

        logger.info(
            f"WorkerAgent initialized: {self.config.get('name', 'UnnamedWorker')}",
            extra={"config": agent_config}
        )

    def should_act(self, context: ConsumerContext, event: Event) -> bool:
        """Decide if worker should act on this event.

        Workers act on worker_task_assigned events.

        Args:
            context: Consumer context
            event: Triggering event

        Returns:
            True if this is a task assignment event
        """
        return event.type == "worker_task_assigned"

    def plan_actions(
        self,
        context: ConsumerContext,
        event: Event
    ) -> List[PlannedAction]:
        """Execute task based on type.

        This is the main entry point for worker task execution:
        1. Extract task_id from event payload
        2. Load WorkerTask from database
        3. Mark task as in_progress
        4. Route to task-specific handler
        5. Generate completion action

        Args:
            context: Consumer context
            event: Task assignment event

        Returns:
            List of planned actions (task completion report)
        """
        try:
            # Extract task_id from event payload
            task_id = UUID(event.payload.get("task_id"))

            # Load task
            task = self.task_service.get_task(task_id)

            if not task:
                logger.error(f"Task not found: {task_id}")
                return []

            # Mark task as in progress
            self.task_service.mark_in_progress(task.id)

            logger.info(
                f"Processing task {task.id}",
                extra={
                    "task_id": str(task.id),
                    "task_type": task.task_type,
                    "consumer_id": str(task.consumer_id),
                }
            )

            # Route to task-specific handler
            handler_name = f"handle_{task.task_type}"
            handler = getattr(self, handler_name, None)

            if handler:
                # Execute custom handler
                result = handler(task)
            else:
                # Fallback to generic handler
                logger.warning(
                    f"No handler found for task type: {task.task_type}, using generic"
                )
                result = self.handle_generic_task(task)

            # Mark task as completed
            self.task_service.mark_completed(task.id, result)

            # Report completion to MainAgent
            return [self.report_task_completion(task, result)]

        except Exception as e:
            logger.error(
                f"Task execution failed: {str(e)}",
                exc_info=True
            )

            # Mark task as failed (will retry if retries available)
            if 'task' in locals():
                self.task_service.mark_failed(task.id, str(e), should_retry=True)

            return []

    def handle_generic_task(self, task: WorkerTask) -> Dict[str, Any]:
        """Generic task handler for unknown task types.

        This is a fallback handler that attempts to execute the task
        based on the task_payload instructions.

        Args:
            task: WorkerTask instance

        Returns:
            Task execution result
        """
        logger.info(f"Executing generic task: {task.task_type}")

        payload = task.task_payload
        actions = payload.get("actions", [])
        required_tools = payload.get("required_tools", [])
        fallback_actions = payload.get("fallback_actions", [])

        result = {
            "task_id": str(task.id),
            "task_type": task.task_type,
            "executed_at": datetime.utcnow().isoformat(),
            "actions_attempted": actions,
            "tools_available": [],
            "tools_missing": [],
            "success": False,
        }

        # Check tool availability
        available_tools = self.tool_registry.get_available_tools()

        for tool_name in required_tools:
            if tool_name in available_tools:
                result["tools_available"].append(tool_name)
            else:
                result["tools_missing"].append(tool_name)

        # If all required tools available, execute
        if not result["tools_missing"]:
            result["success"] = True
            result["message"] = f"Executed {len(actions)} actions using available tools"
        else:
            result["success"] = False
            result["message"] = f"Missing required tools: {result['tools_missing']}"
            result["fallback_actions"] = fallback_actions

        return result

    def handle_create_intro_email(self, task: WorkerTask) -> Dict[str, Any]:
        """Create and send personalized intro email.

        This is a common task type that most workers will implement.
        It demonstrates the full workflow:
        1. Get consumer context via tool
        2. Get creator profile from task payload
        3. Generate email with LLM
        4. Send email via tool
        5. Update consumer stage via tool

        Args:
            task: WorkerTask instance

        Returns:
            Task execution result
        """
        logger.info(f"Creating intro email for consumer {task.consumer_id}")

        try:
            # 1. Get consumer context via tool
            consumer_ctx_result = self.call_tool(
                "get_consumer_context",
                creator_id=UUID(task.task_payload["creator_id"]),
                consumer_id=task.consumer_id
            )

            if not consumer_ctx_result.get("success"):
                return {
                    "success": False,
                    "error": "Failed to get consumer context",
                    "tool_result": consumer_ctx_result
                }

            consumer_ctx = consumer_ctx_result["context"]

            # 2. Get creator profile from task payload
            creator_profile = task.task_payload.get("creator_profile", {})

            # 3. Generate email with LLM
            email = self.generate_email_with_llm(
                consumer_ctx,
                creator_profile,
                email_type="intro"
            )

            # 4. Send email via tool
            send_result = self.call_tool(
                "send_email",
                to=consumer_ctx.get("email"),
                subject=email["subject"],
                body=email["body"],
                creator_id=UUID(task.task_payload["creator_id"])
            )

            if not send_result.get("success"):
                return {
                    "success": False,
                    "error": "Failed to send email",
                    "email_generated": email,
                    "tool_result": send_result
                }

            # 5. Update consumer stage via tool
            stage_result = self.call_tool(
                "update_consumer_stage",
                creator_id=UUID(task.task_payload["creator_id"]),
                consumer_id=task.consumer_id,
                stage="contacted"
            )

            # Return success result
            return {
                "success": True,
                "email_sent": True,
                "message_id": send_result.get("message_id"),
                "email_subject": email["subject"],
                "consumer_stage_updated": stage_result.get("success", False),
                "tools_used": ["get_consumer_context", "send_email", "update_consumer_stage"],
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to create intro email: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def handle_create_followup_email(self, task: WorkerTask) -> Dict[str, Any]:
        """Create and send follow-up email.

        Similar to intro email but with follow-up context.

        Args:
            task: WorkerTask instance

        Returns:
            Task execution result
        """
        logger.info(f"Creating follow-up email for consumer {task.consumer_id}")

        try:
            # Get consumer context
            consumer_ctx_result = self.call_tool(
                "get_consumer_context",
                creator_id=UUID(task.task_payload["creator_id"]),
                consumer_id=task.consumer_id
            )

            if not consumer_ctx_result.get("success"):
                return {
                    "success": False,
                    "error": "Failed to get consumer context"
                }

            consumer_ctx = consumer_ctx_result["context"]
            creator_profile = task.task_payload.get("creator_profile", {})

            # Generate follow-up email
            email = self.generate_email_with_llm(
                consumer_ctx,
                creator_profile,
                email_type="followup"
            )

            # Send email
            send_result = self.call_tool(
                "send_email",
                to=consumer_ctx.get("email"),
                subject=email["subject"],
                body=email["body"],
                creator_id=UUID(task.task_payload["creator_id"])
            )

            return {
                "success": send_result.get("success", False),
                "email_sent": True,
                "message_id": send_result.get("message_id"),
                "email_subject": email["subject"],
                "tools_used": ["get_consumer_context", "send_email"],
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to create follow-up email: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def generate_email_with_llm(
        self,
        consumer_ctx: Dict[str, Any],
        creator_profile: Dict[str, Any],
        email_type: str
    ) -> Dict[str, str]:
        """Use LLM to craft personalized email.

        This method uses the creator's profile to generate emails that
        match their voice and value propositions.

        Args:
            consumer_ctx: Consumer context dict
            creator_profile: Creator profile dict
            email_type: Type of email (intro, followup, etc.)

        Returns:
            Dict with subject and body

        Example:
            email = worker.generate_email_with_llm(
                consumer_ctx={"name": "John", "email": "john@example.com"},
                creator_profile={"name": "Jane", "sales_pitch": "..."},
                email_type="intro"
            )
            # Returns: {"subject": "...", "body": "..."}
        """
        system_prompt = f"""You are a sales agent crafting personalized emails.
Use the creator's voice and value propositions to engage the consumer.

Email type: {email_type}
- intro: First contact, introduce creator and value
- followup: Follow up after engagement, address interest
- reminder: Gentle reminder about offer or deadline
"""

        user_prompt = f"""Create a personalized {email_type} email:

**Creator:**
- Name: {creator_profile.get('name', 'Creator')}
- Services: {json.dumps(creator_profile.get('services', [])[:2], indent=2)}
- Sales Pitch: {creator_profile.get('sales_pitch', 'Great value for you!')}

**Consumer:**
- Name: {consumer_ctx.get('name', 'there')}
- Context: {consumer_ctx.get('summary', 'New lead')}

**Requirements:**
- Compelling subject line (max 60 chars)
- Personalized greeting
- Value proposition highlighting benefits
- Clear CTA (call to action)
- Professional sign-off

Return JSON: {{"subject": "...", "body": "..."}}
"""

        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            content = response.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            email = json.loads(content.strip())

            logger.debug(
                f"Generated {email_type} email",
                extra={
                    "subject": email.get("subject"),
                    "consumer": consumer_ctx.get("name"),
                }
            )

            return email

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM email response: {e}")
            # Return fallback email
            return {
                "subject": f"{creator_profile.get('name')} has a message for you",
                "body": f"Hi {consumer_ctx.get('name', 'there')},\n\n{creator_profile.get('sales_pitch', 'We have something great for you!')}\n\nBest regards,\n{creator_profile.get('name', 'The Team')}"
            }

        except Exception as e:
            logger.error(f"Failed to generate email with LLM: {e}", exc_info=True)
            raise

    def report_task_completion(
        self,
        task: WorkerTask,
        result: Dict[str, Any]
    ) -> PlannedAction:
        """Report task completion to MainAgent via Redpanda.

        This creates a PlannedAction that publishes a WorkerTaskCompletedEvent
        to the task_results topic for MainAgent to consume.

        Args:
            task: Completed WorkerTask
            result: Task execution result

        Returns:
            PlannedAction for publishing event
        """
        from app.infra.events.schemas import WorkerTaskCompletedEvent, EventPriority

        # Calculate execution time
        execution_time_ms = 0.0
        if task.started_at and task.completed_at:
            execution_time_ms = (task.completed_at - task.started_at).total_seconds() * 1000

        # Extract missing tools from result
        missing_tools = result.get("tools_missing", [])

        # Create completion event
        completion_event = WorkerTaskCompletedEvent(
            task_id=task.id,
            workflow_execution_id=task.workflow_execution_id,
            agent_id=task.assigned_agent_id,
            consumer_id=task.consumer_id,
            result=result,
            success=result.get("success", True),
            error=result.get("error"),
            execution_time_ms=execution_time_ms,
            missing_tools=missing_tools,
        )

        # Return action to publish event
        return PlannedAction(
            action_type=ActionType.PUBLISH_EVENT.value,
            channel=Channel.REDPANDA.value,
            payload={
                "topic": "task_results",
                "key": str(task.consumer_id),
                "value": completion_event.model_dump_json()
            },
            send_at=datetime.utcnow(),
            priority=1.0
        )

    def should_escalate(self, consumer_message: str) -> bool:
        """Use LLM to classify if escalation to human needed.

        This analyzes consumer messages to detect scenarios that require
        human intervention:
        - Complex questions beyond agent's knowledge
        - Complaints or dissatisfaction
        - Special requests or customization
        - Pricing negotiation
        - Technical issues

        Args:
            consumer_message: Message from consumer

        Returns:
            True if should escalate to human

        Example:
            if worker.should_escalate("Can I get a custom package?"):
                # Escalate to human
                ...
        """
        system_prompt = """You are analyzing consumer messages to decide if human escalation is needed.

Escalate if message indicates:
- Complex question beyond standard FAQ
- Complaint or dissatisfaction
- Special request or customization
- Pricing negotiation
- Technical issues
- Urgent matter requiring immediate attention

Return JSON: {"escalate": true/false, "reason": "why"}
"""

        user_prompt = f"""Consumer message: "{consumer_message}"

Should this be escalated to a human? Analyze and return classification."""

        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            content = response.content.strip()

            # Remove markdown
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            classification = json.loads(content.strip())

            logger.info(
                f"Escalation decision: {classification['escalate']}",
                extra={"reason": classification.get("reason")}
            )

            return classification.get("escalate", False)

        except Exception as e:
            logger.error(f"Failed to classify escalation: {e}", exc_info=True)
            # Err on side of escalation if uncertain
            return True
