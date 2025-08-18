# Use current Debian base to pick up latest security patches
FROM python:3.11-slim-bookworm

# Set working directory inside the container
WORKDIR /app

# --- OS security updates (this is the part that addresses CVEs) --------------
# Pull package lists and apply security upgrades for the base image layer
RUN apt-get update \
 && apt-get -y --no-install-recommends upgrade \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies without caching
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# (Optional but good hygiene) run as non-root
# RUN useradd -m appuser && chown -R appuser:appuser /app
# USER appuser

# Set default Flask app entrypoint for `flask run`
ENV FLASK_APP=manage.py
ENV FLASK_RUN_HOST=0.0.0.0

# Default container command: run Flask's development server
CMD ["flask", "run", "--host=0.0.0.0"]
