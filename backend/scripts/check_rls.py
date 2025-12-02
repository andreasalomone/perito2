import os
import sys
from dotenv import load_dotenv

# Load env vars BEFORE importing config/database
load_dotenv("backend/.env")

# FIX: Hardcoded Secrets - Only set GOOGLE_APPLICATION_CREDENTIALS if needed
# In Cloud environments (Cloud Run, Cloud Shell), Application Default Credentials work automatically
if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS") and not os.getenv("K_SERVICE"):
    # Local development: look for service account file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sa_path = os.path.join(script_dir, "service-account.json")
    
    if not os.path.exists(sa_path):
        print(f"ERROR: Service account file not found at {sa_path}")
        print("Please set GOOGLE_APPLICATION_CREDENTIALS env var or run from Cloud environment")
        sys.exit(1)
    
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_path

from sqlalchemy import text
from google.cloud.sql.connector import Connector
from app.db import database
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
