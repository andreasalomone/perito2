from sqlalchemy import inspect

from app import app
from core.database import db

with app.app_context():
    print("Database URL:", db.engine.url)
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print("Tables:", tables)
    except Exception as e:
        print("Error listing tables:", e)
