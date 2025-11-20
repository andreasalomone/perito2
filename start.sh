#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Report AI Application Stack...${NC}\n"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    
    # Kill all background processes
    if [ ! -z "$REDIS_PID" ]; then
        echo "Stopping Redis..."
        kill $REDIS_PID 2>/dev/null
    fi
    
    if [ ! -z "$CELERY_PID" ]; then
        echo "Stopping Celery worker..."
        kill $CELERY_PID 2>/dev/null
    fi
    
    if [ ! -z "$FLASK_PID" ]; then
        echo "Stopping Flask app..."
        kill $FLASK_PID 2>/dev/null
    fi
    
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

# Check if Redis is already running
if redis-cli ping &>/dev/null; then
    echo -e "${YELLOW}Redis is already running${NC}"
else
    # Start Redis server
    echo -e "${GREEN}Starting Redis server...${NC}"
    redis-server &
    REDIS_PID=$!
    
    # Wait for Redis to start
    for i in {1..30}; do
        if redis-cli ping &>/dev/null; then
            echo -e "${GREEN}✓ Redis started successfully${NC}"
            break
        fi
        sleep 0.1
    done
    
    if ! redis-cli ping &>/dev/null; then
        echo -e "${RED}✗ Failed to start Redis${NC}"
        cleanup
    fi
fi

# Start Celery worker
echo -e "\n${GREEN}Starting Celery worker...${NC}"
# Set PYTHONPATH to allow Celery worker to import app module
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
.venv/bin/celery -A core.celery_app.celery_app worker --loglevel=info &
CELERY_PID=$!

# Wait a bit for Celery to start
sleep 2
echo -e "${GREEN}✓ Celery worker started (PID: $CELERY_PID)${NC}"

# Start Flask application
echo -e "\n${GREEN}Starting Flask application...${NC}"
.venv/bin/python app.py &
FLASK_PID=$!

# Wait a bit for Flask to start
sleep 2
echo -e "${GREEN}✓ Flask app started (PID: $FLASK_PID)${NC}"

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}All services are running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "Redis:  ${GREEN}Running${NC} (PID: $REDIS_PID)"
echo -e "Celery: ${GREEN}Running${NC} (PID: $CELERY_PID)"
echo -e "Flask:  ${GREEN}Running${NC} (PID: $FLASK_PID)"
echo -e "\nAccess the application at: ${YELLOW}http://127.0.0.1:5000${NC}"
echo -e "\nPress ${YELLOW}Ctrl+C${NC} to stop all services\n"

# Wait for all background processes
wait
