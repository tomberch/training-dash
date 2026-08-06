"""Map tile proxy endpoints with disk caching."""

import os
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(tags=["tiles"])

TILE_CACHE_DIR = Path(os.environ.get("TILE_CACHE_DIR", "/app/tile-cache"))
TILE_CACHE_MAX_AGE_DAYS = 30
TILE_USER_AGENT = "TrainingDash fitness app (personal use)"

_CARTO_STYLES: dict[str, str] = {
    "light": "light_all",
    "dark": "dark_all",
}


def _cache_hit(cache_path: Path) -> bool:
    """Return True if the cached file exists and is still within max age."""
    if not cache_path.exists():
        return False
    mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
    return (datetime.now() - mtime).days < TILE_CACHE_MAX_AGE_DAYS


def _cache_headers(hit: bool) -> dict[str, str]:
    return {
        "Cache-Control": (
            f"public, max-age={TILE_CACHE_MAX_AGE_DAYS * 86400}"
        ),
        "X-Cache": "HIT" if hit else "MISS",
    }


@router.get("/tiles/{z}/{x}/{y}.png")
async def get_osm_tile(z: int, x: int, y: int) -> FileResponse:
    """
    Proxy and cache OpenStreetMap tiles.

    Tiles are cached to disk for 30 days to reduce load on OSM servers
    and improve performance.
    """
    if z < 0 or z > 19:
        raise HTTPException(status_code=400, detail="Invalid zoom level")

    max_coord = 2**z - 1
    if x < 0 or x > max_coord or y < 0 or y > max_coord:
        raise HTTPException(status_code=400, detail="Invalid tile coordinates")

    cache_path = TILE_CACHE_DIR / str(z) / str(x) / f"{y}.png"

    if _cache_hit(cache_path):
        return FileResponse(
            cache_path,
            media_type="image/png",
            headers=_cache_headers(hit=True),
        )

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
        raise HTTPException(
            status_code=502, detail="Could not reach tile server"
        )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(response.content)

    return FileResponse(
        cache_path,
        media_type="image/png",
        headers=_cache_headers(hit=False),
    )


@router.get("/tiles/carto/{style}/{z}/{x}/{y}.png")
async def get_carto_tile(
    style: str, z: int, x: int, y: int
) -> FileResponse:
    """
    Proxy and cache CartoDB (CARTO) raster tiles.

    Supports two styles:
      - light  → Positron (clean light grey, used in latte theme)
      - dark   → Dark Matter (dark background, used in mocha theme)

    Tiles are cached to disk for 30 days.
    """
    if style not in _CARTO_STYLES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown style '{style}'. Use 'light' or 'dark'.",
        )

    if z < 0 or z > 19:
        raise HTTPException(status_code=400, detail="Invalid zoom level")

    max_coord = 2**z - 1
    if x < 0 or x > max_coord or y < 0 or y > max_coord:
        raise HTTPException(
            status_code=400, detail="Invalid tile coordinates"
        )

    cache_path = (
        TILE_CACHE_DIR / "carto" / style / str(z) / str(x) / f"{y}.png"
    )

    if _cache_hit(cache_path):
        return FileResponse(
            cache_path,
            media_type="image/png",
            headers=_cache_headers(hit=True),
        )

    carto_style = _CARTO_STYLES[style]
    carto_url = (
        f"https://a.basemaps.cartocdn.com/{carto_style}/{z}/{x}/{y}.png"
    )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                carto_url,
                headers={"User-Agent": TILE_USER_AGENT},
                timeout=10.0,
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code, detail="Tile fetch failed"
        )
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
