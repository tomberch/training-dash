"""
Geocoding service for reverse geocoding GPS coordinates to place names.

Uses Photon (Komoot) as the primary geocoding provider with Postgres caching
to respect rate limits and improve performance.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Photon API endpoint (OSM-based, maintained by Komoot)
PHOTON_URL = "https://photon.komoot.io/reverse"

# Cache settings
CACHE_TTL_SECONDS = 365 * 24 * 60 * 60  # 1 year (place names rarely change)
COORDINATE_PRECISION = 2  # Round to 2 decimals (~1km grid)

# Rate limiting: 1 request per second to be safe
RATE_LIMIT_DELAY = 1.0


@dataclass
class GeocodedPlace:
    """A geocoded place with name and type."""
    name: str
    place_type: str  # city, town, village, hamlet, etc.
    lat: Optional[float] = None  # Place center latitude
    lon: Optional[float] = None  # Place center longitude
    country: Optional[str] = None
    state: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "place_type": self.place_type,
            "lat": self.lat,
            "lon": self.lon,
            "country": self.country,
            "state": self.state,
        }


    @classmethod
    def from_dict(cls, data: dict) -> "GeocodedPlace":
        return cls(
            name=data["name"],
            place_type=data["place_type"],
            lat=data.get("lat"),
            lon=data.get("lon"),
            country=data.get("country"),
            state=data.get("state"),
        )


# Place type ranking (higher = more important)
PLACE_TYPE_RANK = {
    "city": 100,
    "town": 80,
    "village": 60,
    "district": 55,  # Swiss-style named area within municipality
    "locality": 50,  # Specific settlement/neighborhood
    "hamlet": 40,
    "suburb": 30,
    "neighbourhood": 20,
}


def get_place_rank(place: GeocodedPlace) -> int:
    """Get the importance rank of a place based on its type."""
    return PLACE_TYPE_RANK.get(place.place_type, 0)


def _round_coordinate(coord: float) -> float:
    """Round coordinate to cache precision."""
    return round(coord, COORDINATE_PRECISION)


def _cache_key(lat: float, lon: float, prefer_locality: bool = False) -> str:
    """Generate cache key for coordinates."""
    rounded_lat = _round_coordinate(lat)
    rounded_lon = _round_coordinate(lon)
    suffix = ":loc" if prefer_locality else ""
    return f"geocode:{rounded_lat}:{rounded_lon}{suffix}"


class GeocodingService:
    """
    Async geocoding service with Postgres caching and rate limiting.
    
    Usage:
        service = GeocodingService(db_session)
        place = await service.reverse_geocode(46.9480, 7.4474)
    """
    
    def __init__(self, db: AsyncSession):
        self._db = db
        self._http: Optional[httpx.AsyncClient] = None
        self._last_request_time: float = 0
        self._lock = asyncio.Lock()
        self._table_checked = False

    async def _ensure_cache_table(self):
        """Ensure the geocoding cache table exists."""
        if self._table_checked:
            return
        
        await self._db.execute(text("""
            CREATE TABLE IF NOT EXISTS geocoding_cache (
                cache_key VARCHAR(100) PRIMARY KEY,
                result_json TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """))
        await self._db.commit()
        self._table_checked = True

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http is None:
            self._http = httpx.AsyncClient(
                timeout=10.0,
                headers={"User-Agent": "TrainDash fitness app (personal use)"}
            )
        return self._http
    
    async def close(self):
        """Close HTTP connection."""
        if self._http:
            await self._http.aclose()
            self._http = None
    
    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < RATE_LIMIT_DELAY:
                await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()
    
    async def _get_from_cache(self, cache_key: str) -> Optional[dict]:
        """Get cached result from Postgres."""
        await self._ensure_cache_table()
        result = await self._db.execute(
            text("SELECT result_json FROM geocoding_cache WHERE cache_key = :key"),
            {"key": cache_key}
        )
        row = result.fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return None
    
    async def _set_cache(self, cache_key: str, value: Optional[dict]):
        """Store result in Postgres cache."""
        await self._ensure_cache_table()
        json_value = json.dumps(value) if value is not None else None
        await self._db.execute(
            text("""
                INSERT INTO geocoding_cache (cache_key, result_json)
                VALUES (:key, :value)
                ON CONFLICT (cache_key) DO UPDATE SET result_json = :value, created_at = NOW()
            """),
            {"key": cache_key, "value": json_value}
        )
        await self._db.commit()
    
    async def reverse_geocode(self, lat: float, lon: float, prefer_locality: bool = False) -> Optional[GeocodedPlace]:
        """
        Reverse geocode a coordinate to a place name.
        
        Returns the most relevant place (city/town/village) or None if not found.
        Uses Postgres cache to avoid repeated API calls.
        
        Args:
            lat: Latitude
            lon: Longitude
            prefer_locality: If True, prefer specific locality names (for waypoints).
                           If False, prefer settlement names like city/village (for start/end).
        """
        cache_key = _cache_key(lat, lon, prefer_locality)
        
        # Check cache first
        try:
            cached = await self._get_from_cache(cache_key)
            if cached is not None:
                if cached.get("_null"):
                    return None  # Negative cache hit
                return GeocodedPlace.from_dict(cached)
        except Exception as e:
            logger.warning(f"Postgres cache read error: {e}")
        
        # Rate limit before API call
        await self._rate_limit()

        # Call Photon API
        try:
            http = await self._get_http_client()
            response = await http.get(
                PHOTON_URL,
                params={"lat": lat, "lon": lon, "limit": 1}
            )
            response.raise_for_status()
            data = response.json()
            
            place = self._parse_photon_response(data, prefer_locality=prefer_locality)
            
            # Cache the result (including None for negative caching)
            try:
                if place:
                    await self._set_cache(cache_key, place.to_dict())
                else:
                    await self._set_cache(cache_key, {"_null": True})
            except Exception as e:
                logger.warning(f"Postgres cache write error: {e}")
            
            return place
            
        except httpx.HTTPError as e:
            logger.warning(f"Geocoding API error for ({lat}, {lon}): {e}")
            return None
    
    def _parse_photon_response(self, data: dict, prefer_locality: bool = False) -> Optional[GeocodedPlace]:
        """Parse Photon API response to extract place information.
        
        Args:
            data: Photon API response
            prefer_locality: Ignored - always prefer city/village level names for clarity.
        """
        features = data.get("features", [])
        if not features:
            return None
        
        feature = features[0]
        props = feature.get("properties", {})
        
        # Extract coordinates from geometry
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [])
        place_lon = coords[0] if len(coords) > 0 else None
        place_lat = coords[1] if len(coords) > 1 else None
        
        place_type = None
        place_name = None
        
        # Always prefer recognizable settlement names (city/village level)
        # Priority: village > town > city > hamlet > locality > district
        for ptype in ["village", "town", "city", "hamlet", "locality", "district", "suburb"]:
            if ptype in props and props[ptype]:
                place_name = props[ptype]
                place_type = ptype
                break


        # Fallback to name if available (but skip POI-like names)
        if not place_name and "name" in props:
            name = props["name"]
            # Skip names that look like POIs (contain numbers, "m", etc.)
            if not any(c.isdigit() for c in name):
                place_name = name
                place_type = props.get("type", "locality")
        
        if not place_name:
            return None
        
        return GeocodedPlace(
            name=place_name,
            place_type=place_type or "locality",
            lat=place_lat,
            lon=place_lon,
            country=props.get("country"),
            state=props.get("state"),
        )
    
    async def reverse_geocode_batch(
        self, 
        coordinates: list[tuple[float, float]],
        prefer_locality: bool = False,
    ) -> list[Optional[GeocodedPlace]]:
        """
        Reverse geocode multiple coordinates.
        
        Deduplicates coordinates (by cache key) to minimize API calls.
        Returns results in the same order as input.
        """
        # Deduplicate by cache key
        unique_coords = {}
        coord_to_key = {}
        
        for lat, lon in coordinates:
            key = _cache_key(lat, lon, prefer_locality)
            coord_to_key[(lat, lon)] = key
            if key not in unique_coords:
                unique_coords[key] = (lat, lon)
        
        # Fetch all unique coordinates
        results = {}
        for key, (lat, lon) in unique_coords.items():
            results[key] = await self.reverse_geocode(lat, lon, prefer_locality=prefer_locality)
        
        # Map back to original order
        return [results[coord_to_key[coord]] for coord in coordinates]
