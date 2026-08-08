# Use official lightweight Python image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Set working directory inside container
WORKDIR /app

# Install system dependencies if any are needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all code assets into container
COPY . .

# Expose port
EXPOSE 8000

# Run uvicorn on all interfaces (Render injects $PORT)
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}
