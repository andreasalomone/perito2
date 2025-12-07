# Perito API Documentation

> **Version:** 1.0  
> **Base URL:** `{API_URL}/api/v1`  
> **Authentication:** Firebase JWT Bearer Token

---

## Table of Contents
1. [Health Check](#health-check)
2. [Authentication](#authentication)
3. [Cases](#cases)
4. [Documents](#documents)
5. [Clients](#clients)
6. [Users](#users)
7. [Admin](#admin)
8. [Task Workers](#task-workers-internal)
9. [Enums & Types](#enums--types)
10. [Error Handling](#error-handling)

---

## Health Check

### GET `/health`
Basic health check endpoint (no auth required).

**Response:**
```json
{ "status": "healthy", "service": "robotperizia-api" }
```

---

## Authentication

All endpoints require a valid Firebase ID token in the `Authorization` header:

```
Authorization: Bearer <firebase_id_token>
```

### POST `/auth/check-status` (Public)
Check if an email is registered, invited, or denied. **No authentication required.**

**Request Body:**
```json
{ "email": "user@example.com" }
```

**Response:**
```json
{ "status": "registered" | "invited" | "denied" }
```

| Status | Meaning |
|--------|---------|
| `registered` | User exists → show login form |
| `invited` | Whitelisted → show signup form |
| `denied` | Not allowed → show error |

---

### POST `/auth/sync`
Syncs Firebase user to the internal database. Called on first login.

**Response:** `UserRead`
```json
{
  "id": "firebase_uid",
  "email": "user@example.com",
  "organization_id": "uuid",
  "role": "MEMBER",
  "first_name": "Mario",
  "last_name": "Rossi",
  "is_profile_complete": true
}
```

> **Note:** `is_profile_complete` is `false` when `first_name` or `last_name` is null.
> New users must complete their profile via `PATCH /users/me` before accessing the dashboard.

**Errors:**
| Code | Detail |
|------|--------|
| 400 | Token missing required claims |
| 403 | Email not whitelisted |

---

## Cases

### GET `/cases/`
List cases for the authenticated organization.

**Query Parameters:**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `skip` | int | 0 | Pagination offset |
| `limit` | int | 50 | Max 100 |
| `search` | string | - | Search by reference code or client name |
| `client_id` | UUID | - | Filter by client |
| `status` | CaseStatus | - | Filter by status |
| `scope` | "all" \| "mine" | "all" | Filter by creator |

**Response:** `CaseSummary[]`
```json
[{
  "id": "uuid",
  "reference_code": "Sinistro 2024/001",
  "organization_id": "uuid",
  "client_id": "uuid | null",
  "client_name": "Generali",
  "status": "OPEN",
  "created_at": "2024-01-01T00:00:00Z",
  "creator_email": "user@example.com"
}]
```

---

### GET `/cases/{case_id}`
Get full case details with documents and report versions.

**Response:** `CaseDetail`
```json
{
  "id": "uuid",
  "reference_code": "Sinistro 2024/001",
  "organization_id": "uuid",
  "client_id": "uuid",
  "client_name": "Generali",
  "status": "OPEN",
  "created_at": "2024-01-01T00:00:00Z",
  "documents": [{ "id": "uuid", "filename": "doc.pdf", "ai_status": "SUCCESS", "created_at": "..." }],
  "report_versions": [{ "id": "uuid", "version_number": 1, "is_final": false, "created_at": "..." }]
}
```

---

### GET `/cases/{case_id}/status`
Lightweight polling endpoint for status and document states.

**Response:** `CaseStatusRead`
```json
{
  "id": "uuid",
  "status": "GENERATING",
  "documents": [...],
  "is_generating": true
}
```

---

### POST `/cases/`
Create a new case.

**Request Body:**
```json
{
  "reference_code": "Sinistro 2024/001",
  "client_name": "Generali"  // optional - creates/finds client
}
```

**Response:** `CaseDetail` (201 Created)

---

### POST `/cases/{case_id}/generate`
Trigger AI report generation.

**Response:**
```json
{ "status": "generation_started" }
```

---

### POST `/cases/{case_id}/finalize`
Finalize case with uploaded DOCX.

**Request Body:**
```json
{ "final_docx_path": "uploads/org_id/case_id/final.docx" }
```

**Response:** `VersionRead`

---

### DELETE `/cases/{case_id}`
Soft-delete a case and permanently delete all associated documents from GCS.

**Response:** `204 No Content`

**Effects:**
- Case is soft-deleted (marked with `deleted_at` timestamp)
- All documents are hard-deleted from database
- All document files are removed from GCS

---

### DELETE `/cases/{case_id}/documents/{doc_id}`
Hard-delete a single document from database and GCS.

**Response:** `204 No Content`

**Errors:**
| Code | Detail |
|------|--------|
| 404 | Document not found or doesn't belong to case |

---

## Documents

### POST `/cases/{case_id}/documents/upload-url`
Get signed URL for direct GCS upload.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `filename` | string | File name |
| `content_type` | string | MIME type |

**Response:**
```json
{
  "upload_url": "https://storage.googleapis.com/...",
  "gcs_path": "uploads/org_id/case_id/filename.pdf"
}
```

**Allowed MIME Types:**
- `application/pdf`
- `image/jpeg`, `image/png`
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

---

### POST `/cases/{case_id}/documents/register`
Register uploaded file in database.

**Request Body:**
```json
{
  "filename": "document.pdf",
  "gcs_path": "uploads/org_id/case_id/document.pdf",
  "mime_type": "application/pdf"
}
```

**Response:** `DocumentRead`

**Security:** Path must match `uploads/{org_id}/{case_id}/` prefix.

---

### POST `/cases/{case_id}/versions/{version_id}/download`
Generate download URL for report version.

**Request Body:**
```json
{ "template_type": "bn" | "salomone" }
```

**Response:**
```json
{ "download_url": "https://storage.googleapis.com/..." }
```

---

## Clients

### GET `/clients/`
Search clients within organization.

**Query Parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `q` | string | Search query (min 1 char) |
| `limit` | int | Default 10 |

**Response:** `ClientSimple[]`
```json
[{ "id": "uuid", "name": "Generali" }]
```

---

## Users

> **Requires:** ADMIN role within organization

### POST `/users/invite`
Invite user to your organization (org-scoped admin).

**Request Body:**
```json
{
  "email": "newuser@example.com",
  "role": "MEMBER"
}
```

**Response:**
```json
{ "message": "User newuser@example.com invited successfully" }
```

**Errors:**
| Code | Detail |
|------|--------|
| 403 | Insufficient permissions (not ADMIN) |
| 409 | User already registered or invited |

---

### PATCH `/users/me`
Update current user's profile (first name and last name).

**Request Body:**
```json
{
  "first_name": "Mario",
  "last_name": "Rossi"
}
```

**Response:** `UserProfileResponse`
```json
{
  "id": "firebase_uid",
  "email": "user@example.com",
  "organization_id": "uuid",
  "role": "MEMBER",
  "first_name": "Mario",
  "last_name": "Rossi",
  "is_profile_complete": true
}
```

**Errors:**
| Code | Detail |
|------|--------|
| 401 | Invalid authentication token |
| 404 | User not found |

---

## Admin

> **Requires:** Superadmin role (email in `SUPERADMIN_EMAIL_LIST`)

### GET `/admin/organizations`
List all organizations.

**Response:** `OrganizationResponse[]`
```json
[{ "id": "uuid", "name": "Acme Corp", "created_at": "..." }]
```

---

### POST `/admin/organizations`
Create organization.

**Request Body:**
```json
{ "name": "New Organization" }
```

**Response:** `OrganizationResponse` (201 Created)

---

### GET `/admin/organizations/{org_id}/invites`
List whitelisted emails for organization.

**Response:** `AllowedEmailResponse[]`
```json
[{
  "id": "uuid",
  "email": "user@example.com",
  "role": "MEMBER",
  "organization_id": "uuid",
  "created_at": "..."
}]
```

---

### POST `/admin/organizations/{org_id}/users/invite`
Whitelist email for registration.

**Request Body:**
```json
{
  "email": "newuser@example.com",
  "role": "MEMBER"  // or "ADMIN"
}
```

**Response:**
```json
{ "message": "User newuser@example.com invited to Acme Corp" }
```

---

### DELETE `/admin/invites/{invite_id}`
Remove whitelisted email.

**Response:**
```json
{ "message": "Invite removed successfully" }
```

---

### POST `/admin/storage/cleanup`
Clean orphaned GCS uploads older than 24h.

**Response:**
```json
{
  "status": "success",
  "deleted_count": 5,
  "skipped_count": 100,
  "cutoff_time": "2024-01-01T00:00:00Z"
}
```

---

## Task Workers (Internal)

> **Auth:** Cloud Tasks OIDC token only

### POST `/tasks/process-case`
### POST `/tasks/process-document`
### POST `/tasks/generate-report`
### POST `/tasks/flush-outbox`

---

## Enums & Types

### CaseStatus
```
OPEN | CLOSED | ARCHIVED | PROCESSING | GENERATING | ERROR
```

### ExtractionStatus
```
PENDING | PROCESSING | SUCCESS | ERROR | SKIPPED
```

### UserRole
```
ADMIN | MEMBER
```

---

## Error Handling

All errors follow this format:
```json
{
  "detail": "Error message"
}
```

**Common Status Codes:**
| Code | Meaning |
|------|---------|
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Invalid/missing token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found |
| 409 | Conflict - Resource already exists |
| 500 | Internal Server Error |

---

## Rate Limits

None currently enforced. Recommended client-side limits:
- Polling: 2-5 second intervals
- Batch operations: 10 requests/second
