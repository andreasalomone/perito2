import argparse
import os
import sys

# Add the backend directory to sys.path so we can import app modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models import Organization, User


def create_org(org_name: str, admin_email: str, admin_uid: str):
    db: Session = SessionLocal()
    try:
        # 1. Create Organization
        print(f"Creating Organization: {org_name}")
        new_org = Organization(name=org_name)
        db.add(new_org)
        db.flush() # Get ID
        
        # 2. Create Admin User
        print(f"Creating Admin User: {admin_email} (UID: {admin_uid})")
        new_user = User(
            id=admin_uid,
            email=admin_email,
            organization_id=new_org.id,
            role="admin"
        )
        db.add(new_user)
        
        db.commit()
        print("Success! Organization and Admin created.")
        print(f"Org ID: {new_org.id}")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new Organization and Admin User")
    parser.add_argument("--org", required=True, help="Name of the Organization")
    parser.add_argument("--email", required=True, help="Email of the Admin User")
    parser.add_argument("--uid", required=True, help="Firebase UID of the Admin User")
    
    args = parser.parse_args()
    
    create_org(args.org, args.email, args.uid)
