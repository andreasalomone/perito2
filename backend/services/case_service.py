from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import UUID
from core.models import Case, ReportVersion, MLTrainingPair, Document, Client

def get_or_create_client(db: Session, name: str) -> Client:
    client = db.query(Client).filter(Client.name == name).first()
    if not client:
        # Note: Since RLS is active, this automatically assigns correct Org ID
        # But we need to grab it from session or context if not implicit.
        # Assuming the caller (API) has set RLS context correctly.
        # We need to query what the current Org ID is to insert safely.
        # Better approach: The API caller passes the org_id explicitly to helper functions.
        # For now, we rely on the DB session having the variable set, but SQLAlchemy insert might need explicit ID if not handled by DB trigger.
        # However, our models define organization_id as nullable=False.
        # Let's assume the API layer handles the creation properly or we fetch the org_id from the session variable.
        
        # Fetch current org_id from session variable
        result = db.execute(text("SELECT current_setting('app.current_org_id')")).scalar()
        if result:
            client = Client(name=name, organization_id=result)
            db.add(client)
            db.commit()
            db.refresh(client)
        else:
             # Fallback or error if org_id not set
             pass
             
    return client

# --- THE CRITICAL WORKFLOWS ---

def create_ai_version(db: Session, case_id: UUID, org_id: UUID, ai_text: str, docx_path: str):
    """
    Called by the Worker after Gemini finishes.
    Creates Version 1 (or next version).
    """
    # 1. Determine version number
    count = db.query(ReportVersion).filter(ReportVersion.case_id == case_id).count()
    next_version = count + 1
    
    # 2. Save Version
    version = ReportVersion(
        case_id=case_id,
        organization_id=org_id,
        version_number=next_version,
        docx_storage_path=docx_path,
        ai_raw_output=ai_text,
        is_final=False
    )
    db.add(version)
    db.commit()
    return version

def finalize_case(db: Session, case_id: UUID, org_id: UUID, final_docx_path: str):
    """
    Called when User uploads the final "signed" PDF/DOCX.
    1. Save new version.
    2. Mark as Final.
    3. Create ML Training Pair.
    """
    # 1. Create Final Version
    count = db.query(ReportVersion).filter(ReportVersion.case_id == case_id).count()
    final_version = ReportVersion(
        case_id=case_id,
        organization_id=org_id,
        version_number=count + 1,
        docx_storage_path=final_docx_path,
        is_final=True
    )
    db.add(final_version)
    db.flush() # Get ID
    
    # 2. Find the original AI Draft (Version 1 usually, or last AI version)
    # Simple logic: First version is AI.
    ai_version = db.query(ReportVersion).filter(
        ReportVersion.case_id == case_id,
        ReportVersion.version_number == 1
    ).first()
    
    if ai_version:
        # 3. THE GOLD MINE: Create Training Pair
        pair = MLTrainingPair(
            case_id=case_id,
            ai_version_id=ai_version.id,
            final_version_id=final_version.id
        )
        db.add(pair)
        
    db.commit()
    return final_version

def trigger_extraction_task(doc_id: UUID, org_id: str):
    # Placeholder for Cloud Task trigger
    # In a real implementation, this would use google-cloud-tasks to enqueue a task
    # For now, we just print or log
    print(f"🚀 Triggering extraction for doc {doc_id} in org {org_id}")
