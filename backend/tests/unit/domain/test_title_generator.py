"""Unit tests for trainingdash.domain.title_generator pure functions."""

from datetime import datetime

import pytest

from trainingdash.domain.title_generator import (
    haversine_distance,
    is_roundtrip,
    sample_route,
    find_furthest_point,
    is_place_on_route,
    generate_title,
    RoutePoint,
    TitleWaypoint,
    ROUNDTRIP_THRESHOLD_M,
)
from trainingdash.integrations.geocoding import GeocodedPlace


class TestHaversineDistance:
    """Tests for haversine_distance function."""

    def test_same_point_returns_zero(self):
        """Distance from a point to itself is zero."""
        lat, lon = 46.9481, 7.4474  # Bern
        
        result = haversine_distance(lat, lon, lat, lon)
        
        assert result == 0.0

    def test_known_distance_bern_to_zurich(self):
        """Distance from Bern to Zurich is approximately 95km."""
        bern_lat, bern_lon = 46.9481, 7.4474
        zurich_lat, zurich_lon = 47.3769, 8.5417
        
        result = haversine_distance(bern_lat, bern_lon, zurich_lat, zurich_lon)
        
        # Actual distance is ~95km, allow 5% tolerance
        assert 90_000 < result < 100_000

    def test_short_distance_accuracy(self):
        """Short distances (< 1km) are reasonably accurate."""
        # Two points ~500m apart in Bern
        lat1, lon1 = 46.9481, 7.4474
        lat2, lon2 = 46.9526, 7.4474  # ~500m north
        
        result = haversine_distance(lat1, lon1, lat2, lon2)
        
        assert 450 < result < 550

    def test_symmetric(self):
        """Distance A to B equals distance B to A."""
        lat1, lon1 = 46.9481, 7.4474
        lat2, lon2 = 47.3769, 8.5417
        
        dist_ab = haversine_distance(lat1, lon1, lat2, lon2)
        dist_ba = haversine_distance(lat2, lon2, lat1, lon1)
        
        assert dist_ab == dist_ba


class TestIsRoundtrip:
    """Tests for is_roundtrip function."""

    def test_start_end_same_location_is_roundtrip(self):
        """Route starting and ending at same point is a roundtrip."""
        records = [
            {"lat": 46.9481, "lon": 7.4474},
            {"lat": 46.95, "lon": 7.45},
            {"lat": 46.9481, "lon": 7.4474},  # Back to start
        ]
        
        assert is_roundtrip(records) is True

    def test_start_end_within_threshold_is_roundtrip(self):
        """Route ending within ROUNDTRIP_THRESHOLD_M of start is a roundtrip."""
        records = [
            {"lat": 46.9481, "lon": 7.4474},
            {"lat": 46.95, "lon": 7.45},
            {"lat": 46.9485, "lon": 7.4478},  # ~50m from start
        ]
        
        assert is_roundtrip(records) is True

    def test_start_end_far_apart_is_not_roundtrip(self):
        """Route ending far from start is not a roundtrip."""
        records = [
            {"lat": 46.9481, "lon": 7.4474},  # Bern
            {"lat": 46.95, "lon": 7.50},
            {"lat": 47.3769, "lon": 8.5417},  # Zurich
        ]
        
        assert is_roundtrip(records) is False

    def test_single_record_not_roundtrip(self):
        """Single record cannot be a roundtrip."""
        records = [{"lat": 46.9481, "lon": 7.4474}]
        
        assert is_roundtrip(records) is False

    def test_empty_records_not_roundtrip(self):
        """Empty records list is not a roundtrip."""
        assert is_roundtrip([]) is False

    def test_skips_records_without_gps(self):
        """Records without GPS data are skipped."""
        records = [
            {"lat": None, "lon": None},  # No GPS
            {"lat": 46.9481, "lon": 7.4474},  # Actual start
            {"lat": 46.95, "lon": 7.45},
            {"lat": 46.9481, "lon": 7.4474},  # Actual end
            {"lat": None, "lon": None},  # No GPS
        ]
        
        assert is_roundtrip(records) is True


