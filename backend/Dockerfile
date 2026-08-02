# Build frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Build backend
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml ./
COPY backend/src/ ./src/
COPY backend/alembic.ini ./
COPY backend/migrations/ ./migrations/

# Copy built frontend
COPY --from=frontend-builder /frontend/dist ./static/

RUN uv pip install --system --no-cache .

# Create tile cache directory
RUN mkdir -p /app/tile-cache

EXPOSE 8000

CMD ["uvicorn", "trainingdash.app:app", "--host", "0.0.0.0", "--port", "8000"]
