from database import get_db, SessionLocal
from sqlalchemy import text
from google.cloud.sql.connector import Connector
import database

def migrate():
    # Manually initialize the connector since we aren't running via FastAPI lifespan
    database.connector = Connector()
    
    db = SessionLocal()
    try:
        print("Adding organization_id column to report_log table...")
        # Check if column exists first to avoid error
        check_sql = text("SELECT column_name FROM information_schema.columns WHERE table_name='report_log' AND column_name='organization_id'")
        result = db.execute(check_sql).fetchone()
        
        if not result:
            sql = text("ALTER TABLE report_log ADD COLUMN organization_id VARCHAR(36)")
            db.execute(sql)
            db.commit()
            print("✅ Successfully added organization_id column.")
        else:
            print("ℹ️ Column organization_id already exists.")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
    finally:
        db.close()
        # Cleanup
        if database.connector:
            database.connector.close()

if __name__ == "__main__":
    migrate()