class TestSampleRoute:
    """Tests for sample_route function."""

    def test_samples_at_interval(self):
        """Route is sampled at approximately the specified interval."""
        records = [
            {"lat": 46.9481, "lon": 7.4474, "distance_m": 0},
            {"lat": 46.9490, "lon": 7.4474, "distance_m": 100},
            {"lat": 46.9500, "lon": 7.4474, "distance_m": 200},
            {"lat": 46.9510, "lon": 7.4474, "distance_m": 300},
            {"lat": 46.9520, "lon": 7.4474, "distance_m": 400},
            {"lat": 46.9530, "lon": 7.4474, "distance_m": 500},
        ]
        
        # With 200m interval, should get points at 0, 200, 400, and last
        points = sample_route(records, interval_m=200)
        
        assert len(points) >= 3
        assert points[0].distance_m == 0
        assert points[-1].distance_m == 500

    def test_always_includes_first_point(self):
        """First GPS point is always included."""
        records = [
            {"lat": 46.9481, "lon": 7.4474, "distance_m": 0},
            {"lat": 46.9530, "lon": 7.4474, "distance_m": 500},
        ]
        
        points = sample_route(records)
        
        assert points[0].lat == 46.9481
        assert points[0].distance_m == 0

    def test_always_includes_last_point(self):
        """Last GPS point is always included."""
        records = [
            {"lat": 46.9481, "lon": 7.4474, "distance_m": 0},
            {"lat": 46.9530, "lon": 7.4474, "distance_m": 500},
        ]
        
        points = sample_route(records)
        
        assert points[-1].distance_m == 500

    def test_skips_records_without_gps(self):
        """Records without GPS coordinates are skipped."""
        records = [
            {"lat": 46.9481, "lon": 7.4474, "distance_m": 0},
            {"lat": None, "lon": None, "distance_m": 100},
            {"lat": 46.9530, "lon": 7.4474, "distance_m": 500},
        ]
        
        points = sample_route(records)
        
        # Should only have 2 points (start and end)
        assert all(p.lat is not None for p in points)

    def test_returns_route_points(self):
        """Returns list of RoutePoint objects."""
        records = [
            {"lat": 46.9481, "lon": 7.4474, "distance_m": 0, "altitude_m": 540},
            {"lat": 46.9530, "lon": 7.4474, "distance_m": 500, "altitude_m": 550},
        ]
        
        points = sample_route(records)
        
        assert all(isinstance(p, RoutePoint) for p in points)
        assert points[0].altitude_m == 540


class TestFindFurthestPoint:
    """Tests for find_furthest_point function."""

    def test_finds_furthest_from_start(self):
        """Returns the point with maximum distance from start."""
        points = [
            RoutePoint(lat=46.9481, lon=7.4474, altitude_m=None, distance_m=0),
            RoutePoint(lat=46.95, lon=7.45, altitude_m=None, distance_m=500),
            RoutePoint(lat=47.00, lon=7.50, altitude_m=None, distance_m=1000),  # Furthest
            RoutePoint(lat=46.9481, lon=7.4474, altitude_m=None, distance_m=1500),  # Back to start
        ]
        
        furthest = find_furthest_point(points)
        
        assert furthest is not None
        assert furthest.lat == 47.00
        assert furthest.distance_m == 1000

    def test_single_point_returns_none(self):
        """Single point list returns None."""
        points = [RoutePoint(lat=46.9481, lon=7.4474, altitude_m=None, distance_m=0)]
        
        assert find_furthest_point(points) is None

    def test_empty_list_returns_none(self):
        """Empty list returns None."""
        assert find_furthest_point([]) is None


