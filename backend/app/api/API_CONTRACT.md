# Perito API Contract Documentation

> **Version**: 1.0.0  
> **Last Updated**: 2025-12-05  
> **Base URL**: `${API_URL}/api/v1`

This document defines the contract between the Next.js Frontend and FastAPI Backend. All endpoints require Firebase Authentication unless otherwise noted.

---

## Table of Contents

1. [Authentication](#authentication)
2. [Cases API](#cases-api)
3. [Clients API](#clients-api)
4. [Admin API](#admin-api)
5. [Error Responses](#error-responses)
6. [Enums & Types](#enums--types)
7. [Development Rules](#development-rules)

---

## Authentication

All endpoints (except `/auth/sync`) require a valid Firebase ID Token in the `Authorization` header:

```http
Authorization: Bearer <firebase_id_token>
```

### POST `/auth/sync`

Synchronizes Firebase user with PostgreSQL database. Called automatically on login.

**Request Headers**:
```http
Authorization: Bearer <firebase_id_token>
```

**Response** `200 OK`:
```json
{
    "id": "firebase_uid_string",
    "email": "user@example.com",
    "organization_id": "uuid-string",
    "role": "MEMBER" | "ADMIN"
}
```

**Error Responses**:
- `400` - Token missing required claims
- `403` - Email not whitelisted

---

## Cases API

### GET `/cases/`

Retrieve paginated list of cases for the authenticated organization.

**Query Parameters**:
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `skip` | integer | 0 | Pagination offset |
| `limit` | integer | 50 | Max results (1-100) |
| `search` | string | null | Search by reference code or client name |
| `client_id` | UUID | null | Filter by client ID |
| `status` | CaseStatus | null | Filter by status |
| `scope` | string | "all" | `"all"` or `"mine"` |

**Response** `200 OK`:
```json
[
    {
        "id": "uuid",
        "reference_code": "Sinistro 2024/001",
        "organization_id": "uuid",
        "status": "OPEN",
        "created_at": "2024-01-15T10:30:00.000Z",
        "client_name": "Generali" | null,
        "creator_email": "user@example.com" | null
    }
]
```

**Frontend Validation Schema** (Zod):
```typescript
const CaseSummarySchema = z.object({
    id: z.string().uuid(),
    reference_code: z.string(),
    organization_id: z.string().uuid(),
    status: CaseStatusEnum,
    created_at: z.string(),
    client_name: z.string().nullable().optional(),
    creator_email: z.string().nullable().optional(),
});
```

---

### GET `/cases/{case_id}`

Get full case details including documents and report versions.

**Path Parameters**:
- `case_id` (UUID) - Case identifier

**Response** `200 OK`:
```json
{
    "id": "uuid",
    "reference_code": "Sinistro 2024/001",
    "organization_id": "uuid",
    "status": "OPEN",
    "created_at": "2024-01-15T10:30:00.000Z",
    "client_name": "Generali",
    "documents": [
        {
            "id": "uuid",
            "filename": "report.pdf",
            "ai_status": "SUCCESS",
            "created_at": "2024-01-15T10:30:00.000Z"
        }
    ],
    "report_versions": [
        {
            "id": "uuid",
            "version_number": 1,
            "is_final": false,
            "created_at": "2024-01-15T10:30:00.000Z"
        }
    ]
}
```

---

### GET `/cases/{case_id}/status`

Lightweight endpoint for polling case status. Optimized for frequent calls.

**Response** `200 OK`:
```json
{
    "id": "uuid",
    "status": "GENERATING",
    "documents": [...],
    "is_generating": true
}
```

> **Usage Note**: Call this endpoint during `GENERATING` or `PROCESSING` states at 2-5s intervals, not the full `/cases/{case_id}` endpoint.

---

### POST `/cases/`

Create a new case.

**Request Body**:
```json
{
    "reference_code": "Sinistro 2024/002",
    "client_name": "Allianz"  // Optional: will create client if not exists
}
```

**Response** `201 Created`:
```json
{
    "id": "uuid",
    "reference_code": "Sinistro 2024/002",
    ... // Full CaseDetail object
}
```

---

### POST `/cases/{case_id}/documents/upload-url`

Generate a signed URL for direct GCS upload.

**Query Parameters**:
- `filename` (string) - Original filename
- `content_type` (string) - MIME type

**Allowed MIME Types**:
- `.pdf` → `application/pdf`
- `.docx` → `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- `.xlsx` → `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- `.txt` → `text/plain`
- `.eml` → `message/rfc822`
- `.png` → `image/png`
- `.jpg/.jpeg` → `image/jpeg`
- `.webp` → `image/webp`
- `.gif` → `image/gif`

**Response** `200 OK`:
```json
{
    "upload_url": "https://storage.googleapis.com/...",
    "gcs_path": "uploads/{org_id}/{case_id}/filename.pdf"
}
```

---

### POST `/cases/{case_id}/documents/register`

Register an uploaded file in the database and trigger AI processing.

**Request Body**:
```json
{
    "filename": "document.pdf",
    "gcs_path": "uploads/{org_id}/{case_id}/document.pdf",
    "mime_type": "application/pdf"
}
```

**Security**: The `gcs_path` is validated to ensure it matches the expected pattern for the case's organization.

**Response** `200 OK`:
```json
{
    "id": "uuid",
    "filename": "document.pdf",
    "ai_status": "PENDING",
    "created_at": "2024-01-15T10:30:00.000Z"
}
```

---

### POST `/cases/{case_id}/generate`

Trigger AI report generation.

**Response** `200 OK`:
```json
{
    "status": "generation_started"
}
```

---

### POST `/cases/{case_id}/finalize`

Upload a final signed version of the report.

**Request Body**:
```json
{
    "final_docx_path": "uploads/{org_id}/{case_id}/FINAL_report.docx"
}
```

**Response** `200 OK`:
```json
{
    "id": "uuid",
    "version_number": 2,
    "is_final": true,
    "created_at": "2024-01-15T10:30:00.000Z"
}
```

---

### POST `/cases/{case_id}/versions/{version_id}/download`

Generate a signed download URL for a report version.

**Request Body**:
```json
{
    "template_type": "bn" | "salomone"
}
```

**Response** `200 OK`:
```json
{
    "download_url": "https://storage.googleapis.com/..."
}
```

---

## Clients API

### GET `/clients/`

Search clients within the organization.

**Query Parameters**:
- `q` (string, min 1 char) - Search query
- `limit` (integer, default 10) - Max results

**Response** `200 OK`:
```json
[
    {
        "id": "uuid",
        "name": "Generali"
    }
]
```

---

## Admin API

> **Access**: Requires superadmin email in `SUPERADMIN_EMAIL_LIST` environment variable.

### GET `/admin/organizations`

List all organizations.

### POST `/admin/organizations`

Create a new organization.

**Request Body**:
```json
{
    "name": "My Organization"
}
```

### GET `/admin/organizations/{org_id}/invites`

List whitelisted emails for an organization.

### POST `/admin/organizations/{org_id}/users/invite`

Whitelist an email for registration.

**Request Body**:
```json
{
    "email": "newuser@example.com",
    "role": "MEMBER" | "ADMIN"
}
```

### DELETE `/admin/invites/{invite_id}`

Remove a whitelisted email.

---

## Error Responses

All errors follow this format:

```json
{
    "detail": "Human-readable error message"
}
```

**Standard HTTP Status Codes**:
- `400` - Bad Request (validation error)
- `401` - Unauthorized (invalid/expired token)
- `403` - Forbidden (access denied, IDOR attempt)
- `404` - Not Found
- `409` - Conflict (duplicate resource)
- `500` - Internal Server Error

---

## Enums & Types

### CaseStatus
```python
OPEN = "OPEN"
CLOSED = "CLOSED"
ARCHIVED = "ARCHIVED"
GENERATING = "GENERATING"
PROCESSING = "PROCESSING"
ERROR = "ERROR"
```

### ExtractionStatus (Document AI Status)
```python
PENDING = "PENDING"
PROCESSING = "PROCESSING"
SUCCESS = "SUCCESS"
ERROR = "ERROR"
SKIPPED = "SKIPPED"
```

### UserRole
```python
ADMIN = "ADMIN"
MEMBER = "MEMBER"
```

---

## Development Rules

### 1. Schema Alignment

When modifying backend schemas (`backend/app/schemas/`), always update the corresponding Zod schemas in `frontend/src/types/index.ts`.

### 2. Enum Changes

Any changes to enums in `backend/app/schemas/enums.py` must be reflected in:
- `frontend/src/types/index.ts` - Zod enum definitions
- Any hardcoded status checks in frontend components

### 3. New Endpoints

When adding new endpoints:
1. Define Pydantic request/response models in `backend/app/schemas/`
2. Add endpoint in `backend/app/api/v1/`
3. Add corresponding Zod schema in `frontend/src/types/`
4. Add API method in `frontend/src/lib/api.ts`
5. Update this documentation

### 4. Security Requirements

All endpoints must:
- Validate path parameters to prevent IDOR attacks
- Use RLS-enabled database sessions for multi-tenant isolation
- Never expose internal storage paths (use signed URLs)
- Validate file types and sizes before upload

### 5. Testing Contract Changes

Before deploying schema changes:
```bash
# Backend
cd backend && python -c "from app.schemas import *; print('Schemas OK')"

# Frontend
cd frontend && npx tsc --noEmit
```

---

## Changelog

### v1.0.0 (2025-12-05)
- Initial documentation
- Based on API audit findings
