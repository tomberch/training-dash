"""Google polyline encoding/decoding and GPS simplification.

This module provides utilities for:
1. Simplifying GPS tracks using the Ramer-Douglas-Peucker algorithm
2. Encoding/decoding coordinates using Google's polyline algorithm

The polyline encoding is used for efficient storage and transfer of GPS
tracks for activity list thumbnails.
"""

from typing import Sequence
import math


def _perpendicular_distance(
    point: tuple[float, float],
    line_start: tuple[float, float],
    line_end: tuple[float, float],
) -> float:
    """Calculate perpendicular distance from point to line segment."""
    if line_start == line_end:
        return math.sqrt(
            (point[0] - line_start[0]) ** 2 + (point[1] - line_start[1]) ** 2
        )

    # Line segment length squared
    line_len_sq = (line_end[0] - line_start[0]) ** 2 + (line_end[1] - line_start[1]) ** 2

    # Parameter t for the projection of point onto the line
    t = max(
        0,
        min(
            1,
            (
                (point[0] - line_start[0]) * (line_end[0] - line_start[0])
                + (point[1] - line_start[1]) * (line_end[1] - line_start[1])
            )
            / line_len_sq,
        ),
    )

    # Projection point
    proj_x = line_start[0] + t * (line_end[0] - line_start[0])
    proj_y = line_start[1] + t * (line_end[1] - line_start[1])

    return math.sqrt((point[0] - proj_x) ** 2 + (point[1] - proj_y) ** 2)


def simplify_coords(
    coords: Sequence[tuple[float, float]],
    epsilon: float = 0.0001,
    max_points: int = 100,
) -> list[tuple[float, float]]:
    """Simplify a GPS track using the Ramer-Douglas-Peucker algorithm.

    Args:
        coords: List of (lat, lon) tuples
        epsilon: Distance threshold in degrees (~11m at equator for 0.0001)
        max_points: Maximum number of points to keep

    Returns:
        Simplified list of (lat, lon) tuples
    """
    if len(coords) <= 2:
        return list(coords)

    def rdp(points: list[tuple[float, float]], eps: float) -> list[tuple[float, float]]:
        """Recursive Douglas-Peucker implementation."""
        if len(points) <= 2:
            return points

        # Find the point with maximum distance from the line
        max_dist = 0.0
        max_idx = 0

        for i in range(1, len(points) - 1):
            dist = _perpendicular_distance(points[i], points[0], points[-1])
            if dist > max_dist:
                max_dist = dist
                max_idx = i

        # If max distance is greater than epsilon, recursively simplify
        if max_dist > eps:
            left = rdp(points[: max_idx + 1], eps)
            right = rdp(points[max_idx:], eps)
            # Combine, avoiding duplicate at max_idx
            return left[:-1] + right
        else:
            return [points[0], points[-1]]

    # Convert to list for slicing
    coords_list = list(coords)
    result = rdp(coords_list, epsilon)

    # If still too many points, increase epsilon and try again
    current_epsilon = epsilon
    attempts = 0
    while len(result) > max_points and attempts < 20:
        current_epsilon *= 2.0  # More aggressive increase
        result = rdp(coords_list, current_epsilon)
        attempts += 1

    # Last resort: uniform sampling if still too many
    if len(result) > max_points:
        step = len(result) // max_points + 1
        result = result[::step]
        # Ensure we keep the last point
        if result[-1] != coords_list[-1]:
            result[-1] = coords_list[-1]

    return result


def encode_polyline(coords: Sequence[tuple[float, float]], precision: int = 5) -> str:
    """Encode coordinates to Google polyline format.

    Args:
        coords: List of (lat, lon) tuples
        precision: Number of decimal places (5 = ~1m accuracy)

    Returns:
        Encoded polyline string
    """
    if not coords:
        return ""

    result = []
    prev_lat = 0
    prev_lon = 0
    factor = 10**precision

    for lat, lon in coords:
        lat_int = round(lat * factor)
        lon_int = round(lon * factor)

        # Encode delta from previous point
        d_lat = lat_int - prev_lat
        d_lon = lon_int - prev_lon

        prev_lat = lat_int
        prev_lon = lon_int

        for delta in (d_lat, d_lon):
            # Left-shift and invert if negative
            value = ~(delta << 1) if delta < 0 else (delta << 1)

            # Break into 5-bit chunks
            while value >= 0x20:
                result.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            result.append(chr(value + 63))

    return "".join(result)


def decode_polyline(encoded: str, precision: int = 5) -> list[tuple[float, float]]:
    """Decode Google polyline to coordinates.

    Args:
        encoded: Encoded polyline string
        precision: Number of decimal places used in encoding

    Returns:
        List of (lat, lon) tuples
    """
    if not encoded:
        return []

    coords = []
    index = 0
    lat = 0
    lon = 0
    factor = 10**precision

    while index < len(encoded):
        # Decode latitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        d_lat = ~(result >> 1) if result & 1 else (result >> 1)
        lat += d_lat

        # Decode longitude
        shift = 0
        result = 0
        while True:
            b = ord(encoded[index]) - 63
            index += 1
            result |= (b & 0x1F) << shift
            shift += 5
            if b < 0x20:
                break
        d_lon = ~(result >> 1) if result & 1 else (result >> 1)
        lon += d_lon

        coords.append((lat / factor, lon / factor))

    return coords


def generate_map_polyline(records: list[dict], max_points: int = 100) -> str | None:
    """Generate a simplified polyline from activity records.

    Args:
        records: List of record dicts with 'lat' and 'lon' keys
        max_points: Maximum number of points in the simplified polyline

    Returns:
        Encoded polyline string, or None if no GPS data
    """
    # Extract coordinates from records
    coords = [
        (r["lat"], r["lon"])
        for r in records
        if r.get("lat") is not None and r.get("lon") is not None
    ]

    if len(coords) < 2:
        return None

    # Simplify the track
    simplified = simplify_coords(coords, max_points=max_points)

    # Encode to polyline
    return encode_polyline(simplified)
