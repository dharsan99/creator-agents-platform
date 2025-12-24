"""Logfire configuration and initialization.

This module provides distributed tracing and observability using Pydantic Logfire.
Features:
- Auto-instrumentation for FastAPI, SQLAlchemy, OpenAI
- Custom spans for agent execution, workflow orchestration
- Performance monitoring and error tracking
"""
import logging
from typing import Optional

from app.config import settings, pydantic_config

logger = logging.getLogger(__name__)

# Global Logfire instance
_logfire_instance: Optional[object] = None


def initialize_logfire() -> Optional[object]:
    """Initialize Logfire distributed tracing.

    Returns:
        Logfire instance if enabled and configured, None otherwise

    Configuration:
        - ENABLE_LOGFIRE=true in .env
        - LOGFIRE_TOKEN=<your-token> from https://logfire.pydantic.dev
        - LOGFIRE_SERVICE_NAME=creator-agents-platform
        - LOGFIRE_ENVIRONMENT=development/staging/production
    """
    global _logfire_instance

    # Return existing instance if already initialized
    if _logfire_instance is not None:
        return _logfire_instance

    # Check if Logfire is enabled
    if not pydantic_config.is_logfire_enabled():
        logger.info("Logfire disabled via feature flag or missing token")
        return None

    try:
        import logfire

        # Configure Logfire
        logfire.configure(
            token=settings.logfire_token,
            service_name=settings.logfire_service_name,
            environment=settings.logfire_environment,
            send_to_logfire="if-token-present",
            console=False,  # Don't duplicate console logs
        )

        logger.info(
            "Logfire initialized successfully",
            extra={
                "service_name": settings.logfire_service_name,
                "environment": settings.logfire_environment,
            },
        )

        _logfire_instance = logfire
        return logfire

    except ImportError:
        logger.warning("Logfire package not installed. Run: pip install logfire")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Logfire: {e}", exc_info=True)
        return None


def get_logfire() -> Optional[object]:
    """Get Logfire instance.

    Returns:
        Logfire instance if initialized, None otherwise
    """
    return _logfire_instance


def instrument_fastapi(app):
    """Auto-instrument FastAPI application with Logfire.

    Args:
        app: FastAPI application instance

    Instruments:
        - HTTP requests (method, path, status, duration)
        - Request/response headers and bodies
        - Exceptions and errors
    """
    if not pydantic_config.is_logfire_enabled():
        return

    logfire = get_logfire()
    if logfire is None:
        return

    try:
        logfire.instrument_fastapi(app)
        logger.info("FastAPI instrumented with Logfire")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}", exc_info=True)


def instrument_sqlalchemy(engine):
    """Auto-instrument SQLAlchemy engine with Logfire.

    Args:
        engine: SQLAlchemy engine instance

    Instruments:
        - SQL queries (SELECT, INSERT, UPDATE, DELETE)
        - Query duration and row counts
        - Connection pool metrics
    """
    if not pydantic_config.is_logfire_enabled():
        return

    logfire = get_logfire()
    if logfire is None:
        return

    try:
        logfire.instrument_sqlalchemy(engine=engine)
        logger.info("SQLAlchemy instrumented with Logfire")
    except Exception as e:
        logger.error(f"Failed to instrument SQLAlchemy: {e}", exc_info=True)


def instrument_openai():
    """Auto-instrument OpenAI client with Logfire.

    Instruments:
        - LLM API calls (model, prompt, completion)
        - Token usage and costs
        - Latency and errors
    """
    if not pydantic_config.is_logfire_enabled():
        return

    logfire = get_logfire()
    if logfire is None:
        return

    try:
        logfire.instrument_openai()
        logger.info("OpenAI instrumented with Logfire")
    except Exception as e:
        logger.error(f"Failed to instrument OpenAI: {e}", exc_info=True)


def span(name: str, **attributes):
    """Create a custom Logfire span for manual instrumentation.

    Args:
        name: Span name (e.g., "agent_execution", "workflow_planning")
        **attributes: Additional attributes to attach to span

    Returns:
        Context manager for span

    Example:
        ```python
        with span("agent_execution", agent_id=str(agent.id)):
            result = agent.execute()
        ```
    """
    logfire = get_logfire()
    if logfire is None:
        # Return no-op context manager if Logfire disabled
        from contextlib import nullcontext

        return nullcontext()

    return logfire.span(name, **attributes)


def log_metric(name: str, value: float, **attributes):
    """Log a custom metric to Logfire.

    Args:
        name: Metric name (e.g., "agent_execution_time")
        value: Metric value
        **attributes: Additional attributes (agent_id, workflow_id, etc.)

    Example:
        ```python
        log_metric("agent_execution_time", 1.234, agent_id=str(agent.id))
        ```
    """
    logfire = get_logfire()
    if logfire is None:
        return

    try:
        logfire.info(
            f"{name}={value}",
            _tags=["metric"],
            metric_name=name,
            metric_value=value,
            **attributes,
        )
    except Exception as e:
        logger.error(f"Failed to log metric {name}: {e}", exc_info=True)
