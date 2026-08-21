"""GPX and FIT course file parsing.

This module provides utilities for parsing course files (GPX and FIT)
to extract track data for race planning and pacing optimization.
"""

import math
from dataclasses import dataclass

import gpxpy
import gpxpy.gpx


@dataclass
class CoursePoint:
    """A single point on a course track."""

    latitude: float
    longitude: float
    elevation_m: float | None
    distance_m: float  # cumulative from start


@dataclass
class ParsedCourse:
    """Parsed course data from a GPX or FIT file."""

    name: str | None
    points: list[CoursePoint]
    total_distance_m: float
    has_elevation: bool


class GPXParseError(Exception):
    """Raised when GPX parsing fails."""

    pass


class FITParseError(Exception):
    """Raised when FIT course parsing fails."""

    pass


def _haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate distance between two GPS coordinates in meters.

    Uses the Haversine formula for great-circle distance.
    """
    R = 6371000  # Earth's radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def parse_gpx(gpx_content: str | bytes) -> ParsedCourse:
    """Parse GPX file content.

    Args:
        gpx_content: GPX file content as string or bytes.

    Returns:
        ParsedCourse with extracted track data.

    Raises:
        GPXParseError: If the GPX is malformed or contains no track points.

    Notes:
        - Handles GPX 1.0 and 1.1
        - Extracts track points with lat/lon/elevation
        - Calculates cumulative distance using Haversine
        - Handles missing elevation gracefully
        - If multiple tracks exist, uses only the first track
    """
    if isinstance(gpx_content, bytes):
        gpx_content = gpx_content.decode("utf-8")

    try:
        gpx = gpxpy.parse(gpx_content)
    except Exception as e:
        raise GPXParseError(f"Failed to parse GPX: {e}") from e

    if not gpx.tracks:
        raise GPXParseError("GPX file contains no tracks")

    # Use only the first track (multiple tracks may be non-contiguous)
    track = gpx.tracks[0]

    # Extract name from GPX metadata or track
    name = gpx.name or track.name

    # Collect all track points from all segments in the first track
    points: list[CoursePoint] = []
    cumulative_distance = 0.0
    has_elevation = False
    prev_lat: float | None = None
    prev_lon: float | None = None

    for segment in track.segments:
        for point in segment.points:
            # Calculate distance from previous point
            if prev_lat is not None and prev_lon is not None:
                segment_distance = _haversine_distance(
                    prev_lat, prev_lon, point.latitude, point.longitude
                )
                cumulative_distance += segment_distance

            elevation = point.elevation
            if elevation is not None:
                has_elevation = True

            points.append(
                CoursePoint(
                    latitude=point.latitude,
                    longitude=point.longitude,
                    elevation_m=elevation,
                    distance_m=cumulative_distance,
                )
            )

            prev_lat = point.latitude
            prev_lon = point.longitude

    if not points:
        raise GPXParseError("GPX file contains no track points")

    return ParsedCourse(
        name=name,
        points=points,
        total_distance_m=cumulative_distance,
        has_elevation=has_elevation,
    )


def parse_fit_course(fit_content: bytes) -> ParsedCourse:
    """Parse FIT file as a course.

    Args:
        fit_content: FIT file content as bytes.

    Returns:
        ParsedCourse with extracted course data.

    Raises:
        FITParseError: If the FIT file is invalid or not a course file.

    Notes:
        - Extracts course records from Garmin FIT files
        - Handles both course and activity FIT files
        - Calculates cumulative distance using Haversine if not provided
    """
    try:
        from garmin_fit_sdk import Decoder, Stream
    except ImportError as e:
        raise FITParseError("garmin-fit-sdk is required for FIT parsing") from e

    try:
        stream = Stream.from_byte_array(fit_content)
        decoder = Decoder(stream)
        messages, errors = decoder.read()
    except Exception as e:
        raise FITParseError(f"Failed to decode FIT file: {e}") from e

    if errors:
        raise FITParseError(f"FIT decoding errors: {errors}")

    # Extract course name from file_id or course messages
    name: str | None = None
    for msg in messages.get("course_mesgs", []):
        if "name" in msg:
            name = msg["name"]
            break

    # Try to get records from course_point_mesgs first (actual course files),
    # then fall back to record_mesgs (activity files used as courses)
    record_messages = messages.get("course_point_mesgs", [])
    if not record_messages:
        record_messages = messages.get("record_mesgs", [])

    points: list[CoursePoint] = []
    cumulative_distance = 0.0
    has_elevation = False
    prev_lat: float | None = None
    prev_lon: float | None = None

    for record in record_messages:
        # FIT coordinates are in semicircles, convert to degrees
        lat_semi = record.get("position_lat")
        lon_semi = record.get("position_long")

        if lat_semi is None or lon_semi is None:
            continue

        lat = lat_semi * (180.0 / 2**31)
        lon = lon_semi * (180.0 / 2**31)

        # Get elevation (altitude in FIT)
        elevation = record.get("altitude") or record.get("enhanced_altitude")
        if elevation is not None:
            has_elevation = True

        # Calculate distance - use provided distance if available, else Haversine
        if "distance" in record and record["distance"] is not None:
            cumulative_distance = record["distance"]
        elif prev_lat is not None and prev_lon is not None:
            segment_distance = _haversine_distance(prev_lat, prev_lon, lat, lon)
            cumulative_distance += segment_distance

        points.append(
            CoursePoint(
                latitude=lat,
                longitude=lon,
                elevation_m=elevation,
                distance_m=cumulative_distance,
            )
        )

        prev_lat = lat
        prev_lon = lon

    if not points:
        raise FITParseError("FIT file contains no course/record points")

    return ParsedCourse(
        name=name,
        points=points,
        total_distance_m=cumulative_distance,
        has_elevation=has_elevation,
    )
