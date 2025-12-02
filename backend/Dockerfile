# Use official Python image (Pin to Bookworm for stability)
FROM python:3.10-slim-bookworm

# Set working directory
WORKDIR /app

# Install system dependencies for PyMuPDF and Pillow
# libgl1-mesa-glx is deprecated in Bookworm, use libgl1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port Cloud Run expects (8080)
ENV PORT=8080
EXPOSE 8080

# Command to run the application
# Using 0.0.0.0 to bind to all interfaces
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
