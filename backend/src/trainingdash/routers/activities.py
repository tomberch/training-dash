"""Activity endpoints: CRUD, records, wbal, comparisons, upload, jobs."""

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, func

from trainingdash.auth import CurrentUser, DbSession
from trainingdash.models import Activity, ActivityPeakPower, Record
from trainingdash.thresholds import get_thresholds_for_date
from trainingdash.routers.datetime_utils import utc_str
from trainingdash.routers.serializers import (
    activity_detail,
    activity_summary,
    records_to_geojson,
)

router = APIRouter(prefix="/api", tags=["activities"])

# Pagination defaults
DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    total: int
    page: int
    per_page: int
    total_pages: int


class ActivityUpdateRequest(BaseModel):
    """Request body for updating an activity."""
    title: str | None = None


async def _get_owned_activity(
    db: DbSession, user: CurrentUser, activity_id: UUID
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
async def list_activities(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(DEFAULT_PAGE, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE, description="Items per page"),
):
    """List activities for the current user with pagination.
    
    Returns:
        activities: List of activity summaries
        pagination: Pagination metadata (total, page, per_page, total_pages)
    """
    # Count total activities
    count_result = await db.execute(
        select(func.count(Activity.id)).where(Activity.user_id == user.id)
    )
    total = count_result.scalar() or 0
    
    # Calculate pagination
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    offset = (page - 1) * per_page
    
    # Fetch page of activities
    result = await db.execute(
        select(Activity)
        .where(Activity.user_id == user.id)
        .order_by(Activity.started_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    activities = result.scalars().all()
    
    return {
        "activities": [activity_summary(a) for a in activities],
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        }
    }


@router.get("/activities/{activity_id}")
async def get_activity(db: DbSession, user: CurrentUser, activity_id: UUID):
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
    db: DbSession, user: CurrentUser, activity_id: UUID, request: ActivityUpdateRequest
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
    db: DbSession, user: CurrentUser, activity_id: UUID
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
async def get_activity_records(db: DbSession, user: CurrentUser, activity_id: UUID):
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
    geojson["activity_id"] = str(activity_id)
    return geojson


@router.get("/activities/{activity_id}/wbal")
async def get_activity_wbal(db: DbSession, user: CurrentUser, activity_id: UUID):
    """Get W'bal time series for an activity."""
    activity = await _get_owned_activity(db, user, activity_id)

    # Get threshold effective at activity date
    activity_date = activity.started_at.date()
    threshold = await get_thresholds_for_date(db, user.id, activity_date)

    if threshold is None or threshold.ftp_watts is None:
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
    from trainingdash.domain.wbal import compute_wbal_series

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


def _get_gps_points(records):
    """Extract GPS points with distance from records."""
    return [(r.lat, r.lon, r.distance_m) for r in records 
            if r.lat is not None and r.lon is not None]


def _haversine_distance_m(p1, p2):
    """Calculate distance between two lat/lon points in meters."""
    import math
    lat1, lon1 = math.radians(p1[0]), math.radians(p1[1])
    lat2, lon2 = math.radians(p2[0]), math.radians(p2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return 6371000 * c  # Earth radius in meters


def _is_same_direction(gps_a: list, gps_b: list) -> bool:
    """
    Check if two GPS tracks are going in the same direction.
    
    Samples points from the first 20% of track A and finds their nearest
    points in track B. If the matched distances in B are increasing,
    they're going the same direction; if decreasing, opposite.
    """
    if len(gps_a) < 10 or len(gps_b) < 10:
        return True  # Not enough data, assume same direction
    
    def find_nearest_point(target_lat, target_lon, points):
        min_dist = float('inf')
        nearest_distance_m = None
        for lat, lon, dist_m in points:
            d = _haversine_distance_m((target_lat, target_lon), (lat, lon))
            if d < min_dist:
                min_dist = d
                nearest_distance_m = dist_m
        return nearest_distance_m, min_dist
    
    # Sample points from the first 20% of track A
    sample_count = max(5, len(gps_a) // 5)
    sample_indices = [i * len(gps_a) // (sample_count * 5) for i in range(sample_count)]
    
    # For each sampled point from A, find nearest point in B
    matched_distances_b = []
    for idx in sample_indices:
        lat_a, lon_a, dist_a = gps_a[idx]
        nearest_dist_b, gps_dist = find_nearest_point(lat_a, lon_a, gps_b)
        if nearest_dist_b is not None and gps_dist < 100:  # Within 100m
            matched_distances_b.append((dist_a, nearest_dist_b))
    
    if len(matched_distances_b) < 3:
        return True  # Not enough matched points, assume same direction
    
    # Check if distances in B are increasing (same direction) or decreasing (opposite)
    increasing_count = 0
    decreasing_count = 0
    for i in range(1, len(matched_distances_b)):
        _, prev_b = matched_distances_b[i - 1]
        _, curr_b = matched_distances_b[i]
        if curr_b > prev_b:
            increasing_count += 1
        elif curr_b < prev_b:
            decreasing_count += 1
    
    return increasing_count >= decreasing_count


@router.get("/activities/{activity_id}/same-route")
async def get_same_route_activities(
    db: DbSession, user: CurrentUser, activity_id: UUID
):
    """Get other activities on the same route, filtered to same direction only."""
    activity = await _get_owned_activity(db, user, activity_id)
    if activity.route_id is None:
        return {"route_id": None, "activities": []}
    
    # Get all activities on the same route
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
    
    if not others:
        return {"route_id": activity.route_id, "activities": []}
    
    # Get GPS records for the base activity
    base_records_result = await db.execute(
        select(Record)
        .where(Record.activity_id == activity_id)
        .order_by(Record.timestamp)
    )
    base_records = base_records_result.scalars().all()
    base_gps = _get_gps_points(base_records)
    
    if len(base_gps) < 10:
        # Not enough GPS data to determine direction, return all
        return {
            "route_id": activity.route_id,
            "activities": [activity_summary(a) for a in others],
        }
    
    # Filter to only same-direction activities
    same_direction_activities = []
    for other in others:
        other_records_result = await db.execute(
            select(Record)
            .where(Record.activity_id == other.id)
            .order_by(Record.timestamp)
        )
        other_records = other_records_result.scalars().all()
        other_gps = _get_gps_points(other_records)
        
        if _is_same_direction(base_gps, other_gps):
            same_direction_activities.append(other)
    
    return {
        "route_id": activity.route_id,
        "activities": [activity_summary(a) for a in same_direction_activities],
    }


@router.get("/activities/{activity_id}/compare")
async def compare_activities(
    db: DbSession,
    user: CurrentUser,
    activity_id: UUID,
    other_activity_id: UUID = Query(alias="other"),
):
    """Compare two activities on the same route."""
    activity_a = await _get_owned_activity(db, user, activity_id)
    activity_b = await _get_owned_activity(db, user, other_activity_id)

    if activity_a.route_id is None or activity_a.route_id != activity_b.route_id:
        return {"comparable": False, "gap_series": [], "other_geojson": None, "reason": "different_routes"}

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

    # Verify same direction (should already be filtered, but double-check)
    gps_a = _get_gps_points(records_a)
    gps_b = _get_gps_points(records_b)
    
    if not _is_same_direction(gps_a, gps_b):
        return {
            "comparable": False, 
            "gap_series": [], 
            "other_geojson": None, 
            "reason": "opposite_direction",
        }

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

    from trainingdash.domain.resampler import compute_time_gap_series

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
    return {"id": str(activity.id), "started_at": utc_str(activity.started_at)}


@router.get("/jobs/{job_id}")
async def get_job_status(user: CurrentUser, job_id: str):
    """Get the status of an ingest job."""
    from trainingdash.jobs import get_job_status as _get_job_status

    return await _get_job_status(job_id)



@router.delete("/activities/{activity_id}", status_code=204)
async def delete_activity(
    db: DbSession,
    user: CurrentUser,
    activity_id: UUID,
):
    """
    Permanently delete an activity owned by the current user.

    Cascade constraints remove Records, Laps, and ActivityPeakPower automatically.
    Route ride_count and first_seen_activity_id are repaired synchronously before
    deletion to avoid FK violations (routes.first_seen_activity_id has no ondelete).
    A background job then recomputes the fitness model and breakthrough flags.
    """
    from trainingdash.models import Route
    from trainingdash.jobs import enqueue_recalculate_after_delete_job

    activity = await _get_owned_activity(db, user, activity_id)

    # --- Route maintenance and activity deletion ---
    # routes.first_seen_activity_id has ON DELETE SET NULL, so deleting the
    # activity automatically nulls that field. We only need to maintain
    # ride_count and clean up orphan routes ourselves.
    from sqlalchemy import text as sql_text

    if activity.route_id is not None:
        route_result = await db.execute(
            select(Route).where(Route.id == activity.route_id)
        )
        route = route_result.scalar_one_or_none()
        if route is not None:
            if route.ride_count <= 1:
                # Sole activity — delete the route after nulling activity.route_id
                # (activities.route_id → routes.id has no ondelete; null it first).
                await db.execute(
                    sql_text("UPDATE activities SET route_id = NULL WHERE id = :aid"),
                    {"aid": activity.id},
                )
                await db.execute(
                    sql_text("DELETE FROM routes WHERE id = :rid"),
                    {"rid": route.id},
                )
            else:
                # Decrement ride_count; ON DELETE SET NULL handles first_seen repair.
                await db.execute(
                    sql_text(
                        "UPDATE routes SET ride_count = ride_count - 1 WHERE id = :rid"
                    ),
                    {"rid": route.id},
                )
                await db.execute(
                    sql_text("UPDATE activities SET route_id = NULL WHERE id = :aid"),
                    {"aid": activity.id},
                )

    # Delete the activity (cascades Records, Laps, ActivityPeakPower)
    await db.execute(
        sql_text("DELETE FROM activities WHERE id = :aid"),
        {"aid": activity.id},
    )
    await db.commit()

    # --- Enqueue async recalculation (fitness model + breakthrough flags) ---
    await enqueue_recalculate_after_delete_job(user.id)
