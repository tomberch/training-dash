"""PostgreSQL implementation of AuditLogRepo."""

from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import AuditLog


class PostgresAuditLogRepo:
    """PostgreSQL implementation of AuditLogRepo."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def log(
        self,
        admin_id: int,
        action: str,
        target_user_id: int | None = None,
        details: str | None = None,
    ) -> None:
        log_entry = AuditLog(
            admin_id=admin_id,
            action=action,
            target_user_id=target_user_id,
            details=details,
        )
        self._db.add(log_entry)
        await self._db.commit()
