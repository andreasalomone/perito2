# 🚀 Production Deployment Guide

This guide outlines the steps to deploy **RobotPerizia "Hyperion" v2.0** to Google Cloud Platform (Cloud Run).

## 📋 Prerequisites

Ensure you have the following installed and authenticated:

1.  **Google Cloud SDK (`gcloud`)**: [Install Guide](https://cloud.google.com/sdk/docs/install)
2.  **Login**:
    ```bash
    gcloud auth login
    gcloud config set project perito-479708
    ```
3.  **Application Default Credentials** (for local migration scripts):
    ```bash
    gcloud auth application-default login
    ```

---

## ⚡ Option 1: Automated Deployment (Recommended)

We have created a script to automate the entire process. It will:
1.  **Load configuration from `backend/.env`** (so you don't have to type passwords).
2.  Deploy the Backend and automatically capture its URL.
3.  Deploy the Frontend, injecting the Backend URL automatically.

### Steps:

1.  **Make the script executable:**
    ```bash
    chmod +x deploy.sh
    ```

2.  **Run the script:**
    ```bash
    ./deploy.sh
    ```

That's it! The script will output the final URL for your users.

---

## 🔄 Option 2: Continuous Deployment (CI/CD)

If you want to deploy automatically every time you push to GitHub, use **Google Cloud Build**.

### 1. Connect Repository
1.  Go to [Cloud Build Triggers](https://console.cloud.google.com/cloud-build/triggers).
2.  Click **Create Trigger**.
3.  **Name:** `deploy-robotperizia`
4.  **Event:** Push to a branch.
5.  **Source:** Connect your GitHub repository and select the `main` branch.
6.  **Configuration:** Select **Cloud Build configuration file (yaml or json)**.
7.  **Location:** `cloudbuild.yaml` (We created this file for you).

### 2. Add Substitution Variables
In the **Advanced** section of the trigger, add the following Substitution variables (so you don't commit secrets to git):

*   `_DB_PASS`: *(Your Database Password)*
*   `_GEMINI_API_KEY`: *(Your Gemini API Key)*

### 3. Run
Click **Create**. Now, every time you push to `main`, Google Cloud will automatically build and deploy both your backend and frontend!

### 4. Get the Link
Once the first build finishes (it takes ~3 minutes):
1.  Go to [Cloud Run Console](https://console.cloud.google.com/run).
2.  Click on **`robotperizia-frontend`**.
3.  Copy the URL at the top (e.g., `https://robotperizia-frontend-xyz.a.run.app`).
4.  **This is the link for your users.** It will **not change** for future deployments.

---

## 🛠️ Option 3: Manual Deployment

Use this if you want full control over every step or need to debug.

### 1. Deploy Backend

1.  **Navigate to backend directory:**
    ```bash
    cd backend
    ```

2.  **Deploy Command:**
    Replace `[YOUR_DB_PASSWORD]` and `[YOUR_GEMINI_KEY]` with your actual secrets.

    ```bash
    gcloud run deploy robotperizia-backend \
      --source . \
      --region europe-west1 \
      --allow-unauthenticated \
      --set-env-vars="GOOGLE_CLOUD_PROJECT=perito-479708" \
      --set-env-vars="GOOGLE_CLOUD_REGION=europe-west1" \
      --set-env-vars="CLOUD_SQL_CONNECTION_NAME=perito-479708:europe-west1:robotperizia-db" \
      --set-env-vars="DB_USER=report_user" \
      --set-env-vars="DB_PASS=[YOUR_DB_PASSWORD]" \
      --set-env-vars="DB_NAME=perizia_db" \
      --set-env-vars="STORAGE_BUCKET_NAME=robotperizia-uploads-roberto" \
      --set-env-vars="CLOUD_TASKS_QUEUE_PATH=projects/perito-479708/locations/europe-west1/queues/report-processing-queue" \
      --set-env-vars="GEMINI_API_KEY=[YOUR_GEMINI_KEY]"
    ```

3.  **Copy the Service URL:**
    The command output will show a Service URL (e.g., `https://robotperizia-backend-xyz-ew.a.run.app`).
    **Save this URL.** You need it for the frontend.

### 2. Deploy Frontend

1.  **Navigate to frontend directory:**
    ```bash
    cd ../frontend
    ```

2.  **Deploy Command:**
    Replace `[BACKEND_URL]` with the URL you copied in the previous step.

    ```bash
    gcloud run deploy robotperizia-frontend \
      --source . \
      --region europe-west1 \
      --allow-unauthenticated \
      --set-env-vars="NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSyArgk92E56fnKcUmajrAdROu9BDxl7EQ2A" \
      --set-env-vars="NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=perito-479708.firebaseapp.com" \
      --set-env-vars="NEXT_PUBLIC_FIREBASE_PROJECT_ID=perito-479708" \
      --set-env-vars="NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=perito-479708.firebasestorage.app" \
      --set-env-vars="NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=738291935960" \
      --set-env-vars="NEXT_PUBLIC_FIREBASE_APP_ID=1:738291935960:web:2fa811b15b4717c5ef05ad" \
      --set-env-vars="NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID=G-YVY6S4YY8K" \
      --set-env-vars="NEXT_PUBLIC_API_URL=[BACKEND_URL]"
    ```

---

## 🌐 Custom Domains (The "Pro" Way)

If you want to use your own domain (e.g., `app.robotperizia.com`) and avoid changing URLs every time you redeploy to a new service name:

1.  **Go to Cloud Run Console:** [https://console.cloud.google.com/run](https://console.cloud.google.com/run)
2.  Click **Manage Custom Domains**.
3.  **Map your Backend:**
    *   Service: `robotperizia-backend`
    *   Domain: `api.yourdomain.com`
4.  **Map your Frontend:**
    *   Service: `robotperizia-frontend`
    *   Domain: `app.yourdomain.com`
5.  **Update DNS:** Add the DNS records provided by Google to your domain registrar.

**Benefit:** Once this is set up, you can hardcode `NEXT_PUBLIC_API_URL="https://api.yourdomain.com"` in your `frontend/.env.local` (or build script) and never worry about dynamic URLs again.

---

## 🗄️ Database Migration

Run the migration script locally to update the production database schema.
*Ensure you have run `gcloud auth application-default login` first.*

1.  **Navigate to backend directory:**
    ```bash
    cd backend
    ```

2.  **Run Migration:**
    Ensure your local `.env` has the correct `DB_PASS` and `CLOUD_SQL_CONNECTION_NAME`.

    ```bash
    python migrate_db.py
    ```
