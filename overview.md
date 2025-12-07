# PeritoAI System Overview

**Last Updated:** December 7, 2025
**Project:** `perito-479708`
**Region:** `europe-west1` (Belgium)

## 1. Core Infrastructure

| Component | Resource Name | Details |
|-----------|---------------|---------|
| **Cloud Run (Backend)** | `robotperizia-backend` | `https://api.perito.my` (Custom Domain)<br>Raw: `https://robotperizia-backend-738291935960.europe-west1.run.app` |
| **Cloud Run (Frontend)** | `robotperizia-frontend` | `https://perito.my` (Custom Domain)<br>Raw: `https://robotperizia-frontend-738291935960.europe-west1.run.app` |
| **Cloud SQL** | `robotperizia-db` | **Database:** `perizia_db`<br>**Version:** PostgreSQL 17<br>**Connection:** `perito-479708:europe-west1:robotperizia-db` |
| **Cloud Tasks** | `report-processing-queue` | **Path:** `projects/perito-479708/locations/europe-west1/queues/report-processing-queue`<br>**Rate Limits:** 10/sec, 20 concurrent |
| **Cloud Storage** | `robotperizia-uploads-roberto` | Main storage for case documents and artifacts. |
| **Secret Manager** | Multiple | Managed secrets for DB credentials, API keys, and Service Accounts. |

## 2. Application Architecture

### **Backend (`/backend`)**
*   **Framework:** FastAPI with SQLAlchemy 2.0 (Async + Sync)
*   **Language:** Python 3.13
*   **Auth:** Firebase Authentication (JWT Validation)
*   **Key Services:**
    *   `case_service.py`: Core case orchestration.
    *   `document_processor.py`: Unified file extraction (PDF, DOCX, Images, EML).
    *   `report_generation_service.py`: LLM-based report generation.
*   **Async Workers:** Cloud Tasks trigger specific endpoints in `api/v1/tasks.py` for long-running operations.

### **Frontend (`/frontend`)**
*   **Framework:** Next.js 16 (App Router)
*   **Language:** TypeScript / React 19
*   **Styling:** Tailwind CSS v4 + Radix UI (shadcn/ui compatible)
*   **State/Data:** SWR, Context API for Config & Auth.

## 3. Data Model (PostgreSQL)

**Key Tables & Schemas:**

*   **`organizations`**: Tenant root.
*   **`users`**: Firebase UIDs, linked 1:1 to an Organization.
    *   *Columns:* `id`, `organization_id`, `email`, `role`, `first_name`, `last_name`.
*   **`cases`**: The core "Sinistro" record.
    *   *RLS:* Enforced via `tenant_isolation_policy`.
    *   *Key Fields:* `id`, `organization_id`, `client_id`, `reference_code` (User defined), `status`, `creator_id`.
*   **`documents`**: Files associated with a case.
    *   *Storage Path:* `cases/{case_id}/documents/{filename}` (in GCS).
    *   *Fields:* `gcs_path`, `ai_status`, `ai_extracted_data`.
*   **`clients`**: CRM entity for Insurance Companies/parties.
*   **`audit_logs`**: System-wide action tracking.

## 4. Feature Specifications: Email Intake (Upcoming)

*   **Intake Contact:** `sinistri@perito.my`
*   **Integration Point:** New `email_intake` service module.
*   **Sender Auth:** Will require sender registry (extension of `allowed_emails` or new table).
*   **Flow:**
    1.  Email received (Mechanic TBD: Brevo webhook vs Gmail API).
    2.  Attachment extraction (via `document_processor.py` existing `.eml` logic).
    3.  Case Identification (Subject line regex: `Sinistro {code}`).
    4.  Document Upload to GCS.
    5.  Cloud Task enqueue for AI processing.

## 5. Configuration & Envrionment

*   **Allowed File Types:** PDF, DOCX, XLSX, TXT, EML, Images (PNG, JPG, WEBP, GIF).
*   **Limits:** 50MB per file, 200MB total upload.
*   **Secrets:**
    *   `DB_PASS`, `GEMINI_API_KEY`, `CLOUD_TASKS_SA_EMAIL`, `firebase-creds`
*   **CI/CD:** GitHub Actions (`.github/workflows/main_pipeline.yml`) deploys to Cloud Run.
