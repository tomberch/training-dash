# Reverse Geocoding APIs for Activity Titles

Research for generating activity titles like "Burgistein to Meiringen via Thun, Interlaken" from GPS coordinates.

## Use Case

- Reverse geocode multiple points per activity: start, end, and key waypoints
- Swiss/European locations (Bernese Oberland, Alps)
- Async Python backend (FastAPI + asyncio)
- Need to respect rate limits across many activities

---

## 1. Nominatim (OpenStreetMap)

### Overview
Nominatim is OSM's official geocoding service. Free to use with strict usage policy.

### Usage Policy (as of 2024)
- **Rate limit**: Maximum 1 request per second (absolute limit)
- **Bulk geocoding prohibited** on public instance
- **Requirements**:
  - Valid HTTP User-Agent identifying your application
  - Valid HTTP Referer or include email in User-Agent
  - No heavy automated queries; caching mandatory
- **API endpoint**: `https://nominatim.openstreetmap.org/reverse`

### Response Format
```json
{
  "place_id": 123456,
  "lat": "46.9481",
  "lon": "7.4474",
  "display_name": "Bern, Verwaltungskreis Bern-Mittelland, Verwaltungsregion Bern-Mittelland, Bern/Berne, Switzerland",
  "address": {
    "city": "Bern",
    "municipality": "Bern",
    "county": "Verwaltungskreis Bern-Mittelland",
    "state": "Bern/Berne",
    "country": "Switzerland",
    "country_code": "ch"
  }
}
```

### Quality for Swiss/European Locations
- **Excellent coverage** for Switzerland due to strong OSM community
- Village/town names accurate down to small settlements (Burgistein, Meiringen well mapped)
- Returns `village`, `town`, `city` fields appropriately based on settlement size

### Pros
- Completely free, no API key required
- High quality for Europe/Switzerland
- Returns structured address components

### Cons
- Strict 1 req/sec limit makes bulk processing slow
- Public instance not meant for production apps with heavy traffic
- Must self-host for production use

### Self-Hosting Option
Self-hosted Nominatim removes rate limits but requires:
- ~64GB RAM for full planet, ~4GB for Switzerland extract
- ~1TB SSD storage for full planet
- Significant setup complexity

---

## 2. Photon (Komoot)

### Overview
Photon is a free geocoding API powered by OSM data, hosted by Komoot. Specifically designed for outdoor/sports apps.

### Rate Limits
- **No published rate limit** but fair use expected
- More lenient than Nominatim for moderate traffic
- No API key required

### API Endpoint
```
https://photon.komoot.io/reverse?lat=46.9481&lon=7.4474&lang=en
```

### Response Format
```json
{
  "features": [{
    "geometry": {"coordinates": [7.4474, 46.9481], "type": "Point"},
    "properties": {
      "name": "Bern",
      "city": "Bern",
      "state": "Bern",
      "country": "Switzerland",
      "osm_type": "R",
      "osm_id": 1682248
    }
  }]
}
```

### Pros
- More lenient rate limits than Nominatim
- Designed for sports/outdoor apps (Komoot is a cycling/hiking company)
- Fast responses, good European coverage
- GeoJSON response format

### Cons
- No SLA or guarantees
- Less documentation than Nominatim
- Limited control over response detail level

**Recommendation**: Good choice for a cycling app given Komoot's focus.

---

## 3. OpenCage

### Free Tier
- **2,500 requests/day** (free tier)
- **1 request/second** rate limit
- Requires API key (free signup)

### API Example
```
https://api.opencagedata.com/geocode/v1/json?q=46.9481+7.4474&key=YOUR_KEY
```

### Response Format
```json
{
  "results": [{
    "components": {
      "city": "Bern",
      "state": "Bern",
      "country": "Switzerland",
      "country_code": "ch",
      "_type": "city"
    },
    "formatted": "Bern, Switzerland"
  }]
}
```

### Pros
- Combines multiple data sources (OSM + others)
- Well-documented API with good Python SDK
- Reasonable free tier for small apps
- Includes confidence scores

### Cons
- 2,500/day may be limiting if syncing many activities
- Need to upgrade for production ($50/month for 10k/day)

---

## 4. LocationIQ

### Free Tier
- **5,000 requests/day** (free tier)
- **2 requests/second** rate limit
- Requires API key

