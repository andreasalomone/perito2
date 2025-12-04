import os
import sys
from sqlalchemy import create_engine, inspect, text

# Add backend to path to import settings if needed, but we can just use the env var or default
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.config import settings

def verify_indexes():
    print("Connecting to database...")
    # Construct DB URL manually since it's not in Settings
    # We are using Cloud SQL Proxy, so host is localhost
    database_url = f"postgresql+pg8000://{settings.DB_USER}:{settings.DB_PASS}@localhost:5432/{settings.DB_NAME}"
    
    if not database_url:
        print("Error: Could not construct DATABASE_URL.")
        return

    engine = create_engine(database_url)
    inspector = inspect(engine)

    print("\n--- Checking Indexes ---")
    
    # Check Cases
    cases_indexes = inspector.get_indexes('cases')
    print(f"\nTable: cases")
    found_dashboard = False
    for idx in cases_indexes:
        print(f"  - {idx['name']}: {idx['column_names']}")
        if idx['name'] == 'idx_cases_dashboard':
            found_dashboard = True
    
    if not found_dashboard:
        print("  [WARNING] 'idx_cases_dashboard' is MISSING!")
    else:
        print("  [OK] 'idx_cases_dashboard' found.")

    # Check Documents
    docs_indexes = inspector.get_indexes('documents')
    print(f"\nTable: documents")
    found_doc_case = False
    for idx in docs_indexes:
        print(f"  - {idx['name']}: {idx['column_names']}")
        if idx['name'] == 'idx_documents_case':
            found_doc_case = True
            
    if not found_doc_case:
        print("  [WARNING] 'idx_documents_case' is MISSING!")
    else:
        print("  [OK] 'idx_documents_case' found.")

if __name__ == "__main__":
    verify_indexes()
