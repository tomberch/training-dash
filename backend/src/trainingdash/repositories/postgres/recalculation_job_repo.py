"""PostgreSQL implementation of RecalculationJobRepo."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import RecalculationJob


class PostgresRecalculationJobRepo:
    """PostgreSQL implementation of RecalculationJobRepo."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_by_user_id(self, user_id: int) -> RecalculationJob | None:
        result = await self._db.execute(
            select(RecalculationJob).where(RecalculationJob.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def upsert_pending(self, user_id: int) -> RecalculationJob:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        await self._db.execute(
            pg_insert(RecalculationJob)
            .values(user_id=user_id, status="pending", started_at=now)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "status": "pending",
                    "started_at": now,
                    "completed_at": None,
                    "error_message": None,
                },
            )
        )
        result = await self._db.execute(
            select(RecalculationJob).where(RecalculationJob.user_id == user_id)
        )
        return result.scalar_one()

    async def upsert_failed(self, user_id: int) -> RecalculationJob:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        await self._db.execute(
            pg_insert(RecalculationJob)
            .values(user_id=user_id, status="failed", started_at=now)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={"status": "failed", "started_at": now},
            )
        )
        result = await self._db.execute(
            select(RecalculationJob).where(RecalculationJob.user_id == user_id)
        )
        return result.scalar_one()

    async def mark_running(self, user_id: int) -> None:
        """Mark job as running."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        await self._db.execute(
            pg_insert(RecalculationJob)
            .values(user_id=user_id, status="running", started_at=now)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "status": "running",
                    "started_at": now,
                    "completed_at": None,
                    "error_message": None,
                },
            )
        )

    async def mark_completed(self, user_id: int, activities_updated: int) -> None:
        """Mark job as completed with count of updated activities."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        await self._db.execute(
            pg_insert(RecalculationJob)
            .values(
                user_id=user_id,
                status="completed",
                started_at=now,
                completed_at=now,
                activities_updated=activities_updated,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "status": "completed",
                    "completed_at": now,
                    "activities_updated": activities_updated,
                    "error_message": None,
                },
            )
        )

    async def mark_failed(self, user_id: int, error_message: str) -> None:
        """Mark job as failed with error message."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        await self._db.execute(
            pg_insert(RecalculationJob)
            .values(
                user_id=user_id,
                status="failed",
                started_at=now,
                completed_at=now,
                error_message=error_message,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "status": "failed",
                    "completed_at": now,
                    "error_message": error_message,
                    "activities_updated": None,
                },
            )
        )
