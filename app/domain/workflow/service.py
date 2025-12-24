"""Workflow service with version control.

This service manages workflows with full version history tracking:
- Create workflows with initial version
- Update workflows (creates new version automatically)
- Retrieve specific versions
- Rollback to previous versions
- Track execution state and metrics
- Cache workflow executions for performance
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlmodel import Session, select

from app.domain.workflow.models import (
    Workflow,
    WorkflowExecution,
    WorkflowVersion,
)
from app.infra.cache import get_cache

logger = logging.getLogger(__name__)


class WorkflowService:
    """Service for managing workflows with version control.

    This service provides methods to create, update, and manage workflows
    while automatically tracking all changes through versioning.

    Usage:
        service = WorkflowService(session)
        workflow = service.create_workflow(config_dict)
        updated = service.update_workflow(workflow.id, changes, "Improved email timing")
        history = service.get_workflow_history(workflow.id)
    """

    def __init__(self, session: Session, enable_cache: bool = True):
        """Initialize workflow service.

        Args:
            session: Database session
            enable_cache: Whether to use Redis caching (default: True)
        """
        self.session = session
        self.enable_cache = enable_cache
        self.cache = get_cache() if enable_cache else None

    def create_workflow(self, config: Dict[str, Any]) -> Workflow:
        """Create a new workflow with initial version.

        Args:
            config: Workflow configuration dict with:
                - creator_id: UUID
                - worker_agent_ids: List[UUID]
                - purpose: str
                - workflow_type: str
                - start_date: datetime
                - end_date: datetime
                - goal: str
                - stages: Dict
                - metrics_thresholds: Dict
                - available_tools: List[str]
                - missing_tools: List[Dict] (optional)

        Returns:
            Created Workflow instance

        Example:
            config = {
                "creator_id": creator_uuid,
                "worker_agent_ids": [agent1_uuid, agent2_uuid],
                "purpose": "cohort_conversion",
                "workflow_type": "sequential",
                "start_date": datetime.utcnow(),
                "end_date": datetime.utcnow() + timedelta(days=7),
                "goal": "Convert max consumers with personalized engagement",
                "stages": {...},
                "metrics_thresholds": {...},
                "available_tools": ["send_email", "send_whatsapp"],
                "missing_tools": []
            }
        """
        try:
            # Create workflow
            workflow = Workflow(
                creator_id=config["creator_id"],
                worker_agent_ids=config["worker_agent_ids"],
                purpose=config["purpose"],
                workflow_type=config["workflow_type"],
                start_date=config["start_date"],
                end_date=config["end_date"],
                goal=config["goal"],
                version=1,
                stages=config["stages"],
                metrics_thresholds=config["metrics_thresholds"],
                available_tools=config["available_tools"],
                missing_tools=config.get("missing_tools", []),
                created_by=config.get("created_by", "MainAgent"),
            )

            self.session.add(workflow)
            self.session.commit()
            self.session.refresh(workflow)

            # Create initial version record
            initial_version = WorkflowVersion(
                workflow_id=workflow.id,
                version=1,
                previous_version=None,
                changes={"action": "created", "initial_config": config},
                reason="Initial workflow creation",
                changed_by=config.get("created_by", "MainAgent"),
                diff={},
            )

            self.session.add(initial_version)
            self.session.commit()

            logger.info(
                f"Created workflow {workflow.id} v1",
                extra={
                    "workflow_id": str(workflow.id),
                    "purpose": workflow.purpose,
                    "creator_id": str(workflow.creator_id),
                }
            )

            return workflow

        except Exception as e:
            logger.error(f"Failed to create workflow: {e}", exc_info=True)
            self.session.rollback()
            raise

    def update_workflow(
        self,
        workflow_id: UUID,
        changes: Dict[str, Any],
        reason: str,
        changed_by: str = "MainAgent"
    ) -> Workflow:
        """Update workflow and create new version.

        Args:
            workflow_id: Workflow UUID
            changes: Dict of fields to update (e.g., {"stages": {...}})
            reason: Why this update is being made
            changed_by: Who is making the change

        Returns:
            Updated Workflow instance

        Example:
            changes = {
                "stages": {
                    "intro": {...},
                    "followup": {...}  # New stage added
                },
                "metrics_thresholds": {
                    "email_open_rate": {"threshold": 0.15, "action": "adjust"}
                }
            }
            updated = service.update_workflow(
                workflow_id,
                changes,
                "Added followup stage based on low engagement"
            )
        """
        try:
            # Get current workflow
            workflow = self.session.get(Workflow, workflow_id)

            if not workflow:
                raise ValueError(f"Workflow not found: {workflow_id}")

            # Store old state for diff
            old_state = {
                "stages": workflow.stages,
                "metrics_thresholds": workflow.metrics_thresholds,
                "available_tools": workflow.available_tools,
                "missing_tools": workflow.missing_tools,
            }

            # Apply changes
            diff = {}
            for key, value in changes.items():
                if hasattr(workflow, key):
                    old_value = getattr(workflow, key)
                    diff[key] = {"old": old_value, "new": value}
                    setattr(workflow, key, value)

            # Increment version
            old_version = workflow.version
            workflow.version += 1
            workflow.updated_at = datetime.utcnow()

            self.session.add(workflow)

            # Create version record
            version_record = WorkflowVersion(
                workflow_id=workflow.id,
                version=workflow.version,
                previous_version=old_version,
                changes=changes,
                reason=reason,
                changed_by=changed_by,
                diff=diff,
            )

            self.session.add(version_record)
            self.session.commit()
            self.session.refresh(workflow)

            logger.info(
                f"Updated workflow {workflow.id} to v{workflow.version}",
                extra={
                    "workflow_id": str(workflow.id),
                    "old_version": old_version,
                    "new_version": workflow.version,
                    "reason": reason,
                }
            )

            return workflow

        except Exception as e:
            logger.error(f"Failed to update workflow: {e}", exc_info=True)
            self.session.rollback()
            raise

    def get_workflow(self, workflow_id: UUID) -> Optional[Workflow]:
        """Get workflow by ID.

        Args:
            workflow_id: Workflow UUID

        Returns:
            Workflow instance or None
        """
        return self.session.get(Workflow, workflow_id)

    def get_workflow_version(
        self,
        workflow_id: UUID,
        version: int
    ) -> Optional[WorkflowVersion]:
        """Get specific workflow version.

        Args:
            workflow_id: Workflow UUID
            version: Version number

        Returns:
            WorkflowVersion instance or None
        """
        statement = (
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .where(WorkflowVersion.version == version)
        )
        return self.session.exec(statement).first()

    def get_workflow_history(self, workflow_id: UUID) -> List[WorkflowVersion]:
        """Get all versions of a workflow.

        Args:
            workflow_id: Workflow UUID

        Returns:
            List of WorkflowVersion instances, ordered by version
        """
        statement = (
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(WorkflowVersion.version)
        )
        return list(self.session.exec(statement).all())

    def rollback_workflow(
        self,
        workflow_id: UUID,
        to_version: int,
        reason: str = "Rollback to previous version"
    ) -> Workflow:
        """Rollback workflow to a previous version.

        Creates a new version that restores the state from to_version.

        Args:
            workflow_id: Workflow UUID
            to_version: Version number to rollback to
            reason: Why rolling back

        Returns:
            Workflow instance at new version (rollback creates new version)
        """
        try:
            # Get current workflow
            workflow = self.session.get(Workflow, workflow_id)

            if not workflow:
                raise ValueError(f"Workflow not found: {workflow_id}")

            # Get target version
            target_version = self.get_workflow_version(workflow_id, to_version)

            if not target_version:
                raise ValueError(
                    f"Version {to_version} not found for workflow {workflow_id}"
                )

            # Get the state from target version
            # Note: target_version.changes contains the state at that version
            rollback_changes = target_version.changes

            # Apply rollback as a new update
            return self.update_workflow(
                workflow_id,
                rollback_changes,
                f"{reason} (rolled back from v{workflow.version} to v{to_version})",
                "System"
            )

        except Exception as e:
            logger.error(f"Failed to rollback workflow: {e}", exc_info=True)
            raise

    def create_execution(
        self,
        workflow_id: UUID,
        consumer_ids: List[UUID]
    ) -> WorkflowExecution:
        """Create a new workflow execution.

        Args:
            workflow_id: Workflow UUID
            consumer_ids: List of consumer UUIDs for this execution

        Returns:
            WorkflowExecution instance
        """
        try:
            workflow = self.session.get(Workflow, workflow_id)

            if not workflow:
                raise ValueError(f"Workflow not found: {workflow_id}")

            # Get first stage name (assumes stages dict has consistent ordering)
            first_stage = list(workflow.stages.keys())[0] if workflow.stages else "unknown"

            execution = WorkflowExecution(
                workflow_id=workflow.id,
                workflow_version=workflow.version,
                creator_id=workflow.creator_id,
                consumer_ids=consumer_ids,
                current_stage=first_stage,
                status="running",
                metrics={},
                decisions_log=[],
                tool_usage_log=[],
                missing_tool_attempts=[],
            )

            self.session.add(execution)
            self.session.commit()
            self.session.refresh(execution)

            logger.info(
                f"Created workflow execution {execution.id}",
                extra={
                    "workflow_id": str(workflow.id),
                    "execution_id": str(execution.id),
                    "consumers": len(consumer_ids),
                }
            )

            return execution

        except Exception as e:
            logger.error(f"Failed to create execution: {e}", exc_info=True)
            self.session.rollback()
            raise

    def _invalidate_execution_cache(self, execution_id: UUID):
        """Invalidate cached execution data.

        Args:
            execution_id: Execution UUID
        """
        if self.enable_cache and self.cache:
            self.cache.delete("workflow_exec", execution_id)
            logger.debug(
                f"Invalidated cache for execution {execution_id}",
                extra={"execution_id": str(execution_id)}
            )

    def get_execution(self, execution_id: UUID) -> Optional[WorkflowExecution]:
        """Get workflow execution by ID.

        Checks cache first for performance. Cache TTL is 5 minutes (300s).

        Args:
            execution_id: Execution UUID

        Returns:
            WorkflowExecution instance or None
        """
        # Check cache first
        if self.enable_cache and self.cache:
            cached_data = self.cache.get("workflow_exec", execution_id)

            if cached_data:
                # Reconstruct WorkflowExecution from cached dict
                try:
                    return WorkflowExecution(**cached_data)
                except Exception as e:
                    logger.warning(
                        f"Failed to deserialize cached execution: {e}",
                        extra={"execution_id": str(execution_id)}
                    )
                    # Continue to database query if deserialization fails

        # Load from database
        execution = self.session.get(WorkflowExecution, execution_id)

        # Cache for 5 minutes if found
        if execution and self.enable_cache and self.cache:
            try:
                # Convert to dict for caching (SQLModel supports .dict())
                execution_dict = execution.dict()
                self.cache.set("workflow_exec", execution_id, execution_dict, ttl=300)
            except Exception as e:
                logger.warning(
                    f"Failed to cache execution: {e}",
                    extra={"execution_id": str(execution_id)}
                )

        return execution

    def update_metrics(
        self,
        execution_id: UUID,
        metrics_update: Dict[str, Any]
    ) -> WorkflowExecution:
        """Update execution metrics.

        Args:
            execution_id: Execution UUID
            metrics_update: Dict of metrics to update/add

        Returns:
            Updated WorkflowExecution instance
        """
        from sqlalchemy.orm.attributes import flag_modified

        try:
            execution = self.session.get(WorkflowExecution, execution_id)

            if not execution:
                raise ValueError(f"Execution not found: {execution_id}")

            # Merge new metrics with existing
            execution.metrics.update(metrics_update)
            execution.updated_at = datetime.utcnow()

            # Mark metrics as modified for SQLAlchemy to detect change
            flag_modified(execution, "metrics")

            self.session.add(execution)
            self.session.commit()
            self.session.refresh(execution)

            # Invalidate cache after update
            self._invalidate_execution_cache(execution_id)

            return execution

        except Exception as e:
            logger.error(f"Failed to update metrics: {e}", exc_info=True)
            self.session.rollback()
            raise

    def log_decision(
        self,
        execution_id: UUID,
        decision: str,
        reasoning: str,
        metrics_snapshot: Dict[str, Any]
    ):
        """Log a MainAgent decision.

        Args:
            execution_id: Execution UUID
            decision: What decision was made
            reasoning: Why it was made
            metrics_snapshot: Metrics at time of decision
        """
        from sqlalchemy.orm.attributes import flag_modified

        try:
            execution = self.session.get(WorkflowExecution, execution_id)

            if not execution:
                raise ValueError(f"Execution not found: {execution_id}")

            decision_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "decision": decision,
                "reasoning": reasoning,
                "metrics_snapshot": metrics_snapshot,
            }

            execution.decisions_log.append(decision_entry)
            execution.updated_at = datetime.utcnow()

            # Mark decisions_log as modified for SQLAlchemy to detect change
            flag_modified(execution, "decisions_log")

            self.session.add(execution)
            self.session.commit()

            # Invalidate cache after update
            self._invalidate_execution_cache(execution_id)

        except Exception as e:
            logger.error(f"Failed to log decision: {e}", exc_info=True)
            self.session.rollback()

    def log_tool_usage(
        self,
        execution_id: UUID,
        tool_name: str,
        success: bool,
        latency_ms: float,
        consumer_id: Optional[UUID] = None
    ):
        """Log tool usage.

        Args:
            execution_id: Execution UUID
            tool_name: Name of tool used
            success: Whether tool call succeeded
            latency_ms: Execution time in milliseconds
            consumer_id: Optional consumer UUID
        """
        from sqlalchemy.orm.attributes import flag_modified

        try:
            execution = self.session.get(WorkflowExecution, execution_id)

            if not execution:
                return  # Don't fail if execution not found

            tool_entry = {
                "tool": tool_name,
                "timestamp": datetime.utcnow().isoformat(),
                "success": success,
                "latency_ms": latency_ms,
            }

            if consumer_id:
                tool_entry["consumer_id"] = str(consumer_id)

            execution.tool_usage_log.append(tool_entry)
            execution.updated_at = datetime.utcnow()

            # Mark tool_usage_log as modified for SQLAlchemy to detect change
            flag_modified(execution, "tool_usage_log")

            self.session.add(execution)
            self.session.commit()

            # Invalidate cache after update
            self._invalidate_execution_cache(execution_id)

        except Exception as e:
            logger.warning(f"Failed to log tool usage: {e}")

    def pause_workflow(self, execution_id: UUID, reason: str):
        """Pause a workflow execution.

        Args:
            execution_id: Execution UUID
            reason: Why pausing
        """
        try:
            execution = self.session.get(WorkflowExecution, execution_id)

            if not execution:
                raise ValueError(f"Execution not found: {execution_id}")

            execution.status = "paused"
            execution.updated_at = datetime.utcnow()

            # Log the pause decision
            self.log_decision(
                execution_id,
                "pause_workflow",
                reason,
                execution.metrics
            )

            self.session.add(execution)
            self.session.commit()

            # Invalidate cache after update
            self._invalidate_execution_cache(execution_id)

            logger.info(f"Paused workflow execution {execution_id}: {reason}")

        except Exception as e:
            logger.error(f"Failed to pause workflow: {e}", exc_info=True)
            self.session.rollback()
            raise

    def resume_workflow(self, execution_id: UUID, reason: str):
        """Resume a paused workflow execution.

        Args:
            execution_id: Execution UUID
            reason: Why resuming
        """
        try:
            execution = self.session.get(WorkflowExecution, execution_id)

            if not execution:
                raise ValueError(f"Execution not found: {execution_id}")

            execution.status = "running"
            execution.updated_at = datetime.utcnow()

            # Log the resume decision
            self.log_decision(
                execution_id,
                "resume_workflow",
                reason,
                execution.metrics
            )

            self.session.add(execution)
            self.session.commit()

            # Invalidate cache after update
            self._invalidate_execution_cache(execution_id)

            logger.info(f"Resumed workflow execution {execution_id}: {reason}")

        except Exception as e:
            logger.error(f"Failed to resume workflow: {e}", exc_info=True)
            self.session.rollback()
            raise

    def complete_workflow(self, execution_id: UUID):
        """Mark workflow execution as completed.

        Args:
            execution_id: Execution UUID
        """
        try:
            execution = self.session.get(WorkflowExecution, execution_id)

            if not execution:
                raise ValueError(f"Execution not found: {execution_id}")

            execution.status = "completed"
            execution.completed_at = datetime.utcnow()
            execution.updated_at = datetime.utcnow()

            self.session.add(execution)
            self.session.commit()

            # Invalidate cache after update
            self._invalidate_execution_cache(execution_id)

            logger.info(f"Completed workflow execution {execution_id}")

        except Exception as e:
            logger.error(f"Failed to complete workflow: {e}", exc_info=True)
            self.session.rollback()
            raise
