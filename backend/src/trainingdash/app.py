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
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from trainingdash.routers import activities, admin, analytics, auth, oauth, user

logger = logging.getLogger(__name__)

# Map tile caching configuration
TILE_CACHE_DIR = Path(os.environ.get("TILE_CACHE_DIR", "/app/tile-cache"))
TILE_CACHE_MAX_AGE_DAYS = 30
TILE_USER_AGENT = "TrainingDash fitness app (personal use)"


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
    app.include_router(auth.router)
    app.include_router(oauth.router)
    app.include_router(user.router)
    app.include_router(admin.router)
    app.include_router(activities.router)
    app.include_router(analytics.router)

    # Map tile proxy with caching
    @app.get("/tiles/{z}/{x}/{y}.png")
    async def get_map_tile(z: int, x: int, y: int):
        """
        Proxy and cache OpenStreetMap tiles.

        Tiles are cached to disk for 30 days to reduce load on OSM servers
        and improve performance.
        """
        # Validate zoom level (OSM supports 0-19)
        if z < 0 or z > 19:
            raise HTTPException(status_code=400, detail="Invalid zoom level")

        # Validate tile coordinates
        max_coord = 2**z - 1
        if x < 0 or x > max_coord or y < 0 or y > max_coord:
            raise HTTPException(status_code=400, detail="Invalid tile coordinates")

        # Create cache directory structure
        cache_path = TILE_CACHE_DIR / str(z) / str(x) / f"{y}.png"

        # Check cache
        if cache_path.exists():
            # Check if cache is still valid
            mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
            age = datetime.now() - mtime
            if age.days < TILE_CACHE_MAX_AGE_DAYS:
                return FileResponse(
                    cache_path,
                    media_type="image/png",
                    headers={
                        "Cache-Control": f"public, max-age={TILE_CACHE_MAX_AGE_DAYS * 86400}",
                        "X-Cache": "HIT",
                    },
                )

        # Fetch from OSM
        osm_url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    osm_url,
                    headers={"User-Agent": TILE_USER_AGENT},
                    timeout=10.0,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code, detail="Tile fetch failed"
            )
        except httpx.RequestError:
            raise HTTPException(status_code=502, detail="Could not reach tile server")

        # Save to cache
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(response.content)

        return FileResponse(
            cache_path,
            media_type="image/png",
            headers={
                "Cache-Control": f"public, max-age={TILE_CACHE_MAX_AGE_DAYS * 86400}",
                "X-Cache": "MISS",
            },
        )

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
