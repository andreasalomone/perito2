import os
import uuid
import shutil
import tempfile
import pathlib
import asyncio
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from uuid import UUID

from core.models import Case, Document, ReportVersion
from services.gcs_service import download_file_to_temp, get_storage_client
from config import settings
from services import document_processor, llm_handler, docx_generator, case_service
from database import SessionLocal

logger = logging.getLogger(__name__)

async def run_generation_task(case_id: str, organization_id: str):
    """
    Wrapper for background execution that manages its own DB session.
    """
    db = SessionLocal()
    try:
        await process_case_logic(case_id, organization_id, db)
    finally:
        db.close()

async def process_case_logic(case_id: str, organization_id: str, db: Session):
    """
    Core logic to process a Case:
    1. Fetch all Documents.
    2. Download & OCR.
    3. Generate AI Report.
    4. Create ReportVersion (v1).
    """
    # 1. Setup - Get Case
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        logger.error(f"Case {case_id} not found in DB")
        return

    
    # Update status
    case.status = "processing"
    db.commit()

    tmp_dir = tempfile.mkdtemp()
    processed_data_for_llm = []
    
    try:
        # 2. Fetch Documents
        documents = db.query(Document).filter(Document.case_id == case_id).all()
        if not documents:
            logger.warning(f"No documents found for case {case_id}")
            return

        # 3. Process Each File
        for doc in documents:
            gcs_path = doc.gcs_path
            # FIX: Force extraction of extension using pathlib
            suffix = pathlib.Path(gcs_path).suffix
            if not suffix:
                suffix = ".tmp" # Fallback
                
            local_filename = f"file_{doc.id}{suffix}"
            local_path = os.path.join(tmp_dir, local_filename)
            
            logger.info(f"Downloading {gcs_path} to {local_path}...")
            # Run blocking download in thread
            await asyncio.to_thread(download_file_to_temp, gcs_path, local_path)
            
            # Run blocking extraction in thread
            processed = await asyncio.to_thread(document_processor.process_uploaded_file, local_path, tmp_dir)
            processed_data_for_llm.extend(processed)
            
            # Update Doc Status
            doc.ai_status = "processed"
            # doc.ai_extracted_data = processed # Optional: Save raw extraction to DB (JSONB)
            db.commit()

        # 4. Generate with Gemini
        logger.info("Generating text with Gemini...")
        
        # This is already async
        # This is already async
        report_text, token_usage = await llm_handler.generate_report_from_content(
            processed_files=processed_data_for_llm
        )

        # 5. Generate DOCX
        logger.info("Generating DOCX...")
        # Run blocking DOCX generation in thread
        docx_stream = await asyncio.to_thread(docx_generator.create_styled_docx, report_text)
        
        # 6. Upload Result
        bucket_name = settings.STORAGE_BUCKET_NAME
        
        # Use organization_id for storage path
        blob_name = f"reports/{organization_id}/{case_id}/v1_AI_Draft.docx"
        
        def upload_blob():
            storage_client = get_storage_client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.upload_from_file(docx_stream, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            return f"gs://{bucket_name}/{blob_name}"

        # Run blocking upload in thread
        final_docx_path = await asyncio.to_thread(upload_blob)

        # 7. Save Version 1
        # We use the case_service helper, but we need to adapt it since we are inside a transaction/session
        # Or just create it directly here.
        
        # Check if v1 exists (idempotency)
        v1 = db.query(ReportVersion).filter(ReportVersion.case_id == case_id, ReportVersion.version_number == 1).first()
        if not v1:
            v1 = ReportVersion(
                case_id=case_id,
                organization_id=organization_id,
                version_number=1,
                docx_storage_path=final_docx_path,
                ai_raw_output=report_text,
                is_final=False
            )
            db.add(v1)
        else:
            # Update existing v1
            v1.docx_storage_path = final_docx_path
            v1.ai_raw_output = report_text
            
        case.status = "open" # Back to open, ready for review
        db.commit()
        logger.info("✅ Case processing completed successfully. Version 1 created.")

    except Exception as e:
        logger.error(f"❌ Error during generation: {e}", exc_info=True)
        case.status = "error"
        db.commit()
        raise e 
    finally:
        shutil.rmtree(tmp_dir)

async def generate_docx_variant(
    version_id: str, 
    template_type: str, 
    db: Session
) -> str:
    """
    Generates a DOCX variant (BN or Salomone) on the fly from an existing ReportVersion.
    Returns the signed URL for the generated file.
    """
    # 1. Fetch Version
    version = db.query(ReportVersion).filter(ReportVersion.id == version_id).first()
    if not version:
        raise ValueError("Report version not found")
        
    if not version.ai_raw_output:
        raise ValueError("No AI content found for this version")

    # 2. Select Generator
    if template_type == "salomone":
        from services import docx_generator_salomone as generator
        suffix = "_Salomone.docx"
    elif template_type == "bn":
        from services import docx_generator as generator
        suffix = "_BN.docx"
    else:
        raise ValueError("Invalid template type")

    # 3. Generate DOCX
    logger.info(f"Generating DOCX variant {template_type} for version {version_id}...")
    docx_stream = await asyncio.to_thread(generator.create_styled_docx, version.ai_raw_output)

    # 4. Upload to GCS
    bucket_name = settings.STORAGE_BUCKET_NAME
    # Use a specific path for variants to avoid overwriting the main one if desired, 
    # or overwrite if we want to switch 'default'. 
    # Let's use a variant path: reports/{org}/{case}/variants/{ver_id}_{type}.docx
    blob_name = f"reports/{version.organization_id}/{version.case_id}/variants/{version.id}{suffix}"

    def upload_blob():
        storage_client = get_storage_client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        # Reset stream pointer just in case
        if hasattr(docx_stream, 'seek'):
            docx_stream.seek(0)
        blob.upload_from_file(docx_stream, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        return blob

    blob = await asyncio.to_thread(upload_blob)
    
    # 5. Generate Signed URL (Read)
    # We can use the blob object directly or the gcs_service helper
    url = blob.generate_signed_url(
        version="v4",
        expiration=3600, # 1 hour
        method="GET"
    )
    
    return url
