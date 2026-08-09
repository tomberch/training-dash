"""In-memory fake implementation of RecalculationJobRepo for testing."""

from datetime import UTC, datetime

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
        now = datetime.now(UTC).replace(tzinfo=None)
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
        now = datetime.now(UTC).replace(tzinfo=None)
        job = self._jobs.get(user_id)
        if job is None:
            job = RecalculationJob(user_id=user_id, status="failed", started_at=now)
        else:
            job.status = "failed"
            job.completed_at = now
            job.error_message = "Failed to enqueue job. Please try again."
        self._jobs[user_id] = job
        return job

    async def mark_running(self, user_id: int) -> None:
        """Mark job as running."""
        now = datetime.now(UTC).replace(tzinfo=None)
        job = self._jobs.get(user_id)
        if job is None:
            job = RecalculationJob(user_id=user_id, status="running", started_at=now)
        else:
            job.status = "running"
            job.started_at = now
            job.completed_at = None
            job.error_message = None
        self._jobs[user_id] = job

    async def mark_completed(self, user_id: int, activities_updated: int) -> None:
        """Mark job as completed with count of updated activities."""
        now = datetime.now(UTC).replace(tzinfo=None)
        job = self._jobs.get(user_id)
        if job is None:
            job = RecalculationJob(
                user_id=user_id,
                status="completed",
                started_at=now,
                completed_at=now,
                activities_updated=activities_updated,
            )
        else:
            job.status = "completed"
            job.completed_at = now
            job.activities_updated = activities_updated
            job.error_message = None
        self._jobs[user_id] = job

    async def mark_failed(self, user_id: int, error_message: str) -> None:
        """Mark job as failed with error message."""
        now = datetime.now(UTC).replace(tzinfo=None)
        job = self._jobs.get(user_id)
        if job is None:
            job = RecalculationJob(
                user_id=user_id,
                status="failed",
                started_at=now,
                completed_at=now,
                error_message=error_message,
            )
        else:
            job.status = "failed"
            job.completed_at = now
            job.error_message = error_message
            job.activities_updated = None
        self._jobs[user_id] = job

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
            job.completed_at = datetime.now(UTC).replace(tzinfo=None)
            job.activities_updated = activities_updated
