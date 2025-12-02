from google.cloud.sql.connector import Connector, IPTypes
import logging

logger = logging.getLogger(__name__)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.core.config import settings

# 1. Initialize the Connector (Global State)
# We initialize it as None and set it up in the lifespan event
connector = None

def getconn():
    """
    Helper function used by SQLAlchemy to ask Google for a fresh connection.
    """
    global connector
    conn = connector.connect(
        settings.CLOUD_SQL_CONNECTION_NAME,
        "pg8000",
        user=settings.DB_USER,
        password=settings.DB_PASS,
        db=settings.DB_NAME,
        ip_type=IPTypes.PUBLIC,  # Uses the Public IP (Secured by the Connector)
    )
    return conn

# 2. Create the SQLAlchemy Engine
# We tell SQLAlchemy: "Don't use a normal URL, use this getconn() function instead"
engine = create_engine(
    "postgresql+pg8000://",
    creator=getconn,
    # Connection Pool Optimization for Cloud Run Horizontal Scaling
    # Cloud Run scales horizontally (e.g., 50 concurrent users = ~3-5 containers)
    # CRITICAL: Use NullPool to prevent connection exhaustion:
    #   - Cloud Run containers are ephemeral and stateless.
    #   - Keeping a pool of connections open per container (multiplier effect) is dangerous.
    #   - NullPool ensures connections are closed immediately after use.
    poolclass=NullPool,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 3. Dependency for FastAPI Routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def close_db_connection():
    if connector:
        connector.close()
        logger.info("🛑 Google Cloud SQL Connector closed")

# 4. Lifespan Manager (Handles Startup/Shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs when Cloud Run starts the container.
    Initializes the connection pool safely.
    """
    global connector
    connector = Connector()
    print("✅ Google Cloud SQL Connector initialized")
    
    # Create tables if they don't exist (Simple migration)
    # In a real SaaS, use Alembic, but this is fine for MVP
    # Base.metadata.create_all(bind=engine)
    
    yield
    
    # Cleanup on shutdown
    connector.close()
    print("🛑 Google Cloud SQL Connector closed")