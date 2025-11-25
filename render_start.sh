#!/bin/bash
set -e

echo "Running Database Migration..."
python scripts/migrate_schema.py

echo "Starting Celery Worker..."
celery -A core.celery_app.celery_app worker --loglevel=info --concurrency=1 &

echo "Starting Celery Beat..."
celery -A core.celery_app.celery_app beat --loglevel=info &

echo "Starting Gunicorn..."
# Use 2 workers to save memory on Starter plan
gunicorn -w 2 -b 0.0.0.0:$PORT app:app
