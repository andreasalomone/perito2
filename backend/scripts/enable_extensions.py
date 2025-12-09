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

import database
from google.cloud.sql.connector import Connector
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def enable_extensions():
    # Initialize the connector manually as we are not running via FastAPI lifespan
    database.connector = Connector()
    logger.info("✅ Google Cloud SQL Connector initialized")

    try:
        with database.engine.connect() as connection:
            logger.info("🔌 Connected to database")
            
            extensions = ["uuid-ossp", "btree_gin", "vector"]
            
            for ext in extensions:
                try:
                    logger.info(f"🛠️  Enabling extension: {ext}")
                    # Use double quotes for extension name to handle hyphens safely, though usually not strictly needed for these
                    connection.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{ext}";'))
                    logger.info(f"✅ Extension {ext} enabled")
                except Exception as e:
                    logger.error(f"❌ Failed to enable extension {ext}: {e}")
            
            connection.commit()
            logger.info("🎉 All extensions processed")
            
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
    finally:
        if database.connector:
            database.connector.close()
            logger.info("🛑 Google Cloud SQL Connector closed")

if __name__ == "__main__":
    enable_extensions()
