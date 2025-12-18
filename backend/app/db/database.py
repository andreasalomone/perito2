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
        return connector.connect(
            instance_connection_string=settings.CLOUD_SQL_CONNECTION_NAME,
            driver="pg8000",
            user=settings.DB_USER,
            password=settings.DB_PASS,
            db=settings.DB_NAME,
            ip_type=IPTypes.PUBLIC,
        )
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

from sqlalchemy import event

# Base is imported from app.models.base to avoid circular imports
from app.models.base import (  # noqa: F401 - Required for SQLAlchemy model registration
    Base,
)

# -----------------------------------------------------------------------------
# 4. RLS Cleanup Listeners (Pool Level)
# -----------------------------------------------------------------------------
# CRITICAL: asyncpg does NOT support multiple statements in a single execute().
# We must execute each RESET separately to avoid "cannot insert multiple commands
# into a prepared statement" errors that cause connection invalidation.
SQL_RESET_USER_UID = "RESET app.current_user_uid"
SQL_RESET_ORG_ID = "RESET app.current_org_id"


def _reset_rls_context(dbapi_connection, connection_record):
    """
    Guaranteed cleanup of RLS context when a connection is returned to the pool.
    This prevents "Context Poisoning" where one user's state leaks to another.
    Handles both pg8000 (sync) and asyncpg (async via sync_engine listener).

    IMPORTANT: Commands are executed separately for asyncpg compatibility.
    """
    try:
        if hasattr(dbapi_connection, "cursor"):
            # pg8000 / standard DBAPI - can batch but we stay consistent
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute(SQL_RESET_USER_UID)
                cursor.execute(SQL_RESET_ORG_ID)
            finally:
                cursor.close()
        elif hasattr(dbapi_connection, "execute"):
            # asyncpg connection - MUST execute separately
            dbapi_connection.execute(SQL_RESET_USER_UID)
            dbapi_connection.execute(SQL_RESET_ORG_ID)
        else:
            logger.warning(
                f"Unknown connection type in RLS reset: {type(dbapi_connection)}"
            )

    except Exception as e:
        logger.warning(
            f"RLS reset failed on checkin: {e}. Attempting rollback cleanup."
        )
        try:
            if hasattr(dbapi_connection, "rollback"):
                dbapi_connection.rollback()

            if hasattr(dbapi_connection, "cursor"):
                cursor = dbapi_connection.cursor()
                try:
                    cursor.execute(SQL_RESET_USER_UID)
                    cursor.execute(SQL_RESET_ORG_ID)
                finally:
                    cursor.close()
            elif hasattr(dbapi_connection, "execute"):
                dbapi_connection.execute(SQL_RESET_USER_UID)
                dbapi_connection.execute(SQL_RESET_ORG_ID)
        except Exception as e2:
            logger.critical(
                f"CRITICAL: Connection sanitization FAILED: {e2}. Invalidating connection."
            )
            connection_record.invalidate()


# Register listeners
event.listen(engine, "checkin", _reset_rls_context)
event.listen(async_engine.sync_engine, "checkin", _reset_rls_context)


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
