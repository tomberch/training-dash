"""
IngestActivity use case — orchestrates activity ingestion pipeline.

This use case handles the complete flow of ingesting a FIT file:
1. Parse FIT file data
2. Check for duplicate activities
3. Store Activity, Lap, and Record rows
4. Run pipeline for metrics, peaks, route matching, and title generation

The use case can be called by HTTP routers or background workers.
"""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.events import EventOutcome, EventType
from trainingdash.repositories.postgres.event_repo import PostgresEventRepo
from trainingdash.repositories.postgres.models import Activity

logger = logging.getLogger(__name__)


class IngestActivity:
    """
    Use case for ingesting a FIT file and processing the activity.

    This use case coordinates:
    - Parsing the FIT file
    - Duplicate detection
    - Persisting the activity and related records
    - Running the activity pipeline for metrics, peaks, routes

    Example usage:
        use_case = IngestActivity(db)
        activity = await use_case.execute(
            user_id=1,
            fit_data=fit_bytes,
            source="upload",
            source_ref="ride.fit",
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize the use case with dependencies.

        Args:
            db: Database session for persistence
        """
        self._db = db
        self._event_repo = PostgresEventRepo(db)

    async def execute(
        self,
        user_id: int,
        fit_data: bytes,
        source: str,
        source_ref: str,
        batch_mode: bool = False,
    ) -> Activity | None:
        """
        Ingest a FIT file and process the activity.

        Steps:
        1. Parse FIT file to extract records, laps, and summary data
        2. Check for duplicate activities
        3. Create Activity, Lap, and Record models
        4. Run activity pipeline for metrics, peaks, routes, and titles

        Args:
            user_id: User ID to attribute the activity to
            fit_data: Raw FIT file bytes
            source: Source identifier (e.g., "garmin", "xert", "upload")
            source_ref: Unique reference from the source
            batch_mode: If True, skip per-activity fitness updates and geocoding

        Returns:
            Created Activity or None if parsing failed or duplicate detected
        """
        # Import here to avoid circular imports
        from trainingdash.activity_pipeline import ActivityPipeline
        from trainingdash.ingest import (
            _store_parsed_fit,
            is_duplicate_activity,
            parse_records,
        )

        # Step 1: Parse FIT file
        try:
            parsed = parse_records(fit_data)
        except Exception as e:
            logger.warning(f"Failed to parse FIT file: {e}")
            await self._event_repo.log(
                event_type=EventType.ACTIVITY_INGESTED.value,
                outcome=EventOutcome.FAILURE.value,
                user_id=user_id,
                payload={"source": source, "source_ref": source_ref, "error": str(e)},
            )
            return None

        # Step 2: Check for duplicates (skip for manual uploads)
        # Duplicate detection is for automated syncs from providers to prevent
        # the same activity from being imported twice. Manual uploads trust
        # the user to know what they're uploading.
        if source != "upload" and await is_duplicate_activity(
            self._db,
            user_id,
            parsed["started_at"],
            parsed["total_distance_m"],
            source,
        ):
            logger.info(f"Skipping duplicate activity from {source}")
            return None

        # Step 3: Store parsed data
        activity = await _store_parsed_fit(
            self._db,
            user_id,
            source,
            source_ref,
            fit_data,
            parsed,
        )

        # Step 4: Run activity pipeline
        pipeline = ActivityPipeline(
            db=self._db,
            activity=activity,
            records=parsed["records"],
            batch_mode=batch_mode,
        )
        await pipeline.run()

        # Emit success event
        await self._event_repo.log(
            event_type=EventType.ACTIVITY_INGESTED.value,
            outcome=EventOutcome.SUCCESS.value,
            user_id=user_id,
            payload={
                "activity_id": str(activity.id),
                "source": source,
                "source_ref": source_ref,
            },
        )

        return activity
