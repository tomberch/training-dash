"""
CreateCourseFromActivity use case — create a race course from an existing activity.

This allows users to use their own ride data as a course for race planning,
which is often more convenient than uploading a separate GPX/FIT file.
"""

import logging
import re
from dataclasses import dataclass
from uuid import UUID

import numpy as np
from geoalchemy2 import WKTElement

from trainingdash.domain.course_segmentation import detect_climbs, segment_course
from trainingdash.domain.elevation import smooth_elevation
from trainingdash.domain.grade import calculate_grade
from trainingdash.repositories.postgres.models import RaceCourse
from trainingdash.repositories.protocols import ActivityRepo, CourseRepo, RecordRepo

logger = logging.getLogger(__name__)


class CourseFromActivityError(Exception):
    """Raised when course creation from activity fails."""

    pass


@dataclass
class CreateCourseFromActivityResult:
    """Result of course creation from activity."""

    course: RaceCourse
    warnings: list[str]


class CreateCourseFromActivity:
    """
    Use case for creating a race course from an existing activity.

    This extracts GPS and elevation data from the activity's records
    and processes them into a course suitable for race planning.
    """

    def __init__(
        self,
        activity_repo: ActivityRepo,
        record_repo: RecordRepo,
        course_repo: CourseRepo,
    ) -> None:
        self._activity_repo = activity_repo
        self._record_repo = record_repo
        self._course_repo = course_repo

    async def execute(
        self,
        user_id: int,
        activity_id: str,
        name: str | None = None,
    ) -> CreateCourseFromActivityResult:
        """
        Create a race course from an existing activity.

        Args:
            user_id: User ID (for ownership validation)
            activity_id: UUID of the activity to create course from
            name: Optional course name (defaults to activity title)

        Returns:
            CreateCourseFromActivityResult with course and warnings

        Raises:
            CourseFromActivityError: If activity not found or has insufficient data
        """
        warnings: list[str] = []

        # Convert string activity_id to UUID
        activity_uuid = UUID(activity_id)

        # Step 1: Get activity
        activity = await self._activity_repo.get_by_id(activity_uuid, user_id)
        if activity is None:
            raise CourseFromActivityError(f"Activity {activity_id} not found")

        # Step 2: Get records
        records = await self._record_repo.list_for_activity(activity_uuid)
        if len(records) < 10:
            raise CourseFromActivityError("Activity has too few GPS points for a course. Need at least 10 points.")

        # Step 3: Extract coordinates and elevation
        points_with_gps = [r for r in records if r.lat is not None and r.lon is not None]

        if len(points_with_gps) < 10:
            raise CourseFromActivityError("Activity has insufficient GPS data for a course.")

        lats = [r.lat for r in points_with_gps]
        lons = [r.lon for r in points_with_gps]
        distances = np.array([r.distance_m for r in points_with_gps])

        # Handle elevation
        elevations = []
        has_elevation = False
        for r in points_with_gps:
            if r.altitude_m is not None:
                elevations.append(r.altitude_m)
                has_elevation = True
            else:
                elevations.append(0.0)

        elevations = np.array(elevations)

        if not has_elevation:
            warnings.append("Activity has no elevation data. Elevation set to 0m. Pacing accuracy will be limited.")

        # Step 4: Smooth elevation and calculate grades
        smoothed_elevations = smooth_elevation(elevations)
        grades = calculate_grade(distances, smoothed_elevations)

        # Step 5: Segment course and detect climbs
        segments = segment_course(distances, grades, smoothed_elevations)
        climbs = detect_climbs(segments)

        # Step 6: Calculate metrics
        elevation_gain, elevation_loss = self._calculate_elevation_metrics(smoothed_elevations)
        min_elevation = float(np.min(smoothed_elevations)) if len(smoothed_elevations) > 0 else None
        max_elevation = float(np.max(smoothed_elevations)) if len(smoothed_elevations) > 0 else None
        total_distance = float(distances[-1]) if len(distances) > 0 else 0.0

        # Step 7: Build elevation profile (with lat/lon for curvature)
        elevation_profile = self._build_elevation_profile(distances, smoothed_elevations, grades, lats, lons)

        # Step 8: Build PostGIS geometry
        geometry = self._build_geometry(lats, lons, smoothed_elevations)

        # Step 9: Determine course name
        course_name = name or activity.title or f"Course from {activity.started_at.strftime('%Y-%m-%d')}"

        # Step 10: Create and save course
        course = RaceCourse(
            user_id=user_id,
            name=course_name,
            source_type="activity",
            source_filename=None,
            distance_m=total_distance,
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

        # Security: sanitize course name for logging
        safe_name = re.sub(r"[\r\n\t\x00-\x1f\x7f-\x9f]", "", course_name)
        logger.info(
            "Created course '%s' from activity %s for user %d: %.1fkm, %.0fm gain",
            safe_name,
            activity_id,
            user_id,
            total_distance / 1000,
            elevation_gain,
        )

        return CreateCourseFromActivityResult(course=saved_course, warnings=warnings)

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
        lats: list[float],
        lons: list[float],
    ) -> list[dict]:
        """Build elevation profile for charting and pacing.

        Includes lat/lon for curvature-based speed calculations.
        """
        # Downsample to ~500 points for reasonable chart size
        n_points = len(distances)
        if n_points <= 500:
            indices = list(range(n_points))
        else:
            step = n_points // 500
            indices = list(range(0, n_points, step))

        return [
            {
                "distance_m": float(distances[i]),
                "elevation_m": float(elevations[i]),
                "grade_pct": float(grades[i]) if i < len(grades) else 0.0,
                "lat": lats[i] if i < len(lats) else None,
                "lon": lons[i] if i < len(lons) else None,
            }
            for i in indices
        ]

    def _build_geometry(
        self,
        lats: list[float],
        lons: list[float],
        elevations: np.ndarray,
    ) -> WKTElement:
        """Build PostGIS 3D LineString geometry."""
        coords = [f"{lon} {lat} {elev}" for lon, lat, elev in zip(lons, lats, elevations)]
        wkt = f"LINESTRING Z({', '.join(coords)})"
        return WKTElement(wkt, srid=4326)

    def _segments_to_dicts(self, segments: list) -> list[dict]:
        """Convert CourseSegment objects to dicts for JSONB storage."""
        return [
            {
                "start_m": s.start_distance_m,
                "end_m": s.end_distance_m,
                "distance_m": s.length_m,
                "avg_grade_pct": s.avg_grade_pct,
                "elevation_gain_m": s.elevation_gain_m,
                "elevation_loss_m": s.elevation_loss_m,
                "terrain_type": s.terrain_type,
            }
            for s in segments
        ]

    def _climbs_to_dicts(self, climbs: list) -> list[dict]:
        """Convert Climb objects to dicts for JSONB storage."""
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
