"""
LinkPlease Backend Application

A robust system for receiving webhook events from a mock Instagram API,
matching comments against user-defined rules, and sending direct messages.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging

from app.api import rules, webhooks, stats, health, deliveries
from app.database import engine, Base
from app.config import settings
from app.worker import DeliveryWorker

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and optionally run the delivery worker."""
    logger.info("Starting up LinkPlease backend...")

    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized")

    worker = None
    worker_task = None

    # In production, run the delivery worker inside the same
    # web service so a separate paid background worker is not required.
    if settings.environment == "production":
        worker = DeliveryWorker()
        worker_task = asyncio.create_task(worker.run())
        logger.info("Embedded delivery worker started")

    try:
        yield
    finally:
        if worker is not None:
            logger.info("Stopping embedded delivery worker...")
            worker.running = False

            if worker_task is not None:
                try:
                    await asyncio.wait_for(worker_task, timeout=10)
                except asyncio.TimeoutError:
                    logger.warning("Worker did not stop within timeout")
                    worker_task.cancel()
                    try:
                        await worker_task
                    except asyncio.CancelledError:
                        pass

        logger.info("Shutting down LinkPlease backend...")


app = FastAPI(
    title="LinkPlease Backend",
    description="Rule-based DM automation for Instagram",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
cors_origins = [origin.strip() for origin in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="", tags=["health"])
app.include_router(rules.router, prefix="", tags=["rules"])
app.include_router(webhooks.router, prefix="", tags=["webhooks"])
app.include_router(stats.router, prefix="", tags=["stats"])
app.include_router(deliveries.router, prefix="", tags=["deliveries"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "LinkPlease Backend",
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )