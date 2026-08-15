"""
MatchRoute use case — match a freshly-ingested activity to a route cluster.

Loads the activity and its records, runs route matching, and sets the
activity's route_id. Called by the worker's ``match_route_job`` (thin
dispatch) after an ingest.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.domain.events import EventOutcome, EventType
from trainingdash.repositories.postgres.event_repo import PostgresEventRepo
from trainingdash.repositories.postgres.models import Activity, Record
from trainingdash.route_matching import find_or_create_route_id


class MatchRoute:
    """Match an activity to a route cluster by GPS track similarity."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._event_repo = PostgresEventRepo(db)

    async def execute(self, activity_id: str, user_id: int) -> dict:
        """Match the activity and set its route_id. Returns a result dict.

        ``activity_id`` is a string (UUID serialized) for JSON compatibility
        with the SAQ job queue.
        """
        activity_uuid = UUID(activity_id)

        result = await self._db.execute(select(Activity).where(Activity.id == activity_uuid))
        activity = result.scalar_one_or_none()
        if activity is None:
            await self._event_repo.log(
                event_type=EventType.ROUTE_MATCHED.value,
                outcome=EventOutcome.FAILURE.value,
                user_id=user_id,
                payload={"activity_id": activity_id, "error": "Activity not found"},
            )
            return {"success": False}

        records_result = await self._db.execute(
            select(Record).where(Record.activity_id == activity_uuid).order_by(Record.timestamp)
        )
        all_records = records_result.scalars().all()

        route_id = await find_or_create_route_id(self._db, activity, all_records)
        if route_id is not None:
            activity.route_id = route_id
            await self._db.commit()

        # Emit route.matched event (success if matched, failure if no match)
        await self._event_repo.log(
            event_type=EventType.ROUTE_MATCHED.value,
            outcome=EventOutcome.SUCCESS.value if route_id else EventOutcome.FAILURE.value,
            user_id=user_id,
            payload={
                "activity_id": activity_id,
                "route_id": str(route_id) if route_id else None,
            },
        )

        return {"success": True, "route_id": route_id}