class TestIsPlaceOnRoute:
    """Tests for is_place_on_route function."""

    def test_place_on_route_returns_true(self):
        """Place within threshold of route point returns True."""
        place = GeocodedPlace(name="Bern", place_type="city", lat=46.9481, lon=7.4474)
        points = [
            RoutePoint(lat=46.9481, lon=7.4474, altitude_m=None, distance_m=0),
            RoutePoint(lat=46.95, lon=7.45, altitude_m=None, distance_m=500),
        ]
        
        assert is_place_on_route(place, points) is True

    def test_place_far_from_route_returns_false(self):
        """Place far from all route points returns False."""
        place = GeocodedPlace(name="Zurich", place_type="city", lat=47.3769, lon=8.5417)
        points = [
            RoutePoint(lat=46.9481, lon=7.4474, altitude_m=None, distance_m=0),
            RoutePoint(lat=46.95, lon=7.45, altitude_m=None, distance_m=500),
        ]
        
        assert is_place_on_route(place, points) is False

    def test_place_without_coords_returns_true(self):
        """Place without coordinates returns True (can't verify)."""
        place = GeocodedPlace(name="Unknown", place_type="unknown", lat=None, lon=None)
        points = [
            RoutePoint(lat=46.9481, lon=7.4474, altitude_m=None, distance_m=0),
        ]
        
        assert is_place_on_route(place, points) is True

    def test_custom_threshold(self):
        """Respects custom threshold parameter."""
        # Place ~200m from route point
        place = GeocodedPlace(name="Nearby", place_type="village", lat=46.9499, lon=7.4474)
        points = [
            RoutePoint(lat=46.9481, lon=7.4474, altitude_m=None, distance_m=0),
        ]
        
        # With 100m threshold, should be False
        assert is_place_on_route(place, points, threshold_m=100) is False
        
        # With 300m threshold, should be True
        assert is_place_on_route(place, points, threshold_m=300) is True


class TestGenerateTitle:
    """Tests for generate_title function."""

    def test_roundtrip_without_waypoints(self):
        """Roundtrip with no waypoints: 'Roundtrip {start}'."""
        title = generate_title(
            start_name="Bern",
            end_name=None,
            waypoints=[],
            is_roundtrip=True,
        )
        
        assert title == "Roundtrip Bern"

    def test_roundtrip_with_waypoints(self):
        """Roundtrip with waypoints: 'Roundtrip {start} via {waypoints}'."""
        waypoints = [
            TitleWaypoint(name="Thun", distance_m=20000),
            TitleWaypoint(name="Interlaken", distance_m=40000),
        ]
        
        title = generate_title(
            start_name="Bern",
            end_name=None,
            waypoints=waypoints,
            is_roundtrip=True,
        )
        
        assert title == "Roundtrip Bern via Thun, Interlaken"

    def test_point_to_point_without_waypoints(self):
        """Point-to-point with no waypoints: '{start} to {end}'."""
        title = generate_title(
            start_name="Bern",
            end_name="Zurich",
            waypoints=[],
            is_roundtrip=False,
        )
        
        assert title == "Bern to Zurich"

    def test_point_to_point_with_waypoints(self):
        """Point-to-point with waypoints: '{start} to {end} via {waypoints}'."""
        waypoints = [TitleWaypoint(name="Aarau", distance_m=50000)]
        
        title = generate_title(
            start_name="Bern",
            end_name="Zurich",
            waypoints=waypoints,
            is_roundtrip=False,
        )
        
        assert title == "Bern to Zurich via Aarau"

    def test_same_start_end_treated_as_roundtrip(self):
        """When start equals end (not roundtrip flag), treated as roundtrip."""
        title = generate_title(
            start_name="Bern",
            end_name="Bern",
            waypoints=[],
            is_roundtrip=False,
        )
        
        assert title == "Roundtrip Bern"

    def test_no_start_name_with_date_fallback(self):
        """No start name with date: 'Activity on {date}'."""
        activity_date = datetime(2024, 7, 15, 10, 30)
        
        title = generate_title(
            start_name="",
            end_name=None,
            waypoints=[],
            is_roundtrip=True,
            activity_date=activity_date,
        )
        
        assert title == "Activity on 15 Jul 2024"

    def test_no_start_name_no_date_fallback(self):
        """No start name and no date: 'Activity'."""
        title = generate_title(
            start_name="",
            end_name=None,
            waypoints=[],
            is_roundtrip=True,
            activity_date=None,
        )
        
        assert title == "Activity"

    def test_limits_waypoints_to_max(self):
        """Waypoints are limited to MAX_WAYPOINTS (3)."""
        waypoints = [
            TitleWaypoint(name="A", distance_m=10000),
            TitleWaypoint(name="B", distance_m=20000),
            TitleWaypoint(name="C", distance_m=30000),
            TitleWaypoint(name="D", distance_m=40000),
            TitleWaypoint(name="E", distance_m=50000),
        ]
        
        title = generate_title(
            start_name="Start",
            end_name=None,
            waypoints=waypoints,
            is_roundtrip=True,
        )
        
        # Should only include first 3 waypoints
        assert title == "Roundtrip Start via A, B, C"
        assert "D" not in title
        assert "E" not in title



