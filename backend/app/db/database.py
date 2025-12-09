import logging
from contextlib import asynccontextmanager
from typing import Any, Generator

from fastapi import FastAPI
from google.cloud.sql.connector import Connector, IPTypes, create_async_connector
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings

logger = logging.getLogger("app.db")

# -----------------------------------------------------------------------------
# 1. Global State for BOTH Connectors
# -----------------------------------------------------------------------------
_connector: Connector | None = None
_async_connector: Any | None = None


def get_connector() -> Connector:
    """
    Retrieves the active Google Cloud SQL Connector.
    Raises a runtime error if the connector has not been initialized.
    """
    if _connector is None:
        raise RuntimeError(
            "Sync Connector not initialized. Ensure lifespan has started."
        )
    return _connector


# -----------------------------------------------------------------------------
# 2. Connection Factories
# -----------------------------------------------------------------------------
def getconn() -> Any:
    """Sync Connection Factory (for API endpoints)"""
    connector = get_connector()
    try:
        conn = connector.connect(
            instance_connection_string=settings.CLOUD_SQL_CONNECTION_NAME,
            driver="pg8000",
            user=settings.DB_USER,
            password=settings.DB_PASS,
            db=settings.DB_NAME,
            ip_type=IPTypes.PUBLIC,
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to establish Cloud SQL connection: {e}")
        raise


async def getconn_async() -> Any:
    """Async Connection Factory (for AI Workers)"""
    if _async_connector is None:
        raise RuntimeError(
            "Async Connector not initialized. Ensure lifespan has started."
        )
    return await _async_connector.connect_async(
        settings.CLOUD_SQL_CONNECTION_NAME,
        "asyncpg",
        user=settings.DB_USER,
        password=settings.DB_PASS,
        db=settings.DB_NAME,
        ip_type=IPTypes.PUBLIC,
    )


# -----------------------------------------------------------------------------
# 3. Engines & Session Factories
# -----------------------------------------------------------------------------
# Sync Engine (existing - for API)
engine = create_engine(
    "postgresql+pg8000://",
    creator=getconn,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,  # Recycle connections every 30 mins
    pool_timeout=30,
    echo=(settings.LOG_LEVEL == "DEBUG"),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async Engine (new - for AI Workers)
async_engine = create_async_engine(
    "postgresql+asyncpg://",
    async_creator=getconn_async,
    pool_size=5,
    max_overflow=0,  # Strict limit for workers to prevent starvation
    pool_recycle=1800,
    echo=(settings.LOG_LEVEL == "DEBUG"),
)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

# Base is imported from app.models.base to avoid circular imports
from app.models.base import (  # noqa: F401 - Required for SQLAlchemy model registration
    Base,
)


# -----------------------------------------------------------------------------
# 4. FastAPI Dependency (unchanged)
# -----------------------------------------------------------------------------
def get_raw_db() -> Generator[Session, None, None]:
    """
    Dependency to yield a database session per request.
    Ensures the session is closed even if an error occurs.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


# -----------------------------------------------------------------------------
# 5. Lifespan (UPDATED - initializes BOTH connectors)
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifespan Context Manager.
    Handles initialization and teardown of BOTH Cloud SQL Connectors:
    - Sync Connector (for API endpoints using pg8000)
    - Async Connector (for AI Workers using asyncpg)
    """
    global _connector, _async_connector

    logger.info("🚀 Initializing Database Connectors...")
    try:
        # A. Sync Connector (background thread for cert refresh)
        _connector = Connector()

        # B. Async Connector (current event loop) - MUST be awaited!
        _async_connector = await create_async_connector()

        # Warm-up ping to verify connectivity
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("✅ Database connectors initialized.")
    except Exception as e:
        logger.critical(f"❌ Failed to initialize database: {e}")
        raise e

    yield

    logger.info("🛑 Shutting down Database Connectors...")
    if _connector:
        _connector.close()
    if _async_connector:
        await _async_connector.close_async()  # MUST be close_async(), not close()
