"""FastAPI application entrypoint."""
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.api.routers import (
    creators,
    consumers,
    products,
    events,
    agents,
    onboarding,
    conversations,
    dlq,
    performance,
    workflows,
    tasks,
    admin,
    email_webhooks,
)
from app.infra.logging import setup_logging, CorrelationIdMiddleware
from app.infra.metrics import get_metrics

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Setup structured logging with correlation IDs
setup_logging()

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track HTTP request metrics."""

    async def dispatch(self, request: Request, call_next):
        """Track request duration and status."""
        start_time = time.time()
        metrics = get_metrics()

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Track metrics
            metrics.http_requests.labels(
                method=request.method,
                endpoint=request.url.path,
                status=response.status_code
            ).inc()

            metrics.http_request_duration.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)

            return response

        except Exception as e:
            duration = time.time() - start_time

            # Track error
            metrics.http_requests.labels(
                method=request.method,
                endpoint=request.url.path,
                status=500
            ).inc()

            metrics.http_request_duration.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)

            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Creator Agents Platform...")
    # Initialize metrics
    get_metrics()
    logger.info("Metrics service initialized")
    yield
    logger.info("Shutting down Creator Agents Platform...")


# Create FastAPI app
app = FastAPI(
    title="Creator Agents Platform",
    description="Event-driven CRM and AI agent runtime for creators",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add correlation ID middleware
app.add_middleware(CorrelationIdMiddleware)

# Add metrics middleware
app.add_middleware(MetricsMiddleware)

# Include routers
app.include_router(creators.router)
app.include_router(consumers.router)
app.include_router(products.router)
app.include_router(events.router)
app.include_router(agents.router)
app.include_router(onboarding.router)
app.include_router(conversations.router)
app.include_router(dlq.router)
app.include_router(performance.router)
app.include_router(workflows.router)  # Dashboard integration
app.include_router(tasks.router)  # Dashboard integration
app.include_router(admin.router)  # Admin endpoints for dashboard
app.include_router(email_webhooks.router)  # Email status webhooks


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "creator-agents"}


@app.get("/metrics")
def metrics_endpoint():
    """Prometheus metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    """
    metrics = get_metrics()
    return Response(
        content=metrics.export_metrics(),
        media_type=metrics.get_content_type()
    )


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "service": "Creator Agents Platform",
        "version": "1.0.0",
        "docs": "/docs",
        "metrics": "/metrics",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.env == "development",
    )
