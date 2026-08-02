"""Activity endpoints: CRUD, records, wbal, comparisons, upload, jobs."""

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, func

from trainingdash.auth import CurrentUser, DbSession
from trainingdash.models import Activity, ActivityPeakPower, Record, ThresholdHistory
from trainingdash.routers.serializers import (
    activity_detail,
    activity_summary,
    records_to_geojson,
)

router = APIRouter(prefix="/api", tags=["activities"])


class ActivityUpdateRequest(BaseModel):
    """Request body for updating an activity."""
    title: str | None = None


async def _get_owned_activity(
    db: DbSession, user: CurrentUser, activity_id: int
) -> Activity:
    """Fetch an activity owned by the current user or raise 404."""
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == user.id)
    )
    activity = result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found"
        )
    return activity


@router.get("/activities")
async def list_activities(db: DbSession, user: CurrentUser):
    """List all activities for the current user."""
    result = await db.execute(
        select(Activity)
        .where(Activity.user_id == user.id)
        .order_by(Activity.started_at.desc())
    )
    activities = result.scalars().all()
    return [activity_summary(a) for a in activities]


@router.get("/activities/{activity_id}")
async def get_activity(db: DbSession, user: CurrentUser, activity_id: int):
    """Get full details for an activity including peak powers."""
    activity = await _get_owned_activity(db, user, activity_id)
    result = activity_detail(activity)

    # Fetch peak powers for this activity
    peaks_result = await db.execute(
        select(ActivityPeakPower)
        .where(ActivityPeakPower.activity_id == activity_id)
        .order_by(ActivityPeakPower.duration_seconds)
    )
    peaks = peaks_result.scalars().all()

    # Fetch all-time PRs for this user at each duration
    all_time_prs: dict[int, int] = {}
    for p in peaks:
        pr_result = await db.execute(
            select(func.max(ActivityPeakPower.watts))
            .join(Activity, ActivityPeakPower.activity_id == Activity.id)
            .where(
                Activity.user_id == user.id,
                ActivityPeakPower.duration_seconds == p.duration_seconds,
            )
        )
        max_watts = pr_result.scalar()
        if max_watts:
            all_time_prs[p.duration_seconds] = max_watts

    result["peaks"] = [
        {
            "duration_seconds": p.duration_seconds,
            "watts": p.watts,
            "all_time_pr": all_time_prs.get(p.duration_seconds),
            "pct_of_pr": round(p.watts / all_time_prs[p.duration_seconds] * 100, 1)
            if all_time_prs.get(p.duration_seconds)
            else None,
            "is_pr": p.watts == all_time_prs.get(p.duration_seconds),
        }
        for p in peaks
    ]

    return result


@router.patch("/activities/{activity_id}")
async def update_activity(
    db: DbSession, user: CurrentUser, activity_id: int, request: ActivityUpdateRequest
):
    """Update an activity (currently only title)."""
    activity = await _get_owned_activity(db, user, activity_id)
    
    if request.title is not None:
        activity.title = request.title
        activity.title_source = "manual"
    
    await db.commit()
    await db.refresh(activity)
    
    return activity_summary(activity)


@router.post("/activities/{activity_id}/generate-title")
async def generate_activity_title_endpoint(
    db: DbSession, user: CurrentUser, activity_id: int
):
    """Generate title for an activity using geocoding.
    
    This is useful for activities that were bulk-imported and skipped
    title generation due to rate limits.
    """
    activity = await _get_owned_activity(db, user, activity_id)
    
    # Don't overwrite manually set titles
    if activity.title_source == "manual":
        return activity_summary(activity)
    
    # Get GPS records
    result = await db.execute(
        select(Record)
        .where(Record.activity_id == activity_id)
        .order_by(Record.timestamp)
    )
    records = result.scalars().all()
    
    # Convert to dict format for title generator
    records_dicts = [
        {"lat": r.lat, "lon": r.lon, "altitude_m": r.altitude_m, "distance_m": r.distance_m}
        for r in records
    ]
    
    # Generate title
    from trainingdash.title_generator import generate_activity_title
    
    title = await generate_activity_title(records_dicts, activity.started_at)
    
    if title:
        activity.title = title
        activity.title_source = "auto"
        await db.commit()
        await db.refresh(activity)
    
    return activity_summary(activity)


@router.get("/activities/{activity_id}/records")
async def get_activity_records(db: DbSession, user: CurrentUser, activity_id: int):
    """Get GPS and sensor records for an activity as GeoJSON."""
    await _get_owned_activity(db, user, activity_id)
    result = await db.execute(
        select(Record)
        .where(Record.activity_id == activity_id)
        .order_by(Record.timestamp)
    )
    records = result.scalars().all()
    geojson = records_to_geojson(
        records,
        [
            "timestamp",
            "distance_m",
            "hr_bpm",
            "power_w",
            "speed_mps",
            "altitude_m",
            "cadence_rpm",
        ],
    )
    geojson["activity_id"] = activity_id
    return geojson


