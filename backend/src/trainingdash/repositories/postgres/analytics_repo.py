"""PostgreSQL implementation of AnalyticsRepo.

Read-only analytics queries for the dashboard endpoints: fitness history,
PMC source activities, power curve, and lifetime/per-route records.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import (
    Activity,
    ActivityPeakPower,
    FitnessHistory,
)


@dataclass
class RoutePrView:
    """One per-route PR entry returned by ``AnalyticsRepo.get_records``."""

    route_id: int
    route_label: str
    fastest_time_s: int
    activity_id: str | None


@dataclass
class RecordsView:
    """Composite lifetime + per-route records returned by ``get_records``."""

    lifetime_prs: dict[str, Any]
    route_prs: list[RoutePrView]


class PostgresAnalyticsRepo:
    """PostgreSQL implementation of the AnalyticsRepo protocol.

    Read-only queries only; no commits. The router serializes the ORM
    objects returned (``FitnessHistory``, ``Activity``, joined rows), with
    the exception of ``get_records`` which returns a typed ``RecordsView``.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_latest_fitness(self, user_id: int) -> FitnessHistory | None:
        """Most recent fitness snapshot for the user, or None."""
        result = await self._session.execute(
            select(FitnessHistory)
            .where(FitnessHistory.user_id == user_id)
            .order_by(FitnessHistory.computed_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_fitness_history(
        self, user_id: int, limit: int = 10
    ) -> list[FitnessHistory]:
        """Recent fitness snapshots, most recent first."""
        result = await self._session.execute(
            select(FitnessHistory)
            .where(FitnessHistory.user_id == user_id)
            .order_by(FitnessHistory.computed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_activities_for_pmc(self, user_id: int) -> list[Activity]:
        """All activities for the user, ordered by started_at ASC (for TSS aggregation)."""
        result = await self._session.execute(
            select(Activity)
            .where(Activity.user_id == user_id)
            .order_by(Activity.started_at)
        )
        return list(result.scalars().all())

    async def get_power_curve(
        self,
        user_id: int,
        start: date | None = None,
        end: date | None = None,
    ) -> list[Any]:
        """Peak powers joined with activity start time, optionally date-filtered.

        Returns a list of SQLAlchemy Row objects with ``ActivityPeakPower``
        and ``Activity.started_at`` columns.
        """
        query = (
            select(ActivityPeakPower, Activity.started_at)
            .join(Activity, ActivityPeakPower.activity_id == Activity.id)
            .where(Activity.user_id == user_id)
        )
        if start is not None:
            query = query.where(
                Activity.started_at >= datetime.combine(start, datetime.min.time())
            )
        if end is not None:
            query = query.where(
                Activity.started_at <= datetime.combine(end, datetime.max.time())
            )
        result = await self._session.execute(query)
        return list(result.all())

    async def get_records(self, user_id: int) -> RecordsView:
        """Lifetime PRs + per-route PRs in a single composite query.

        Replaces the old 5+N query implementation:
        - 1 aggregate query for 6 lifetime maxes
        - 3 queries for fastest times at 5km/10km/40km
        - 1 window-function query for per-route PRs (was N+1)
        """
        lifetime_prs = await self._get_lifetime_prs(user_id)
        route_prs = await self._get_route_prs(user_id)
        return RecordsView(lifetime_prs=lifetime_prs, route_prs=route_prs)

    async def _get_lifetime_prs(self, user_id: int) -> dict[str, Any]:
        """6 max aggregates + 3 fastest-time-at-distance queries."""
        result = await self._session.execute(
            select(
                func.max(Activity.total_distance_m).label("longest_distance_m"),
                func.max(Activity.moving_time_s).label("longest_moving_time_s"),
                func.max(Activity.max_speed_mps).label("max_speed_mps"),
                func.max(Activity.max_hr_bpm).label("max_hr_bpm"),
                func.max(Activity.elevation_gain_m).label("biggest_elevation_gain_m"),
                func.max(Activity.np_power_w).label("highest_sustained_power_w"),
            ).where(Activity.user_id == user_id)
        )
        row = result.one()

        def _pr(val: Any) -> dict[str, Any] | None:
            return {"value": val} if val is not None else None

        prs: dict[str, Any] = {
            "longest_distance_m": _pr(row.longest_distance_m),
            "longest_moving_time_s": _pr(row.longest_moving_time_s),
            "max_speed_mps": _pr(row.max_speed_mps),
            "max_hr_bpm": _pr(row.max_hr_bpm),
            "biggest_elevation_gain_m": _pr(row.biggest_elevation_gain_m),
            "highest_sustained_power_w": _pr(row.highest_sustained_power_w),
        }

        for target_m in [5000, 10000, 40000]:
            result = await self._session.execute(
                select(Activity.id, Activity.avg_speed_mps)
                .where(
                    Activity.user_id == user_id,
                    Activity.total_distance_m >= target_m,
                    Activity.avg_speed_mps > 0,
                )
                .order_by(Activity.avg_speed_mps.desc())
                .limit(1)
            )
            fastest = result.first()
            key = f"fastest_{target_m}_m"
            if fastest is not None:
                projected_time_s = target_m / fastest.avg_speed_mps
                prs[key] = {
                    "value": projected_time_s,
                    "activity_id": str(fastest.id),
                }
            else:
                prs[key] = None

        return prs

    async def _get_route_prs(self, user_id: int) -> list[RoutePrView]:
        """Per-route fastest times + labels in a single window-function query.

        Replaces the old N+1 implementation (2 queries per route).
        Uses ``FIRST_VALUE`` partitioned by route to get both:
        - the activity holding the fastest time (by elapsed_time_s)
        - the first activity's started_at (for the route label)
        """
        # Window functions: fastest activity per route + earliest activity per route
        # We compute MIN(elapsed_time_s) per route, then find the activity matching it.
        # FIRST_VALUE gives us the first activity's started_at for the label.
        fastest_time = (
            func.min(Activity.elapsed_time_s)
            .over(partition_by=Activity.route_id)
            .label("fastest_time")
        )
        # Rank activities within each route by elapsed_time_s ASC to find the record holder
        fastest_rank = (
            func.row_number()
            .over(
                partition_by=Activity.route_id,
                order_by=Activity.elapsed_time_s.asc(),
            )
            .label("rn")
        )
        # Earliest activity per route (for the route label)
        first_started_rank = (
            func.row_number()
            .over(
                partition_by=Activity.route_id,
                order_by=Activity.started_at.asc(),
            )
            .label("first_rn")
        )

        subq = (
            select(
                Activity.route_id,
                Activity.id,
                Activity.started_at,
                Activity.elapsed_time_s,
                fastest_time,
                fastest_rank,
                first_started_rank,
            )
            .where(
                Activity.user_id == user_id,
                Activity.route_id.isnot(None),
            )
            .subquery()
        )

        # The record holder = row with rn=1; the first activity = row with first_rn=1.
        # Join these per route to assemble the label + record holder in one query.
        record_holders = (
            select(
                subq.c.route_id,
                subq.c.id.label("activity_id"),
                subq.c.elapsed_time_s.label("fastest_time_s"),
            )
            .where(literal_column("rn") == 1)
            .subquery()
        )
        first_activities = (
            select(
                subq.c.route_id,
                subq.c.started_at.label("first_started_at"),
            )
            .where(literal_column("first_rn") == 1)
            .subquery()
        )

        result = await self._session.execute(
            select(
                record_holders.c.route_id,
                record_holders.c.activity_id,
                record_holders.c.fastest_time_s,
                first_activities.c.first_started_at,
            )
            .join(
                first_activities,
                first_activities.c.route_id == record_holders.c.route_id,
            )
            .order_by(record_holders.c.route_id)
        )

        route_prs: list[RoutePrView] = []
        for row in result.all():
            route_label = (
                row.first_started_at.strftime("%Y-%m-%d")
                if row.first_started_at
                else f"Route {row.route_id}"
            )
            route_prs.append(
                RoutePrView(
                    route_id=row.route_id,
                    route_label=route_label,
                    fastest_time_s=row.fastest_time_s,
                    activity_id=str(row.activity_id) if row.activity_id else None,
                )
            )
        return route_prs