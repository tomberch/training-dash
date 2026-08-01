from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from fitter.auth import CurrentUser, DbSession, LoginRequest, create_session_cookie, verify_password
from fitter.db import Base, async_session, engine
from fitter.models import Activity, Lap, Record, User


def create_app() -> FastAPI:
    app = FastAPI(title="Fitter")
    app.post("/login")(login)
    app.get("/activities")(list_activities)
    app.get("/activities/{activity_id}")(get_activity)
    app.get("/activities/{activity_id}/records")(get_activity_records)
    app.get("/activities/{activity_id}/same-route")(get_same_route_activities)
    app.get("/activities/{activity_id}/compare")(compare_activities)
    app.get("/records")(get_records)
    app.post("/upload")(upload_activity)
    app.get("/jobs/{job_id}")(get_job_status)
    return app


async def login(db: DbSession, request: LoginRequest):
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    cookie = create_session_cookie(user.id)
    response = JSONResponse({"user_id": user.id, "username": user.username})
    response.set_cookie("session", cookie, httponly=True, samesite="lax")
    return response


def _activity_summary(a: Activity) -> dict[str, Any]:
    return {
        "id": a.id,
        "started_at": a.started_at.isoformat(),
        "total_distance_m": a.total_distance_m,
        "moving_time_s": a.moving_time_s,
        "elapsed_time_s": a.elapsed_time_s,
        "elevation_gain_m": a.elevation_gain_m,
        "avg_speed_mps": a.avg_speed_mps,
        "avg_hr_bpm": a.avg_hr_bpm,
        "avg_power_w": a.avg_power_w,
        "max_speed_mps": a.max_speed_mps,
        "max_hr_bpm": a.max_hr_bpm,
    }


async def _get_owned_activity(db: DbSession, user: CurrentUser, activity_id: int) -> Activity:
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == user.id)
    )
    activity = result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return activity


def _records_to_geojson(records: list[Record], props_keys: list[str]) -> dict:
    features = []
    for r in records:
        props = {key: getattr(r, key) for key in props_keys}
        if "timestamp" in props and props["timestamp"] is not None:
            props["timestamp"] = props["timestamp"].isoformat()
        if r.lat is not None and r.lon is not None:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
                "properties": props,
            })
        else:
            features.append({
                "type": "Feature",
                "geometry": None,
                "properties": props,
            })
    return {"type": "FeatureCollection", "features": features}


async def list_activities(db: DbSession, user: CurrentUser):
    result = await db.execute(
        select(Activity)
        .where(Activity.user_id == user.id)
        .order_by(Activity.started_at.desc())
    )
    activities = result.scalars().all()
    return [_activity_summary(a) for a in activities]


async def get_activity(db: DbSession, user: CurrentUser, activity_id: int):
    activity = await _get_owned_activity(db, user, activity_id)
    return _activity_summary(activity)


async def get_activity_records(db: DbSession, user: CurrentUser, activity_id: int):
    await _get_owned_activity(db, user, activity_id)
    result = await db.execute(
        select(Record).where(Record.activity_id == activity_id).order_by(Record.timestamp)
    )
    records = result.scalars().all()
    geojson = _records_to_geojson(records, [
        "timestamp", "distance_m", "hr_bpm", "power_w", "speed_mps", "altitude_m", "cadence_rpm"
    ])
    geojson["activity_id"] = activity_id
    return geojson


async def upload_activity(db: DbSession, user: CurrentUser, file: UploadFile = File(...)):
    fit_bytes = await file.read()
    source_ref = file.filename or "upload.fit"

    from fitter.jobs import enqueue_ingest_job

    job_id = await enqueue_ingest_job(user.id, fit_bytes, "upload", source_ref)
    if job_id is not None:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"job_id": job_id, "source_ref": source_ref},
        )

    from fitter.ingest import ingest_fit
    activity = await ingest_fit(db, user.id, fit_bytes, "upload", source_ref)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to parse FIT file")
    return {"id": activity.id, "started_at": activity.started_at.isoformat()}


async def get_job_status(user: CurrentUser, job_id: str):
    """Get the status of an ingest job."""
    from fitter.jobs import get_job_status as _get_job_status
    return await _get_job_status(job_id)


