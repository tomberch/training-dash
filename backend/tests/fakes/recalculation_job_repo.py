"""In-memory fake implementation of RecalculationJobRepo for testing."""

from datetime import datetime, timezone

from trainingdash.repositories.postgres.models import RecalculationJob


class FakeRecalculationJobRepo:
    """
    In-memory fake implementation of RecalculationJobRepo protocol.
    
    Stores jobs in a dict keyed by user_id (one job per user).
    """

    def __init__(self) -> None:
        self._jobs: dict[int, RecalculationJob] = {}

    # --- Protocol methods ---

    async def get_by_user_id(self, user_id: int) -> RecalculationJob | None:
        return self._jobs.get(user_id)

    async def upsert_pending(self, user_id: int) -> RecalculationJob:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        job = self._jobs.get(user_id)
        if job is None:
            job = RecalculationJob(user_id=user_id, status="pending", started_at=now)
        else:
            job.status = "pending"
            job.started_at = now
            job.completed_at = None
            job.error_message = None
        self._jobs[user_id] = job
        return job

    async def upsert_failed(self, user_id: int) -> RecalculationJob:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        job = self._jobs.get(user_id)
        if job is None:
            job = RecalculationJob(user_id=user_id, status="failed", started_at=now)
        else:
            job.status = "failed"
            job.completed_at = now
            job.error_message = "Failed to enqueue job. Please try again."
        self._jobs[user_id] = job
        return job

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored jobs."""
        self._jobs.clear()

    def all(self) -> list[RecalculationJob]:
        """Return all stored jobs (for test assertions)."""
        return list(self._jobs.values())

    def set_completed(self, user_id: int, activities_updated: int = 0) -> None:
        """Mark a job as completed (for test setup)."""
        job = self._jobs.get(user_id)
        if job:
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            job.activities_updated = activities_updated
