# ====================================================================
# Delivery Tracking System - Production Cloud Dockerfile
# ====================================================================
FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr (crucial for real-time cloud logs)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

# Install minimal system dependencies required for networking and compiling C extensions if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    librdkafka-dev \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY config.py producer.py consumer.py api.py run_all.py ./

# Expose dynamic web server port
EXPOSE 8000

# Default healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Start all services concurrently (Producer, Consumer, and FastAPI Dashboard)
CMD ["python", "run_all.py"]