async def get_same_route_activities(db: DbSession, user: CurrentUser, activity_id: int):
    activity = await _get_owned_activity(db, user, activity_id)
    if activity.route_id is None:
        return {"route_id": None, "activities": []}
    result = await db.execute(
        select(Activity).where(
            Activity.route_id == activity.route_id,
            Activity.user_id == user.id,
            Activity.id != activity_id,
        ).order_by(Activity.started_at.desc())
    )
    others = result.scalars().all()
    return {
        "route_id": activity.route_id,
        "activities": [_activity_summary(a) for a in others],
    }


async def compare_activities(
    db: DbSession, user: CurrentUser, activity_id: int, other_activity_id: int = Query(alias="other")
):
    activity_a = await _get_owned_activity(db, user, activity_id)
    activity_b = await _get_owned_activity(db, user, other_activity_id)

    if activity_a.route_id is None or activity_a.route_id != activity_b.route_id:
        return {"comparable": False, "gap_series": [], "other_geojson": None}

    records_a_result = await db.execute(
        select(Record).where(Record.activity_id == activity_id).order_by(Record.timestamp)
    )
    records_b_result = await db.execute(
        select(Record).where(Record.activity_id == other_activity_id).order_by(Record.timestamp)
    )
    records_a = records_a_result.scalars().all()
    records_b = records_b_result.scalars().all()

    first_ts_a = records_a[0].timestamp if records_a else None
    first_ts_b = records_b[0].timestamp if records_b else None

    def to_resample_input(records, first_ts):
        return [
            {
                "distance_m": r.distance_m,
                "timestamp_s": (r.timestamp - first_ts).total_seconds(),
            }
            for r in records
        ]

    from fitter.resampler import compute_time_gap_series
    gap_series = compute_time_gap_series(
        to_resample_input(records_a, first_ts_a),
        to_resample_input(records_b, first_ts_b),
    )

    other_geojson = _records_to_geojson(records_b, ["timestamp", "distance_m", "speed_mps"])

    return {
        "comparable": True,
        "gap_series": gap_series,
        "other_geojson": other_geojson,
    }


async def get_records(db: DbSession, user: CurrentUser):
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
            select(Activity.id, Activity.avg_speed_mps).where(
                Activity.user_id == user.id,
                Activity.total_distance_m >= target_m,
                Activity.avg_speed_mps > 0,
            ).order_by(Activity.avg_speed_mps.desc()).limit(1)
        )
        fastest = result.first()
        key = f"fastest_{target_m}_m"
        if fastest is not None:
            projected_time_s = target_m / fastest.avg_speed_mps
            prs[key] = {"value": projected_time_s, "activity_id": fastest.id}
        else:
            prs[key] = None

    # Per-route PRs: fastest elapsed_time per route for this user
    route_result = await db.execute(
        select(
            Activity.route_id,
            func.min(Activity.elapsed_time_s).label("fastest_time"),
        ).where(
            Activity.user_id == user.id,
            Activity.route_id.isnot(None),
        ).group_by(Activity.route_id)
    )
    route_rows = route_result.all()

    route_prs = []
    for row in route_rows:
        # Get the activity that holds the record + its date as a label
        pr_activity_result = await db.execute(
            select(Activity.id, Activity.started_at).where(
                Activity.user_id == user.id,
                Activity.route_id == row.route_id,
                Activity.elapsed_time_s == row.fastest_time,
            ).order_by(Activity.started_at.asc()).limit(1)
        )
        pr_activity = pr_activity_result.first()
        # Get the first activity on this route for a label
        first_activity_result = await db.execute(
            select(Activity.started_at).where(
                Activity.user_id == user.id,
                Activity.route_id == row.route_id,
            ).order_by(Activity.started_at.asc()).limit(1)
        )
        first_started = first_activity_result.scalar()
        route_label = first_started.strftime("%Y-%m-%d") if first_started else f"Route {row.route_id}"
        route_prs.append({
            "route_id": row.route_id,
            "route_label": route_label,
            "fastest_time_s": row.fastest_time,
            "activity_id": pr_activity.id if pr_activity else None,
        })

    return {"lifetime_prs": prs, "route_prs": route_prs}


app = create_app()