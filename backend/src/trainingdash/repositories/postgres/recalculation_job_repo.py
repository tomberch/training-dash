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
                set_={"status": "pending", "started_at": now},
            )
        )
        await self._db.commit()
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
        await self._db.commit()
        result = await self._db.execute(
            select(RecalculationJob).where(RecalculationJob.user_id == user_id)
        )
        return result.scalar_one()
