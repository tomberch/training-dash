"""Tests for the polyline encoding/decoding module."""

import pytest
from trainingdash.polyline import (
    encode_polyline,
    decode_polyline,
    simplify_coords,
    generate_map_polyline,
)


class TestEncodeDecodeRoundtrip:
    """Test encoding and decoding produces same coordinates."""

    def test_simple_coords(self):
        coords = [(47.3769, 8.5417), (47.3800, 8.5500), (47.3850, 8.5600)]
        encoded = encode_polyline(coords)
        decoded = decode_polyline(encoded)
        
        assert len(decoded) == len(coords)
        for (orig_lat, orig_lon), (dec_lat, dec_lon) in zip(coords, decoded):
            assert abs(orig_lat - dec_lat) < 0.00001
            assert abs(orig_lon - dec_lon) < 0.00001

    def test_empty_coords(self):
        assert encode_polyline([]) == ""
        assert decode_polyline("") == []

    def test_single_point(self):
        coords = [(47.3769, 8.5417)]
        encoded = encode_polyline(coords)
        decoded = decode_polyline(encoded)
        assert len(decoded) == 1
        assert abs(decoded[0][0] - coords[0][0]) < 0.00001
        assert abs(decoded[0][1] - coords[0][1]) < 0.00001

    def test_negative_coords(self):
        """Test coordinates in southern/western hemispheres."""
        coords = [(-33.8688, 151.2093), (-33.8700, 151.2100)]  # Sydney
        encoded = encode_polyline(coords)
        decoded = decode_polyline(encoded)
        
        for (orig_lat, orig_lon), (dec_lat, dec_lon) in zip(coords, decoded):
            assert abs(orig_lat - dec_lat) < 0.00001
            assert abs(orig_lon - dec_lon) < 0.00001


class TestSimplifyCoords:
    """Test GPS track simplification."""

    def test_straight_line_simplifies_to_endpoints(self):
        """A straight line should simplify to just start and end."""
        coords = [(47.0 + i * 0.001, 8.0 + i * 0.001) for i in range(100)]
        simplified = simplify_coords(coords, epsilon=0.0001)
        assert len(simplified) == 2
        assert simplified[0] == coords[0]
        assert simplified[-1] == coords[-1]

    def test_respects_max_points(self):
        """Should not exceed max_points."""
        # Create a zig-zag pattern that won't simplify easily
        coords = []
        for i in range(200):
            lat = 47.0 + (i % 2) * 0.01
            lon = 8.0 + i * 0.001
            coords.append((lat, lon))
        
        simplified = simplify_coords(coords, max_points=50)
        assert len(simplified) <= 50

    def test_preserves_shape(self):
        """Should preserve important shape features."""
        # L-shaped route
        coords = [
            (47.0, 8.0),
            (47.0, 8.1),  # Go east
            (47.0, 8.2),  # Continue east
            (47.1, 8.2),  # Turn north
            (47.2, 8.2),  # Continue north
        ]
        simplified = simplify_coords(coords, epsilon=0.001)
        # Should keep the corner point
        assert len(simplified) >= 3

    def test_short_track_unchanged(self):
        """Tracks with <= 2 points should be unchanged."""
        coords = [(47.0, 8.0), (47.1, 8.1)]
        simplified = simplify_coords(coords)
        assert simplified == coords


class TestGenerateMapPolyline:
    """Test the high-level polyline generation from records."""

    def test_generates_polyline_from_records(self):
        records = [
            {"lat": 47.0, "lon": 8.0},
            {"lat": 47.1, "lon": 8.1},
            {"lat": 47.2, "lon": 8.2},
        ]
        polyline = generate_map_polyline(records)
        assert polyline is not None
        assert len(polyline) > 0
        
        # Should decode back to valid coords
        decoded = decode_polyline(polyline)
        assert len(decoded) >= 2

    def test_handles_missing_gps(self):
        records = [
            {"lat": None, "lon": None},
            {"lat": None, "lon": 8.1},
            {"lat": 47.2, "lon": None},
        ]
        polyline = generate_map_polyline(records)
        assert polyline is None

    def test_handles_partial_gps(self):
        """Should work with records that have some missing GPS."""
        records = [
            {"lat": 47.0, "lon": 8.0},
            {"lat": None, "lon": None},  # Indoor segment
            {"lat": 47.1, "lon": 8.1},
        ]
        polyline = generate_map_polyline(records)
        assert polyline is not None

    def test_empty_records(self):
        assert generate_map_polyline([]) is None

    def test_single_point(self):
        """Need at least 2 points for a polyline."""
        records = [{"lat": 47.0, "lon": 8.0}]
        polyline = generate_map_polyline(records)
        assert polyline is None