# ============================================================================
# Tests for generate_activity_title (async, with mocked GeocodingService)
# ============================================================================

from unittest.mock import AsyncMock, MagicMock
from trainingdash.domain.title_generator import generate_activity_title


def _make_gps_route(
    start: tuple[float, float],
    end: tuple[float, float],
    waypoints: list[tuple[float, float]] | None = None,
    total_distance_m: float = 50000,
) -> list[dict]:
    """
    Generate a list of GPS records for testing.
    
    Creates a route from start to end via optional waypoints with
    evenly distributed distance_m values.
    """
    waypoints = waypoints or []
    all_points = [start] + waypoints + [end]
    
    records = []
    num_points = len(all_points)
    
    for i, (lat, lon) in enumerate(all_points):
        distance = (i / (num_points - 1)) * total_distance_m if num_points > 1 else 0
        records.append({
            "lat": lat,
            "lon": lon,
            "altitude_m": 500,
            "distance_m": distance,
        })
    
    return records


def _make_roundtrip_route(
    start: tuple[float, float],
    furthest: tuple[float, float],
    total_distance_m: float = 80000,
) -> list[dict]:
    """
    Generate a roundtrip GPS route (start → furthest → back to start).
    """
    records = []
    
    # Start
    records.append({"lat": start[0], "lon": start[1], "altitude_m": 500, "distance_m": 0})
    
    # Midpoint toward furthest
    mid_lat = (start[0] + furthest[0]) / 2
    mid_lon = (start[1] + furthest[1]) / 2
    records.append({"lat": mid_lat, "lon": mid_lon, "altitude_m": 600, "distance_m": total_distance_m * 0.25})
    
    # Furthest point
    records.append({"lat": furthest[0], "lon": furthest[1], "altitude_m": 700, "distance_m": total_distance_m * 0.5})
    
    # Return via slightly different path
    records.append({"lat": mid_lat + 0.01, "lon": mid_lon + 0.01, "altitude_m": 600, "distance_m": total_distance_m * 0.75})
    
    # Back to start (within ROUNDTRIP_THRESHOLD_M)
    records.append({"lat": start[0] + 0.001, "lon": start[1] + 0.001, "altitude_m": 500, "distance_m": total_distance_m})
    
    return records


