"""PostgreSQL implementation of AnalyticsRepo.

Read-only analytics queries for the dashboard endpoints: fitness history,
PMC source activities, power curve, and lifetime/per-route records.
"""

from dataclasses import dataclass
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
    activity_title: str | None
    polyline: str | None


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

    async def get_fitness_history(self, user_id: int, limit: int = 10) -> list[FitnessHistory]:
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
            select(Activity).where(Activity.user_id == user_id).order_by(Activity.started_at)
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
            query = query.where(Activity.started_at >= datetime.combine(start, datetime.min.time()))
        if end is not None:
            query = query.where(Activity.started_at <= datetime.combine(end, datetime.max.time()))
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
        """Get lifetime PRs with activity IDs for all PR types."""
        prs: dict[str, Any] = {}

        # Define max-based PRs: (key, column, filter)
        max_prs = [
            ("longest_distance_m", Activity.total_distance_m, None),
            ("longest_moving_time_s", Activity.moving_time_s, None),
            ("max_speed_mps", Activity.max_speed_mps, Activity.max_speed_mps > 0),
            ("max_hr_bpm", Activity.max_hr_bpm, Activity.max_hr_bpm > 0),
            ("biggest_elevation_gain_m", Activity.elevation_gain_m, Activity.elevation_gain_m > 0),
            ("highest_sustained_power_w", Activity.np_power_w, Activity.np_power_w > 0),
        ]

        for key, column, extra_filter in max_prs:
            query = (
                select(Activity.id, column)
                .where(Activity.user_id == user_id, column.isnot(None))
            )
            if extra_filter is not None:
                query = query.where(extra_filter)
            query = query.order_by(column.desc()).limit(1)

            result = await self._session.execute(query)
            row = result.first()
            if row is not None:
                prs[key] = {"value": row[1], "activity_id": str(row[0])}
            else:
                prs[key] = None

        # Fastest time at distance PRs
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
        """Per-route fastest times with activity title and polyline.

        For each route, finds the activity with the fastest elapsed_time_s
        and includes its title and polyline for display.
        """
        # Rank activities within each route by elapsed_time_s ASC to find the record holder
        fastest_rank = (
            func.row_number()
            .over(
                partition_by=Activity.route_id,
                order_by=Activity.elapsed_time_s.asc(),
            )
            .label("rn")
        )

        subq = (
            select(
                Activity.route_id,
                Activity.id,
                Activity.title,
                Activity.map_polyline,
                Activity.elapsed_time_s,
                fastest_rank,
            )
            .where(
                Activity.user_id == user_id,
                Activity.route_id.isnot(None),
            )
            .subquery()
        )

        # Select only the fastest activity per route (rn=1)
        result = await self._session.execute(
            select(
                subq.c.route_id,
                subq.c.id.label("activity_id"),
                subq.c.title,
                subq.c.map_polyline,
                subq.c.elapsed_time_s.label("fastest_time_s"),
            )
            .where(literal_column("rn") == 1)
            .order_by(subq.c.elapsed_time_s.asc())  # Sort by fastest time
        )

        route_prs: list[RoutePrView] = []
        for row in result.all():
            # Use activity title as route label, fallback to "Route {id}"
            route_label = row.title if row.title else f"Route {row.route_id}"
            route_prs.append(
                RoutePrView(
                    route_id=row.route_id,
                    route_label=route_label,
                    fastest_time_s=row.fastest_time_s,
                    activity_id=str(row.activity_id) if row.activity_id else None,
                    activity_title=row.title,
                    polyline=row.map_polyline,
                )
            )
        return route_prs
