import logging
import os
import sys
from logging.config import fileConfig

from google.cloud.sql.connector import Connector, IPTypes
from sqlalchemy import create_engine, pool

from alembic import context

# -----------------------------------------------------------------------------
# 1. Path Setup & Imports
# -----------------------------------------------------------------------------
# Add the project root to python path so we can import 'app'
sys.path.append(os.getcwd())

import app.models  # noqa: F401 - Ensure models are registered with Base.metadata
from app.core.config import settings
from app.db.database import Base  # Import the declarative base from our refactored file

# -----------------------------------------------------------------------------
# 2. Config & Logging
# -----------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# -----------------------------------------------------------------------------
# 3. Metadata Definition
# -----------------------------------------------------------------------------
# This is crucial for 'autogenerate' support
target_metadata = Base.metadata


# -----------------------------------------------------------------------------
# 4. Offline Migrations (Generate SQL Scripts)
# -----------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.
    """
    # In offline mode, we don't connect to Cloud SQL.
    # We just need the dialect name (postgresql).
    # Ensure alembic.ini has: sqlalchemy.url = postgresql+pg8000://...
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# -----------------------------------------------------------------------------
# 5. Online Migrations (Apply Changes to DB)
# -----------------------------------------------------------------------------
def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    In this scenario we need to create an Engine and associate a connection with the context.

    CRITICAL CHANGE:
    We verify if we are running locally (Development) or in Cloud Run (Production).
    If Production, we use the Google Cloud SQL Connector.
    If Local, we connect via TCP (localhost:5432), assuming Cloud SQL Proxy is running.
    """

    if settings.RUN_LOCALLY:
        # Local Development: Connect via TCP (Cloud SQL Proxy or Local DB)
        # We construct the URL manually to handle special chars in password safely
        from sqlalchemy.engine.url import URL

        # Use standard credentials (report_user owns alembic_version)
        db_user = settings.DB_USER
        db_pass = settings.DB_PASS

        url = URL.create(
            drivername="postgresql+pg8000",
            username=db_user,
            password=db_pass,
            host="localhost",
            port=5432,
            database=settings.DB_NAME,
        )

        connectable = create_engine(url)

        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)

            with context.begin_transaction():
                context.run_migrations()

    else:
        # Production: Use Cloud SQL Connector

        # Define the connector helper internal to this scope
        # We don't rely on the app's global state because the app isn't running here.

        def getconn():
            """
            Standalone connector function specifically for migrations.
            Uses a fresh Connector instance.
            Uses standard credentials (report_user owns alembic_version).
            """
            db_user = settings.DB_USER
            db_pass = settings.DB_PASS

            # Note: We must access the connector instance from the outer scope's context manager
            conn = global_connector.connect(
                instance_connection_string=settings.CLOUD_SQL_CONNECTION_NAME,
                driver="pg8000",
                user=db_user,
                password=db_pass,
                db=settings.DB_NAME,
                ip_type=IPTypes.PUBLIC,
            )
            return conn

        # -------------------------------------------------------------
        # Scenario A: Using Cloud SQL Connector (Production / Staging)
        # -------------------------------------------------------------
        # We use a Context Manager to ensure the Connector is closed after migration
        with Connector() as global_connector:

            # Create the engine dynamically
            connectable = create_engine(
                "postgresql+pg8000://",
                creator=getconn,
                poolclass=pool.NullPool,  # No need for pooling during migrations
            )

            with connectable.connect() as connection:
                context.configure(
                    connection=connection, target_metadata=target_metadata
                )

                with context.begin_transaction():
                    context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
