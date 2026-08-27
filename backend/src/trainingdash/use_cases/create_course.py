"""
CreateCourse use case — orchestrates course creation from GPX/FIT upload.

This use case handles the complete flow of creating a race course:
1. Detect file type (GPX or FIT) from extension/content
2. Parse file to extract points
3. Smooth elevation (Savitzky-Golay)
4. Calculate grades
5. Segment course
6. Detect climbs
7. Build PostGIS geometry
8. Save to database
"""

import logging
from dataclasses import dataclass

import numpy as np
from geoalchemy2 import WKTElement

from trainingdash.domain.course_segmentation import (
    Climb,
    CourseSegment,
    assign_segment_bearings,
    detect_climbs,
    segment_course,
)
from trainingdash.domain.elevation import smooth_elevation
from trainingdash.domain.gpx import (
    FITParseError,
    GPXParseError,
    ParsedCourse,
    parse_fit_course,
    parse_gpx,
)
from trainingdash.domain.grade import calculate_grade
from trainingdash.repositories.postgres.models import RaceCourse
from trainingdash.repositories.protocols import CourseRepo

logger = logging.getLogger(__name__)


class CourseCreationError(Exception):
    """Raised when course creation fails."""

    pass


@dataclass
class CreateCourseResult:
    """Result of course creation."""

    course: RaceCourse
    warnings: list[str]  # e.g., "Elevation data was missing, set to 0"


