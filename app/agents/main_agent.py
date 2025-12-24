"""MainAgent - Purpose-Agnostic Supervisor Agent with Dynamic Tool Discovery.

This is the GLOBAL supervisor agent that orchestrates workflows for ALL creators,
regardless of their purpose (sales, coaching, content, community management, etc.).

Key Features:
- Purpose-agnostic: NOT limited to sales
- Dynamic tool discovery: Plans with available tools, logs missing ones
- Workflow versioning: Tracks all changes with reasoning
- Multi-worker delegation: Delegates to multiple specialized worker agents
- Metric-driven decisions: Adjusts workflows based on real-time metrics
- Missing tool handling: Plans workflows even when tools are unavailable

Architecture:
- Single Global MainAgent (not per-creator)
- Analyzes creator purpose and goals
- Plans workflow stages dynamically using LLM
- Delegates tasks to worker agents via Redpanda
- Monitors metrics and adjusts workflow on-the-fly
- Escalates to human when necessary
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlmodel import Session

from app.domain.agents.base_agent import BaseAgent
from app.infra.events.schemas import CreatorOnboardedEvent, WorkerTaskEvent, EventPriority
from app.domain.schemas import PlannedAction
from app.domain.tools.registry import get_registry
from app.domain.tools.missing_tools import MissingToolLogger
from app.domain.workflow.models import Workflow, WorkflowExecution
from app.domain.workflow.service import WorkflowService
from app.domain.tasks.models import WorkerTask, TaskStatus
from app.infra.db.models import ConsumerContext, Event
from app.infra.external.onboarding_client import get_onboarding_client
from app.infra.events.producer import RedpandaProducer

logger = logging.getLogger(__name__)


class MainAgent(BaseAgent):
    """Global supervisor agent for all creators and purposes.

    This agent is NOT purpose-specific - it adapts to any creator's goals:
    - Sales/conversion campaigns
    - Coaching programs
    - Content creation schedules
    - Community engagement
    - Event management
    - Course delivery

    The agent uses LLM reasoning to:
    1. Analyze creator purpose and goals
    2. Discover available tools dynamically
    3. Plan workflow stages with fallbacks for missing tools
    4. Delegate tasks to worker agents
    5. Monitor metrics and adjust workflow
    6. Escalate complex scenarios to humans
    """

    def __init__(self, agent_config: dict, session: Session):
        """Initialize MainAgent.

        Args:
            agent_config: Agent configuration (usually minimal for MainAgent)
            session: Database session
        """
        super().__init__(agent_config)
        self.session = session

        # Configure LLM with OpenRouter support
        from app.config import settings
        model = settings.openai_model_name or settings.openai_model
        base_url = settings.openai_api_base

        if base_url:
            self.llm = ChatOpenAI(
                model=model,
                temperature=0.7,
                base_url=base_url,
                openai_api_key=settings.openai_api_key
            )
        else:
            self.llm = ChatOpenAI(
                model=model,
                temperature=0.7,
                openai_api_key=settings.openai_api_key
            )

        self.onboarding_client = get_onboarding_client()
        self.workflow_service = WorkflowService(session)
        self.tool_registry = get_registry()
        self.missing_tool_logger = MissingToolLogger(session)
        self.event_producer = RedpandaProducer(bootstrap_servers=settings.redpanda_brokers)

        logger.info(f"MainAgent initialized (global supervisor) using model: {model}")

    def should_act(self, context: ConsumerContext, event: Event) -> bool:
        """Decide if MainAgent should act on this event.

        MainAgent acts on:
        - creator_onboarded: Initialize workflow
        - workflow metrics: Adjust workflow based on performance
        - worker_task_completed: Check if stage is complete

        Args:
            context: Consumer context
            event: Triggering event

        Returns:
            True if should act
        """
        # MainAgent acts on high-level orchestration events
        orchestration_events = [
            "creator_onboarded",
            "workflow_metric_update",
            "worker_task_completed",
            "workflow_state_change",
        ]

        return event.type in orchestration_events

    def plan_actions(
        self,
        context: ConsumerContext,
        event: Event
    ) -> List[PlannedAction]:
        """Plan actions based on event type.

        Args:
            context: Consumer context
            event: Triggering event

        Returns:
            List of planned actions
        """
        if event.type == "creator_onboarded":
            return self._handle_creator_onboarded(event)

        elif event.type == "workflow_metric_update":
            return self._handle_metric_update(event)

        elif event.type == "worker_task_completed":
            return self._handle_task_completed(event)

        return []

    def _handle_creator_onboarded(self, event: Event) -> List[PlannedAction]:
        """Handle creator onboarded event by creating workflow.

        This is the main entry point for MainAgent - when a creator
        completes onboarding, MainAgent:
        1. Fetches creator profile and worker agent configs
        2. Discovers available tools
        3. Plans workflow using LLM (purpose-agnostic)
        4. Creates workflow with version tracking
        5. Delegates initial tasks to worker agents

        Args:
            event: creator_onboarded event

        Returns:
            List of planned actions (task delegations)
        """
        try:
            payload = event.payload
            creator_id = UUID(payload["creator_id"])
            worker_agent_ids = [UUID(aid) for aid in payload["worker_agent_ids"]]
            consumer_ids = [UUID(cid) for cid in payload["consumers"]]
            purpose = payload["purpose"]
            goal = payload["goal"]
            start_date = datetime.fromisoformat(payload["start_date"])
            end_date = datetime.fromisoformat(payload["end_date"])

            logger.info(
                f"MainAgent handling creator_onboarded",
                extra={
                    "creator_id": str(creator_id),
                    "purpose": purpose,
                    "goal": goal,
                    "consumers": len(consumer_ids),
                }
            )

            # 1. Fetch creator profile
            creator_profile = self.onboarding_client.get_creator_profile(creator_id)

            if not creator_profile:
                logger.warning(f"Creator profile not found: {creator_id}, using fallback profile")
                # Create fallback profile from event data for testing
                creator_profile_dict = {
                    "id": creator_id,
                    "creator_id": creator_id,
                    "external_username": payload.get("config", {}).get("creator_name", "Unknown Creator"),
                    "llm_summary": "Test creator profile",
                    "sales_pitch": f"Join our {payload.get('config', {}).get('product_name', 'program')}!",
                    "target_audience_description": "Everyone interested",
                    "value_propositions": ["Great value", "Quality service"],
                    "services": [{
                        "name": payload.get("config", {}).get("product_name", "Test Product"),
                        "price": payload.get("config", {}).get("product_price", "$0")
                    }],
                    "agent_instructions": "Be helpful and friendly",
                    "objection_handling": {},
                    "pricing_info": {},
                    "ratings": {},
                    "social_proof": {}
                }
                # Convert to dict-like object
                from types import SimpleNamespace
                creator_profile = SimpleNamespace(**creator_profile_dict)
                creator_profile.dict = lambda: creator_profile_dict
            else:
                creator_profile_dict = creator_profile.dict()

            # 2. Discover available tools
            available_tools = self.tool_registry.get_available_tools()
            available_tool_names = list(available_tools.keys())
            tool_schemas = self.tool_registry.get_tool_schemas(available_only=True)

            logger.info(
                f"Discovered {len(available_tools)} available tools",
                extra={"tools": available_tool_names}
            )

            # 3. Plan workflow using LLM (purpose-agnostic)
            workflow_plan = self._plan_workflow_with_llm(
                creator_profile=creator_profile_dict,
                purpose=purpose,
                goal=goal,
                start_date=start_date,
                end_date=end_date,
                consumer_count=len(consumer_ids),
                available_tools=available_tool_names,
                tool_schemas=tool_schemas,
            )

            # 4. Create workflow in database
            workflow_config = {
                "creator_id": str(creator_id),
                "worker_agent_ids": [str(aid) for aid in worker_agent_ids],
                "purpose": purpose,
                "workflow_type": workflow_plan.get("workflow_type", "sequential"),
                "start_date": start_date.isoformat() if hasattr(start_date, 'isoformat') else start_date,
                "end_date": end_date.isoformat() if hasattr(end_date, 'isoformat') else end_date,
                "goal": goal,
                "stages": workflow_plan["stages"],
                "metrics_thresholds": workflow_plan["metrics_thresholds"],
                "available_tools": available_tool_names,
                "missing_tools": workflow_plan.get("missing_tools", []),
                "created_by": "MainAgent",
            }

            workflow = self.workflow_service.create_workflow(workflow_config)

            logger.info(f"✅ Workflow created: {workflow.id}, now creating execution...")

            # 5. Create workflow execution
            execution = self.workflow_service.create_execution(
                workflow.id,
                [str(cid) for cid in consumer_ids]
            )

            logger.info(f"✅ Execution created: {execution.id}")

            # 6. Log any missing tools discovered during planning
            for missing_tool in workflow_plan.get("missing_tools", []):
                self.missing_tool_logger.log_missing_tool(
                    tool_name=missing_tool["name"],
                    use_case=f"Workflow {workflow.id}: {missing_tool['use_case']}",
                    agent_id=None,  # MainAgent doesn't have agent_id
                    creator_id=creator_id,
                    workflow_id=workflow.id,
                    priority=missing_tool.get("priority", "medium"),
                    category=missing_tool.get("category"),
                )

            # 7. Delegate initial tasks to worker agents
            # Get first stage name (current_stage was already set to first stage in execution)
            first_stage_name = execution.current_stage
            actions = self._delegate_stage_tasks(
                execution,
                workflow,
                first_stage_name,
                consumer_ids
            )

            logger.info(
                f"Created workflow {workflow.id} v{workflow.version} and published {len(consumer_ids)} tasks to Redpanda",
                extra={
                    "workflow_id": str(workflow.id),
                    "execution_id": str(execution.id),
                    "stages": len(workflow.stages),
                    "missing_tools": len(workflow.missing_tools),
                    "tasks_delegated": len(consumer_ids),
                }
            )

            return actions

        except Exception as e:
            logger.error(
                f"Failed to handle creator_onboarded: {e}",
                exc_info=True
            )
            return []

    def _plan_workflow_with_llm(
        self,
        creator_profile: Dict[str, Any],
        purpose: str,
        goal: str,
        start_date: datetime,
        end_date: datetime,
        consumer_count: int,
        available_tools: List[str],
        tool_schemas: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Use LLM to plan workflow stages dynamically.

        This is the core intelligence of MainAgent - it analyzes the
        creator's purpose and available tools, then plans an optimal
        workflow that adapts to tool availability.

        Args:
            creator_profile: Creator profile data
            purpose: Generic purpose (sales, coaching, content, etc.)
            goal: Specific goal
            start_date: Workflow start
            end_date: Workflow end
            consumer_count: Number of consumers
            available_tools: List of available tool names
            tool_schemas: Tool schemas for reference

        Returns:
            Dict with workflow plan including stages, thresholds, missing tools
        """
        duration_days = (end_date - start_date).days

        system_prompt = """You are a workflow planning AI that creates purpose-agnostic workflows.

Your task is to analyze the creator's purpose, goals, and available tools, then design
an optimal multi-stage workflow that achieves their objectives.

IMPORTANT: You must plan workflows regardless of available tools. If a tool is missing:
1. Note it in missing_tools array
2. Suggest alternative actions using available tools
3. Continue planning the workflow with fallbacks

Return JSON with this structure:
{
    "workflow_type": "sequential|parallel|conditional|event_driven",
    "stages": {
        "stage_name": {
            "day": <int>,
            "actions": ["action_description"],
            "conditions": {"metric_name": "comparison_value"},
            "required_tools": ["tool_name"],
            "fallback_actions": ["alternative_action"]
        }
    },
    "metrics_thresholds": {
        "metric_name": {
            "threshold": <float>,
            "comparison": ">=|<=|==|>|<",
            "action": "what_to_do",
            "priority": "critical|high|normal|low"
        }
    },
    "missing_tools": [
        {
            "name": "tool_name",
            "use_case": "why_needed",
            "alternative": "what_to_use_instead",
            "priority": "critical|high|medium|low",
            "category": "communication|data|analytics|etc"
        }
    ]
}"""

        user_prompt = f"""Plan a workflow for this creator:

**Creator Profile:**
- Name: {creator_profile.get('external_username', 'Unknown')}
- Purpose: {purpose}
- Goal: {goal}
- Duration: {duration_days} days ({start_date.date()} to {end_date.date()})
- Consumers: {consumer_count}

**Creator Details:**
{json.dumps(creator_profile, indent=2, default=str)}

**Available Tools:**
{json.dumps(available_tools, indent=2)}

**Tool Schemas (for reference):**
{json.dumps(tool_schemas[:5], indent=2, default=str)}  # Show first 5 for context

Create a purpose-specific workflow that:
1. Achieves the creator's goal within the timeline
2. Uses available tools optimally
3. Notes missing tools but continues planning with alternatives
4. Includes metric-based decision points
5. Adapts to the specific purpose (not generic)

Return ONLY valid JSON, no markdown or explanation."""

        try:
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            # Parse LLM response
            content = response.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            workflow_plan = json.loads(content.strip())

            logger.info(
                f"LLM generated workflow plan",
                extra={
                    "stages": len(workflow_plan.get("stages", {})),
                    "workflow_type": workflow_plan.get("workflow_type"),
                    "missing_tools": len(workflow_plan.get("missing_tools", [])),
                }
            )

            return workflow_plan

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM workflow plan: {e}")
            logger.error(f"Raw response: {content}")

            # Return minimal fallback plan
            return self._create_fallback_workflow_plan(
                purpose,
                duration_days,
                available_tools
            )

        except Exception as e:
            logger.error(f"Failed to plan workflow with LLM: {e}", exc_info=True)
            return self._create_fallback_workflow_plan(
                purpose,
                duration_days,
                available_tools
            )

    def _create_fallback_workflow_plan(
        self,
        purpose: str,
        duration_days: int,
        available_tools: List[str]
    ) -> Dict[str, Any]:
        """Create a fallback workflow plan if LLM fails.

        Args:
            purpose: Creator purpose
            duration_days: Workflow duration
            available_tools: Available tools

        Returns:
            Basic workflow plan
        """
        return {
            "workflow_type": "sequential",
            "stages": {
                "intro": {
                    "day": 1,
                    "actions": ["Send introduction message"],
                    "conditions": {},
                    "required_tools": available_tools[:3] if available_tools else [],
                    "fallback_actions": ["Log activity"]
                }
            },
            "metrics_thresholds": {
                "engagement_rate": {
                    "threshold": 0.1,
                    "comparison": ">=",
                    "action": "continue_workflow",
                    "priority": "normal"
                }
            },
            "missing_tools": []
        }

    def _delegate_stage_tasks(
        self,
        execution: "WorkflowExecution",
        workflow: "Workflow",
        stage_name: str,
        consumer_ids: List[UUID]
    ) -> List[PlannedAction]:
        """Delegate tasks for a specific workflow stage to worker agents.

        Creates WorkerTask database records AND WorkerTaskEvent for each consumer,
        then publishes to Redpanda.

        Args:
            execution: Workflow execution
            workflow: Workflow definition
            stage_name: Name of the stage to delegate tasks for
            consumer_ids: List of consumer UUIDs

        Returns:
            List of PlannedAction (empty, tasks published to Redpanda)
        """
        actions = []

        # Get stage configuration
        stage = workflow.stages.get(stage_name)
        if not stage:
            logger.error(f"Stage '{stage_name}' not found in workflow {workflow.id}")
            return []

        worker_agent_ids = workflow.worker_agent_ids

        # Collect tasks to create in database
        tasks_to_create = []

        # Distribute consumers across worker agents (round-robin)
        for i, consumer_id in enumerate(consumer_ids):
            worker_agent_id = worker_agent_ids[i % len(worker_agent_ids)]

            # Generate task_id
            task_id = uuid4()

            # Create WorkerTask database record
            worker_task = WorkerTask(
                id=task_id,
                workflow_execution_id=execution.id,
                assigned_agent_id=worker_agent_id,
                consumer_id=consumer_id,
                task_type=f"{stage_name}_task",
                task_payload={
                    "workflow_id": str(workflow.id),
                    "stage": stage_name,
                    "actions": stage["actions"],
                    "required_tools": stage.get("required_tools", []),
                    "fallback_actions": stage.get("fallback_actions", []),
                    "creator_id": str(workflow.creator_id),
                },
                status=TaskStatus.PENDING,
            )

            tasks_to_create.append(worker_task)

            # Create task event with same task_id
            task_event = WorkerTaskEvent(
                event_id=uuid4(),
                event_type="worker_task_assigned",
                timestamp=datetime.utcnow(),
                priority=EventPriority.HIGH,
                task_id=task_id,  # Same as WorkerTask.id
                workflow_execution_id=execution.id,
                agent_id=worker_agent_id,
                consumer_id=consumer_id,
                task_type=f"{stage_name}_task",
                task_payload={
                    "workflow_id": str(workflow.id),
                    "stage": stage_name,
                    "actions": stage["actions"],
                    "required_tools": stage.get("required_tools", []),
                    "fallback_actions": stage.get("fallback_actions", []),
                    "creator_id": str(workflow.creator_id),
                },
                deadline=None
            )

            # Publish to Redpanda
            try:
                self.event_producer.produce(
                    topic="supervisor_tasks",
                    key=str(consumer_id),
                    value=task_event.model_dump_json()
                )

                logger.debug(
                    f"Delegated task {task_id} to worker {worker_agent_id} for consumer {consumer_id}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to delegate task: {e}",
                    extra={
                        "task_id": str(task_id),
                        "worker_agent_id": str(worker_agent_id),
                        "consumer_id": str(consumer_id),
                    }
                )

        # Bulk insert WorkerTask records
        try:
            for task in tasks_to_create:
                self.session.add(task)
            self.session.commit()

            logger.info(
                f"✅ Created {len(tasks_to_create)} WorkerTask database records",
                extra={
                    "workflow_id": str(workflow.id),
                    "execution_id": str(execution.id),
                }
            )

        except Exception as e:
            logger.error(
                f"Failed to create WorkerTask database records: {e}",
                exc_info=True
            )
            self.session.rollback()

        logger.info(
            f"Delegated {len(consumer_ids)} tasks to {len(worker_agent_ids)} worker agents via Redpanda",
            extra={
                "workflow_id": str(workflow.id),
                "execution_id": str(execution.id),
                "stage": stage_name,
                "consumers": len(consumer_ids),
                "workers": len(worker_agent_ids),
            }
        )

        # Flush messages to ensure delivery
        self.event_producer.flush()

        return actions  # Empty, tasks are published to Redpanda

    def _handle_metric_update(self, event: Event) -> List[PlannedAction]:
        """Handle workflow metric updates.

        TODO: Phase 3 - Implement metric-based workflow adjustments

        Args:
            event: workflow_metric_update event

        Returns:
            List of actions
        """
        # Placeholder for Phase 3 completion
        return []

    def _handle_task_completed(self, event: Event) -> List[PlannedAction]:
        """Handle worker task completion and progress workflow.

        This method implements the MainAgent feedback loop:
        1. Update workflow metrics from task results
        2. Check if current stage is complete
        3. Decide whether to progress to next stage
        4. Delegate new tasks if needed
        5. Adjust workflow based on metrics

        Args:
            event: worker_task_completed event

        Returns:
            List of actions (new task delegations, workflow updates, etc.)
        """
        from app.domain.workflow.service import WorkflowService
        from app.domain.tasks.models import WorkerTask, TaskStatus

        logger.info(
            f"Handling task completion",
            extra={
                "event_id": str(event.id),
                "consumer_id": str(event.consumer_id),
            }
        )

        try:
            # Extract task result from event payload
            task_id = UUID(event.payload["task_id"])
            task_result = event.payload.get("result", {})
            execution_time_ms = event.payload.get("execution_time_ms", 0)
            missing_tools = event.payload.get("missing_tools", [])
            workflow_execution_id = UUID(event.payload["workflow_execution_id"])

            # Get WorkerTask from database
            worker_task = self.session.get(WorkerTask, task_id)
            if not worker_task:
                logger.error(f"WorkerTask not found: {task_id}")
                return []

            # Get WorkflowExecution
            workflow_service = WorkflowService(self.session)
            execution = workflow_service.get_execution(workflow_execution_id)

            if not execution:
                logger.error(f"WorkflowExecution not found: {workflow_execution_id}")
                return []

            # Get Workflow definition
            workflow = workflow_service.get_workflow(execution.workflow_id)
            if not workflow:
                logger.error(f"Workflow not found: {execution.workflow_id}")
                return []

            # Log tool usage from task result
            workflow_service.log_tool_usage(
                execution_id=execution.id,
                tool_name=worker_task.task_type,
                success=worker_task.status == TaskStatus.COMPLETED,
                latency_ms=execution_time_ms,
                consumer_id=event.consumer_id
            )

            # Log missing tools if any
            if missing_tools:
                from sqlalchemy.orm.attributes import flag_modified

                for tool_name in missing_tools:
                    execution.missing_tool_attempts.append({
                        "tool": tool_name,
                        "timestamp": datetime.utcnow().isoformat(),
                        "task_id": str(task_id),
                        "consumer_id": str(event.consumer_id),
                    })

                # Mark as modified for SQLAlchemy to detect change
                flag_modified(execution, "missing_tool_attempts")

                self.session.add(execution)
                self.session.commit()

            # Update workflow metrics based on task result
            metrics_update = self._extract_metrics_from_task_result(
                worker_task, task_result
            )

            if metrics_update:
                logger.info(
                    f"Updating workflow metrics: {metrics_update}",
                    extra={
                        "execution_id": str(execution.id),
                        "metrics_update": metrics_update,
                    }
                )
                workflow_service.update_metrics(execution.id, metrics_update)

                # Refresh execution to get updated metrics
                self.session.refresh(execution)

            # Check if current stage is complete
            stage_complete = self._is_stage_complete(
                execution, workflow, event.consumer_id
            )

            logger.info(
                f"Stage completion check: stage={execution.current_stage}, complete={stage_complete}",
                extra={
                    "execution_id": str(execution.id),
                    "current_stage": execution.current_stage,
                    "stage_complete": stage_complete,
                }
            )

            # Analyze workflow state and decide next actions
            decisions = self._analyze_workflow_state(
                execution, workflow, stage_complete
            )

            logger.info(
                f"LLM analysis generated {len(decisions)} decisions",
                extra={
                    "execution_id": str(execution.id),
                    "decisions_count": len(decisions),
                    "decisions": decisions,
                }
            )

            # Execute decisions and generate actions
            actions = []
            for decision in decisions:
                decision_actions = self._execute_decision(
                    decision, execution, workflow, event.consumer_id
                )
                actions.extend(decision_actions)

            # Log decision to workflow (with detailed error handling)
            if decisions:
                try:
                    # Refresh execution again to get latest state after progression
                    self.session.refresh(execution)

                    logger.info(
                        f"Logging {len(decisions)} decisions to workflow",
                        extra={
                            "execution_id": str(execution.id),
                            "metrics_snapshot": execution.metrics,
                        }
                    )

                    workflow_service.log_decision(
                        execution_id=execution.id,
                        decision=f"Processed {len(decisions)} decisions from task completion",
                        reasoning=f"Task {worker_task.task_type} completed for consumer {event.consumer_id}. Decisions: {[d.get('decision') for d in decisions]}",
                        metrics_snapshot=execution.metrics
                    )

                    logger.info(
                        f"Successfully logged decisions to workflow",
                        extra={"execution_id": str(execution.id)}
                    )
                except Exception as log_error:
                    logger.error(
                        f"Failed to log decisions to workflow: {log_error}",
                        exc_info=True,
                        extra={
                            "execution_id": str(execution.id),
                            "decisions": decisions,
                        }
                    )

            logger.info(
                f"Task completion handling generated {len(actions)} actions",
                extra={
                    "task_id": str(task_id),
                    "workflow_execution_id": str(execution.id),
                    "actions_count": len(actions),
                }
            )

            return actions

        except Exception as e:
            logger.error(
                f"Failed to handle task completion: {e}",
                exc_info=True,
                extra={"event_id": str(event.id)}
            )
            return []

    def _extract_metrics_from_task_result(
        self,
        worker_task: "WorkerTask",
        task_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract metrics from worker task result.

        Args:
            worker_task: Completed worker task
            task_result: Result dict from worker

        Returns:
            Dict of metrics to update
        """
        metrics_update = {}

        # Extract task-specific metrics based on task type
        task_type = worker_task.task_type.lower()

        # Generic metrics for ALL task types
        metrics_update["tasks_completed"] = 1

        # Track messages sent (any communication)
        if task_result.get("sent"):
            metrics_update["messages_sent"] = 1

        # Task-specific metrics
        if "email" in task_type:
            # Email task metrics
            if task_result.get("sent"):
                metrics_update["emails_sent"] = 1
            if task_result.get("message_id"):
                metrics_update["email_messages_tracked"] = 1

        elif "whatsapp" in task_type:
            # WhatsApp task metrics
            if task_result.get("sent"):
                metrics_update["whatsapp_sent"] = 1
            if task_result.get("message_id"):
                metrics_update["whatsapp_messages_tracked"] = 1

        elif "sms" in task_type:
            # SMS task metrics
            if task_result.get("sent"):
                metrics_update["sms_sent"] = 1
            if task_result.get("message_id"):
                metrics_update["sms_messages_tracked"] = 1

        # Stage-specific task tracking
        if "assessment" in task_type:
            metrics_update["assessments_completed"] = 1
        elif "interest" in task_type:
            metrics_update["interest_tasks_completed"] = 1
        elif "engagement" in task_type:
            metrics_update["engagement_tasks_completed"] = 1
        elif "objection" in task_type:
            metrics_update["objection_handling_completed"] = 1
        elif "conversion" in task_type:
            metrics_update["conversion_tasks_completed"] = 1
        elif "outreach" in task_type:
            metrics_update["outreach_tasks_completed"] = 1

        # Extract engagement metrics if present
        if task_result.get("engagement_score"):
            metrics_update["total_engagement_score"] = task_result["engagement_score"]

        # Extract success indicators
        if task_result.get("success"):
            metrics_update["successful_tasks"] = 1

        # Extract error indicators
        if task_result.get("error") or task_result.get("failed"):
            metrics_update["failed_tasks"] = 1

        logger.info(
            f"Extracted metrics from task {worker_task.task_type}",
            extra={
                "task_id": str(worker_task.id),
                "task_type": worker_task.task_type,
                "metrics": metrics_update,
            }
        )

        return metrics_update

    def _is_stage_complete(
        self,
        execution: "WorkflowExecution",
        workflow: "Workflow",
        consumer_id: UUID
    ) -> bool:
        """Check if current workflow stage is complete.

        Args:
            execution: Workflow execution
            workflow: Workflow definition
            consumer_id: Consumer UUID

        Returns:
            True if stage is complete
        """
        from app.domain.tasks.models import WorkerTask, TaskStatus
        from sqlmodel import select

        current_stage = execution.current_stage
        stage_config = workflow.stages.get(current_stage)

        if not stage_config:
            logger.warning(f"Stage not found in workflow: {current_stage}")
            return False

        # Check if all required tasks for this stage are complete
        # Get all tasks for this consumer in this workflow execution
        statement = (
            select(WorkerTask)
            .where(WorkerTask.workflow_execution_id == execution.id)
            .where(WorkerTask.consumer_id == consumer_id)
        )

        tasks = list(self.session.exec(statement).all())

        if not tasks:
            return False

        # Count completed vs pending/failed tasks for current stage
        stage_tasks = [
            t for t in tasks
            if t.task_payload.get("stage") == current_stage
        ]

        if not stage_tasks:
            return False

        completed_count = len([
            t for t in stage_tasks
            if t.status == TaskStatus.COMPLETED
        ])

        # Stage is complete if all tasks are done
        stage_complete = completed_count == len(stage_tasks)

        logger.debug(
            f"Stage completion check: {completed_count}/{len(stage_tasks)} tasks done",
            extra={
                "stage": current_stage,
                "consumer_id": str(consumer_id),
                "stage_complete": stage_complete,
            }
        )

        return stage_complete

    def _analyze_workflow_state(
        self,
        execution: "WorkflowExecution",
        workflow: "Workflow",
        stage_complete: bool
    ) -> List[Dict[str, Any]]:
        """Analyze workflow state and decide next actions.

        Uses LLM to make intelligent decisions based on:
        - Current metrics vs thresholds
        - Stage completion status
        - Workflow goals

        Args:
            execution: Workflow execution
            workflow: Workflow definition
            stage_complete: Whether current stage is complete

        Returns:
            List of decision dicts
        """
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage

        # Prepare analysis prompt
        system_prompt = """You are a workflow orchestration AI analyzing campaign performance.

Your job is to:
1. Evaluate current metrics against thresholds
2. Decide if workflow should progress to next stage
3. Identify if any adjustments are needed
4. Recommend specific actions

Return decisions as JSON list:
[
    {
        "decision": "progress_to_next_stage" | "continue_current_stage" | "adjust_workflow" | "complete_workflow",
        "reasoning": "Why this decision was made",
        "action": "specific action to take",
        "priority": "high" | "medium" | "low"
    }
]"""

        user_prompt = f"""
Workflow Analysis:

Goal: {workflow.goal}
Purpose: {workflow.purpose}
Current Stage: {execution.current_stage}
Stage Complete: {stage_complete}

Current Metrics:
{json.dumps(execution.metrics, indent=2)}

Thresholds:
{json.dumps(workflow.metrics_thresholds, indent=2)}

Available Stages:
{json.dumps(list(workflow.stages.keys()), indent=2)}

What decisions should be made?
"""

        try:
            llm = ChatOpenAI(
                model=self.config.get("model", "gpt-4-turbo-preview"),
                temperature=0.7
            )

            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            # Parse LLM response
            content = response.content.strip()

            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            decisions = json.loads(content)

            logger.info(
                f"Workflow analysis generated {len(decisions)} decisions",
                extra={
                    "workflow_execution_id": str(execution.id),
                    "decisions": decisions,
                }
            )

            return decisions

        except Exception as e:
            logger.error(
                f"Failed to analyze workflow state: {e}",
                exc_info=True
            )

            # Fallback: Simple rule-based decision
            if stage_complete:
                return [{
                    "decision": "progress_to_next_stage",
                    "reasoning": "Current stage completed",
                    "action": "move_to_next_stage",
                    "priority": "high"
                }]
            else:
                return [{
                    "decision": "continue_current_stage",
                    "reasoning": "Stage not yet complete",
                    "action": "wait_for_completion",
                    "priority": "low"
                }]

    def _execute_decision(
        self,
        decision: Dict[str, Any],
        execution: "WorkflowExecution",
        workflow: "Workflow",
        consumer_id: UUID
    ) -> List[PlannedAction]:
        """Execute a workflow decision.

        Args:
            decision: Decision dict from analysis
            execution: Workflow execution
            workflow: Workflow definition
            consumer_id: Consumer UUID

        Returns:
            List of PlannedActions
        """
        from app.domain.workflow.service import WorkflowService

        decision_type = decision.get("decision")
        actions = []

        if decision_type == "progress_to_next_stage":
            # Move to next stage and delegate tasks
            actions.extend(
                self._progress_to_next_stage(execution, workflow, consumer_id)
            )

        elif decision_type == "adjust_workflow":
            # Adjust workflow parameters
            actions.extend(
                self._adjust_workflow(decision, execution, workflow)
            )

        elif decision_type == "complete_workflow":
            # Mark workflow as complete
            workflow_service = WorkflowService(self.session)
            workflow_service.complete_workflow(execution.id)

            logger.info(
                f"Workflow {execution.id} marked as complete",
                extra={"workflow_execution_id": str(execution.id)}
            )

        elif decision_type == "continue_current_stage":
            # No action needed - stage still in progress
            pass

        return actions

    def _progress_to_next_stage(
        self,
        execution: "WorkflowExecution",
        workflow: "Workflow",
        consumer_id: UUID
    ) -> List[PlannedAction]:
        """Progress workflow to next stage.

        Args:
            execution: Workflow execution
            workflow: Workflow definition
            consumer_id: Consumer UUID

        Returns:
            List of PlannedActions for new stage
        """
        from app.domain.workflow.service import WorkflowService

        # Get ordered stage list
        stage_keys = list(workflow.stages.keys())
        current_index = stage_keys.index(execution.current_stage)

        if current_index >= len(stage_keys) - 1:
            # No more stages - complete workflow
            workflow_service = WorkflowService(self.session)
            workflow_service.complete_workflow(execution.id)

            logger.info(
                f"Workflow {execution.id} completed - no more stages",
                extra={"workflow_execution_id": str(execution.id)}
            )

            return []

        # Move to next stage
        next_stage = stage_keys[current_index + 1]
        execution.current_stage = next_stage
        execution.updated_at = datetime.utcnow()

        self.session.add(execution)
        self.session.commit()

        logger.info(
            f"Progressed to next stage: {next_stage}",
            extra={
                "workflow_execution_id": str(execution.id),
                "previous_stage": stage_keys[current_index],
                "next_stage": next_stage,
            }
        )

        # Delegate tasks for new stage
        return self._delegate_stage_tasks(
            execution, workflow, next_stage, [consumer_id]
        )

    def _adjust_workflow(
        self,
        decision: Dict[str, Any],
        execution: "WorkflowExecution",
        workflow: "Workflow"
    ) -> List[PlannedAction]:
        """Adjust workflow based on decision.

        Args:
            decision: Decision dict with adjustment details
            execution: Workflow execution
            workflow: Workflow definition

        Returns:
            List of PlannedActions
        """
        # Placeholder for workflow adjustments
        # Could implement:
        # - Change email timing
        # - Add additional touchpoints
        # - Modify message templates
        # - Adjust thresholds

        logger.info(
            f"Workflow adjustment requested: {decision.get('action')}",
            extra={
                "workflow_execution_id": str(execution.id),
                "decision": decision,
            }
        )

        # For now, log the adjustment request
        # Future: Implement actual workflow modifications

        return []