### API Example
```
https://us1.locationiq.com/v1/reverse?key=YOUR_KEY&lat=46.9481&lon=7.4474&format=json
```

### Response Format
Similar to Nominatim (same underlying OSM data):
```json
{
  "display_name": "Bern, Switzerland",
  "address": {
    "city": "Bern",
    "state": "Bern",
    "country": "Switzerland"
  }
}
```

### Pros
- More generous free tier than OpenCage
- Nominatim-compatible response format
- Faster rate limit (2/sec vs 1/sec)

### Cons
- May require paid plan for sustained use
- US-based servers may have higher latency for Swiss locations

---

## Comparison Table

| Provider    | Free Limit       | Rate Limit  | API Key | Best For                    |
|-------------|------------------|-------------|---------|------------------------------|
| Nominatim   | Unlimited*       | 1 req/sec   | No      | Occasional use, self-hosted  |
| Photon      | Fair use         | Lenient     | No      | Sports apps, cycling         |
| OpenCage    | 2,500/day        | 1 req/sec   | Yes     | Small apps, multi-source     |
| LocationIQ  | 5,000/day        | 2 req/sec   | Yes     | Moderate traffic             |

*Must follow usage policy strictly

---

## 5. Caching Strategies

Caching is **mandatory** for all providers and dramatically reduces API calls.

### Coordinate Rounding Strategy

Round coordinates to reduce cache key variations while maintaining useful precision:

```python
from decimal import Decimal, ROUND_DOWN

def round_coords(lat: float, lon: float, precision: int = 3) -> tuple[str, str]:
    """
    Round coordinates to N decimal places.
    
    Precision guide:
    - 3 decimals = ~111m accuracy (good for city/town lookup)
    - 2 decimals = ~1.1km accuracy (good for village lookup)
    - 1 decimal  = ~11km accuracy (too coarse)
    
    For activity titles, 2-3 decimals is ideal.
    """
    lat_rounded = str(Decimal(str(lat)).quantize(Decimal(10) ** -precision, rounding=ROUND_DOWN))
    lon_rounded = str(Decimal(str(lon)).quantize(Decimal(10) ** -precision, rounding=ROUND_DOWN))
    return lat_rounded, lon_rounded

def cache_key(lat: float, lon: float, precision: int = 2) -> str:
    """Generate cache key for geocoding result."""
    lat_r, lon_r = round_coords(lat, lon, precision)
    return f"geocode:{lat_r}:{lon_r}"
```

### Redis Caching Implementation

```python
import json
import redis.asyncio as redis
from datetime import timedelta

class GeocodingCache:
    """Redis-based geocoding cache with coordinate rounding."""
    
    TTL = timedelta(days=30)  # Location names rarely change
    PRECISION = 2  # ~1.1km grid
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    def _key(self, lat: float, lon: float) -> str:
        lat_r = round(lat, self.PRECISION)
        lon_r = round(lon, self.PRECISION)
        return f"geocode:v1:{lat_r}:{lon_r}"
    
    async def get(self, lat: float, lon: float) -> dict | None:
        """Get cached geocoding result."""
        key = self._key(lat, lon)
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set(self, lat: float, lon: float, result: dict) -> None:
        """Cache geocoding result."""
        key = self._key(lat, lon)
        await self.redis.setex(
            key,
            int(self.TTL.total_seconds()),
            json.dumps(result)
        )
    
    async def get_or_fetch(
        self, 
        lat: float, 
        lon: float, 
        fetch_fn: callable
    ) -> dict:
        """Get from cache or fetch and cache."""
        cached = await self.get(lat, lon)
        if cached:
            return cached
        
        result = await fetch_fn(lat, lon)
        await self.set(lat, lon, result)
        return result
```

### Database Caching Alternative

For persistence across Redis restarts, store in PostgreSQL:

```sql
CREATE TABLE geocode_cache (
    lat_rounded NUMERIC(6, 2) NOT NULL,
    lon_rounded NUMERIC(7, 2) NOT NULL,
    place_name VARCHAR(255),
    city VARCHAR(100),
    region VARCHAR(100),
    country VARCHAR(100),
    raw_response JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (lat_rounded, lon_rounded)
);

CREATE INDEX idx_geocode_cache_created ON geocode_cache(created_at);
```

---

## 6. Rate-Limited Request Queue (Async Python)

### Using asyncio.Semaphore + Token Bucket

