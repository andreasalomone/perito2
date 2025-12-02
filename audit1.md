Here is the Full System Audit for the **RobotPerizia "Hyperion" v2.0** codebase.

## 1\. Executive System Health

  * **Overall Score:** **8.5/10**
  * **Architecture Verdict:** **Robust Cloud-Native Hybrid.**
    The system correctly leverages the "Google Stack" (Cloud Run, Cloud Tasks, Cloud SQL, Vertex AI). It moves away from the monolithic "Celery worker" pattern to a modern, serverless, event-driven architecture. The use of PostgreSQL Row Level Security (RLS) for multi-tenancy is an advanced and highly secure design choice that reduces the risk of data leaks at the application layer.
  * **Top 3 Critical Risks:**
    1.  **The "Last Runner" Race Condition:** The logic to trigger report generation when documents finish processing is susceptible to a race condition where multiple workers can trigger duplicate report generations simultaneously.
    2.  **Authentication Bypass via Config:** The `RUN_LOCALLY` environment variable, if accidentally left `True` in a production deployment, completely bypasses Cloud Task authentication security.
    3.  **Frontend/Backend Type Drift (Polling):** The frontend relies on a specific polling logic that assumes the backend status updates instantanously, but the eventual consistency of Cloud Tasks + Database commits creates a "flicker" state where the UI might behave unpredictably.

-----

## 2\. Functional Logic Flaws (The "It doesn't work" section)

### A. The Double-Generation Race Condition

  * **Location:** `backend/app/services/case_service.py` (Lines 442-458)
  * **Issue:** When a document finishes extraction, the worker checks if all documents for that case are done. If yes, it triggers report generation.
      * *Scenario:* A case has 2 documents. Worker A finishes Doc 1. Worker B finishes Doc 2. They finish milliseconds apart.
      * Worker A commits Doc 1 status. Worker B commits Doc 2 status.
      * Worker B locks Case, sees 0 pending, triggers generation.
      * Worker A locks Case, sees 0 pending, **also triggers generation**.
      * *Result:* Two reports are generated, costing double API credits and creating duplicate versions (v1, v2) instantly.
  * **Fix:** You must check if the *current* worker processed the *last* pending document, or strictly check the Case status inside the lock.

<!-- end list -->

```python
# FIX in backend/app/services/case_service.py

    # ... inside process_document_extraction ...
    # 3. Save to DB (Commit the processed status FIRST)
    doc.ai_extracted_data = processed
    doc.ai_status = "processed"
    db.commit() 
    
    # 4. Check for Case Completion with STRICT LOCKING
    try:
        # Lock the Case immediately
        case = db.query(Case).filter(Case.id == doc.case_id).with_for_update().first()
        
        # Check if we are already generating to fail fast
        if case.status == "generating":
            return

        # Re-query all docs inside this locked transaction
        all_docs = db.query(Document).filter(Document.case_id == doc.case_id).all()
        pending_docs = [d for d in all_docs if d.ai_status not in ["processed", "error"]]
        
        if not pending_docs:
            logger.info(f"All documents finished. Triggering generation.")
            # OPTIONAL: Set status here to prevent the other worker from entering
            case.status = "generating" 
            db.commit() 
            
            # Now trigger the task
            from app.services import report_generation_service
            await report_generation_service.trigger_generation_task(str(doc.case_id), str(org_id))
            
    except Exception as e:
        db.rollback()
        logger.error(f"Error checking case completion: {e}")
```

### B. "Ouroboros" Cloud Task URL

  * **Location:** `backend/app/core/config.py` (Lines 211-214) and `backend/app/services/case_service.py` (Line 423)
  * **Issue:** The system attempts to self-discover its URL using `K_SERVICE`. However, Cloud Tasks requires an absolute, publicly resolvable URL (or an internal one if using VPC connectors). If `BACKEND_URL` is misconfigured or `K_SERVICE` resolves to a local internal DNS that Cloud Tasks (which lives outside the VPC by default) cannot reach, tasks will fail 100% of the time.
  * **Fix:** Ensure `BACKEND_URL` is explicitly set in `cloudbuild.yaml` to the *public* Cloud Run URL (as you have done in `cloudbuild.yaml` Line 61: `BACKEND_URL=https://api.perito.my`). Do not rely on dynamic `K_SERVICE` resolution for Cloud Tasks URLs unless you are certain about VPC peering.

-----

## 3\. Cross-File Integration Issues

### A. Frontend Environment Injection Strategy

  * **Location:** `frontend/Dockerfile` vs `frontend/src/app/layout.tsx`
  * **Issue:** Next.js `NEXT_PUBLIC_` variables are typically inlined at **build time**.
      * Your `Dockerfile` (Line 921) runs `npm run build`.
      * Your `cloudbuild.yaml` (Line 63) injects env vars at **runtime** (`--set-env-vars`).
      * *Result:* The React code built in the Docker image will NOT have the environment variables from Cloud Run. It will likely have empty strings or undefined values, breaking the API connection (`NEXT_PUBLIC_API_URL`).
  * **Fix:** You have implemented a workaround in `frontend/src/app/layout.tsx` using `window.__ENV__`. This is a valid "Runtime Config" strategy, but you need to ensure your `api.ts` (Line 1368) actually uses this window object instead of `process.env`.
      * *Current Code:* `const API_URL = getEnv("NEXT_PUBLIC_API_URL")...`
      * *Verify:* Ensure `getEnv` implementation correctly prioritizes `window.__ENV__` over `process.env` (which seems correct in `lib/env.ts`), otherwise the frontend will try to connect to `localhost:8000` or crash.

