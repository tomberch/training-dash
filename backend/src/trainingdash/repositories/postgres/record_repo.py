"""
PostgreSQL implementation of RecordRepo.

Uses SQLAlchemy async session for all database operations.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import Record


class PostgresRecordRepo:
    """
    PostgreSQL implementation of the RecordRepo protocol.

    Requires an AsyncSession to be injected at construction time.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_activity(self, activity_id: UUID) -> list[Record]:
        """
        List all records for an activity, ordered by timestamp.

        Args:
            activity_id: Activity UUID

        Returns:
            List of Record objects ordered by timestamp ascending
        """
        result = await self._session.execute(
            select(Record)
            .where(Record.activity_id == activity_id)
            .order_by(Record.timestamp)
        )
        return list(result.scalars().all())
