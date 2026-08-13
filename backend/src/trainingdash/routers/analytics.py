"""Analytics endpoints: fitness, pmc, power-curve, records."""

from datetime import date, timedelta

from fastapi import APIRouter, Query

from trainingdash.auth import CurrentUser
from trainingdash.dependencies import AnalyticsRepoD
from trainingdash.routers.datetime_utils import utc_str

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/fitness")
async def get_fitness(repo: AnalyticsRepoD, user: CurrentUser):
    """Current fitness model and recent history."""
    current = await repo.get_latest_fitness(user.id)
    history = await repo.get_fitness_history(user.id, limit=10)

    if current is None:
        return {"current": None, "history": []}

    return {
        "current": {
            "computed_at": utc_str(current.computed_at),
            "pp_watts": current.pp_watts,
            "w_prime_joules": current.w_prime_joules,
            "cp_watts": current.cp_watts,
        },
        "history": [
            {
                "computed_at": utc_str(h.computed_at),
                "pp_watts": h.pp_watts,
                "w_prime_joules": h.w_prime_joules,
                "cp_watts": h.cp_watts,
            }
            for h in history
        ],
    }


@router.get("/pmc")
async def get_pmc(
    repo: AnalyticsRepoD,
    user: CurrentUser,
    start: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end: date | None = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Daily CTL/ATL/TSB for the requested date range (default: last 12 weeks)."""
    from trainingdash.domain.pmc import aggregate_daily_tss, compute_pmc

    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(weeks=12)

    activities = await repo.list_activities_for_pmc(user.id)
    daily_tss = aggregate_daily_tss([{"started_at": a.started_at, "tss": a.tss} for a in activities])
    return compute_pmc(daily_tss, start, end)


@router.get("/power-curve")
async def get_power_curve(
    repo: AnalyticsRepoD,
    user: CurrentUser,
    start: date | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end: date | None = Query(None, description="End date (YYYY-MM-DD)"),
):
    """Best power at each duration, with date achieved and days since."""
    rows = await repo.get_power_curve(user.id, start, end)

    best_by_duration: dict[int, tuple[int, date]] = {}
    for peak, started_at in rows:
        duration = peak.duration_seconds
        watts = peak.watts
        achieved_date = started_at.date() if hasattr(started_at, "date") else started_at
        if duration not in best_by_duration or watts > best_by_duration[duration][0]:
            best_by_duration[duration] = (watts, achieved_date)

    today = date.today()
    return [
        {
            "duration_seconds": duration,
            "watts": watts,
            "achieved_date": achieved_date.isoformat(),
            "days_ago": (today - achieved_date).days,
        }
        for duration, (watts, achieved_date) in sorted(best_by_duration.items())
    ]


@router.get("/records")
async def get_records(repo: AnalyticsRepoD, user: CurrentUser):
    """Lifetime PRs and per-route PRs."""
    view = await repo.get_records(user.id)
    return {
        "lifetime_prs": view.lifetime_prs,
        "route_prs": [
            {
                "route_id": r.route_id,
                "route_label": r.route_label,
                "fastest_time_s": r.fastest_time_s,
                "activity_id": r.activity_id,
                "activity_title": r.activity_title,
                "polyline": r.polyline,
                "started_at": r.started_at.isoformat() if r.started_at else None,
            }
            for r in view.route_prs
        ],
    }
