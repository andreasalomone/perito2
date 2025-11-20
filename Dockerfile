# Production Dockerfile for Report AI Application
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/uploads /app/instance

# Set working directory
WORKDIR /app

# Copy requirements files
COPY requirements.txt requirements-dev.txt ./

# Install Python dependencies as root
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser . .

# Ensure proper ownership of critical directories
# This prevents the "chown trap" when Docker mounts volumes
RUN chown -R appuser:appuser /app/uploads /app/instance && \
    chmod -R 755 /app/uploads /app/instance

# Switch to non-root user
USER appuser

# Expose port for Flask application
EXPOSE 5000

# Default command (can be overridden in docker-compose)
CMD ["python", "run_server.py"]
