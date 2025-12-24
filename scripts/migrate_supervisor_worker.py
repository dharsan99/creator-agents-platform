"""Database migration script for Supervisor-Worker architecture.

This script creates all new tables required for the supervisor-worker
pattern with tool calling, workflow versioning, and human-in-loop.

New Tables:
- missing_tool_requests (Phase 1)
- workflows, workflow_versions, workflow_executions (Phase 3)
- worker_tasks (Phase 4)
- conversation_threads, messages (Phase 5)

Usage:
    python scripts/migrate_supervisor_worker.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
from sqlmodel import SQLModel, create_engine

from app.config import settings
from app.infra.db.connection import engine

# Import all models to ensure they're registered with SQLModel
from app.infra.db.models import (
    Creator,
    Consumer,
    ConsumerContext,
    Event,
    Agent,
    AgentTrigger,
    AgentInvocation,
    Action,
)
from app.infra.db.creator_profile_models import (
    CreatorProfile,
    OnboardingLog,
)
from app.domain.tools.missing_tools import MissingToolRequest
from app.domain.workflow.models import Workflow, WorkflowVersion, WorkflowExecution
from app.domain.tasks.models import WorkerTask
from app.domain.conversations.models import ConversationThread, Message

logger = logging.getLogger(__name__)


def create_tables():
    """Create all database tables for supervisor-worker architecture.

    This function is idempotent - it can be run multiple times safely.
    Existing tables will not be modified.
    """
    logger.info("=" * 60)
    logger.info("Supervisor-Worker Architecture Migration")
    logger.info("=" * 60)
    logger.info(f"Database: {settings.database_url}")
    logger.info("")

    try:
        # Use global engine from connection module

        logger.info("Creating tables...")
        logger.info("")

        # Create all tables
        # SQLModel will only create tables that don't exist
        SQLModel.metadata.create_all(engine)

        logger.info("✅ Tables created successfully!")
        logger.info("")

        # List all new tables
        logger.info("New Tables for Supervisor-Worker Architecture:")
        logger.info("")

        logger.info("Phase 1 - Tool Calling:")
        logger.info("  - missing_tool_requests")
        logger.info("")

        logger.info("Phase 3 - Workflow Versioning:")
        logger.info("  - workflows")
        logger.info("  - workflow_versions")
        logger.info("  - workflow_executions")
        logger.info("")

        logger.info("Phase 4 - Worker Tasks:")
        logger.info("  - worker_tasks")
        logger.info("")

        logger.info("Phase 5 - Human-in-Loop:")
        logger.info("  - conversation_threads")
        logger.info("  - messages")
        logger.info("")

        logger.info("Existing Tables (Unchanged):")
        logger.info("  - creators")
        logger.info("  - consumers")
        logger.info("  - consumer_context")
        logger.info("  - events")
        logger.info("  - agents")
        logger.info("  - agent_triggers")
        logger.info("  - agent_invocations")
        logger.info("  - actions")
        logger.info("  - creator_profiles")
        logger.info("  - onboarding_logs")
        logger.info("")

        logger.info("=" * 60)
        logger.info("Migration completed successfully!")
        logger.info("=" * 60)
        logger.info("")

        logger.info("Next Steps:")
        logger.info("1. Deploy MainAgent:")
        logger.info("   python scripts/deploy_main_agent.py")
        logger.info("   OR")
        logger.info("   POST /onboarding/admin/deploy-main-agent")
        logger.info("")
        logger.info("2. Start consumer services:")
        logger.info("   docker-compose up high-priority-consumer worker-task-consumer")
        logger.info("")
        logger.info("3. Test with creator_onboarded event")
        logger.info("")

    except Exception as e:
        logger.error("=" * 60)
        logger.error("Migration failed!")
        logger.error("=" * 60)
        logger.error(f"Error: {e}")
        logger.error("")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def verify_tables():
    """Verify that all required tables exist.

    Returns:
        bool: True if all tables exist, False otherwise
    """
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    required_tables = {
        # Existing tables
        "creators",
        "consumers",
        "consumer_context",
        "events",
        "agents",
        "agent_triggers",
        "agent_invocations",
        "actions",
        "creator_profiles",
        "onboarding_logs",
        # New tables
        "missing_tool_requests",
        "workflows",
        "workflow_versions",
        "workflow_executions",
        "worker_tasks",
        "conversation_threads",
        "messages",
    }

    missing_tables = required_tables - existing_tables

    if missing_tables:
        logger.warning(f"Missing tables: {missing_tables}")
        return False

    logger.info("✅ All required tables exist")
    return True


def main():
    """Main entry point."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create tables
    create_tables()

    # Verify tables
    logger.info("Verifying tables...")
    if verify_tables():
        logger.info("Migration verification successful!")
    else:
        logger.warning("Some tables may be missing. Review the output above.")


if __name__ == "__main__":
    main()
