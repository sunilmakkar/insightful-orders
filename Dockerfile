# ---------- Builder Stage ----------
FROM python:3.11-slim-bookworm AS builder

# Set working directory inside the container
WORKDIR /app

# System dependencies for building psycopg2, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and build wheels
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# ---------- Runtime Stage ----------
FROM python:3.11-slim-bookworm

WORKDIR /app

# Install runtime deps only (from wheels)
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy app source
COPY . .

# Run as non-root (optional but recommended)
# RUN useradd -m appuser && chown -R appuser:appuser /app
# USER appuser

# Environment variables
ENV FLASK_APP=manage.py
ENV FLASK_RUN_HOST=0.0.0.0

# Default command (dev). For prod, override in docker-compose.prod.yml with gunicorn
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
