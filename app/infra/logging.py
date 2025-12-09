"""Structured logging with correlation IDs."""
import logging
import uuid
from contextvars import ContextVar
from typing import Optional

# Context variables for correlation IDs
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
creator_id_var: ContextVar[Optional[str]] = ContextVar("creator_id", default=None)
consumer_id_var: ContextVar[Optional[str]] = ContextVar("consumer_id", default=None)
event_id_var: ContextVar[Optional[str]] = ContextVar("event_id", default=None)
invocation_id_var: ContextVar[Optional[str]] = ContextVar("invocation_id", default=None)


class CorrelationIdFilter(logging.Filter):
    """Logging filter that adds correlation IDs to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation IDs to log record."""
        record.correlation_id = correlation_id_var.get() or "-"
        record.creator_id = creator_id_var.get() or "-"
        record.consumer_id = consumer_id_var.get() or "-"
        record.event_id = event_id_var.get() or "-"
        record.invocation_id = invocation_id_var.get() or "-"
        return True


def setup_logging():
    """Configure structured logging with correlation IDs."""
    # Add filter to root logger
    correlation_filter = CorrelationIdFilter()

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(correlation_filter)

    # Update format to include correlation IDs
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - "
        "[correlation_id=%(correlation_id)s] "
        "[creator_id=%(creator_id)s] "
        "[consumer_id=%(consumer_id)s] "
        "[event_id=%(event_id)s] "
        "[invocation_id=%(invocation_id)s] - "
        "%(message)s"
    )

    for handler in root_logger.handlers:
        handler.setFormatter(formatter)


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set correlation ID for current context."""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())

    correlation_id_var.set(correlation_id)
    return correlation_id


def set_creator_id(creator_id: Optional[str]) -> None:
    """Set creator ID for current context."""
    creator_id_var.set(creator_id)


def set_consumer_id(consumer_id: Optional[str]) -> None:
    """Set consumer ID for current context."""
    consumer_id_var.set(consumer_id)


def set_event_id(event_id: Optional[str]) -> None:
    """Set event ID for current context."""
    event_id_var.set(event_id)


def set_invocation_id(invocation_id: Optional[str]) -> None:
    """Set invocation ID for current context."""
    invocation_id_var.set(invocation_id)


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id_var.get()


# Middleware for FastAPI to add correlation IDs
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation IDs to requests."""

    async def dispatch(self, request: Request, call_next):
        """Process request with correlation ID."""
        # Get or create correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        set_correlation_id(correlation_id)

        # Get creator ID if present
        creator_id = request.headers.get("X-Creator-ID")
        if creator_id:
            set_creator_id(creator_id)

        response: Response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response
