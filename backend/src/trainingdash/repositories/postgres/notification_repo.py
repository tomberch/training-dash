"""PostgreSQL implementation of NotificationRepo."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import Notification


class PostgresNotificationRepo:
    """PostgreSQL implementation of NotificationRepo."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def list_for_user(
        self, user_id: int, limit: int = 50, offset: int = 0
    ) -> list[Notification]:
        result = await self._db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_id(self, notification_id: UUID, user_id: int) -> Notification | None:
        result = await self._db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_read(self, notification_id: UUID, user_id: int) -> bool:
        result = await self._db.execute(
            update(Notification)
            .where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
            .values(read_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )
        await self._db.commit()
        return result.rowcount > 0

    async def mark_all_read(self, user_id: int) -> int:
        result = await self._db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )
        await self._db.commit()
        return result.rowcount
