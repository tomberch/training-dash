"""
Activity title generator from GPS coordinates.

Analyzes GPS tracks to generate descriptive titles like:
- "Roundtrip Burgistein via Grosse Scheidegg, Interlaken"
- "Bern to Thun via Belp"

This module contains pure domain logic for title generation.
The GeocodingService dependency is injected by callers.
"""

import json
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from trainingdash.integrations.geocoding import GeocodingService

from trainingdash.integrations.geocoding import (
    GeocodedPlace,
    get_place_rank,
)

logger = logging.getLogger(__name__)

# Distance thresholds
ROUNDTRIP_THRESHOLD_M = 1000  # Start/end within 1km = roundtrip
WAYPOINT_MIN_SPACING_M = 5000  # Minimum 5km between waypoints
SAMPLE_INTERVAL_M = 200  # Sample route every 200m (was 500m) for better accuracy
PASS_MATCH_THRESHOLD_M = 200  # Match passes within 200m of route
PLACE_PROXIMITY_THRESHOLD_M = 500  # Only include places within 500m of actual route

# Maximum waypoints in title
MAX_WAYPOINTS = 3


@dataclass
class RoutePoint:
    """A point along the route with coordinates and distance from start."""

    lat: float
    lon: float
    altitude_m: float | None
    distance_m: float
    timestamp: datetime | None = None


@dataclass
class TitleWaypoint:
    """A waypoint for the title with name and distance from start."""

    name: str
    distance_m: float
    is_pass: bool = False  # True if mountain pass


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    R = 6371000  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def is_roundtrip(records: list[dict]) -> bool:
    """Check if route is a roundtrip (start/end within threshold)."""
    if len(records) < 2:
        return False

    # Find first and last records with valid GPS
    start = None
    end = None

    for r in records:
        if r.get("lat") is not None and r.get("lon") is not None:
            start = r
            break

    for r in reversed(records):
        if r.get("lat") is not None and r.get("lon") is not None:
            end = r
            break

    if start is None or end is None:
        return False

    distance = haversine_distance(start["lat"], start["lon"], end["lat"], end["lon"])

    return distance <= ROUNDTRIP_THRESHOLD_M


def sample_route(records: list[dict], interval_m: float = SAMPLE_INTERVAL_M) -> list[RoutePoint]:
    """
    Sample route at regular distance intervals.

    Returns a list of RoutePoint objects spaced approximately `interval_m` apart.
    Handles merged GPS tracks where distance_m may reset by also checking geographic distance.
    """
    points = []
    last_sample_distance = 0

    for r in records:
        lat = r.get("lat")
        lon = r.get("lon")
        if lat is None or lon is None:
            continue

        distance_m = r.get("distance_m", 0)

        # Sample at regular intervals based on distance_m field
        should_sample = False
        if not points:
            should_sample = True
        elif (distance_m - last_sample_distance) >= interval_m:
            # Normal case: distance increased by at least interval_m
            should_sample = True
        elif distance_m < last_sample_distance:
            # Distance reset (merged tracks) - check geographic distance instead
            geo_dist = haversine_distance(points[-1].lat, points[-1].lon, lat, lon)
            if geo_dist >= interval_m:
                should_sample = True

        if should_sample:
            points.append(
                RoutePoint(
                    lat=lat,
                    lon=lon,
                    altitude_m=r.get("altitude_m"),
                    distance_m=distance_m,
                    timestamp=r.get("timestamp"),
                )
            )
            last_sample_distance = distance_m

    # Always include last point if it's geographically different from the last sampled point
    for r in reversed(records):
        if r.get("lat") is not None and r.get("lon") is not None:
            last_point = RoutePoint(
                lat=r["lat"],
                lon=r["lon"],
                altitude_m=r.get("altitude_m"),
                distance_m=r.get("distance_m", 0),
                timestamp=r.get("timestamp"),
            )
            # Check if last point is geographically different from last sampled point
            if points:
                dist_from_last_sample = haversine_distance(
                    points[-1].lat, points[-1].lon, last_point.lat, last_point.lon
                )
                # Add if more than 100m away from last sampled point
                if dist_from_last_sample > 100:
                    points.append(last_point)
            else:
                points.append(last_point)
            break

    return points


