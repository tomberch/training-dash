"""TrainingDash FastAPI application factory.

This module creates the FastAPI app and mounts routers. Domain logic
lives in the routers/ subpackage; this file handles infrastructure:
- Exception handlers
- Static file serving (SPA)
- Map tile proxy
"""

import logging
import os
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from trainingdash.integrations.garmin.mock_client import setup_mock_garmin_client
from trainingdash.integrations.xert.mock_client import setup_mock_xert_client
from trainingdash.routers import (
    activities,
    admin,
    admin_system,
    analytics,
    auth,
    bikes,
    courses,
    events,
    health,
    metrics,
    oauth,
    query,
    race_plans,
    saved_filters,
    tiles,
    user,
)

logger = logging.getLogger(__name__)

# Initialize mock clients if enabled (for E2E testing)
setup_mock_xert_client()
setup_mock_garmin_client()


def generate_error_id() -> str:
    """Generate a short, unique error ID for tracking."""
    return uuid.uuid4().hex[:8]


def create_app() -> FastAPI:
    app = FastAPI(title="TrainingDash")

    # Global exception handler for unhandled errors
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # Don't intercept HTTPExceptions - let FastAPI handle those
        if isinstance(exc, HTTPException):
            raise exc

        error_id = generate_error_id()
        logger.error(
            f"Unhandled exception [error_id={error_id}] {request.method} {request.url.path}: {exc}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal error occurred",
                "error_id": error_id,
            },
        )

    # Enhanced HTTPException handler to include error_id for 500s
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        content = {"detail": exc.detail}
        if exc.status_code >= 500:
            error_id = generate_error_id()
            content["error_id"] = error_id
            logger.error(
                f"HTTP {exc.status_code} [error_id={error_id}] {request.method} {request.url.path}: {exc.detail}"
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=getattr(exc, "headers", None),
        )

    # Mount routers
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(oauth.router)
    app.include_router(user.router)
    app.include_router(admin.router)
    app.include_router(admin_system.router)
    app.include_router(activities.router)
    app.include_router(analytics.router)
    app.include_router(bikes.router)
    app.include_router(courses.router)
    app.include_router(events.router)
    app.include_router(metrics.router)
    app.include_router(query.router)
    app.include_router(race_plans.router)
    app.include_router(saved_filters.router)
    app.include_router(tiles.router)

    # Serve frontend static files if the dist directory exists
    static_dir = Path("/app/static")
    if static_dir.exists():
        # Serve favicon and other root static files
        @app.get("/favicon.svg")
        async def serve_favicon():
            return FileResponse(static_dir / "favicon.svg")

        @app.get("/icons.svg")
        async def serve_icons():
            return FileResponse(static_dir / "icons.svg")

        # Serve static assets (JS, CSS, etc.)
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        # Serve map preview images
        map_previews_dir = static_dir / "map-previews"
        if map_previews_dir.exists():
            app.mount("/map-previews", StaticFiles(directory=map_previews_dir), name="map-previews")

    # Serve uploaded files (avatars, etc.)
    uploads_dir = Path(os.environ.get("TRAININGDASH_UPLOADS_DIR", "/app/uploads"))
    uploads_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    # Serve frontend static files if the dist directory exists
    if static_dir.exists():
        # Catch-all route for SPA - must be registered last
        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str):
            # For any non-API route, serve index.html (SPA handles routing)
            index_path = static_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
            raise HTTPException(status_code=404, detail="Not found")

    return app


app = create_app()
