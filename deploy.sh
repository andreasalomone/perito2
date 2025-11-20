#!/bin/bash

# Report AI - Docker Deployment Script
# This script automates the complete deployment process

set -e  # Exit on any error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Functions
print_step() {
    echo -e "\n${BLUE}===> $1${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

print_success "Docker is running"

# Check if .env file exists
if [ ! -f .env ]; then
    print_warning ".env file not found. Please create one from .env.example"
    echo "Run: cp .env.example .env"
    echo "Then edit .env with your configuration"
    exit 1
fi

print_success ".env file found"

# Step 1: Build Docker images
print_step "Step 1/5: Building Docker images..."
docker compose build

print_success "Docker images built successfully"

# Step 2: Start database and Redis
print_step "Step 2/5: Starting database and Redis..."
docker compose up -d db redis

print_success "Database and Redis started"

# Step 3: Wait for database to be ready
print_step "Step 3/5: Waiting for PostgreSQL to be ready..."
echo "Waiting 10 seconds for database initialization..."
sleep 10

# Check if database is ready
MAX_RETRIES=30
RETRY_COUNT=0
while ! docker compose exec -T db pg_isready -U reportai > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        print_error "Database failed to start after ${MAX_RETRIES} seconds"
        docker compose logs db
        exit 1
    fi
    echo "Waiting for database... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 1
done

print_success "PostgreSQL is ready"

# Step 4: Initialize database schema
print_step "Step 4/5: Initializing database schema..."

# Start web container temporarily to run init-db
docker compose run --rm web flask init-db

print_success "Database schema initialized"

# Step 5: Start all services
print_step "Step 5/5: Starting all services..."
docker compose up -d

print_success "All services started"

# Wait a moment for services to be ready
sleep 3

# Check service status
print_step "Service Status:"
docker compose ps

# Verify web application is responding
print_step "Verifying application..."
echo "Testing http://localhost:5000..."

MAX_RETRIES=10
RETRY_COUNT=0
while ! curl -s -o /dev/null -w "%{http_code}" http://localhost:5000 | grep -q "200\|401"; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        print_warning "Application may not be responding yet. Check logs with: docker compose logs web"
        break
    fi
    echo "Waiting for application to respond... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
    print_success "Application is responding!"
fi

# Final summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo "Application is running at: http://localhost:5000"
echo ""
echo "Useful commands:"
echo "  View logs:           docker compose logs -f"
echo "  View specific logs:  docker compose logs -f web"
echo "  Stop services:       docker compose down"
echo "  Restart services:    docker compose restart"
echo "  Check status:        docker compose ps"
echo ""
echo -e "${YELLOW}Note: You'll need to authenticate with credentials from your .env file${NC}"
echo ""
