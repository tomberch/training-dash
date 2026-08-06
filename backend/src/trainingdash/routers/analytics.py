"""Analytics endpoints: fitness, pmc, power-curve, records."""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import select, func

from trainingdash.auth import CurrentUser, DbSession
from trainingdash.models import Activity, ActivityPeakPower, FitnessHistory
from trainingdash.routers.serializers import _utc

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/fitness")
async def get_fitness(db: DbSession, user: CurrentUser):
    """
    Get current fitness model and recent history.

    Returns the latest fitness snapshot (PP, W', CP) and
    history of model changes over time.
    """
    # Get most recent fitness snapshot
    result = await db.execute(
        select(FitnessHistory)
        .where(FitnessHistory.user_id == user.id)
        .order_by(FitnessHistory.computed_at.desc())
        .limit(1)
    )
    current = result.scalar_one_or_none()

    # Get recent history (last 10 snapshots)
    result = await db.execute(
        select(FitnessHistory)
        .where(FitnessHistory.user_id == user.id)
        .order_by(FitnessHistory.computed_at.desc())
        .limit(10)
    )
    history = result.scalars().all()

    if current is None:
        return {
            "current": None,
            "history": [],
        }

    return {
        "current": {
            "computed_at": _utc(current.computed_at),
            "pp_watts": current.pp_watts,
            "w_prime_joules": current.w_prime_joules,
            "cp_watts": current.cp_watts,
        },
        "history": [
            {
                "computed_at": _utc(h.computed_at),
                "pp_watts": h.pp_watts,
                "w_prime_joules": h.w_prime_joules,
                "cp_watts": h.cp_watts,
            }
            for h in history
        ],
    }


@router.get("/pmc")
async def get_pmc(
    db: DbSession,
    user: CurrentUser,
    start: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end: date | None = Query(None, description="End date (YYYY-MM-DD)"),
):
    """
    Get Performance Management Chart data.

    Returns daily CTL (Chronic Training Load), ATL (Acute Training Load),
    and TSB (Training Stress Balance) values for the requested date range.

    CTL: 42-day exponentially weighted moving average of TSS (fitness)
    ATL: 7-day exponentially weighted moving average of TSS (fatigue)
    TSB: CTL - ATL (form indicator, positive = fresh, negative = tired)
    """
    from trainingdash.pmc import aggregate_daily_tss, compute_pmc

    # Default to last 12 weeks if not specified
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(weeks=12)

    # Get all activities with TSS for this user
    result = await db.execute(
        select(Activity)
        .where(Activity.user_id == user.id)
        .order_by(Activity.started_at)
    )
    activities = result.scalars().all()

    # Aggregate TSS by date
    activity_data = [{"started_at": a.started_at, "tss": a.tss} for a in activities]
    daily_tss = aggregate_daily_tss(activity_data)

    # Compute PMC
    pmc_data = compute_pmc(daily_tss, start, end)

    return pmc_data


@router.get("/power-curve")
async def get_power_curve(
    db: DbSession,
    user: CurrentUser,
    start: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end: date | None = Query(None, description="End date (YYYY-MM-DD)"),
):
    """
    Get power curve data (best power at each duration).

    Returns the user's best power at each of the 14 standard durations,
    along with the date achieved and days since that PR was set.

    Use date range params to compare periods (e.g., last 90 days vs all time).
    """
    # Build query for peaks
    query = (
        select(ActivityPeakPower, Activity.started_at)
        .join(Activity, ActivityPeakPower.activity_id == Activity.id)
        .where(Activity.user_id == user.id)
    )

    # Apply date filters if specified
    if start is not None:
        query = query.where(
            Activity.started_at >= datetime.combine(start, datetime.min.time())
        )
    if end is not None:
        query = query.where(
            Activity.started_at <= datetime.combine(end, datetime.max.time())
        )

    result = await db.execute(query)
    rows = result.all()

    # Find best at each duration
    best_by_duration: dict[int, tuple[int, date]] = {}  # duration -> (watts, achieved_date)

    for peak, started_at in rows:
        duration = peak.duration_seconds
        watts = peak.watts
        achieved_date = (
            started_at.date() if hasattr(started_at, "date") else started_at
        )

        if duration not in best_by_duration or watts > best_by_duration[duration][0]:
            best_by_duration[duration] = (watts, achieved_date)

    # Build response with days_ago
    today = date.today()
    curve = []
    for duration in sorted(best_by_duration.keys()):
        watts, achieved_date = best_by_duration[duration]
        days_ago = (today - achieved_date).days
        curve.append(
            {
                "duration_seconds": duration,
                "watts": watts,
                "achieved_date": achieved_date.isoformat(),
                "days_ago": days_ago,
            }
        )

    return curve


