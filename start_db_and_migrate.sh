#!/bin/bash

echo "Starting Cloud SQL Proxy and Alembic Migration..."

# Command 1: Cloud SQL Proxy
# Opens a new Terminal window/tab and runs the proxy
osascript -e 'tell application "Terminal" to do script "cloud_sql_proxy -instances=perito-479708:europe-west1:robotperizia-db=tcp:5432"'

# Command 2: Alembic Upgrade
# Opens a new Terminal window/tab, navigates to backend, sets SSL cert, and runs migration
osascript -e 'tell application "Terminal" to do script "cd /Users/andreasalomone/perito-wrap/robotperizia/report-ai-v2/perito/backend && export SSL_CERT_FILE=/Users/andreasalomone/perito-wrap/robotperizia/report-ai-v2/perito/backend/venv/lib/python3.13/site-packages/certifi/cacert.pem && alembic upgrade head"'

echo "Commands launched in new Terminal windows."
