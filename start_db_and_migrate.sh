#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$SCRIPT_DIR/backend"

echo "Starting Cloud SQL Proxy..."
# Start proxy in background
cloud_sql_proxy -instances=perito-479708:europe-west1:robotperizia-db=tcp:5432 &
PROXY_PID=$!

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "Stopping Cloud SQL Proxy..."
    kill $PROXY_PID
}

# Set trap to call cleanup on script exit
trap cleanup EXIT

echo "Waiting for Cloud SQL Proxy to initialize (5 seconds)..."
sleep 5

echo "Running Alembic Migration..."
cd "$BACKEND_DIR" || exit 1

# Set SSL_CERT_FILE relative to backend directory
export SSL_CERT_FILE="$BACKEND_DIR/venv/lib/python3.13/site-packages/certifi/cacert.pem"

alembic upgrade head

echo "Migration completed."
