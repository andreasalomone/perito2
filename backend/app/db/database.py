import logging
from typing import Generator, Any

from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.core.config import settings

# Configure structured logging for Cloud Run
logger = logging.getLogger("app.db")

# -----------------------------------------------------------------------------
# 1. Global State Management
# -----------------------------------------------------------------------------
# We hold the connector instance here, but we access it safely.
_connector: Connector | None = None

def get_connector() -> Connector:
    """
    Retrieves the active Google Cloud SQL Connector.
    Raises a runtime error if the connector has not been initialized.
    """
    if _connector is None:
        raise RuntimeError(
            "Database connector is not initialized. "
            "Ensure the application lifespan has started."
        )
    return _connector

# -----------------------------------------------------------------------------
# 2. Connection Creator
# -----------------------------------------------------------------------------
def getconn() -> Any:
    """
    Callback function used by SQLAlchemy to request a raw DBAPI connection.
    Uses the Cloud SQL Connector to establish a secure mTLS tunnel.
    """
    connector = get_connector()
    try:
        conn = connector.connect(
            instance_connection_string=settings.CLOUD_SQL_CONNECTION_NAME,
            driver="pg8000",
            user=settings.DB_USER,
            password=settings.DB_PASS,
            db=settings.DB_NAME,
            ip_type=IPTypes.PUBLIC,  # Change to IPTypes.PRIVATE if using VPC Peering
        )
        return conn
    except Exception as e:
        logger.error(f"Failed to establish Cloud SQL connection: {e}")
        raise

# -----------------------------------------------------------------------------
# 3. SQLAlchemy Engine & Session Setup
# -----------------------------------------------------------------------------
# We use NullPool for Cloud Run to disable client-side pooling.
# Cloud Run scales horizontally; maintaining a pool per instance exhausts
# the database connection limit.
engine: Engine = create_engine(
    "postgresql+pg8000://",
    creator=getconn,
    poolclass=NullPool,
    # Echo SQL queries in Dev, silence in Prod
    echo=(settings.LOG_LEVEL == "DEBUG"), 
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Base is now imported from app.models.base to avoid circular imports
from app.models.base import Base

# -----------------------------------------------------------------------------
# 4. FastAPI Dependency
# -----------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
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
# 5. Lifespan Event Manager
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifespan Context Manager.
    Handles the initialization and teardown of the Cloud SQL Connector.
    """
    global _connector
    
    logger.info("🚀 Initializing Google Cloud SQL Connector...")
    try:
        _connector = Connector()
        # Optional: Perform a 'warm-up' ping to ensure connectivity before accepting traffic
        # This fails fast if credentials are wrong.
        with engine.connect() as connection:
             connection.execute(text("SELECT 1"))
        logger.info("✅ Database connection established and verified.")
    except Exception as e:
        logger.critical(f"❌ Failed to initialize database: {e}")
        raise e

    yield

    logger.info("🛑 Shutting down Google Cloud SQL Connector...")
    if _connector:
        _connector.close()