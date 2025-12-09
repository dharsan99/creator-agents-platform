"""FastAPI application entrypoint."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routers import creators, consumers, products, events, agents, onboarding
from app.infra.logging import setup_logging, CorrelationIdMiddleware

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Setup structured logging with correlation IDs
setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting Creator Agents Platform...")
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

# Include routers
app.include_router(creators.router)
app.include_router(consumers.router)
app.include_router(products.router)
app.include_router(events.router)
app.include_router(agents.router)
app.include_router(onboarding.router)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "creator-agents"}


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "service": "Creator Agents Platform",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.env == "development",
    )