class TestGenerateActivityTitle:
    """Tests for the async generate_activity_title orchestration function."""
    
    @pytest.mark.asyncio
    async def test_one_way_ride_start_to_end(self):
        """One-way ride produces 'Start to End' title."""
        # Bern to Zurich
        records = _make_gps_route(
            start=(46.9481, 7.4474),  # Bern
            end=(47.3769, 8.5417),    # Zurich
            total_distance_m=95000,
        )
        
        # Mock geocoding service
        geocoding = MagicMock()
        geocoding.reverse_geocode = AsyncMock(side_effect=[
            GeocodedPlace(name="Bern", place_type="city", lat=46.9481, lon=7.4474),
            GeocodedPlace(name="Zurich", place_type="city", lat=47.3769, lon=8.5417),
        ])
        geocoding.reverse_geocode_batch = AsyncMock(return_value=[])
        
        title = await generate_activity_title(records, geocoding=geocoding)
        
        assert title == "Bern to Zurich"
    
    @pytest.mark.asyncio
    async def test_roundtrip_produces_roundtrip_title(self):
        """Roundtrip produces 'Roundtrip Start' title."""
        # Roundtrip from Bern
        records = _make_roundtrip_route(
            start=(46.9481, 7.4474),  # Bern
            furthest=(46.68, 7.85),   # ~30km away
        )
        
        # Mock geocoding service
        geocoding = MagicMock()
        geocoding.reverse_geocode = AsyncMock(side_effect=[
            # Start point
            GeocodedPlace(name="Bern", place_type="city", lat=46.9481, lon=7.4474),
            # Furthest point - same name, should be excluded
            GeocodedPlace(name="Thun", place_type="town", lat=46.68, lon=7.85),
        ])
        geocoding.reverse_geocode_batch = AsyncMock(return_value=[])
        
        title = await generate_activity_title(records, geocoding=geocoding)
        
        assert title == "Roundtrip Bern via Thun"
    
    @pytest.mark.asyncio
    async def test_roundtrip_furthest_point_same_as_start_excluded(self):
        """Furthest point with same name as start is excluded from waypoints."""
        records = _make_roundtrip_route(
            start=(46.9481, 7.4474),
            furthest=(46.95, 7.45),  # Very close, same city
        )
        
        geocoding = MagicMock()
        geocoding.reverse_geocode = AsyncMock(side_effect=[
            GeocodedPlace(name="Bern", place_type="city", lat=46.9481, lon=7.4474),
            GeocodedPlace(name="Bern", place_type="city", lat=46.95, lon=7.45),  # Same name
        ])
        geocoding.reverse_geocode_batch = AsyncMock(return_value=[])
        
        title = await generate_activity_title(records, geocoding=geocoding)
        
        assert title == "Roundtrip Bern"
        assert "via" not in title
    
    @pytest.mark.asyncio
    async def test_furthest_point_not_on_route_excluded(self):
        """Furthest point geocoded to place NOT on route is excluded."""
        records = _make_roundtrip_route(
            start=(46.9481, 7.4474),
            furthest=(46.68, 7.85),
        )
        
        geocoding = MagicMock()
        geocoding.reverse_geocode = AsyncMock(side_effect=[
            GeocodedPlace(name="Bern", place_type="city", lat=46.9481, lon=7.4474),
            # Geocoding returns place far from the actual route points
            GeocodedPlace(name="Interlaken", place_type="town", lat=46.69, lon=7.86 + 0.1),  # 10km+ off route
        ])
        geocoding.reverse_geocode_batch = AsyncMock(return_value=[])
        
        title = await generate_activity_title(records, geocoding=geocoding)
        
        # Interlaken should be excluded because it's not on the route
        assert title == "Roundtrip Bern"
        assert "Interlaken" not in title
    
    @pytest.mark.asyncio
    async def test_settlements_along_route_included(self):
        """Settlements along the route are included as waypoints."""
        # Longer route with middle points
        records = _make_gps_route(
            start=(46.9481, 7.4474),  # Bern
            end=(47.3769, 8.5417),    # Zurich
            waypoints=[
                (47.05, 7.62),  # Burgdorf area
                (47.16, 7.79),  # Langenthal area
                (47.25, 8.05),  # Olten area
            ],
            total_distance_m=95000,
        )
        
        geocoding = MagicMock()
        geocoding.reverse_geocode = AsyncMock(side_effect=[
            GeocodedPlace(name="Bern", place_type="city", lat=46.9481, lon=7.4474),
            GeocodedPlace(name="Zurich", place_type="city", lat=47.3769, lon=8.5417),
        ])
        # Batch returns settlements along the route
        geocoding.reverse_geocode_batch = AsyncMock(return_value=[
            GeocodedPlace(name="Burgdorf", place_type="town", lat=47.05, lon=7.62),
            GeocodedPlace(name="Langenthal", place_type="town", lat=47.16, lon=7.79),
            GeocodedPlace(name="Olten", place_type="town", lat=47.25, lon=8.05),
        ])
        
        title = await generate_activity_title(records, geocoding=geocoding)
        
        assert "Bern to Zurich" in title
        # At least one waypoint should be included
        assert "via" in title
    
    @pytest.mark.asyncio
    async def test_settlements_deduped_against_start_end(self):
        """Settlements that match start/end names are excluded."""
        records = _make_gps_route(
            start=(46.9481, 7.4474),
            end=(47.3769, 8.5417),
            waypoints=[(47.16, 7.79)],
            total_distance_m=95000,
        )
        
        geocoding = MagicMock()
        geocoding.reverse_geocode = AsyncMock(side_effect=[
            GeocodedPlace(name="Bern", place_type="city", lat=46.9481, lon=7.4474),
            GeocodedPlace(name="Zurich", place_type="city", lat=47.3769, lon=8.5417),
        ])
        # Batch returns Bern again (should be deduped)
        geocoding.reverse_geocode_batch = AsyncMock(return_value=[
            GeocodedPlace(name="Bern", place_type="city", lat=47.16, lon=7.79),
        ])
        
        title = await generate_activity_title(records, geocoding=geocoding)
        
        # Should be "Bern to Zurich" without duplicate via
        assert title == "Bern to Zurich"
    
    @pytest.mark.asyncio
    async def test_insufficient_gps_data_returns_none(self):
        """Less than 2 GPS records returns None."""
        records = [{"lat": 46.9481, "lon": 7.4474, "altitude_m": 500, "distance_m": 0}]
        
        geocoding = MagicMock()
        
        title = await generate_activity_title(records, geocoding=geocoding)
        
        assert title is None
    
    @pytest.mark.asyncio
    async def test_no_gps_data_returns_none(self):
        """Records without GPS coordinates returns None."""
        records = [
            {"lat": None, "lon": None, "altitude_m": 500, "distance_m": 0},
            {"lat": None, "lon": None, "altitude_m": 510, "distance_m": 100},
        ]
        
        geocoding = MagicMock()
        
        title = await generate_activity_title(records, geocoding=geocoding)
        
        assert title is None
    
    @pytest.mark.asyncio
    async def test_no_geocoding_service_returns_fallback(self):
        """Without geocoding service, returns date-based fallback."""
        records = _make_gps_route(
            start=(46.9481, 7.4474),
            end=(47.3769, 8.5417),
        )
        activity_date = datetime(2024, 7, 15, 10, 30)
        
        title = await generate_activity_title(records, activity_date=activity_date, geocoding=None)
        
        assert title == "Activity on 15 Jul 2024"
    
    @pytest.mark.asyncio
    async def test_no_geocoding_no_date_returns_generic(self):
        """Without geocoding or date, returns 'Activity'."""
        records = _make_gps_route(
            start=(46.9481, 7.4474),
            end=(47.3769, 8.5417),
        )
        
        title = await generate_activity_title(records, geocoding=None)
        
        assert title == "Activity"
    
    @pytest.mark.asyncio
    async def test_geocoding_returns_none_uses_fallback(self):
        """When geocoding fails (returns None), uses fallback title."""
        records = _make_gps_route(
            start=(46.9481, 7.4474),
            end=(47.3769, 8.5417),
        )
        activity_date = datetime(2024, 7, 15)
        
        geocoding = MagicMock()
        geocoding.reverse_geocode = AsyncMock(return_value=None)
        geocoding.reverse_geocode_batch = AsyncMock(return_value=[])
        
        title = await generate_activity_title(records, activity_date=activity_date, geocoding=geocoding)
        
        assert title == "Activity on 15 Jul 2024"
