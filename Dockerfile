# ==========================================================================
# Dockerfile — Insightful-Orders
# - Multi-stage build (builder → runtime)
# - Pre-builds wheels for faster installs
# - Keeps runtime image slim & patched
# - Runs Gunicorn via WSGI in production
# ==========================================================================

# ----------------------------------------------------------------------
# Builder Stage — install deps & build wheels
# ----------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app

# System dependencies for building psycopg2, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (leverage Docker cache)
COPY requirements.txt .

# Upgrade pip + build wheels
RUN pip install --upgrade pip \
 && pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt


# ----------------------------------------------------------------------
# Runtime Stage — final slim image
# ----------------------------------------------------------------------
FROM python:3.11-slim-bookworm

WORKDIR /app

# Keep system packages patched
RUN apt-get update && apt-get dist-upgrade -y && rm -rf /var/lib/apt/lists/*

# Install runtime deps from wheels
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache /wheels/*

# Copy application source (controlled by .dockerignore)
COPY . .

# Entrypoint shim (loads env before running CMD/command)
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Optional: run as non-root for security
# RUN useradd -m appuser && chown -R appuser:appuser /app
# USER appuser

# ----------------------------------------------------------------------
# Environment + Entrypoint
# ----------------------------------------------------------------------
ENV FLASK_APP=manage.py
ENV FLASK_RUN_HOST=0.0.0.0

ENTRYPOINT ["/entrypoint.sh"]

# Default CMD (dev). In production, docker-compose overrides with gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:5000", "wsgi:application"]