def find_furthest_point(points: list[RoutePoint]) -> RoutePoint | None:
    """Find the point furthest from the start (for roundtrips)."""
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


def is_place_on_route(
    place: GeocodedPlace, points: list[RoutePoint], threshold_m: float = PLACE_PROXIMITY_THRESHOLD_M
) -> bool:
    """
    Check if a geocoded place is actually on the route.

    Returns True if any route point is within threshold_m of the place center.
    This filters out places that are returned by geocoding but weren't
    actually visited.
    """
    if place.lat is None or place.lon is None:
        # Can't verify, assume it's valid
        return True

    for point in points:
        dist = haversine_distance(point.lat, point.lon, place.lat, place.lon)
        if dist <= threshold_m:
            return True

    return False


def load_mountain_passes() -> list[dict]:
    """
    Load pre-extracted mountain passes from JSON file.

    Expected format: [{"name": "Grosse Scheidegg", "lat": 46.65, "lon": 8.10}, ...]
    """
    passes_file = Path(__file__).parent / "data" / "mountain_passes.json"
    if not passes_file.exists():
        logger.debug("Mountain passes file not found, skipping pass detection")
        return []

    try:
        with open(passes_file) as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Error loading mountain passes: {e}")
        return []


def find_passes_along_route(
    points: list[RoutePoint], passes: list[dict], threshold_m: float = PASS_MATCH_THRESHOLD_M
) -> list[TitleWaypoint]:
    """
    Find mountain passes that the route passes through.

    Returns waypoints for passes within threshold_m of any route point.
    """
    if not passes:
        return []

    found_passes = []

    for pass_info in passes:
        pass_lat = pass_info["lat"]
        pass_lon = pass_info["lon"]
        pass_name = pass_info["name"]

        for point in points:
            dist = haversine_distance(point.lat, point.lon, pass_lat, pass_lon)
            if dist <= threshold_m:
                found_passes.append(
                    TitleWaypoint(
                        name=pass_name,
                        distance_m=point.distance_m,
                        is_pass=True,
                    )
                )
                break  # Only add each pass once

    return found_passes


