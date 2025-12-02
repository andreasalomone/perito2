# ==========================================
# Stage 1: Builder (Compile dependencies)
# ==========================================
FROM python:3.10-slim-bookworm as builder

WORKDIR /app

# Install build dependencies (needed for compiling some pip packages)
# We do NOT include these in the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment to isolate dependencies
RUN python -m venv /app/venv
ENV PATH="/app/venv/bin:$PATH"

COPY requirements.txt .

# Install dependencies into the virtual environment
RUN pip install --no-cache-dir -r requirements.txt

# ==========================================
# Stage 2: Runner (Final Runtime Image)
# ==========================================
FROM python:3.10-slim-bookworm as runner

WORKDIR /app

# Set recommended Python environment variables
# 1. Force stdout/stderr to be unbuffered (crucial for Cloud Logging)
# 2. Prevent writing .pyc files (saves space in read-only containers)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/venv/bin:$PATH"

# Install ONLY runtime libraries (no compilers)
# libgl1 and libglib2.0-0 are likely needed for cv2/pillow runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
# UID 1000 is standard
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

# Copy the virtual environment from the builder stage
COPY --from=builder /app/venv /app/venv

# Copy application code
# Ensure the non-root user owns the files
COPY --chown=appuser:appuser . .

# Switch to the non-root user
USER appuser

# Expose port (Documentation only, Cloud Run ignores this but useful for local)
EXPOSE 8080

# Command to run the application
# We use the shell form to properly expand the $PORT variable provided by Cloud Run
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}

