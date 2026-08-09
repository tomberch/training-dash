"""
EnsureDefaultThresholds use case — create default thresholds if none exist.

Orchestrates: check if user has any threshold entry → compute defaults
from DOB + weight → create entries. Idempotent — no-op if thresholds
already exist or if DOB is missing.
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.thresholds import compute_default_thresholds
from trainingdash.repositories.postgres.threshold_repo import PostgresThresholdRepo


class EnsureDefaultThresholds:
    """Ensure a user has at least one threshold entry, creating defaults if needed."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = PostgresThresholdRepo(db)

    async def execute(
        self, user_id: int, dob: date | None, weight_kg: float | None
    ) -> bool:
        """Returns True if defaults were created, False otherwise."""
        if dob is None:
            return False

        if await self._repo.has_any_threshold(user_id):
            return False

        defaults = compute_default_thresholds(dob, weight_kg)
        await self._repo.create(
            user_id,
            date.today(),
            ftp_watts=defaults["ftp_watts"],
            lthr_bpm=defaults["lthr_bpm"],
            hrmax_bpm=defaults["hrmax_bpm"],
            source="calculated",
            source_detail="default_from_age_weight",
        )
        await self._db.commit()
        return True