async def find_settlements_along_route(
    points: list[RoutePoint],
    geocoding: "GeocodingService",
    max_settlements: int = 5,
    min_spacing_m: float = WAYPOINT_MIN_SPACING_M,
) -> list[TitleWaypoint]:
    """
    Find significant settlements along the route via reverse geocoding.

    Returns waypoints for the most significant settlements, spaced apart.
    Only includes places that are actually on the route (within proximity threshold).
    """
    if len(points) < 3:
        return []

    # Skip first and last points (those are start/end)
    middle_points = points[1:-1]
    if not middle_points:
        return []

    # Sample evenly spaced points for geocoding
    step = max(1, len(middle_points) // 10)  # ~10 points max
    sample_points = middle_points[::step]

    # Geocode sampled points
    coords = [(p.lat, p.lon) for p in sample_points]
    places = await geocoding.reverse_geocode_batch(coords)

    # Build candidates with place info and distance
    candidates = []
    seen_names = set()

    for point, place in zip(sample_points, places):
        if place is None:
            continue
        if place.name in seen_names:
            continue

        # Filter to significant places
        rank = get_place_rank(place)
        if rank < 40:  # Skip hamlets and below
            continue

        # Check if place is actually on the route (proximity check)
        if not is_place_on_route(place, points):
            logger.debug(f"Skipping {place.name} - not on route (place at {place.lat}, {place.lon})")
            continue

        seen_names.add(place.name)
        candidates.append(
            (
                TitleWaypoint(name=place.name, distance_m=point.distance_m),
                rank,
            )
        )

    # Sort by rank (most important first)
    candidates.sort(key=lambda x: -x[1])

    # Select top candidates with minimum spacing
    selected = []
    for waypoint, rank in candidates:
        # Check spacing from already selected
        too_close = False
        for existing in selected:
            if abs(waypoint.distance_m - existing.distance_m) < min_spacing_m:
                too_close = True
                break

        if not too_close:
            selected.append(waypoint)
            if len(selected) >= max_settlements:
                break

    # Sort by distance (chronological order)
    selected.sort(key=lambda w: w.distance_m)

    return selected


def generate_title(
    start_name: str,
    end_name: str | None,
    waypoints: list[TitleWaypoint],
    is_roundtrip: bool,
    activity_date: datetime | None = None,
) -> str:
    """
    Generate activity title from components.

    Templates:
    - Roundtrip: "Roundtrip {start} via {waypoints}"
    - Point-to-point: "{start} to {end} via {waypoints}"
    - Fallback: "Activity on {date}"
    """
    # Fallback if no geocoding data
    if not start_name:
        if activity_date:
            return f"Activity on {activity_date.strftime('%d %b %Y')}"
        return "Activity"

    # Limit waypoints
    waypoints = waypoints[:MAX_WAYPOINTS]

    # Build via clause
    via_clause = ""
    if waypoints:
        waypoint_names = [w.name for w in waypoints]
        via_clause = f" via {', '.join(waypoint_names)}"

    if is_roundtrip:
        return f"Roundtrip {start_name}{via_clause}"
    else:
        if end_name and end_name != start_name:
            return f"{start_name} to {end_name}{via_clause}"
        else:
            return f"Roundtrip {start_name}{via_clause}"


async def generate_activity_title(
    records: list[dict],
    activity_date: datetime | None = None,
    geocoding: Optional["GeocodingService"] = None,
) -> str | None:
    """
    Generate a title for an activity from its GPS records.

    Args:
        records: List of record dicts with lat, lon, altitude_m, distance_m
        activity_date: Activity start date for fallback title
        geocoding: GeocodingService for reverse geocoding (optional - if not provided,
            geocoding will be skipped and a generic title returned)

    Returns:
        Generated title string, or None if insufficient data
    """
    # Check for sufficient GPS data
    gps_records = [r for r in records if r.get("lat") is not None and r.get("lon") is not None]
    if len(gps_records) < 2:
        logger.debug("Insufficient GPS data for title generation")
        return None

    # Sample route
    points = sample_route(records)
    if len(points) < 2:
        return None

    # Check if roundtrip
    roundtrip = is_roundtrip(records)

    # If no geocoding service, skip geocoding and return generic title
    if geocoding is None:
        if activity_date:
            return f"Activity on {activity_date.strftime('%d %b %Y')}"
        return "Activity"

    # Geocode start point
    start_point = points[0]
    start_place = await geocoding.reverse_geocode(start_point.lat, start_point.lon)
    start_name = start_place.name if start_place else None

    # Geocode end point (for point-to-point)
    end_name = None
    if not roundtrip:
        end_point = points[-1]
        end_place = await geocoding.reverse_geocode(end_point.lat, end_point.lon)
        end_name = end_place.name if end_place else None

    # Find waypoints
    waypoints = []

    # For roundtrips, add furthest point (if it's actually on route)
    if roundtrip:
        furthest = find_furthest_point(points)
        if furthest:
            furthest_place = await geocoding.reverse_geocode(furthest.lat, furthest.lon)
            if furthest_place and furthest_place.name != start_name:
                # Check if the place is actually near the furthest point
                if is_place_on_route(furthest_place, points):
                    waypoints.append(
                        TitleWaypoint(
                            name=furthest_place.name,
                            distance_m=furthest.distance_m,
                        )
                    )
                else:
                    logger.debug(f"Skipping furthest point {furthest_place.name} - not on route")

    # Find mountain passes
    passes = load_mountain_passes()
    pass_waypoints = find_passes_along_route(points, passes)
    waypoints.extend(pass_waypoints)

    # Find settlements
    settlements = await find_settlements_along_route(points, geocoding, max_settlements=3)

    # Filter out settlements that duplicate start/end/passes
    existing_names = {w.name for w in waypoints}
    if start_name:
        existing_names.add(start_name)
    if end_name:
        existing_names.add(end_name)

    for s in settlements:
        if s.name not in existing_names:
            waypoints.append(s)
            existing_names.add(s.name)

    # Sort by distance and limit
    waypoints.sort(key=lambda w: w.distance_m)
    waypoints = waypoints[:MAX_WAYPOINTS]

    # Generate title
    title = generate_title(
        start_name=start_name,
        end_name=end_name,
        waypoints=waypoints,
        is_roundtrip=roundtrip,
        activity_date=activity_date,
    )

    return title
