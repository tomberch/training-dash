"""Health check endpoint for E2E testing and container orchestration."""

from fastapi import APIRouter
from sqlalchemy import text

from trainingdash.auth import DbSession

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health_check(db: DbSession):
    """Health check that verifies database connectivity.
    
    Returns 200 if the app and database are ready.
    Used by:
    - Docker Compose healthchecks
    - Playwright webServer to wait for app readiness
    - Container orchestration (k8s liveness/readiness probes)
    """
    # Verify database connection works
    await db.execute(text("SELECT 1"))
    return {"status": "healthy", "database": "connected"}
