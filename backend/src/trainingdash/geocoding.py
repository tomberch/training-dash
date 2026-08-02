"""
Geocoding service for reverse geocoding GPS coordinates to place names.

Uses Photon (Komoot) as the primary geocoding provider with Redis caching
to respect rate limits and improve performance.
"""

import asyncio
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

import httpx
import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Photon API endpoint (OSM-based, maintained by Komoot)
PHOTON_URL = "https://photon.komoot.io/reverse"

# Cache settings
CACHE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
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


def _cache_key(lat: float, lon: float) -> str:
    """Generate cache key for coordinates."""
    rounded_lat = _round_coordinate(lat)
    rounded_lon = _round_coordinate(lon)
    key = f"geocode:{rounded_lat}:{rounded_lon}"
    return key


class GeocodingService:
    """
    Async geocoding service with Redis caching and rate limiting.
    
    Usage:
        service = GeocodingService()
        await service.initialize()
        place = await service.reverse_geocode(46.9480, 7.4474)
        await service.close()
    """
    
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._http: Optional[httpx.AsyncClient] = None
        self._last_request_time: float = 0
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize Redis and HTTP connections."""
        redis_host = os.environ.get("REDIS_HOST", "localhost")
        redis_port = int(os.environ.get("REDIS_PORT", 6379))
        
        self._redis = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self._http = httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "TrainDash fitness app (personal use)"}
        )
    
    async def close(self):
        """Close connections."""
        if self._redis:
            await self._redis.close()
        if self._http:
            await self._http.aclose()
    
    async def _rate_limit(self):
        """Enforce rate limiting between requests."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request_time
            if elapsed < RATE_LIMIT_DELAY:
                await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)
            self._last_request_time = asyncio.get_event_loop().time()
    
    async def reverse_geocode(self, lat: float, lon: float, prefer_locality: bool = False) -> Optional[GeocodedPlace]:
        """
        Reverse geocode a coordinate to a place name.
        
        Returns the most relevant place (city/town/village) or None if not found.
        Uses Redis cache to avoid repeated API calls.
        
        Args:
            lat: Latitude
            lon: Longitude
            prefer_locality: If True, prefer specific locality names (for waypoints).
                           If False, prefer settlement names like city/village (for start/end).
        """
        if self._redis is None or self._http is None:
            await self.initialize()
        
        # Include prefer_locality in cache key
        cache_key = _cache_key(lat, lon) + (":loc" if prefer_locality else "")
        try:
            cached = await self._redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                if data is None:
                    return None
                return GeocodedPlace.from_dict(data)
        except Exception as e:
            logger.warning(f"Redis cache read error: {e}")
        
        # Rate limit before API call
        await self._rate_limit()
        
        # Call Photon API
        try:
            response = await self._http.get(
                PHOTON_URL,
                params={"lat": lat, "lon": lon, "limit": 1}
            )
            response.raise_for_status()
            data = response.json()
            
            place = self._parse_photon_response(data, prefer_locality=prefer_locality)
            
            # Cache the result (including None for negative caching)
            try:
                cache_value = json.dumps(place.to_dict() if place else None)
                await self._redis.setex(cache_key, CACHE_TTL_SECONDS, cache_value)
            except Exception as e:
                logger.warning(f"Redis cache write error: {e}")
            
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
            key = _cache_key(lat, lon)
            coord_to_key[(lat, lon)] = key
            if key not in unique_coords:
                unique_coords[key] = (lat, lon)
        
        # Fetch all unique coordinates
        results = {}
        for key, (lat, lon) in unique_coords.items():
            results[key] = await self.reverse_geocode(lat, lon, prefer_locality=prefer_locality)
        
        # Map back to original order
        return [results[coord_to_key[coord]] for coord in coordinates]


# Module-level singleton for convenience
_service: Optional[GeocodingService] = None


async def get_geocoding_service() -> GeocodingService:
    """Get or create the singleton geocoding service."""
    global _service
    if _service is None:
        _service = GeocodingService()
        await _service.initialize()
    return _service