### B. Client Creation Race Condition

  * **Location:** `backend/app/services/case_service.py` -\> `get_or_create_client`
  * **Issue:**
    ```python
    try:
        with db.begin_nested():
            client = Client(...)
            db.add(client)
            db.flush()
    except IntegrityError:
        return db.query(Client).filter(...).one()
    ```
    While `begin_nested()` handles the savepoint, if `IntegrityError` occurs, the `db` session might still be in a "partial rollback" state depending on the driver configuration.
  * **Integration Risk:** If two users create a case for "Generali" at the same time, one might fail if the `IntegrityError` bubbles up or if `db.flush()` doesn't strictly enforce the constraint until commit.
  * **Fix:** This pattern is generally okay in Postgres, but ensure the unique constraint `uq_clients_org_name` (defined in `models/__init__.py`) exists in the active DB.

-----

## 4\. Security & Performance Deep Dive

### Security: Dangerous `RUN_LOCALLY` Bypass

  * **File:** `backend/app/api/v1/tasks.py`
    ```python
    async def verify_cloud_tasks_auth(...):
        if settings.RUN_LOCALLY:
            return True # <--- DANGER
    ```
  * **Risk:** If `RUN_LOCALLY` is set to `True` in the Cloud Run environment variables (e.g., for debugging), **any** user on the internet can POST to `/tasks/process-case` and trigger expensive AI operations or manipulate case data, bypassing all authentication.
  * **Remediation:** Add a check that prevents `RUN_LOCALLY` from working if the environment looks like production (e.g., if `K_SERVICE` is present).

### Security: IDOR Protection via RLS (Success)

  * **Observation:** You are using manual RLS context setting:
    ```python
    db.execute(text("SELECT set_config('app.current_org_id', :org_id, false)"), ...)
    ```
  * **Verdict:** This is excellent. Even if there is a SQL injection flaw in a higher-level query (unlikely with SQLAlchemy), the database kernel itself prevents cross-tenant data access.

### Performance: Connection Pooling in Cloud Run

  * **File:** `backend/app/db/database.py`
    ```python
    pool_size=5,
    max_overflow=10,
    ```
  * **Risk:** Cloud Run scales horizontally. If you scale to 100 containers, that is $100 \times 5 = 500$ open connections to Cloud SQL. This can exhaust the database `max_connections` (usually 100-500 for smaller instances).
  * **Optimization:** For Cloud Run, use **SQLAlchemy NullPool** (disable pooling) and rely on the *PgBouncer* sidecar or Cloud SQL Auth Proxy if connection overhead is high. Or, keep the pool size very low (e.g., 2) and `max_overflow` higher. Ideally, use `NullPool` because Cloud Run containers might only handle 1 request at a time (if concurrency=1), making the pool wasteful.

### Performance: DOCX Generation Blocking

  * **File:** `backend/app/services/docx_generator.py`
  * **Issue:** The image downloading and processing happens synchronously within the request flow or task. If a report has many high-res images, `docx_stream = await asyncio.to_thread(docx_generator.create_styled_docx, ...)` offloads it to a thread, but Python's GIL might still bottleneck CPU-bound XML generation operations.
  * **Fix:** Ensure the Cloud Run instance has enough CPU (at least 2 vCPU) to handle the XML parsing/zipping of `python-docx` without starving the async loop for other incoming requests.

-----

## 5\. Refactoring Roadmap

If I were taking over this codebase, here is the immediate roadmap:

1.  **Harden the Task Worker Logic (Day 1):**
    Rewrite `process_document_extraction` and `generate_report_logic` to handle the "Last Runner" race condition. Implement an idempotent check: "Is the report already generated?" before spending money on Gemini tokens.

2.  **Fix Frontend Build/Runtime Config (Day 2):**
    Remove the complexity of `window.__ENV__` if possible. Since you are using Cloud Run, you can use **Next.js Output Standalone** (which you are) with `publicRuntimeConfig` or simply bake the env vars into the image at build time (simplest for MVP). If you must inject at runtime, the current `window.__ENV__` solution is fragile; consider a dedicated `/api/config` endpoint that the frontend calls on hydration to get its config.

3.  **Optimize Database Connection (Day 3):**
    Switch SQLAlchemy to use `NullPool` in production to prevent "Too many clients" errors during auto-scaling events.

4.  **Security Hardening (Day 4):**
    Remove the `if settings.RUN_LOCALLY: return True` bypass from production code entirely. Use a dependency injection pattern where the "AuthStrategy" is swapped based on env, rather than an `if` statement inside the security barrier.

**Final Thought:** The project is well-structured and uses modern patterns. The biggest risks are concurrency controls in the async workers and the complexity of hybrid (Next.js + Python) environment configuration. Fixing the race condition is the highest priority.