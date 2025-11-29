#!/bin/bash

# RobotPerizia Deployment Script
# Usage: ./deploy.sh

set -e # Exit immediately if a command exits with a non-zero status.

echo "🚀 Starting RobotPerizia Deployment..."

# 1. Configuration
PROJECT_ID="perito-479708"
REGION="europe-west1"
DB_INSTANCE="robotperizia-db"
DB_CONNECTION="$PROJECT_ID:$REGION:$DB_INSTANCE"

# Load secrets from backend/.env if available
if [ -f "backend/.env" ]; then
  echo "📜 Loading configuration from backend/.env..."
  # Use set -a to export variables defined in .env
  set -a
  source backend/.env
  set +a
fi

# Check for secrets (You can also load these from a .env file)
if [ -z "$DB_PASS" ]; then
    read -s -p "Enter Database Password: " DB_PASS
    echo ""
fi

if [ -z "$GEMINI_API_KEY" ]; then
    read -s -p "Enter Gemini API Key: " GEMINI_API_KEY
    echo ""
fi

echo "--------------------------------------------------"
echo "📦 Deploying Backend..."
echo "--------------------------------------------------"

cd backend

# Deploy Backend and capture the URL
gcloud run deploy robotperizia-backend \
  --source . \
  --region $REGION \
  --project $PROJECT_ID \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
  --set-env-vars="GOOGLE_CLOUD_REGION=$REGION" \
  --set-env-vars="CLOUD_SQL_CONNECTION_NAME=$DB_CONNECTION" \
  --set-env-vars="DB_USER=report_user" \
  --set-env-vars="DB_PASS=$DB_PASS" \
  --set-env-vars="DB_NAME=perizia_db" \
  --set-env-vars="STORAGE_BUCKET_NAME=robotperizia-uploads-roberto" \
  --set-env-vars="CLOUD_TASKS_QUEUE_PATH=projects/$PROJECT_ID/locations/$REGION/queues/report-processing-queue" \
  --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY" \
  --format="value(status.url)" > ../backend_url.txt

BACKEND_URL=$(cat ../backend_url.txt)
rm ../backend_url.txt

echo "✅ Backend deployed at: $BACKEND_URL"

echo "--------------------------------------------------"
echo "🌐 Deploying Frontend..."
echo "--------------------------------------------------"

cd ../frontend

# Deploy Frontend with the captured Backend URL
gcloud run deploy robotperizia-frontend \
  --source . \
  --region $REGION \
  --project $PROJECT_ID \
  --allow-unauthenticated \
  --set-env-vars="NEXT_PUBLIC_FIREBASE_API_KEY=AIzaSyArgk92E56fnKcUmajrAdROu9BDxl7EQ2A" \
  --set-env-vars="NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=perito-479708.firebaseapp.com" \
  --set-env-vars="NEXT_PUBLIC_FIREBASE_PROJECT_ID=perito-479708" \
  --set-env-vars="NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET=perito-479708.firebasestorage.app" \
  --set-env-vars="NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID=738291935960" \
  --set-env-vars="NEXT_PUBLIC_FIREBASE_APP_ID=1:738291935960:web:2fa811b15b4717c5ef05ad" \
  --set-env-vars="NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID=G-YVY6S4YY8K" \
  --set-env-vars="NEXT_PUBLIC_API_URL=$BACKEND_URL"

echo "--------------------------------------------------"
echo "🎉 Deployment Complete!"
echo "--------------------------------------------------"
echo "Backend:  $BACKEND_URL"
echo "Frontend: (See URL above)"