```python
import asyncio
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

import httpx

T = TypeVar('T')

class RateLimiter:
    """Token bucket rate limiter for geocoding APIs."""
    
    def __init__(self, requests_per_second: float = 1.0):
        self.rate = requests_per_second
        self.tokens = 1.0
        self.last_update = time.monotonic()
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Wait until a request token is available."""
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(1.0, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0.0
            else:
                self.tokens -= 1.0


class GeocodingService:
    """Async geocoding service with rate limiting and caching."""
    
    USER_AGENT = "TrainingDash/1.0 (cycling activity tracker; contact@example.com)"
    
    def __init__(
        self, 
        cache: GeocodingCache,
        provider: str = "photon"  # "nominatim", "photon", "opencage", "locationiq"
    ):
        self.cache = cache
        self.provider = provider
        self.rate_limiter = RateLimiter(
            requests_per_second=1.0 if provider == "nominatim" else 2.0
        )
        self.client = httpx.AsyncClient(
            headers={"User-Agent": self.USER_AGENT},
            timeout=10.0
        )
    
    async def _fetch_nominatim(self, lat: float, lon: float) -> dict:
        """Fetch from Nominatim API."""
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "jsonv2",
            "zoom": 10,  # City/town level
            "addressdetails": 1
        }
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
    
    async def _fetch_photon(self, lat: float, lon: float) -> dict:
        """Fetch from Photon API."""
        url = "https://photon.komoot.io/reverse"
        params = {"lat": lat, "lon": lon, "lang": "en"}
        resp = await self.client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        
        # Normalize to common format
        if data.get("features"):
            props = data["features"][0]["properties"]
            return {
                "name": props.get("name"),
                "city": props.get("city") or props.get("town") or props.get("village"),
                "state": props.get("state"),
                "country": props.get("country")
            }
        return {}
    
    async def _fetch(self, lat: float, lon: float) -> dict:
        """Fetch from configured provider with rate limiting."""
        await self.rate_limiter.acquire()
        
        if self.provider == "nominatim":
            return await self._fetch_nominatim(lat, lon)
        elif self.provider == "photon":
            return await self._fetch_photon(lat, lon)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    async def reverse_geocode(self, lat: float, lon: float) -> dict:
        """
        Reverse geocode coordinates with caching.
        Returns dict with 'city', 'state', 'country' keys.
        """
        return await self.cache.get_or_fetch(lat, lon, self._fetch)
    
    async def batch_reverse_geocode(
        self, 
        coordinates: list[tuple[float, float]]
    ) -> list[dict]:
        """
        Batch geocode multiple coordinates.
        Uses cache where possible, rate-limits API calls.
        """
        results = []
        
        for lat, lon in coordinates:
            # Check cache first (no rate limit needed)
            cached = await self.cache.get(lat, lon)
            if cached:
                results.append(cached)
            else:
                # Rate-limited API call
                result = await self.reverse_geocode(lat, lon)
                results.append(result)
        
        return results


def extract_place_name(geocode_result: dict, provider: str = "photon") -> str:
    """Extract a clean place name from geocoding result."""
    if provider == "photon":
        return (
            geocode_result.get("city") or 
            geocode_result.get("name") or 
            "Unknown"
        )
    elif provider == "nominatim":
        addr = geocode_result.get("address", {})
        return (
            addr.get("city") or 
            addr.get("town") or 
            addr.get("village") or 
            addr.get("municipality") or
            "Unknown"
        )
    return "Unknown"
```

### Using arq for Background Job Queue

Since the project uses arq, integrate geocoding with the job worker:

