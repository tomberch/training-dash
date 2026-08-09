"""Map tile proxy endpoints with disk caching."""

import os
from datetime import datetime
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["tiles"])

TILE_CACHE_DIR = Path(os.environ.get("TILE_CACHE_DIR", "/app/tile-cache"))
TILE_CACHE_MAX_AGE_DAYS = 30
TILE_USER_AGENT = "TrainingDash fitness app (personal use)"

# Allowlisted tile providers - only these URLs are fetched
_OSM_TILE_URL = "https://tile.openstreetmap.org"
_CARTO_TILE_URL = "https://a.basemaps.cartocdn.com"

# Carto style mapping (Literal type ensures only these values are accepted)
CartoStyle = Literal["light", "dark"]
_CARTO_STYLES: dict[CartoStyle, str] = {
    "light": "light_all",
    "dark": "dark_all",
}


def _tile_coord_str(value: int, *, max_inclusive: int, name: str) -> str:
    """
    Validate and normalize a tile coordinate (z/x/y) to a safe string.

    Returns the value's decimal string iff 0 <= value <= max_inclusive.
    The returned string is derived purely from the validated int, so it
    contains only digits and is safe to interpolate into a URL or path.
    Raises HTTPException(400) otherwise.
    """
    if value < 0 or value > max_inclusive:
        raise HTTPException(status_code=400, detail=f"Invalid {name}")
    return str(value)


def _safe_cache_path(base_dir: Path, *parts: str) -> Path:
    """
    Construct a cache path with traversal protection.

    Raises ValueError if the resulting path would escape base_dir.
    """
    # Resolve both paths to absolute to handle any ../ attempts
    base_resolved = base_dir.resolve()
    target = base_dir.joinpath(*parts).resolve()

    if not target.is_relative_to(base_resolved):
        raise ValueError("Path traversal detected")

    return target


def _cache_hit(cache_path: Path) -> bool:
    """Return True if the cached file exists and is still within max age."""
    if not cache_path.exists():
        return False
    mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
    return (datetime.now() - mtime).days < TILE_CACHE_MAX_AGE_DAYS


def _cache_headers(hit: bool) -> dict[str, str]:
    return {
        "Cache-Control": (f"public, max-age={TILE_CACHE_MAX_AGE_DAYS * 86400}"),
        "X-Cache": "HIT" if hit else "MISS",
    }


@router.get("/tiles/{z}/{x}/{y}.png")
async def get_osm_tile(z: int, x: int, y: int) -> FileResponse:
    """
    Proxy and cache OpenStreetMap tiles.

    Tiles are cached to disk for 30 days to reduce load on OSM servers
    and improve performance.
    """
    # Validate zoom level (0-19 is standard for web maps)
    z_s = _tile_coord_str(z, max_inclusive=19, name="zoom level")

    # Validate tile coordinates for the given zoom level
    max_coord = 2**z - 1
    x_s = _tile_coord_str(x, max_inclusive=max_coord, name="tile coordinate")
    y_s = _tile_coord_str(y, max_inclusive=max_coord, name="tile coordinate")

    # Construct cache path with traversal protection
    try:
        cache_path = _safe_cache_path(TILE_CACHE_DIR, z_s, x_s, f"{y_s}.png")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tile path")

    if _cache_hit(cache_path):
        return FileResponse(
            cache_path,
            media_type="image/png",
            headers=_cache_headers(hit=True),
        )

    # URL built from validated, digit-only coordinate strings.
    osm_url = f"{_OSM_TILE_URL}/{z_s}/{x_s}/{y_s}.png"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                osm_url,
                headers={"User-Agent": TILE_USER_AGENT},
                timeout=10.0,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Tile fetch failed")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Could not reach tile server")

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(response.content)

    return FileResponse(
        cache_path,
        media_type="image/png",
        headers=_cache_headers(hit=False),
    )


@router.get("/tiles/carto/{style}/{z}/{x}/{y}.png")
async def get_carto_tile(style: CartoStyle, z: int, x: int, y: int) -> FileResponse:
    """
    Proxy and cache CartoDB (CARTO) raster tiles.

    Supports two styles:
      - light  → Positron (clean light grey, used in latte theme)
      - dark   → Dark Matter (dark background, used in mocha theme)

    Tiles are cached to disk for 30 days.
    """
    # Style is validated by Literal type, but check dict membership for safety
    if style not in _CARTO_STYLES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown style '{style}'. Use 'light' or 'dark'.",
        )

    # Validate zoom level (0-19 is standard for web maps)
    z_s = _tile_coord_str(z, max_inclusive=19, name="zoom level")

    # Validate tile coordinates for the given zoom level
    max_coord = 2**z - 1
    x_s = _tile_coord_str(x, max_inclusive=max_coord, name="tile coordinate")
    y_s = _tile_coord_str(y, max_inclusive=max_coord, name="tile coordinate")

    # Construct cache path with traversal protection
    try:
        cache_path = _safe_cache_path(TILE_CACHE_DIR, "carto", style, z_s, x_s, f"{y_s}.png")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tile path")

    if _cache_hit(cache_path):
        return FileResponse(
            cache_path,
            media_type="image/png",
            headers=_cache_headers(hit=True),
        )

    # URL built from validated, digit-only coordinate strings + validated style.
    carto_style = _CARTO_STYLES[style]
    carto_url = f"{_CARTO_TILE_URL}/{carto_style}/{z_s}/{x_s}/{y_s}.png"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                carto_url,
                headers={"User-Agent": TILE_USER_AGENT},
                timeout=10.0,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Tile fetch failed")
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="Could not reach CartoDB tile server",
        )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(response.content)

    return FileResponse(
        cache_path,
        media_type="image/png",
        headers=_cache_headers(hit=False),
    )
