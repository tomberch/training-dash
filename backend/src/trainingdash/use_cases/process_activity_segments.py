"""
ProcessActivitySegments use case — match activities to segments and detect climbs.

This use case handles segment processing for an activity:
1. Load activity with GPS records
2. Find candidate segments (SQL: bounds intersect + direction ±60°)
3. Run precise matching (Python: 25m tolerance, 90% overlap)
4. Create SegmentEffort for each match, update PRs
5. Detect climbs and create suggestions for repeat rides

The use case can be called by the activity pipeline or background workers.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from geoalchemy2 import WKTElement
from geoalchemy2.functions import ST_MakeEnvelope
from geoalchemy2.shape import to_shape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.climb_detection import DetectedClimb, detect_climbs
from trainingdash.domain.polyline import encode_polyline
from trainingdash.domain.segment_geometry import (
    compute_bearing,
    compute_bounds,
    compute_segment_geometry,
)
from trainingdash.domain.segment_matching import (
    SegmentCandidate,
    SegmentMatch,
    compute_path_overlap,
    match_activity_to_segments,
)
from trainingdash.repositories.postgres.models import (
    Activity,
    Record,
    Segment,
    SegmentEffort,
    SegmentSuggestion,
)
from trainingdash.repositories.protocols import (
    SegmentEffortRepo,
    SegmentRepo,
    SegmentSuggestionRepo,
)

if TYPE_CHECKING:
    from geoalchemy2.elements import WKBElement

logger = logging.getLogger(__name__)

# Constants
SUGGESTION_EXPIRY_DAYS = 90
SKIP_DETECTION_OVERLAP_PCT = 80


@dataclass
class ProcessResult:
    """Result of processing an activity for segments.

    Attributes:
        matched_efforts: Number of segment efforts created
        detected_climbs: Number of climbs detected
        new_prs: Number of new personal records set
    """

    matched_efforts: int
    detected_climbs: int
    new_prs: int


class ProcessActivitySegments:
    """
    Use case for matching activity against segments and detecting climbs.

    This use case coordinates:
    - Loading activity and GPS records
    - Finding candidate segments via spatial query
    - Running precise matching algorithm
    - Creating segment efforts with PR tracking
    - Detecting climbs and creating suggestions

    Example usage:
        use_case = ProcessActivitySegments(
            db, segment_repo, effort_repo, suggestion_repo
        )
        result = await use_case.execute(activity_id, user_id)
    """

    def __init__(
        self,
        db: AsyncSession,
        segment_repo: SegmentRepo,
        effort_repo: SegmentEffortRepo,
        suggestion_repo: SegmentSuggestionRepo,
    ) -> None:
        """
        Initialize the use case with dependencies.

        Args:
            db: Database session for loading activity data
            segment_repo: Repository for segment operations
            effort_repo: Repository for effort operations
            suggestion_repo: Repository for suggestion operations
        """
        self._db = db
        self._segment_repo = segment_repo
        self._effort_repo = effort_repo
        self._suggestion_repo = suggestion_repo

    async def execute(self, activity_id: UUID, user_id: int) -> ProcessResult:
        """
        Match activity against segments and detect new climbs.

        Pipeline:
        1. Load activity with GPS records
        2. Find candidate segments (SQL: bounds intersect + direction ±60°)
        3. Run precise matching (Python: 25m tolerance, 90% overlap)
        4. Create SegmentEffort for each match, update PRs
        5. If no match has >80% overlap with a potential climb zone:
           a. Run climb detection
           b. For each detected climb, check duplicate
           c. Create Segment (status=suggested) if not duplicate
           d. Create/update SegmentSuggestion for user

        Args:
            activity_id: UUID of the activity to process
            user_id: User ID who owns the activity

        Returns:
            ProcessResult with counts of matched efforts, detected climbs, new PRs
        """
        # Step 1: Load activity with records
        activity, activity_records = await self._load_activity_with_records(activity_id, user_id)
        if activity is None:
            logger.warning(f"Activity {activity_id} not found for user {user_id}")
            return ProcessResult(matched_efforts=0, detected_climbs=0, new_prs=0)

        records = self._prepare_records(activity_records)
        if len(records) < 2:
            logger.debug(f"Activity {activity_id} has insufficient records for segment matching")
            return ProcessResult(matched_efforts=0, detected_climbs=0, new_prs=0)

        # Step 2: Find candidate segments
        candidates = await self._find_candidates(records)
        logger.debug(f"Found {len(candidates)} candidate segments for activity {activity_id}")

        # Step 3: Run precise matching
        matches = match_activity_to_segments(records, candidates)
        logger.debug(f"Matched {len(matches)} segments for activity {activity_id}")

        # Step 4: Create efforts
        new_prs = 0
        for match in matches:
            effort, is_pr = await self._create_effort_with_pr_check(
                match=match,
                activity=activity,
                user_id=user_id,
                records=records,
            )
            if is_pr:
                new_prs += 1

        # Step 5: Detect climbs and create suggestions
        detected_climbs = await self._process_climb_detection(
            activity=activity,
            user_id=user_id,
            records=records,
            matches=matches,
        )

        return ProcessResult(
            matched_efforts=len(matches),
            detected_climbs=detected_climbs,
            new_prs=new_prs,
        )

    async def _load_activity_with_records(
        self, activity_id: UUID, user_id: int
    ) -> tuple[Activity | None, list[Record]]:
        """Load activity and its GPS records."""
        # Load activity
        result = await self._db.execute(select(Activity).where(Activity.id == activity_id, Activity.user_id == user_id))
        activity = result.scalar_one_or_none()
        if activity is None:
            return None, []

        # Load records
        records_result = await self._db.execute(
            select(Record).where(Record.activity_id == activity_id).order_by(Record.timestamp)
        )
        records = list(records_result.scalars().all())

        return activity, records

    def _prepare_records(self, activity_records: list[Record]) -> list[dict]:
        """Convert activity records to dicts for domain functions."""
        records = []
        for r in activity_records:  # Already sorted by timestamp from query
            if r.lat is not None and r.lon is not None:
                records.append(
                    {
                        "lat": r.lat,
                        "lon": r.lon,
                        "altitude_m": r.altitude_m,
                        "distance_m": r.distance_m or 0.0,
                        "timestamp": r.timestamp,
                        "power_w": r.power_w,
                        "hr_bpm": r.hr_bpm,
                    }
                )
        return records

    async def _find_candidates(self, records: list[dict]) -> list[SegmentCandidate]:
        """Find candidate segments that might match the activity."""
        if len(records) < 2:
            return []

        # Compute activity bounds and bearing
        coords = [(r["lat"], r["lon"]) for r in records]
        min_lat, min_lon, max_lat, max_lon = compute_bounds(coords)
        bearing = compute_bearing(
            records[0]["lat"],
            records[0]["lon"],
            records[-1]["lat"],
            records[-1]["lon"],
        )

        # Query candidates via repository
        # The repo handles PostGIS spatial query
        bounds_geom = ST_MakeEnvelope(
            min_lon,
            min_lat,  # SW corner
            max_lon,
            max_lat,  # NE corner
            4326,
        )

        segments = await self._segment_repo.find_candidates_for_matching(
            bounds=bounds_geom,
            direction_bearing=bearing,
        )

        # Convert to SegmentCandidate objects
        candidates = []
        for seg in segments:
            # Extract start/end points from PostGIS geometry
            # The segment model stores these as POINT geometries
            start_lat, start_lon = self._extract_point(seg.start_point)
            end_lat, end_lon = self._extract_point(seg.end_point)

            candidates.append(
                SegmentCandidate(
                    id=seg.id,
                    polyline=seg.polyline,
                    start_lat=start_lat,
                    start_lon=start_lon,
                    end_lat=end_lat,
                    end_lon=end_lon,
                    direction_bearing=seg.direction_bearing or 0.0,
                    distance_m=seg.distance_m,
                )
            )

        return candidates

    def _extract_point(self, point_geom: "WKBElement") -> tuple[float, float]:
        """Extract lat/lon from a PostGIS POINT geometry."""
        shape = to_shape(point_geom)
        return (shape.y, shape.x)  # lat, lon

    async def _create_effort_with_pr_check(
        self,
        match: SegmentMatch,
        activity: Activity,
        user_id: int,
        records: list[dict],
    ) -> tuple[SegmentEffort, bool]:
        """
        Create effort and update PR flags atomically.

        Args:
            match: The segment match
            activity: The activity
            user_id: User ID
            records: Activity records as dicts

        Returns:
            Tuple of (created effort, is_new_pr)
        """
        # Calculate effort metrics
        start_record = records[match.start_index]
        end_record = records[match.end_index]

        started_at = start_record["timestamp"]
        elapsed_time = int((end_record["timestamp"] - start_record["timestamp"]).total_seconds())

        # Calculate averages for the matched section
        section_records = records[match.start_index : match.end_index + 1]
        avg_power = self._compute_avg_power(section_records)
        avg_hr = self._compute_avg_hr(section_records)

        # Check if this is a new PR
        current_pr = await self._effort_repo.get_user_pr(match.segment_id, user_id)
        is_new_pr = current_pr is None or elapsed_time < current_pr.elapsed_time_seconds

        # Clear existing PR if we have a new one
        if is_new_pr and current_pr is not None:
            await self._effort_repo.clear_user_pr(match.segment_id, user_id)

        # Create the effort
        effort = SegmentEffort(
            id=uuid4(),
            segment_id=match.segment_id,
            activity_id=activity.id,
            user_id=user_id,
            started_at=started_at,
            elapsed_time_seconds=elapsed_time,
            avg_power_watts=avg_power,
            avg_hr_bpm=avg_hr,
            start_index=match.start_index,
            end_index=match.end_index,
            is_pr=is_new_pr,
        )

        saved_effort = await self._effort_repo.save(effort)

        # Update segment counts
        # Check if this is user's first effort on this segment
        existing_efforts = await self._effort_repo.list_for_segment(match.segment_id, user_id, limit=2)
        new_athlete = len(existing_efforts) <= 1  # Only the one we just created

        await self._segment_repo.increment_counts(match.segment_id, new_athlete)

        return saved_effort, is_new_pr

    def _compute_avg_power(self, records: list[dict]) -> int | None:
        """Compute average power for a section of records."""
        powers = [r["power_w"] for r in records if r.get("power_w") is not None]
        if not powers:
            return None
        return int(sum(powers) / len(powers))

    def _compute_avg_hr(self, records: list[dict]) -> int | None:
        """Compute average heart rate for a section of records."""
        hrs = [r["hr_bpm"] for r in records if r.get("hr_bpm") is not None]
        if not hrs:
            return None
        return int(sum(hrs) / len(hrs))

    async def _process_climb_detection(
        self,
        activity: Activity,
        user_id: int,
        records: list[dict],
        matches: list[SegmentMatch],
    ) -> int:
        """
        Detect climbs and create suggestions.

        Skip detection rule: If any matched segment overlaps >80% with
        a detected climb zone, skip creating suggestion for that climb.

        Args:
            activity: The activity
            user_id: User ID
            records: Activity records as dicts
            matches: List of segment matches

        Returns:
            Number of detected climbs processed
        """
        # Detect climbs
        detected = detect_climbs(records)
        if not detected:
            return 0

        climb_count = 0
        for climb in detected:
            # Check if any matched segment overlaps with this climb
            if self._climb_overlaps_matched_segment(climb, matches, records):
                logger.debug(f"Skipping climb detection at index {climb.start_index}: overlaps existing segment match")
                continue

            # Process this climb
            await self._process_detected_climb(
                climb=climb,
                activity=activity,
                user_id=user_id,
                records=records,
            )
            climb_count += 1

        return climb_count

    def _climb_overlaps_matched_segment(
        self,
        climb: DetectedClimb,
        matches: list[SegmentMatch],
        records: list[dict],
    ) -> bool:
        """
        Check if a detected climb overlaps significantly with any matched segment.

        Returns True if any match has >80% overlap with the climb zone.
        """
        if not matches:
            return False

        # Get climb coordinates
        climb_coords = [(records[i]["lat"], records[i]["lon"]) for i in range(climb.start_index, climb.end_index + 1)]
        climb_polyline = encode_polyline(climb_coords)

        for match in matches:
            # Check overlap
            overlap = compute_path_overlap(
                records,
                match.start_index,
                match.end_index,
                climb_polyline,
                buffer_m=35,
            )
            if overlap >= SKIP_DETECTION_OVERLAP_PCT:
                return True

        return False

    async def _process_detected_climb(
        self,
        climb: DetectedClimb,
        activity: Activity,
        user_id: int,
        records: list[dict],
    ) -> None:
        """
        Process a detected climb — create/update segment and suggestion.

        Creates a suggested segment and increments the user's suggestion
        repetition count. Suggestions appear after 3+ repetitions.
        """
        # Compute geometry from the climb records
        geometry = compute_segment_geometry(
            records,
            climb.start_index,
            climb.end_index,
        )

        # Extract climb coordinates for PostGIS geometries
        start_lat = records[climb.start_index]["lat"]
        start_lon = records[climb.start_index]["lon"]
        end_lat = records[climb.end_index]["lat"]
        end_lon = records[climb.end_index]["lon"]

        # Create segment (status=suggested)
        start_wkt = WKTElement(f"POINT({start_lon} {start_lat})", srid=4326)
        end_wkt = WKTElement(f"POINT({end_lon} {end_lat})", srid=4326)

        # bounds is (min_lat, min_lon, max_lat, max_lon) = (sw_lat, sw_lng, ne_lat, ne_lng)
        sw_lat, sw_lng, ne_lat, ne_lng = geometry.bounds
        bounds_wkt = WKTElement(
            f"POLYGON(({sw_lng} {sw_lat}, {ne_lng} {sw_lat}, {ne_lng} {ne_lat}, {sw_lng} {ne_lat}, {sw_lng} {sw_lat}))",
            srid=4326,
        )

        segment = Segment(
            id=uuid4(),
            name="Detected Climb",  # Will be named by user if approved
            type="climb",
            status="suggested",
            climb_category=climb.category,
            polyline=geometry.polyline,
            start_point=start_wkt,
            end_point=end_wkt,
            bounds=bounds_wkt,
            direction_bearing=geometry.direction_bearing,
            distance_m=climb.distance_m,
            elevation_gain_m=climb.elevation_gain_m,
            avg_grade_pct=climb.avg_grade_pct,
            max_grade_pct=climb.max_grade_pct,
            gradient_segments=[{"distance_m": g.distance_m, "grade_pct": g.grade_pct} for g in climb.gradient_segments],
            created_by=user_id,
            source_activity_id=activity.id,
        )

        saved_segment = await self._segment_repo.save(segment)

        # Create or update suggestion
        now = datetime.now()
        expires_at = now + timedelta(days=SUGGESTION_EXPIRY_DAYS)

        existing_suggestion = await self._suggestion_repo.get_for_user_segment(user_id, saved_segment.id)

        if existing_suggestion:
            # Increment repetition count
            existing_suggestion.repetition_count += 1
            existing_suggestion.last_ridden_at = now
            existing_suggestion.expires_at = expires_at
            await self._suggestion_repo.save(existing_suggestion)
        else:
            # Create new suggestion
            suggestion = SegmentSuggestion(
                id=uuid4(),
                segment_id=saved_segment.id,
                user_id=user_id,
                repetition_count=1,
                first_ridden_at=now,
                last_ridden_at=now,
                expires_at=expires_at,
            )
            await self._suggestion_repo.save(suggestion)
