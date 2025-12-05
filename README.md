# PeritoAI v2.1.0

**PeritoAI** is an advanced, AI-powered **Case Management System** designed to streamline the workflow of insurance surveyors, legal experts, and claims adjusters. By leveraging the power of **Google's Gemini 2.5 LLM via the Gemini API**, it automates the extraction of critical information from uploaded documents and generates comprehensive, professionally formatted reports (DOCX).

## 🎯 Target Audience

This application is specifically built for:
*   **Insurance Surveyors (Periti Assicurativi):** To automate the creation of survey reports, reducing manual data entry and analysis time.
*   **Legal Experts:** To quickly summarize and extract key facts from large volumes of case documents.
*   **Claims Adjusters:** To facilitate the processing of claims by automatically generating preliminary assessments based on submitted evidence.

## ✨ Key Features

*   **End-to-End Case Management:** Create cases, track status, and manage document lifecycles from a unified dashboard.
*   **AI-Driven Analysis:** Utilizes **Gemini API (Gemini 2.5 Pro/Flash)** for deep semantic understanding of documents and accurate data extraction.
*   **Multi-Template Reports:** Generate reports in various professional formats (e.g., "BN Surveys", "Salomone & Associati") on demand.
*   **Secure & Scalable:** Built on a **Cloud-Native Hybrid Architecture** using Google Cloud Platform (GCP).
*   **Direct-to-Cloud Uploads:** Secure, high-performance file uploads directly to Google Cloud Storage (GCS) using signed URLs.
*   **Real-Time Progress Tracking:** Users can monitor the status of their report generation in real-time.
*   **Secure Multi-Tenancy:** Robust user authentication, Row Level Security (RLS), and data isolation using **Firebase Authentication**.

## 🏗️ Technical Architecture (The "Google Stack")

We have decoupled the legacy monolith into a **Cloud-Native Hybrid Architecture** hosted entirely on Google Cloud Platform (GCP). This shift eliminates server management, enables infinite scalability via serverless containers, and optimizes costs.

### Core Components

| Component | Technology Selection | Justification |
| :--- | :--- | :--- |
| **Frontend** | **Next.js 16 + React 19 + Firebase Auth** | Hosted on **Cloud Run**. Client-side uploads directly to storage. Styled with **Tailwind CSS v4**. |
| **Backend** | **FastAPI + Cloud Tasks** | Hosted on **Cloud Run**. Replaces Celery workers with HTTP-triggered task handlers. |
| **Database** | **Cloud SQL (PostgreSQL)** | Managed Postgres with RLS for multi-tenancy. Connections secured via *Cloud SQL Auth Connector* (no public IP exposure). |
| **Storage** | **Google Cloud Storage (GCS)** | Replaces local disk. Configured with CORS for secure browser-direct uploads. |
| **Async Queue** | **Cloud Tasks** | Serverless task queue. Zero-maintenance, free-tier eligible solution replacing Redis. |
| **AI Engine** | **Gemini API (`google-genai`)** | Direct API access using `gemini-2.5-pro` as primary and `gemini-2.5-flash-lite` as fallback. |

### Infrastructure Details

*   **API Gateway & Services:** Cloud Run, Cloud SQL Admin, Cloud Storage, Cloud Tasks, Secret Manager.
*   **Object Storage (Data Layer):**
    *   **CORS Enabled:** Allows `PUT` requests from web browsers for direct uploads.
    *   **Data Safety:** Soft-delete policy enabled (7-day recovery window).
    *   **Access:** Uniform Bucket-Level Access enforced.
*   **Database (State Layer):**
    *   **Spec:** PostgreSQL with Row Level Security (RLS).
    *   **Security:** Public IP enabled but secured via IAM Auth.
*   **Identity (Auth Layer):**
    *   **Provider:** Firebase Identity Platform.
    *   **Methods:** Google & Email/Password enabled.
*   **Asynchronous Processing (Queue Layer):**
    *   **Rate Limit:** Max 10 tasks/sec dispatch to protect the DB.
    *   **Concurrency:** Max 20 concurrent instances to protect the DB connection pool.
    *   **Retry Policy:** Max 5 attempts with exponential backoff to handle temporary AI glitches.

## 🚀 Getting Started

### Prerequisites

*   Node.js 18+
*   Python 3.10+
*   Google Cloud SDK
*   Docker (optional, for containerized development)

### Local Development

#### 1. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the `backend` directory with your local configuration (see `.env.example` if available).

Run the server:
```bash
uvicorn app.main:app --reload
```

#### 2. Frontend Setup

```bash
cd frontend
npm install
```

Create a `.env.local` file in the `frontend` directory with your Firebase and API configuration.

Run the development server:
```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## 📂 Project Structure

*   `backend/`: FastAPI application, database models, and AI logic.
*   `frontend/`: Next.js application, UI components, and client-side logic.
*   `docs/`: Project documentation and architectural decisions.
*   `tests/`: Unit and integration tests (currently under development).

## 📄 License

Proprietary software. All rights reserved.
