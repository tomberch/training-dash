"""PostgreSQL implementation of EventRepo."""

from datetime import datetime

from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import Event


def _apply_event_filters[T](
    query: Select[T],
    event_type: str | None = None,
    outcome: str | None = None,
    user_id: int | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> Select[T]:
    """Apply common event filters to a query."""
    if event_type is not None:
        query = query.where(Event.event_type == event_type)
    if outcome is not None:
        query = query.where(Event.outcome == outcome)
    if user_id is not None:
        query = query.where(Event.user_id == user_id)
    if since is not None:
        query = query.where(Event.created_at >= since)
    if until is not None:
        query = query.where(Event.created_at < until)
    return query


class PostgresEventRepo:
    """PostgreSQL implementation of EventRepo for system event logging."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def log(
        self,
        event_type: str,
        outcome: str,
        user_id: int | None = None,
        payload: dict | None = None,
    ) -> int:
        """
        Log an event to the system event log.

        Returns the ID of the created event.
        """
        event = Event(
            event_type=event_type,
            outcome=outcome,
            user_id=user_id,
            payload=payload or {},
        )
        self._db.add(event)
        await self._db.flush()  # Get the ID without committing
        return event.id

    async def list(
        self,
        event_type: str | None = None,
        outcome: str | None = None,
        user_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Event]:
        """
        List events with optional filters, ordered by created_at descending.
        """
        limit = min(limit, 100)  # Cap limit at 100

        query = _apply_event_filters(
            select(Event),
            event_type=event_type,
            outcome=outcome,
            user_id=user_id,
            since=since,
            until=until,
        )
        query = query.order_by(Event.created_at.desc()).limit(limit).offset(offset)

        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def count(
        self,
        event_type: str | None = None,
        outcome: str | None = None,
        user_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> int:
        """
        Count events matching the given filters.
        """
        query = _apply_event_filters(
            select(func.count()).select_from(Event),
            event_type=event_type,
            outcome=outcome,
            user_id=user_id,
            since=since,
            until=until,
        )

        result = await self._db.execute(query)
        return result.scalar_one()

    async def delete_before(self, cutoff: datetime, batch_size: int = 1000) -> int:
        """
        Delete events older than the cutoff time in batches.

        Returns total number of events deleted.
        """
        total_deleted = 0

        while True:
            # Find IDs to delete (batched to avoid long locks)
            id_query = select(Event.id).where(Event.created_at < cutoff).limit(batch_size)
            id_result = await self._db.execute(id_query)
            ids_to_delete = [row[0] for row in id_result.fetchall()]

            if not ids_to_delete:
                break

            # Delete the batch
            delete_query = delete(Event).where(Event.id.in_(ids_to_delete))
            result = await self._db.execute(delete_query)
            await self._db.commit()

            total_deleted += result.rowcount

        return total_deleted
