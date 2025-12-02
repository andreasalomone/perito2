# RobotPerizia Backend

This is the backend for the RobotPerizia application, built with FastAPI and designed to run on Google Cloud Run.

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
DATABASE_URL=...
GOOGLE_CLOUD_PROJECT=...
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
    docker build -t robotperizia-backend .
    ```

2.  **Run the container:**

    ```bash
    docker run -p 8080:8080 --env-file .env robotperizia-backend
    ```

## 🛠️ Key Technologies

*   **FastAPI:** High-performance web framework for building APIs.
*   **Cloud Tasks:** Asynchronous task execution.
*   **Cloud SQL (PostgreSQL):** Managed relational database.
*   **Vertex AI (Gemini 2.5):** AI-powered document analysis and report generation.
*   **SQLAlchemy:** ORM for database interactions.
*   **Pydantic:** Data validation and settings management.