class CreateCourse:
    """
    Use case for creating a race course from an uploaded file.

    This use case coordinates:
    - File type detection and parsing
    - Elevation smoothing
    - Grade calculation
    - Course segmentation
    - Climb detection
    - Persistence

    Example usage:
        use_case = CreateCourse(course_repo)
        result = await use_case.execute(
            user_id=1,
            file_content=gpx_bytes,
            filename="race.gpx",
            name="My Race Course",
        )
    """

    def __init__(self, course_repo: CourseRepo) -> None:
        """
        Initialize the use case with dependencies.

        Args:
            course_repo: Repository for course persistence
        """
        self._course_repo = course_repo

    async def execute(
        self,
        user_id: int,
        file_content: bytes,
        filename: str,
        name: str | None = None,
    ) -> CreateCourseResult:
        """
        Create a race course from uploaded file.

        Pipeline:
        1. Detect file type (GPX or FIT) from extension/content
        2. Parse file to extract points
        3. If no elevation: set to 0 (DEM fetch is out of scope for MVP)
        4. Smooth elevation (Savitzky-Golay)
        5. Calculate grades
        6. Segment course
        7. Detect climbs
        8. Build PostGIS geometry
        9. Save to database

        Args:
            user_id: User ID to attribute the course to
            file_content: Raw file bytes (GPX or FIT)
            filename: Original filename (used for type detection)
            name: Optional course name (defaults to parsed name or filename)

        Returns:
            CreateCourseResult with course and any warnings

        Raises:
            CourseCreationError: If parsing fails or file is invalid
        """
        warnings: list[str] = []

        # Step 1: Detect file type and parse
        source_type = self._detect_file_type(filename, file_content)
        parsed = self._parse_file(file_content, source_type)

        # Step 2: Determine course name
        course_name = name or parsed.name or self._name_from_filename(filename)

        # Step 3: Handle missing elevation
        elevations = self._extract_elevations(parsed, warnings)

        # Step 4: Smooth elevation
        distances = np.array([p.distance_m for p in parsed.points])
        smoothed_elevations = smooth_elevation(elevations)

        # Step 5: Calculate grades
        grades = calculate_grade(distances, smoothed_elevations)

        # Step 6: Segment course
        segments = segment_course(distances, grades, smoothed_elevations)

        # Step 6b: Assign bearings to segments from GPS track
        gps_points = [(p.latitude, p.longitude, p.distance_m) for p in parsed.points]
        assign_segment_bearings(segments, gps_points)

        # Step 7: Detect climbs
        climbs = detect_climbs(segments)

        # Step 8: Calculate course metrics
        elevation_gain, elevation_loss = self._calculate_elevation_metrics(smoothed_elevations)
        min_elevation = float(np.min(smoothed_elevations)) if len(smoothed_elevations) > 0 else None
        max_elevation = float(np.max(smoothed_elevations)) if len(smoothed_elevations) > 0 else None

        # Step 9: Build elevation profile (for charting and pacing)
        elevation_profile = self._build_elevation_profile(distances, smoothed_elevations, grades, parsed.points)

        # Step 10: Build PostGIS geometry
        geometry = self._build_geometry(parsed.points, smoothed_elevations)

        # Step 11: Create and save course
        course = RaceCourse(
            user_id=user_id,
            name=course_name,
            source_type=source_type,
            source_filename=filename,
            distance_m=parsed.total_distance_m,
            elevation_gain_m=elevation_gain,
            elevation_loss_m=elevation_loss,
            min_elevation_m=min_elevation,
            max_elevation_m=max_elevation,
            geometry=geometry,
            elevation_profile=elevation_profile,
            segments=self._segments_to_dicts(segments),
            climbs=self._climbs_to_dicts(climbs),
        )

        saved_course = await self._course_repo.save(course)

        # Security: use %r (repr) to escape special characters and truncate to prevent log injection
        logger.info(
            "Created course %r for user %d: %.1fkm, %.0fm gain, %d segments, %d climbs",
            course_name[:100],
            user_id,
            parsed.total_distance_m / 1000,
            elevation_gain,
            len(segments),
            len(climbs),
        )

        return CreateCourseResult(course=saved_course, warnings=warnings)

    def _detect_file_type(self, filename: str, content: bytes) -> str:
        """Detect file type from filename extension or content."""
        filename_lower = filename.lower()

        if filename_lower.endswith(".gpx"):
            return "gpx"
        elif filename_lower.endswith(".fit"):
            return "fit"

        # Try to detect from content
        # FIT files start with a header size byte (usually 12 or 14)
        # followed by protocol/profile version
        if len(content) >= 12:
            # FIT magic bytes at offset 8-11 are ".FIT"
            if content[8:12] == b".FIT":
                return "fit"

        # GPX files are XML
        if content.strip().startswith(b"<?xml") or b"<gpx" in content[:500]:
            return "gpx"

        raise CourseCreationError(f"Cannot determine file type for '{filename}'. Supported formats: .gpx, .fit")

    def _parse_file(self, content: bytes, source_type: str) -> ParsedCourse:
        """Parse file content based on detected type."""
        try:
            if source_type == "gpx":
                return parse_gpx(content)
            elif source_type == "fit":
                return parse_fit_course(content)
            else:
                raise CourseCreationError(f"Unsupported file type: {source_type}")
        except GPXParseError as e:
            raise CourseCreationError(f"Failed to parse GPX file: {e}") from e
        except FITParseError as e:
            raise CourseCreationError(f"Failed to parse FIT file: {e}") from e

    def _name_from_filename(self, filename: str) -> str:
        """Extract course name from filename."""
        # Remove extension
        name = filename.rsplit(".", 1)[0]
        # Replace underscores/dashes with spaces
        name = name.replace("_", " ").replace("-", " ")
        # Title case
        return name.title()

    def _extract_elevations(self, parsed: ParsedCourse, warnings: list[str]) -> np.ndarray:
        """Extract elevations from parsed course, handling missing data."""
        elevations = []

        for point in parsed.points:
            if point.elevation_m is not None:
                elevations.append(point.elevation_m)
            else:
                elevations.append(0.0)

        if not parsed.has_elevation:
            warnings.append(
                "Course file has no elevation data. Elevation set to 0m. "
                "For accurate pacing, use a file with elevation data."
            )

        return np.array(elevations)

    def _calculate_elevation_metrics(self, elevations: np.ndarray) -> tuple[float, float]:
        """Calculate total elevation gain and loss."""
        if len(elevations) < 2:
            return 0.0, 0.0

        diffs = np.diff(elevations)
        gain = float(np.sum(diffs[diffs > 0]))
        loss = float(np.abs(np.sum(diffs[diffs < 0])))

        return gain, loss

    def _build_elevation_profile(
        self,
        distances: np.ndarray,
        elevations: np.ndarray,
        grades: np.ndarray,
        points: list,
    ) -> list[dict]:
        """Build elevation profile for charting and pacing.
        
        Includes lat/lon for curvature-based speed calculations.
        """
        profile = []

        for i in range(len(distances)):
            profile.append(
                {
                    "distance_m": float(distances[i]),
                    "elevation_m": float(elevations[i]),
                    "grade_pct": float(grades[i] * 100),
                    "lat": points[i].latitude if i < len(points) else None,
                    "lon": points[i].longitude if i < len(points) else None,
                }
            )

        return profile

    def _build_geometry(self, points: list, smoothed_elevations: np.ndarray) -> WKTElement:
        """Build PostGIS LineStringZ geometry from points."""
        if len(points) < 2:
            raise CourseCreationError("Course must have at least 2 points")

        coords = []
        for i, point in enumerate(points):
            elevation = float(smoothed_elevations[i]) if i < len(smoothed_elevations) else 0.0
            coords.append(f"{point.longitude} {point.latitude} {elevation}")

        wkt = f"LINESTRING Z({', '.join(coords)})"
        return WKTElement(wkt, srid=4326)

    def _segments_to_dicts(self, segments: list[CourseSegment]) -> list[dict]:
        """Convert CourseSegment dataclasses to dicts for JSONB storage."""
        return [
            {
                "start_m": s.start_distance_m,
                "end_m": s.end_distance_m,
                "distance_m": s.length_m,
                "avg_grade_pct": s.avg_grade_pct,
                "elevation_gain_m": s.elevation_gain_m,
                "elevation_loss_m": s.elevation_loss_m,
                "terrain_type": s.terrain_type,
                "bearing_deg": s.bearing_deg,
            }
            for s in segments
        ]

    def _climbs_to_dicts(self, climbs: list[Climb]) -> list[dict]:
        """Convert Climb dataclasses to dicts for JSONB storage."""
        return [
            {
                "name": c.name,
                "start_m": c.start_distance_m,
                "end_m": c.end_distance_m,
                "distance_m": c.length_m,
                "avg_grade_pct": c.avg_grade_pct,
                "elevation_gain_m": c.elevation_gain_m,
                "max_grade_pct": c.max_grade_pct,
                "category": c.category,
            }
            for c in climbs
        ]
