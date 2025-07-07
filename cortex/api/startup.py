from contextlib import asynccontextmanager
from fastapi import FastAPI

from ..core.logger import get_logger
from ..core.database.manager import init_database, close_database

logger = get_logger("startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager for FastAPI application."""
    # Startup
    logger.info("Starting up Cortex API...")
    await init_database()
    yield

    # Shutdown
    logger.info("Shutting down Cortex API...")
    await close_database()
