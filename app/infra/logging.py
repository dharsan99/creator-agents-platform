"""Structured logging with correlation IDs and JSON formatting."""
import json
import logging
import uuid
from contextvars import ContextVar
from datetime import datetime
from typing import Optional, Dict, Any

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


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Formats log records as JSON for better machine parsing and log aggregation.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation IDs if present
        if hasattr(record, "correlation_id") and record.correlation_id != "-":
            log_data["correlation_id"] = record.correlation_id
        if hasattr(record, "creator_id") and record.creator_id != "-":
            log_data["creator_id"] = record.creator_id
        if hasattr(record, "consumer_id") and record.consumer_id != "-":
            log_data["consumer_id"] = record.consumer_id
        if hasattr(record, "event_id") and record.event_id != "-":
            log_data["event_id"] = record.event_id
        if hasattr(record, "invocation_id") and record.invocation_id != "-":
            log_data["invocation_id"] = record.invocation_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_data["extra"] = record.extra

        return json.dumps(log_data)


def setup_logging(use_json: bool = False):
    """Configure structured logging with correlation IDs.

    Args:
        use_json: If True, use JSON formatter for machine parsing.
                  If False, use human-readable formatter.
                  Defaults to False (human-readable).
    """
    # Add filter to root logger
    correlation_filter = CorrelationIdFilter()

    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(correlation_filter)

    # Choose formatter based on configuration
    if use_json:
        # JSON formatter for production/log aggregation
        formatter = JSONFormatter()
    else:
        # Human-readable formatter for development
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
