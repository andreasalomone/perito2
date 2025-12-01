from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from database import get_db
from core.models import Case, Document, ReportVersion, Client
from deps import get_current_user_token
import schemas
from services import gcs_service, case_service

router = APIRouter()

# 1. LIST CASES (RLS Protected automatically)
@router.get("/", response_model=List[schemas.CaseRead])
def list_cases(db: Session = Depends(get_db)):
    # RLS magic: This only returns rows for the current tenant
    return db.query(Case).order_by(Case.created_at.desc()).all()

# 2. CREATE CASE
@router.post("/", response_model=schemas.CaseRead)
def create_case(
    case_in: schemas.CaseCreate, 
    current_user: dict = Depends(get_current_user_token), # From deps.py
    db: Session = Depends(get_db)
):
    # Optional: CRM Logic (Find or Create Client)
    client_id = None
    if case_in.client_name:
        client = case_service.get_or_create_client(db, case_in.client_name)
        client_id = client.id

    new_case = Case(
        reference_code=case_in.reference_code,
        organization_id=current_user['organization_id'], # Explicit for safety
        client_id=client_id,
        status="open"
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)
    return new_case

# 3. GET DETAILS (Docs + Versions)
@router.get("/{case_id}", response_model=schemas.CaseDetail)
def get_case(case_id: UUID, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

# 4. UPLOAD DOCUMENT URL
@router.post("/{case_id}/documents/upload-url")
def get_doc_upload_url(
    case_id: UUID, 
    filename: str, 
    content_type: str,
    db: Session = Depends(get_db)
):
    # Verify case access
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Generate path: uploads/{org_id}/{case_id}/{filename}
    # We use case.organization_id to ensure clean bucket structure
    return gcs_service.generate_upload_signed_url(
        org_id=str(case.organization_id),
        case_id=str(case.id),
        filename=filename,
        content_type=content_type
    )

# 5. REGISTER UPLOADED DOC & TRIGGER AI
@router.post("/{case_id}/documents/register")
def register_document(
    case_id: UUID,
    gcs_path: str,
    filename: str,
    db: Session = Depends(get_db)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    new_doc = Document(
        case_id=case.id,
        organization_id=case.organization_id,
        filename=filename,
        gcs_path=gcs_path,
        ai_status="pending"
    )
    db.add(new_doc)
    db.commit()
    
    # Trigger Async Extraction (Cloud Task or Background)
    # We pass org_id because the Worker needs to set RLS context manually!
    case_service.trigger_extraction_task(new_doc.id, str(case.organization_id))
    
    return {"status": "registered", "doc_id": new_doc.id}

# 6. TRIGGER GENERATION
@router.post("/{case_id}/generate")
async def trigger_generation(
    case_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # In production, this should enqueue a Cloud Task.
    # For now/local, we use FastAPI BackgroundTasks + generation_service
    from services import generation_service
    
    background_tasks.add_task(
        generation_service.run_generation_task,
        case_id=str(case.id),
        organization_id=str(case.organization_id)
    )
    
    return {"status": "generation_started"}

# 7. FINALIZE CASE
@router.post("/{case_id}/finalize")
def finalize_case_endpoint(
    case_id: UUID,
    payload: schemas.FinalizePayload,
    db: Session = Depends(get_db)
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Call service
    final_version = case_service.finalize_case(
        db=db,
        case_id=case.id,
        org_id=case.organization_id,
        final_docx_path=payload.final_docx_path
    )
    
    return {"status": "finalized", "version_id": final_version.id}

# 8. DOWNLOAD GENERATED VARIANT
@router.post("/{case_id}/versions/{version_id}/download-generated")
async def download_generated_variant(
    case_id: UUID,
    version_id: UUID,
    payload: schemas.DownloadVariantPayload,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user_token)
):
    """
    Generates and returns a signed URL for a specific template variant (BN or Salomone).
    """
    # Verify access (RLS)
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
        
    # Verify version belongs to case
    version = db.query(ReportVersion).filter(ReportVersion.id == version_id, ReportVersion.case_id == case_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")

    from services import generation_service
    try:
        url = await generation_service.generate_docx_variant(
            version_id=str(version_id),
            template_type=payload.template_type,
            db=db
        )
        return {"download_url": url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
