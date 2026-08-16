# Build frontend
FROM node:24-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Build Python dependencies in a separate stage
FROM python:3.14-slim AS python-builder

WORKDIR /app

# Install build dependencies and uv
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.12.3

# Copy only dependency file first
COPY backend/pyproject.toml ./

# Install dependencies into a virtual env (easier to copy)
RUN uv venv /opt/venv \
    && . /opt/venv/bin/activate \
    && uv pip install --no-cache .

# Copy source and install package
COPY backend/src/ ./src/
RUN . /opt/venv/bin/activate && uv pip install --no-cache . \
    # Clean up unnecessary files to reduce image size
    && find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/venv -type f -name "*.pyc" -delete 2>/dev/null || true \
    && find /opt/venv -type f -name "*.pyo" -delete 2>/dev/null || true \
    && find /opt/venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /opt/venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true

# Final runtime image
FROM python:3.14-slim AS runtime

WORKDIR /app

# Install only runtime system dependencies
# hadolint ignore=DL3008
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    # Remove pip/setuptools from runtime - we don't need them
    && pip uninstall -y pip setuptools \
    && rm -rf /root/.cache

# Copy virtual environment from builder
COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Copy application code
COPY backend/alembic.ini ./
COPY backend/migrations/ ./migrations/

# Copy built frontend
COPY --from=frontend-builder /frontend/dist ./static/

# Create tile cache directory
RUN mkdir -p /app/tile-cache

EXPOSE 8000

CMD ["uvicorn", "trainingdash.app:app", "--host", "0.0.0.0", "--port", "8000"]
