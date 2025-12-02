import os
from dotenv import load_dotenv

# Load env vars BEFORE importing config/database
load_dotenv("backend/.env")

# Fix GOOGLE_APPLICATION_CREDENTIALS path to be absolute or relative to backend
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") == "service-account.json":
    # If it's just the filename, assume it's in the same dir as this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(script_dir, "service-account.json")

from app.db.database import engine, Base
from app.db import database
from google.cloud.sql.connector import Connector

# Import all models to ensure they are registered
from app.models import Organization, User, Client, Case, Document, ReportVersion, MLTrainingPair

def reset_db():
    print("Initializing connector...")
    database.connector = Connector()
    
    try:
        print("Creating new tables...")
        Base.metadata.create_all(bind=engine)
        print("✅ Database schema initialized.")
    finally:
        if database.connector:
            database.connector.close()

if __name__ == "__main__":
    reset_db()