@router.get("/records")
async def get_records(db: DbSession, user: CurrentUser):
    """
    Get lifetime PRs and per-route PRs.

    Lifetime PRs include: longest distance, longest time, max speed, max HR,
    biggest elevation gain, highest sustained power, and fastest times at
    standard distances (5km, 10km, 40km).

    Route PRs show the fastest elapsed time on each route the user has ridden.
    """
    result = await db.execute(
        select(
            func.max(Activity.total_distance_m).label("longest_distance_m"),
            func.max(Activity.moving_time_s).label("longest_moving_time_s"),
            func.max(Activity.max_speed_mps).label("max_speed_mps"),
            func.max(Activity.max_hr_bpm).label("max_hr_bpm"),
            func.max(Activity.elevation_gain_m).label("biggest_elevation_gain_m"),
            func.max(Activity.np_power_w).label("highest_sustained_power_w"),
        ).where(Activity.user_id == user.id)
    )
    row = result.one()

    def _pr(val):
        return {"value": val} if val is not None else None

    prs = {
        "longest_distance_m": _pr(row.longest_distance_m),
        "longest_moving_time_s": _pr(row.longest_moving_time_s),
        "max_speed_mps": _pr(row.max_speed_mps),
        "max_hr_bpm": _pr(row.max_hr_bpm),
        "biggest_elevation_gain_m": _pr(row.biggest_elevation_gain_m),
        "highest_sustained_power_w": _pr(row.highest_sustained_power_w),
    }

    for target_m in [5000, 10000, 40000]:
        result = await db.execute(
            select(Activity.id, Activity.avg_speed_mps)
            .where(
                Activity.user_id == user.id,
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
            prs[key] = {"value": projected_time_s, "activity_id": str(fastest.id)}
        else:
            prs[key] = None

    # Per-route PRs: fastest elapsed_time per route for this user
    route_result = await db.execute(
        select(
            Activity.route_id,
            func.min(Activity.elapsed_time_s).label("fastest_time"),
        )
        .where(
            Activity.user_id == user.id,
            Activity.route_id.isnot(None),
        )
        .group_by(Activity.route_id)
    )
    route_rows = route_result.all()

    route_prs = []
    for row in route_rows:
        # Get the activity that holds the record + its date as a label
        pr_activity_result = await db.execute(
            select(Activity.id, Activity.started_at)
            .where(
                Activity.user_id == user.id,
                Activity.route_id == row.route_id,
                Activity.elapsed_time_s == row.fastest_time,
            )
            .order_by(Activity.started_at.asc())
            .limit(1)
        )
        pr_activity = pr_activity_result.first()
        # Get the first activity on this route for a label
        first_activity_result = await db.execute(
            select(Activity.started_at)
            .where(
                Activity.user_id == user.id,
                Activity.route_id == row.route_id,
            )
            .order_by(Activity.started_at.asc())
            .limit(1)
        )
        first_started = first_activity_result.scalar()
        route_label = (
            first_started.strftime("%Y-%m-%d")
            if first_started
            else f"Route {row.route_id}"
        )
        route_prs.append(
            {
                "route_id": row.route_id,
                "route_label": route_label,
                "fastest_time_s": row.fastest_time,
                "activity_id": str(pr_activity.id) if pr_activity else None,
            }
        )

    return {"lifetime_prs": prs, "route_prs": route_prs}