@router.get("/activities/{activity_id}/wbal")
async def get_activity_wbal(db: DbSession, user: CurrentUser, activity_id: int):
    """Get W'bal time series for an activity."""
    activity = await _get_owned_activity(db, user, activity_id)

    # Get threshold effective at activity date
    activity_date = activity.started_at.date()
    result = await db.execute(
        select(ThresholdHistory)
        .where(
            ThresholdHistory.user_id == user.id,
            ThresholdHistory.effective_date <= activity_date,
        )
        .order_by(ThresholdHistory.effective_date.desc())
        .limit(1)
    )
    threshold = result.scalar_one_or_none()

    if threshold is None:
        return {"wbal_series": [], "w_prime_joules": None, "ftp_watts": None}

    ftp = threshold.ftp_watts
    w_prime = ftp * 60  # Estimate W' as FTP * 60 joules

    # Get records with power data
    result = await db.execute(
        select(Record)
        .where(Record.activity_id == activity_id)
        .order_by(Record.timestamp)
    )
    records = result.scalars().all()

    # Compute W'bal series using differential equation model
    from trainingdash.wbal import compute_wbal_series

    power_values = [r.power_w for r in records]
    first_ts = records[0].timestamp if records else None

    wbal_result = compute_wbal_series(power_values, ftp, w_prime)

    # Build response with timestamps
    series = []
    for i, (record, wbal) in enumerate(zip(records, wbal_result["series"])):
        elapsed_s = (record.timestamp - first_ts).total_seconds() if first_ts else 0
        series.append(
            {
                "elapsed_s": elapsed_s,
                "distance_m": record.distance_m or 0,
                "wbal_joules": wbal,
                "wbal_pct": (wbal / w_prime * 100) if w_prime > 0 else 0,
            }
        )

    return {
        "wbal_series": series,
        "w_prime_joules": w_prime,
        "ftp_watts": ftp,
        "wbal_min_joules": activity.wbal_min_joules,
        "wbal_min_pct": activity.wbal_min_pct,
    }


@router.get("/activities/{activity_id}/same-route")
async def get_same_route_activities(
    db: DbSession, user: CurrentUser, activity_id: int
):
    """Get other activities on the same route."""
    activity = await _get_owned_activity(db, user, activity_id)
    if activity.route_id is None:
        return {"route_id": None, "activities": []}
    result = await db.execute(
        select(Activity)
        .where(
            Activity.route_id == activity.route_id,
            Activity.user_id == user.id,
            Activity.id != activity_id,
        )
        .order_by(Activity.started_at.desc())
    )
    others = result.scalars().all()
    return {
        "route_id": activity.route_id,
        "activities": [activity_summary(a) for a in others],
    }


@router.get("/activities/{activity_id}/compare")
async def compare_activities(
    db: DbSession,
    user: CurrentUser,
    activity_id: int,
    other_activity_id: int = Query(alias="other"),
):
    """Compare two activities on the same route."""
    activity_a = await _get_owned_activity(db, user, activity_id)
    activity_b = await _get_owned_activity(db, user, other_activity_id)

    if activity_a.route_id is None or activity_a.route_id != activity_b.route_id:
        return {"comparable": False, "gap_series": [], "other_geojson": None}

    records_a_result = await db.execute(
        select(Record)
        .where(Record.activity_id == activity_id)
        .order_by(Record.timestamp)
    )
    records_b_result = await db.execute(
        select(Record)
        .where(Record.activity_id == other_activity_id)
        .order_by(Record.timestamp)
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

    from trainingdash.resampler import compute_time_gap_series

    gap_series = compute_time_gap_series(
        to_resample_input(records_a, first_ts_a),
        to_resample_input(records_b, first_ts_b),
    )

    other_geojson = records_to_geojson(
        records_b, ["timestamp", "distance_m", "speed_mps"]
    )

    return {
        "comparable": True,
        "gap_series": gap_series,
        "other_geojson": other_geojson,
    }


@router.post("/upload")
async def upload_activity(
    db: DbSession, user: CurrentUser, file: UploadFile = File(...)
):
    """Upload a FIT file for processing."""
    fit_bytes = await file.read()
    source_ref = file.filename or "upload.fit"

    from trainingdash.jobs import enqueue_ingest_job

    job_id = await enqueue_ingest_job(user.id, fit_bytes, "upload", source_ref)
    if job_id is not None:
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"job_id": job_id, "source_ref": source_ref},
        )

    from trainingdash.ingest import ingest_fit

    activity = await ingest_fit(db, user.id, fit_bytes, "upload", source_ref)
    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to parse FIT file"
        )
    return {"id": activity.id, "started_at": activity.started_at.isoformat()}


@router.get("/jobs/{job_id}")
async def get_job_status(user: CurrentUser, job_id: str):
    """Get the status of an ingest job."""
    from trainingdash.jobs import get_job_status as _get_job_status

    return await _get_job_status(job_id)
