# MyPerito Backend

This is the backend for the MyPerito application, built with FastAPI and designed to run on Google Cloud Run.

## 🚀 Getting Started

### Prerequisites

*   **Python 3.10+**
*   **Docker** (optional, for containerized development)
*   **Google Cloud SDK** (for deploying and interacting with GCP services)

### Setup

1.  **Create a virtual environment:**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

2.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

### Configuration

Create a `.env` file in the `backend` directory. You can use `.env.example` as a template if available, or populate it with the necessary environment variables:

```env
# Example variables (adjust as needed)
PORT=8080
GOOGLE_CLOUD_PROJECT=...
CLOUD_SQL_CONNECTION_NAME=...
DB_USER=report_user
DB_PASS=...
DB_NAME=perizia_db
STORAGE_BUCKET_NAME=...
CLOUD_TASKS_QUEUE_PATH=...
GEMINI_API_KEY=...
```

### Running Locally

To start the development server with hot reloading:

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### Docker

To build and run the backend using Docker:

1.  **Build the image:**

    ```bash
    docker build -t MyPerito-backend .
    ```

2.  **Run the container:**

    ```bash
    docker run -p 8080:8080 --env-file .env MyPerito-backend
    ```

## 🛠️ Key Technologies

*   **FastAPI:** High-performance async web framework for building APIs.
*   **Cloud Tasks:** Asynchronous task execution for report generation.
*   **Cloud SQL (PostgreSQL):** Managed relational database with Row Level Security (RLS).
*   **Gemini API (`google-genai`):** AI-powered document analysis using `gemini-2.5-pro` (primary) and `gemini-2.5-flash-lite` (fallback).
*   **SQLAlchemy:** Async ORM for database interactions.
*   **Pydantic:** Data validation and settings management.
*   **Alembic:** Database migrations.
*   **Firebase Admin:** Server-side token verification for authentication.
*   **Tenacity:** Retry logic with exponential backoff for LLM API calls.
