# Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Build backend
FROM python:3.12-slim AS backend

WORKDIR /app

# Install system dependencies for psycopg (libpq) and curl for healthchecks
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    # Upgrade pip, setuptools (CVE-2025-47273, CVE-2026-59890), msgpack (GHSA-6v7p-g79w-8964) and install uv
    && pip install --no-cache-dir pip==26.2.1 setuptools==83.0.0 msgpack==1.2.1 \
    && pip install --no-cache-dir uv==0.12.3

# Copy only dependency file first (cached layer for deps)
COPY backend/pyproject.toml ./

# Install dependencies (cached unless pyproject.toml changes)
RUN uv pip install --system --no-cache .

# Now copy source code (changes frequently, but deps already cached)
COPY backend/src/ ./src/
COPY backend/alembic.ini ./
COPY backend/migrations/ ./migrations/

# Re-install to register the package (fast, deps already there)
RUN uv pip install --system --no-cache .

# Copy built frontend
COPY --from=frontend-builder /frontend/dist ./static/

# Create tile cache directory
RUN mkdir -p /app/tile-cache

EXPOSE 8000

CMD ["uvicorn", "trainingdash.app:app", "--host", "0.0.0.0", "--port", "8000"]
