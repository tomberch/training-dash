#!/usr/bin/env python3
"""
Compare Photon vs Nominatim for activity title generation.

Loads real activities from the database, runs the full title generation
algorithm with both geocoding providers, and compares the results.

Usage:
    cd backend
    .venv/bin/python scripts/compare_geocoders.py [--limit N]
"""

import argparse
import asyncio
import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Rate limiting: 1 request per second for both services
RATE_LIMIT_DELAY = 1.1

# Title generation constants (from title_generator.py)
ROUNDTRIP_THRESHOLD_M = 1000
SAMPLE_INTERVAL_M = 500
MAX_WAYPOINTS = 3


@dataclass
class GeoResult:
    """Result from a geocoding service."""
    name: str | None
    place_type: str | None
    raw: dict


@dataclass 
class RoutePoint:
    """A point along the route."""
    lat: float
    lon: float
    distance_m: float


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class GeocodingProvider:
    """Base class for geocoding providers."""
    
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.name = "base"
    
    async def reverse_geocode(self, lat: float, lon: float) -> GeoResult:
        raise NotImplementedError


class PhotonProvider(GeocodingProvider):
    """Photon (Komoot) geocoding provider."""
    
    def __init__(self, client: httpx.AsyncClient):
        super().__init__(client)
        self.name = "Photon"
    
    async def reverse_geocode(self, lat: float, lon: float) -> GeoResult:
        try:
            response = await self.client.get(
                "https://photon.komoot.io/reverse",
                params={"lat": lat, "lon": lon, "limit": 1},
                headers={"User-Agent": "TrainDash fitness app"},
            )
            response.raise_for_status()
            data = response.json()
            
            features = data.get("features", [])
            if not features:
                return GeoResult(name=None, place_type=None, raw={})
            
            props = features[0].get("properties", {})
            
            # Extract best name (priority: village > town > city)
            name = None
            place_type = None
            for ptype in ["village", "town", "city", "locality", "district"]:
                if ptype in props and props[ptype]:
                    name = props[ptype]
                    place_type = ptype
                    break
            
            if not name and "name" in props:
                name = props["name"]
                place_type = "name"
            
            return GeoResult(name=name, place_type=place_type, raw=props)
        except Exception as e:
            return GeoResult(name=f"ERROR: {e}", place_type=None, raw={})


class NominatimProvider(GeocodingProvider):
    """Nominatim (OSM) geocoding provider."""
    
    def __init__(self, client: httpx.AsyncClient):
        super().__init__(client)
        self.name = "Nominatim"
    
    async def reverse_geocode(self, lat: float, lon: float) -> GeoResult:
        try:
            response = await self.client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat,
                    "lon": lon,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "zoom": 14,
                },
                headers={
                    "User-Agent": "TrainDash fitness app (github.com/tomberch/training-dash)",
                    "Referer": "https://github.com/tomberch/training-dash",
                },
            )
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                return GeoResult(name=None, place_type=None, raw=data)
            
            address = data.get("address", {})
            
            # Extract best name - prefer larger recognizable places
            # Priority: city > town > village > municipality > suburb
            name = None
            place_type = None
            for ptype in ["city", "town", "village", "municipality", "suburb", "hamlet"]:
                if ptype in address and address[ptype]:
                    name = address[ptype]
                    place_type = ptype
                    break
            
            return GeoResult(name=name, place_type=place_type, raw=address)
        except Exception as e:
            return GeoResult(name=f"ERROR: {e}", place_type=None, raw={})


def sample_route(records: list[dict], interval_m: float = SAMPLE_INTERVAL_M) -> list[RoutePoint]:
    """Sample route at regular distance intervals."""
    points = []
    last_sample_distance = 0
    
    for r in records:
        lat = r.get("lat")
        lon = r.get("lon")
        if lat is None or lon is None:
            continue
        
        distance_m = r.get("distance_m", 0)
        
        if not points or (distance_m - last_sample_distance) >= interval_m:
            points.append(RoutePoint(lat=lat, lon=lon, distance_m=distance_m))
            last_sample_distance = distance_m
    
    # Always include last point
    for r in reversed(records):
        if r.get("lat") is not None and r.get("lon") is not None:
            last_point = RoutePoint(
                lat=r["lat"],
                lon=r["lon"],
                distance_m=r.get("distance_m", 0),
            )
            if not points or points[-1].distance_m < last_point.distance_m - 10:
                points.append(last_point)
            break
    
    return points