```python
# In worker.py or similar
from arq import cron
from arq.connections import RedisSettings

async def geocode_activity_title(
    ctx: dict,
    activity_id: int,
    start_coords: tuple[float, float],
    end_coords: tuple[float, float],
    via_coords: list[tuple[float, float]] | None = None
) -> str:
    """
    Generate activity title from coordinates.
    Called as background job to respect rate limits.
    """
    geocoding = ctx["geocoding_service"]
    
    # Geocode start and end
    start = await geocoding.reverse_geocode(*start_coords)
    end = await geocoding.reverse_geocode(*end_coords)
    
    start_name = extract_place_name(start)
    end_name = extract_place_name(end)
    
    # Build title
    if start_name == end_name:
        title = f"Loop from {start_name}"
    else:
        title = f"{start_name} to {end_name}"
    
    # Add via points if provided
    if via_coords:
        via_results = await geocoding.batch_reverse_geocode(via_coords)
        via_names = [extract_place_name(r) for r in via_results]
        # Remove duplicates while preserving order
        seen = {start_name, end_name}
        unique_via = []
        for name in via_names:
            if name not in seen:
                seen.add(name)
                unique_via.append(name)
        
        if unique_via:
            title += f" via {', '.join(unique_via)}"
    
    return title


class WorkerSettings:
    redis_settings = RedisSettings()
    
    functions = [geocode_activity_title]
    
    @staticmethod
    async def on_startup(ctx: dict):
        import redis.asyncio as redis
        ctx["redis"] = await redis.from_url("redis://localhost")
        ctx["geocoding_service"] = GeocodingService(
            cache=GeocodingCache(ctx["redis"]),
            provider="photon"
        )
    
    @staticmethod
    async def on_shutdown(ctx: dict):
        await ctx["redis"].close()
```

### Deduplication During Batch Sync

When syncing many activities, deduplicate coordinates first:

```python
async def geocode_batch_activities(
    activities: list[Activity],
    geocoding: GeocodingService
) -> dict[int, str]:
    """
    Efficiently geocode multiple activities.
    Returns {activity_id: title} mapping.
    """
    # Collect all unique coordinate pairs (rounded)
    coord_set: set[tuple[float, float]] = set()
    activity_coords: dict[int, dict] = {}
    
    for activity in activities:
        start = (round(activity.start_lat, 2), round(activity.start_lon, 2))
        end = (round(activity.end_lat, 2), round(activity.end_lon, 2))
        coord_set.add(start)
        coord_set.add(end)
        activity_coords[activity.id] = {"start": start, "end": end}
    
    # Pre-fetch all unique coordinates
    for coords in coord_set:
        await geocoding.reverse_geocode(*coords)  # This populates cache
    
    # Now generate titles (all cache hits)
    titles = {}
    for activity_id, coords in activity_coords.items():
        start_result = await geocoding.cache.get(*coords["start"])
        end_result = await geocoding.cache.get(*coords["end"])
        
        start_name = extract_place_name(start_result)
        end_name = extract_place_name(end_result)
        
        if start_name == end_name:
            titles[activity_id] = f"Loop from {start_name}"
        else:
            titles[activity_id] = f"{start_name} to {end_name}"
    
    return titles
```

---

## 7. Recommendations

### Primary Choice: Photon

For TrainingDash, **Photon** is recommended:

1. **Sports-focused**: Komoot (host) is a cycling/hiking company, so coverage priorities align
2. **Lenient limits**: More forgiving than Nominatim for a self-hosted app
3. **No API key**: Simpler setup
4. **Good Swiss coverage**: Strong OSM data for Swiss Alps

### Fallback: LocationIQ

If Photon reliability becomes an issue, **LocationIQ** is a solid backup:
- 5,000 free requests/day is generous
- Nominatim-compatible responses
- Easy to swap in

### Implementation Priority

1. **Implement caching first** - Redis with 2-decimal rounding
2. **Start with Photon** - Test with Swiss coordinates
3. **Add rate limiter** - 1 req/sec to be safe
4. **Queue via arq** - Geocode in background during activity sync
5. **Monitor usage** - Track cache hit rate, API errors

### Cache Effectiveness

For a typical cycling app:
- Most rides start/end near home (high cache hits)
- 2-decimal rounding (~1km grid) is sufficient for city/town names
- 30-day TTL is appropriate (place names don't change)
- Expected cache hit rate: >80% after initial seeding

---

## 8. Example Integration

```python
# In activity sync job
async def on_activity_synced(activity: Activity, ctx: dict):
    """Called after a new activity is saved."""
    redis = ctx["redis"]
    
    # Queue title generation (rate-limited)
    await redis.enqueue_job(
        "geocode_activity_title",
        activity.id,
        (activity.start_lat, activity.start_lon),
        (activity.end_lat, activity.end_lon),
        # Optional: extract via points from records
        _queue_name="geocoding"
    )
```

---

## References

- [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/)
- [Photon API](https://photon.komoot.io/)
- [OpenCage API Docs](https://opencagedata.com/api)
- [LocationIQ Docs](https://locationiq.com/docs)
- [OSM Switzerland Quality](https://wiki.openstreetmap.org/wiki/Switzerland)
