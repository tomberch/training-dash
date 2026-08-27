"""
RetroactiveMatch use case — match historical activities to a newly created segment.

When a segment is created or approved, this use case scans all historical
activities to find those that match the segment. It processes activities
in batches with checkpoint/resume capability for reliability.

Key features:
1. Batched processing (100 activities per commit)
2. Direction bearing filter (±60°) for candidate filtering
3. Checkpoint/resume via segment.matching_job_id
4. PR tracking for each user
5. Denormalized count updates at completion
"""

import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from geoalchemy2.shape import to_shape

from trainingdash.domain.segment_matching import (
    SegmentCandidate,
    match_activity_to_segments,
)
from trainingdash.repositories.postgres.models import (
    Activity,
    Record,
    Segment,
    SegmentEffort,
)
from trainingdash.repositories.protocols import SegmentEffortRepo, SegmentRepo

logger = logging.getLogger(__name__)

# Constants
DEFAULT_BATCH_SIZE = 100
DIRECTION_TOLERANCE = 60  # degrees ±60° for direction matching


@dataclass
class RetroactiveMatchResult:
    """Result of retroactive matching for a segment.

    Attributes:
        success: Whether the matching completed successfully
        activities_scanned: Number of activities processed
        efforts_created: Number of new segment efforts created
        error: Error message if not successful
    """

    success: bool
    activities_scanned: int
    efforts_created: int
    error: str | None = None