def is_roundtrip(points: list[RoutePoint]) -> bool:
    """Check if route is a roundtrip."""
    if len(points) < 2:
        return False
    start = points[0]
    end = points[-1]
    distance = haversine_distance(start.lat, start.lon, end.lat, end.lon)
    return distance <= ROUNDTRIP_THRESHOLD_M


def find_furthest_point(points: list[RoutePoint]) -> Optional[RoutePoint]:
    """Find the point furthest from the start."""
    if len(points) < 2:
        return None
    start = points[0]
    max_distance = 0
    furthest = None
    for p in points[1:]:
        dist = haversine_distance(start.lat, start.lon, p.lat, p.lon)
        if dist > max_distance:
            max_distance = dist
            furthest = p
    return furthest


async def generate_title_with_provider(
    provider: GeocodingProvider,
    points: list[RoutePoint],
    roundtrip: bool,
) -> tuple[str, list[str]]:
    """
    Generate activity title using a specific geocoding provider.
    
    Returns (title, list of geocoded names for debugging).
    """
    if len(points) < 2:
        return "Activity", []
    
    geocoded_names = []
    
    # Geocode start point
    start_result = await provider.reverse_geocode(points[0].lat, points[0].lon)
    await asyncio.sleep(RATE_LIMIT_DELAY)
    start_name = start_result.name
    geocoded_names.append(f"start: {start_name} [{start_result.place_type}]")
    
    # Geocode end point (for point-to-point)
    end_name = None
    if not roundtrip:
        end_result = await provider.reverse_geocode(points[-1].lat, points[-1].lon)
        await asyncio.sleep(RATE_LIMIT_DELAY)
        end_name = end_result.name
        geocoded_names.append(f"end: {end_name} [{end_result.place_type}]")
    
    # Find waypoints
    waypoints = []
    
    # For roundtrips, add furthest point
    if roundtrip:
        furthest = find_furthest_point(points)
        if furthest:
            furthest_result = await provider.reverse_geocode(furthest.lat, furthest.lon)
            await asyncio.sleep(RATE_LIMIT_DELAY)
            if furthest_result.name and furthest_result.name != start_name:
                waypoints.append(furthest_result.name)
                geocoded_names.append(f"furthest: {furthest_result.name} [{furthest_result.place_type}]")
    
    # Sample middle points for additional waypoints
    if len(points) > 4:
        middle_indices = [len(points) // 3, 2 * len(points) // 3]
        seen_names = {start_name, end_name} | set(waypoints)
        
        for idx in middle_indices:
            if len(waypoints) >= MAX_WAYPOINTS:
                break
            point = points[idx]
            result = await provider.reverse_geocode(point.lat, point.lon)
            await asyncio.sleep(RATE_LIMIT_DELAY)
            if result.name and result.name not in seen_names:
                waypoints.append(result.name)
                seen_names.add(result.name)
                geocoded_names.append(f"waypoint: {result.name} [{result.place_type}]")
    
    # Build title
    if not start_name:
        return "Activity", geocoded_names
    
    via_clause = ""
    if waypoints:
        via_clause = f" via {', '.join(waypoints[:MAX_WAYPOINTS])}"
    
    if roundtrip:
        title = f"Roundtrip {start_name}{via_clause}"
    else:
        if end_name and end_name != start_name:
            title = f"{start_name} to {end_name}{via_clause}"
        else:
            title = f"Roundtrip {start_name}{via_clause}"
    
    return title, geocoded_names


async def get_activity_records(db: AsyncSession, activity_id: int) -> list[dict]:
    """Get GPS records for an activity."""
    from trainingdash.repositories.postgres.models import Record
    
    result = await db.execute(
        select(Record)
        .where(Record.activity_id == activity_id)
        .order_by(Record.timestamp)
    )
    records = result.scalars().all()
    
    return [
        {"lat": r.lat, "lon": r.lon, "distance_m": r.distance_m}
        for r in records
        if r.lat is not None and r.lon is not None
    ]


async def get_activities(db: AsyncSession, limit: int) -> list:
    """Get recent activities with GPS data."""
    from trainingdash.repositories.postgres.models import Activity
    
    result = await db.execute(
        select(Activity)
        .where(Activity.total_distance_m > 5000)  # At least 5km
        .order_by(Activity.started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


async def compare_providers(limit: int = 5):
    """Compare title generation between Photon and Nominatim."""
    
    db_url = "postgresql+asyncpg://trainingdash:trainingdash@localhost:5432/trainingdash"
    engine = create_async_engine(db_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        activities = await get_activities(db, limit)
        
        if not activities:
            print("No activities found in database.")
            return
        
        print(f"\n{'='*90}")
        print("TITLE GENERATION COMPARISON: Photon vs Nominatim")
        print(f"{'='*90}")
        print(f"\nTesting {len(activities)} activities...\n")
        
        results = []
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            photon = PhotonProvider(client)
            nominatim = NominatimProvider(client)
            
            for activity in activities:
                print(f"\n{'─'*90}")
                print(f"Activity {activity.id}: {activity.started_at.strftime('%Y-%m-%d %H:%M')}")
                print(f"Distance: {activity.total_distance_m/1000:.1f} km | Current title: {activity.title or '(none)'}")
                print(f"{'─'*90}")
                
                # Get GPS records
                records = await get_activity_records(db, activity.id)
                if len(records) < 10:
                    print("  Insufficient GPS data, skipping...")
                    continue
                
                # Sample route
                points = sample_route(records)
                roundtrip = is_roundtrip(points)
                route_type = "Roundtrip" if roundtrip else "Point-to-point"
                print(f"  Route type: {route_type} | GPS points: {len(records)} | Sampled: {len(points)}")
                
                # Generate with Photon
                print(f"\n  Generating with Photon...")
                photon_title, photon_names = await generate_title_with_provider(photon, points, roundtrip)
                
                # Generate with Nominatim
                print(f"  Generating with Nominatim...")
                nominatim_title, nominatim_names = await generate_title_with_provider(nominatim, points, roundtrip)
                
                results.append({
                    "activity_id": activity.id,
                    "date": activity.started_at,
                    "distance_km": activity.total_distance_m / 1000,
                    "current_title": activity.title,
                    "photon_title": photon_title,
                    "nominatim_title": nominatim_title,
                    "match": photon_title == nominatim_title,
                })
                
                # Print results
                print(f"\n  PHOTON:    {photon_title}")
                for name in photon_names:
                    print(f"             └─ {name}")
                
                print(f"\n  NOMINATIM: {nominatim_title}")
                for name in nominatim_names:
                    print(f"             └─ {name}")
                
                match_indicator = "✓ SAME" if photon_title == nominatim_title else "≠ DIFFERENT"
                print(f"\n  Result: {match_indicator}")
        
        # Summary
        print(f"\n{'='*90}")
        print("SUMMARY")
        print(f"{'='*90}")
        
        matches = sum(1 for r in results if r["match"])
        print(f"\nActivities compared: {len(results)}")
        print(f"Same title:          {matches}/{len(results)} ({100*matches/len(results):.0f}%)" if results else "")
        print(f"Different title:     {len(results)-matches}/{len(results)}")
        
        print(f"\n{'─'*90}")
        print("COMPARISON TABLE")
        print(f"{'─'*90}")
        print(f"{'Date':<12} {'Distance':>8} {'Photon':<35} {'Nominatim':<35}")
        print(f"{'-'*12} {'-'*8} {'-'*35} {'-'*35}")
        for r in results:
            date = r["date"].strftime("%Y-%m-%d")
            dist = f"{r['distance_km']:.0f}km"
            p_title = r["photon_title"][:33] + ".." if len(r["photon_title"]) > 35 else r["photon_title"]
            n_title = r["nominatim_title"][:33] + ".." if len(r["nominatim_title"]) > 35 else r["nominatim_title"]
            print(f"{date:<12} {dist:>8} {p_title:<35} {n_title:<35}")
        
        print(f"\n{'='*90}")
        print("RECOMMENDATION")
        print(f"{'='*90}")
        print("""
Based on the comparison above, consider:

1. If titles are mostly the SAME: Either provider works. Stick with Photon
   (sports-focused, no strict usage policy).

2. If Photon produces BETTER titles (more recognizable place names):
   Keep Photon as primary provider.

3. If Nominatim produces BETTER titles (more accurate locations):
   Consider switching to Nominatim, but note the stricter usage policy.

4. If results are MIXED: Consider using Photon as primary with Nominatim
   as fallback when Photon returns unhelpful results.
""")
    
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Compare geocoding providers for title generation")
    parser.add_argument("--limit", "-l", type=int, default=5, help="Number of activities to test")
    args = parser.parse_args()
    
    asyncio.run(compare_providers(limit=args.limit))


if __name__ == "__main__":
    main()
