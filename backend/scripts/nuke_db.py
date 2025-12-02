import logging
import os
from dotenv import load_dotenv

# Load env vars BEFORE importing config/database
load_dotenv("backend/.env")

# Fix GOOGLE_APPLICATION_CREDENTIALS path to be absolute or relative to backend
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") == "service-account.json":
    # If it's just the filename, assume it's in the same dir as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(script_dir, "service-account.json")

from sqlalchemy import text
from google.cloud.sql.connector import Connector
import database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def nuke_db():
    # SAFETY CHECK 1: Environment
    if os.getenv("ENVIRONMENT") == "production":
        logger.error("❌ CRITICAL: Attempting to nuke database in PRODUCTION environment. Operation aborted.")
        return

    # SAFETY CHECK 2: User Confirmation
    print("⚠️  WARNING: This will DESTROY all data in the 'public' schema.")
    confirmation = input("Type 'NUKE' to confirm: ")
    if confirmation != "NUKE":
        logger.info("Operation cancelled by user.")
        return

    # Initialize the connector manually
    database.connector = Connector()
    logger.info("✅ Google Cloud SQL Connector initialized")

    try:
        with database.engine.connect() as connection:
            logger.info("🔌 Connected to database")
            logger.warning("☢️  NUKING DATABASE: Dropping public schema...")
            
            connection.execute(text("DROP SCHEMA public CASCADE;"))
            connection.execute(text("CREATE SCHEMA public;"))
            connection.execute(text("GRANT ALL ON SCHEMA public TO postgres;"))
            connection.execute(text("GRANT ALL ON SCHEMA public TO public;"))
            
            connection.commit()
            logger.info("✅ Database nuked and paved. Public schema is empty.")
            
    except Exception as e:
        logger.error(f"❌ Database operation failed: {e}")
    finally:
        if database.connector:
            database.connector.close()
            logger.info("🛑 Google Cloud SQL Connector closed")

if __name__ == "__main__":
    nuke_db()
