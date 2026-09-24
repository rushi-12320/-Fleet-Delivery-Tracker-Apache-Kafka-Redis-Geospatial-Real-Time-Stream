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
COPY config.py demo_fleet.py producer.py consumer.py api.py run_all.py ./

# Expose the Render-assigned port for the web service
EXPOSE 8000

# Healthcheck uses the runtime PORT environment variable so it works on Render.
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=5 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get('PORT', '8000')}/health', timeout=5).read()" || exit 1

# Run the single FastAPI app entrypoint that serves the dashboard and health endpoint.
CMD ["python", "api.py"]