class RetroactiveMatch:
    """
    Use case for matching historical activities to a newly created segment.

    This use case:
    1. Loads the segment with its bounding box
    2. Sets matching_job_id as progress indicator
    3. Iterates through candidate activities in batches
    4. Runs precise matching for each
    5. Creates SegmentEffort for matches with PR tracking
    6. Commits after each batch
    7. Updates denormalized counts on completion
    8. Clears matching_job_id

    Example usage:
        use_case = RetroactiveMatch(db, segment_repo, effort_repo)
        result = await use_case.execute(segment_id, batch_size=100)
    """

    def __init__(
        self,
        db: AsyncSession,
        segment_repo: SegmentRepo,
        effort_repo: SegmentEffortRepo,
    ) -> None:
        """
        Initialize the use case with dependencies.

        Args:
            db: Database session for queries and batched commits
            segment_repo: Repository for segment operations
            effort_repo: Repository for effort operations
        """
        self._db = db
        self._segment_repo = segment_repo
        self._effort_repo = effort_repo

    async def execute(
        self, segment_id: UUID, batch_size: int = DEFAULT_BATCH_SIZE
    ) -> RetroactiveMatchResult:
        """
        Find all historical activities that match a segment.

        Algorithm:
        1. Load segment with bounding box
        2. Set segment.matching_job_id (progress indicator)
        3. Loop:
           a. Find next batch of candidate activities (ST_Intersects + direction)
           b. For each, run precise matching
           c. Create SegmentEffort if match (with PR check)
           d. Commit batch
        4. Update segment.effort_count, athlete_count
        5. Clear segment.matching_job_id

        Args:
            segment_id: UUID of the segment to match against
            batch_size: Number of activities to process per batch

        Returns:
            RetroactiveMatchResult with counts and success status
        """
        # Step 1: Load segment
        segment = await self._segment_repo.get_by_id(segment_id)
        if segment is None:
            return RetroactiveMatchResult(
                success=False,
                activities_scanned=0,
                efforts_created=0,
                error=f"Segment {segment_id} not found",
            )

        # Step 2: Set matching job ID (for progress tracking and resume)
        job_id = str(uuid4())
        checkpoint_activity_id = await self._get_checkpoint(segment)
        if checkpoint_activity_id:
            logger.info(
                f"Resuming retroactive match for segment {segment_id} "
                f"from activity {checkpoint_activity_id}"
            )
        else:
            await self._set_matching_job_id(segment_id, job_id)

        # Extract segment geometry for matching
        segment_candidate = self._build_segment_candidate(segment)

        # Step 3: Process activities in batches
        total_scanned = 0
        total_efforts = 0
        after_id = checkpoint_activity_id
        user_prs: dict[int, int] = {}  # user_id -> best elapsed time

        try:
            while True:
                # Find next batch of candidate activities
                activities = await self._find_candidate_activities(
                    segment=segment,
                    after_id=after_id,
                    limit=batch_size,
                )

                if not activities:
                    break  # No more candidates

                # Process each activity
                batch_efforts = 0
                for activity in activities:
                    total_scanned += 1
                    after_id = activity.id

                    # Load records for this activity
                    records = await self._load_activity_records(activity.id)
                    if len(records) < 2:
                        continue

                    # Run precise matching
                    matches = match_activity_to_segments(records, [segment_candidate])

                    for match in matches:
                        # Check if we already have an effort for this activity/segment
                        existing = await self._check_existing_effort(
                            segment_id, activity.id, match.start_index
                        )
                        if existing:
                            continue  # Don't create duplicates

                        # Create effort
                        effort = await self._create_effort(
                            segment_id=segment_id,
                            activity=activity,
                            records=records,
                            start_index=match.start_index,
                            end_index=match.end_index,
                            user_prs=user_prs,
                        )
                        if effort:
                            batch_efforts += 1
                            total_efforts += 1

                # Commit batch and update checkpoint
                await self._db.commit()
                await self._set_checkpoint(segment_id, after_id)
                logger.debug(
                    f"Processed batch: {len(activities)} activities, "
                    f"{batch_efforts} efforts created"
                )

            # Step 4: Update denormalized counts
            await self._update_segment_counts(segment_id)

            # Step 5: Clear matching job ID
            await self._clear_matching_job_id(segment_id)
            await self._db.commit()

            return RetroactiveMatchResult(
                success=True,
                activities_scanned=total_scanned,
                efforts_created=total_efforts,
            )

        except Exception as e:
            logger.exception(f"Retroactive match failed for segment {segment_id}")
            await self._db.rollback()
            return RetroactiveMatchResult(
                success=False,
                activities_scanned=total_scanned,
                efforts_created=total_efforts,
                error=str(e),
            )

    async def _find_candidate_activities(
        self,
        segment: Segment,
        after_id: UUID | None,
        limit: int,
    ) -> list[Activity]:
        """
        Find activities whose direction matches the segment bearing.

        Filters by direction bearing (±60°) for candidate selection.
        Activities are ordered by id for stable pagination.

        Args:
            segment: The segment to match against
            after_id: Pagination cursor (activities after this ID)
            limit: Maximum activities to return

        Returns:
            List of candidate Activity objects ordered by id for stable pagination
        """
        # TODO: Add ST_Intersects spatial filter for performance optimization
        # Currently relies on direction filter; spatial filter would reduce
        # candidates further by checking activity bounds vs segment bounds

        # Build direction filter
        # Activities must have direction_bearing within ±60° of segment
        segment_bearing = segment.direction_bearing or 0
        low_bearing = (segment_bearing - DIRECTION_TOLERANCE) % 360
        high_bearing = (segment_bearing + DIRECTION_TOLERANCE) % 360

        # Build query
        query = (
            select(Activity)
            .where(Activity.direction_bearing.isnot(None))
            .order_by(Activity.id)  # Stable ordering for pagination
            .limit(limit)
        )

        # Add after_id filter for pagination
        if after_id:
            query = query.where(Activity.id > after_id)

        # Direction bearing filter
        # Handle wraparound (e.g., bearing 350° with tolerance crosses 0°)
        if low_bearing < high_bearing:
            # Normal case: low < bearing < high
            query = query.where(
                Activity.direction_bearing >= low_bearing,
                Activity.direction_bearing <= high_bearing,
            )
        else:
            # Wraparound case: bearing > low OR bearing < high
            query = query.where(
                (Activity.direction_bearing >= low_bearing)
                | (Activity.direction_bearing <= high_bearing)
            )

        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def _load_activity_records(self, activity_id: UUID) -> list[dict]:
        """Load and prepare activity records for matching."""
        result = await self._db.execute(
            select(Record)
            .where(Record.activity_id == activity_id)
            .order_by(Record.timestamp)
        )
        records = []
        for r in result.scalars().all():
            if r.lat is not None and r.lon is not None:
                records.append({
                    "lat": r.lat,
                    "lon": r.lon,
                    "altitude_m": r.altitude_m,
                    "distance_m": r.distance_m or 0.0,
                    "timestamp": r.timestamp,
                    "power_w": r.power_w,
                    "hr_bpm": r.hr_bpm,
                })
        return records

    def _build_segment_candidate(self, segment: Segment) -> SegmentCandidate:
        """Build a SegmentCandidate from a Segment model."""
        start_shape = to_shape(segment.start_point)
        end_shape = to_shape(segment.end_point)

        return SegmentCandidate(
            id=segment.id,
            polyline=segment.polyline,
            start_lat=start_shape.y,
            start_lon=start_shape.x,
            end_lat=end_shape.y,
            end_lon=end_shape.x,
            direction_bearing=segment.direction_bearing or 0.0,
            distance_m=segment.distance_m,
        )

    async def _check_existing_effort(
        self, segment_id: UUID, activity_id: UUID, start_index: int
    ) -> bool:
        """Check if an effort already exists for this segment/activity/start_index."""
        result = await self._db.execute(
            select(SegmentEffort.id)
            .where(
                SegmentEffort.segment_id == segment_id,
                SegmentEffort.activity_id == activity_id,
                SegmentEffort.start_index == start_index,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _create_effort(
        self,
        segment_id: UUID,
        activity: Activity,
        records: list[dict],
        start_index: int,
        end_index: int,
        user_prs: dict[int, int],
    ) -> SegmentEffort | None:
        """
        Create a segment effort with PR tracking.

        Args:
            segment_id: Segment ID
            activity: Activity object
            records: Activity records as dicts
            start_index: Start index in records
            end_index: End index in records
            user_prs: Mutable dict tracking best times per user this batch

        Returns:
            Created SegmentEffort or None if invalid data
        """
        start_record = records[start_index]
        end_record = records[end_index]

        started_at = start_record["timestamp"]
        elapsed_time = int(
            (end_record["timestamp"] - start_record["timestamp"]).total_seconds()
        )

        if elapsed_time <= 0:
            return None

        # Calculate averages for the matched section
        section_records = records[start_index : end_index + 1]
        avg_power = self._compute_avg_power(section_records)
        avg_hr = self._compute_avg_hr(section_records)

        user_id = activity.user_id

        # Determine PR status
        # First check in-memory cache for this batch
        current_best = user_prs.get(user_id)
        if current_best is None:
            # Check database for existing PR
            existing_pr = await self._effort_repo.get_user_pr(segment_id, user_id)
            if existing_pr:
                current_best = existing_pr.elapsed_time_seconds
                user_prs[user_id] = current_best

        is_new_pr = current_best is None or elapsed_time < current_best

        # If new PR, clear existing PR flag and update cache
        if is_new_pr:
            await self._effort_repo.clear_user_pr(segment_id, user_id)
            user_prs[user_id] = elapsed_time

        # Create the effort
        effort = SegmentEffort(
            id=uuid4(),
            segment_id=segment_id,
            activity_id=activity.id,
            user_id=user_id,
            started_at=started_at,
            elapsed_time_seconds=elapsed_time,
            avg_power_watts=avg_power,
            avg_hr_bpm=avg_hr,
            start_index=start_index,
            end_index=end_index,
            is_pr=is_new_pr,
        )

        return await self._effort_repo.save(effort)

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

    async def _set_matching_job_id(self, segment_id: UUID, job_id: str) -> None:
        """Set the matching_job_id on the segment."""
        await self._db.execute(
            update(Segment)
            .where(Segment.id == segment_id)
            .values(matching_job_id=job_id)
        )
        await self._db.commit()

    async def _clear_matching_job_id(self, segment_id: UUID) -> None:
        """Clear the matching_job_id on the segment."""
        await self._db.execute(
            update(Segment)
            .where(Segment.id == segment_id)
            .values(matching_job_id=None)
        )

    async def _get_checkpoint(self, segment: Segment) -> UUID | None:
        """
        Get the checkpoint activity ID for resuming.

        If matching_job_id is set, we're resuming from a previous run.
        The checkpoint is encoded in matching_job_id as 'job_id:activity_id'.
        """
        if not segment.matching_job_id:
            return None
        if ":" not in segment.matching_job_id:
            return None  # Just a job ID, no checkpoint yet
        _, activity_id_str = segment.matching_job_id.split(":", 1)
        try:
            return UUID(activity_id_str)
        except ValueError:
            return None

    async def _set_checkpoint(self, segment_id: UUID, activity_id: UUID) -> None:
        """
        Save checkpoint progress.

        Encodes as 'job_id:activity_id' in matching_job_id.
        """
        # Get current job_id
        result = await self._db.execute(
            select(Segment.matching_job_id).where(Segment.id == segment_id)
        )
        current = result.scalar_one_or_none()
        if not current:
            return

        # Extract base job_id
        base_job_id = current.split(":")[0] if ":" in current else current

        # Update with checkpoint
        await self._db.execute(
            update(Segment)
            .where(Segment.id == segment_id)
            .values(matching_job_id=f"{base_job_id}:{activity_id}")
        )

    async def _update_segment_counts(self, segment_id: UUID) -> None:
        """Update denormalized effort_count and athlete_count on segment."""
        # Count total efforts
        effort_count_result = await self._db.execute(
            select(func.count())
            .select_from(SegmentEffort)
            .where(SegmentEffort.segment_id == segment_id)
        )
        effort_count = effort_count_result.scalar() or 0

        # Count unique athletes
        athlete_count_result = await self._db.execute(
            select(func.count(func.distinct(SegmentEffort.user_id)))
            .select_from(SegmentEffort)
            .where(SegmentEffort.segment_id == segment_id)
        )
        athlete_count = athlete_count_result.scalar() or 0

        # Update segment
        await self._db.execute(
            update(Segment)
            .where(Segment.id == segment_id)
            .values(effort_count=effort_count, athlete_count=athlete_count)
        )
