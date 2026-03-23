# Multi-stage Dockerfile for HRV Agentic Intelligence System

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: Production ───────────────────────────────────────────────────────
FROM python:3.11-slim AS production

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application source
COPY . .

# Create directories
RUN mkdir -p data/lancedb ml/models

# Copy dataset
COPY data/HRV_data_20201209_2.xlsx data/

# Environment defaults (override at runtime)
ENV PYTHONPATH=/app
ENV LOG_LEVEL=INFO
ENV AWS_REGION=us-east-1
ENV HRV_DATA_PATH=/app/data/HRV_data_20201209_2.xlsx
ENV MODEL_PATH=/app/ml/models/xgb_hrv_v1.pkl
ENV LANCEDB_PATH=/app/data/lancedb

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# Start FastAPI
CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
