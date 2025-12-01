import os
from dotenv import load_dotenv

# Load env vars BEFORE importing config/database
load_dotenv("backend/.env")

# Fix GOOGLE_APPLICATION_CREDENTIALS path to be absolute or relative to backend
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") == "service-account.json":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(script_dir, "service-account.json")

from sqlalchemy import text
from google.cloud.sql.connector import Connector
import database
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_rls():
    database.connector = Connector()
    try:
        with database.engine.connect() as connection:
            logger.info("🔌 Connected to database. Checking RLS status...")
            
            # Query to find tables with RLS enabled
            # relrowsecurity is the flag for RLS
            sql = text("""
                SELECT relname, relrowsecurity 
                FROM pg_class 
                WHERE relname IN ('users', 'cases', 'documents', 'organizations')
                AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public');
            """)
            
            try:
                result = connection.execute(sql)
                for row in result:
                    status = "ENABLED" if row.relrowsecurity else "DISABLED"
                    icon = "🔒" if row.relrowsecurity else "🔓"
                    logger.info(f"{icon} Table '{row.relname}': RLS is {status}")
            except Exception as e:
                logger.error(f"Error querying RLS status: {e}")
                
    finally:
        if database.connector:
            database.connector.close()

if __name__ == "__main__":
    check_rls()
