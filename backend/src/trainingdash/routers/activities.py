"""Activity endpoints: CRUD, records, wbal, comparisons, upload, jobs."""

from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from trainingdash.auth import CurrentUser, DbSession
from trainingdash.dependencies import ActivityRepoD, BikeRepoD, DeleteActivityD, ThresholdRepoD
from trainingdash.domain.activity_type import validate_activity_type
from trainingdash.domain.fit_modifier import FitModifications
from trainingdash.repositories.postgres.models import Activity, ActivityPeakPower, Record
from trainingdash.routers.datetime_utils import utc_str
from trainingdash.routers.serializers import (
    activity_detail,
    activity_summary,
    records_to_geojson,
)
from trainingdash.use_cases.upload_to_provider import (
    ActivityNotFoundError,
    CredentialsDecryptError,
    CredentialsNotFoundError,
    FitModifyError,
    NoFitFileError,
    Provider,
    ProviderUploadError,
    UploadToProvider,
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
    activity_type: str | None = None
    bike_id: int | None = None  # Set to update, explicitly set to null to remove


class UploadToProviderRequest(BaseModel):
    """Request body for uploading an activity to a provider."""

    provider: Provider
    device_product_id: int | None = None  # Optional device spoofing


async def _get_owned_activity(repo: ActivityRepoD, user: CurrentUser, activity_id: UUID) -> Activity:
    """Fetch an activity owned by the current user or raise 404."""
    activity = await repo.get_by_id(activity_id, user.id)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return activity


@router.get("/activities")
async def list_activities(
    repo: ActivityRepoD,
    user: CurrentUser,
    page: int = Query(DEFAULT_PAGE, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE, description="Items per page"),
    activity_type: str | None = Query(None, description="Filter by activity type (empty string for unclassified)"),
):
    """List activities for the current user with pagination.

    Returns:
        activities: List of activity summaries
        pagination: Pagination metadata (total, page, per_page, total_pages)
    """
    # Count total activities
    total = await repo.count_for_user(user.id, activity_type=activity_type)

    # Calculate pagination
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    offset = (page - 1) * per_page

    # Fetch page of activities
    activities = await repo.list_for_user(user.id, limit=per_page, offset=offset, activity_type=activity_type)

    return {
        "activities": [activity_summary(a) for a in activities],
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
    }


@router.get("/activities/{activity_id}")
async def get_activity(db: DbSession, repo: ActivityRepoD, user: CurrentUser, activity_id: UUID):
    """Get full details for an activity including peak powers."""
    activity = await _get_owned_activity(repo, user, activity_id)
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
    db: DbSession,
    repo: ActivityRepoD,
    bike_repo: BikeRepoD,
    user: CurrentUser,
    activity_id: UUID,
    request: ActivityUpdateRequest,
):
    """Update an activity (title, activity_type, and/or bike_id)."""
    activity = await _get_owned_activity(repo, user, activity_id)

    if request.title is not None:
        activity.title = request.title
        activity.title_source = "manual"

    if request.activity_type is not None:
        try:
            activity.activity_type = validate_activity_type(request.activity_type)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    # Handle bike_id changes
    # Use model_dump to distinguish "not provided" from "explicitly set to null"
    if "bike_id" in request.model_dump(exclude_unset=True):
        new_bike_id = request.bike_id
        old_bike_id = activity.bike_id
        activity_distance = activity.total_distance_m or 0

        # Validate new bike belongs to user (if not removing)
        if new_bike_id is not None:
            new_bike = await bike_repo.get_by_id(new_bike_id, user.id)
            if new_bike is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bike not found or not owned by user",
                )
            if new_bike.retired_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot assign a retired bike to an activity",
                )

        # Update bike distance totals if bike changed
        if old_bike_id != new_bike_id and activity_distance > 0:
            # Subtract from old bike
            if old_bike_id is not None:
                await bike_repo.update_distance(old_bike_id, user.id, -activity_distance)
            # Add to new bike
            if new_bike_id is not None:
                await bike_repo.update_distance(new_bike_id, user.id, activity_distance)

        activity.bike_id = new_bike_id

    await db.commit()
    await db.refresh(activity)

    return activity_summary(activity)


@router.post("/activities/{activity_id}/generate-title")
async def generate_activity_title_endpoint(db: DbSession, repo: ActivityRepoD, user: CurrentUser, activity_id: UUID):
    """Generate title for an activity using geocoding.

    This is useful for activities that were bulk-imported and skipped
    title generation due to rate limits.
    """
    activity = await _get_owned_activity(repo, user, activity_id)

    # Don't overwrite manually set titles
    if activity.title_source == "manual":
        return activity_summary(activity)

    # Get GPS records
    result = await db.execute(select(Record).where(Record.activity_id == activity_id).order_by(Record.timestamp))
    records = result.scalars().all()

    # Convert to dict format for title generator
    records_dicts = [
        {"lat": r.lat, "lon": r.lon, "altitude_m": r.altitude_m, "distance_m": r.distance_m} for r in records
    ]

    # Create geocoding service via the single wiring point in dependencies.py
    from trainingdash.dependencies import get_geocoding_service
    from trainingdash.domain.title_generator import generate_activity_title

    geocoding = get_geocoding_service(db)

    title = await generate_activity_title(records_dicts, activity.started_at, geocoding=geocoding)

    if title:
        activity.title = title
        activity.title_source = "auto"
        await db.commit()
        await db.refresh(activity)

    return activity_summary(activity)


@router.get("/activities/{activity_id}/records")
async def get_activity_records(db: DbSession, repo: ActivityRepoD, user: CurrentUser, activity_id: UUID):
    """Get GPS and sensor records for an activity as GeoJSON."""
    await _get_owned_activity(repo, user, activity_id)
    result = await db.execute(select(Record).where(Record.activity_id == activity_id).order_by(Record.timestamp))
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
async def get_activity_wbal(
    db: DbSession, repo: ActivityRepoD, threshold_repo: ThresholdRepoD, user: CurrentUser, activity_id: UUID
):
    """Get W'bal time series for an activity."""
    activity = await _get_owned_activity(repo, user, activity_id)

    # Get threshold effective at activity date
    activity_date = activity.started_at.date()
    threshold = await threshold_repo.get_for_date(user.id, activity_date)

    if threshold is None or threshold.ftp_watts is None:
        return {"wbal_series": [], "w_prime_joules": None, "ftp_watts": None}

    ftp = threshold.ftp_watts
    w_prime = ftp * 60  # Estimate W' as FTP * 60 joules

    # Get records with power data
    result = await db.execute(select(Record).where(Record.activity_id == activity_id).order_by(Record.timestamp))
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


@router.get("/activities/{activity_id}/same-route")
async def get_same_route_activities(db: DbSession, repo: ActivityRepoD, user: CurrentUser, activity_id: UUID):
    """Get other activities on the same route, filtered to same direction only.

    Uses dual-bearing comparison (25% and 75%) for direction detection.
    This catches opposite-direction loops where both directions initially
    head the same way but diverge later.
    """
    from trainingdash.domain.direction import bearings_match

    activity = await _get_owned_activity(repo, user, activity_id)
    if activity.route_id is None:
        return {"route_id": None, "activities": []}

    # Get all activities on the same route
    others = await repo.list_by_route(activity.route_id, user.id, exclude_activity_id=activity_id)

    if not others:
        return {"route_id": activity.route_id, "activities": []}

    # Filter to same-direction activities using precomputed bearings (25% and 75%)
    same_direction_activities = [
        a
        for a in others
        if bearings_match(
            activity.direction_bearing,
            a.direction_bearing,
            activity.direction_bearing_75,
            a.direction_bearing_75,
        )
    ]

    return {
        "route_id": activity.route_id,
        "activities": [activity_summary(a) for a in same_direction_activities],
    }


@router.get("/activities/{activity_id}/compare")
async def compare_activities(
    db: DbSession,
    repo: ActivityRepoD,
    user: CurrentUser,
    activity_id: UUID,
    other_activity_id: UUID = Query(alias="other"),
):
    """Compare two activities on the same route."""
    from trainingdash.domain.direction import bearings_match

    activity_a = await _get_owned_activity(repo, user, activity_id)
    activity_b = await _get_owned_activity(repo, user, other_activity_id)

    if activity_a.route_id is None or activity_a.route_id != activity_b.route_id:
        return {"comparable": False, "gap_series": [], "other_geojson": None, "reason": "different_routes"}

    # Verify same direction using precomputed bearings (25% and 75%)
    if not bearings_match(
        activity_a.direction_bearing,
        activity_b.direction_bearing,
        activity_a.direction_bearing_75,
        activity_b.direction_bearing_75,
    ):
        return {
            "comparable": False,
            "gap_series": [],
            "other_geojson": None,
            "reason": "opposite_direction",
        }

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

    from trainingdash.domain.resampler import compute_time_gap_series

    gap_series = compute_time_gap_series(
        to_resample_input(records_a, first_ts_a),
        to_resample_input(records_b, first_ts_b),
    )

    other_geojson = records_to_geojson(records_b, ["timestamp", "distance_m", "speed_mps"])

    return {
        "comparable": True,
        "gap_series": gap_series,
        "other_geojson": other_geojson,
    }


@router.post("/upload")
async def upload_activity(db: DbSession, user: CurrentUser, file: UploadFile = File(...)):
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

    from trainingdash.use_cases import IngestActivity

    use_case = IngestActivity(db)
    activity = await use_case.execute(user.id, fit_bytes, "upload", source_ref)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to parse FIT file")
    return {"id": str(activity.id), "started_at": utc_str(activity.started_at)}


@router.get("/jobs/{job_id}")
async def get_job_status(user: CurrentUser, job_id: str):
    """Get the status of an ingest job."""
    from trainingdash.jobs import get_job_status as _get_job_status

    return await _get_job_status(job_id)


@router.delete("/activities/{activity_id}", status_code=204)
async def delete_activity(
    user: CurrentUser,
    activity_id: UUID,
    delete_use_case: DeleteActivityD,
):
    """
    Permanently delete an activity owned by the current user.

    Cascade constraints remove Records, Laps, and ActivityPeakPower automatically.
    Route ride_count and first_seen_activity_id are repaired synchronously before
    deletion to avoid FK violations (routes.first_seen_activity_id has no ondelete).
    A background job then recomputes the fitness model and breakthrough flags.
    """
    deleted = await delete_use_case.execute(user.id, activity_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")


# =============================================================================
# Activity-Event Quick-Link Endpoints
# =============================================================================


@router.get("/activities/{activity_id}/available-events")
async def get_available_events(
    db: DbSession,
    repo: ActivityRepoD,
    user: CurrentUser,
    activity_id: UUID,
):
    """
    Get events that this activity could be linked to.

    Returns events where the activity's date falls within the event's date range.
    """
    from trainingdash.repositories.postgres.models import RideEvent

    activity = await _get_owned_activity(repo, user, activity_id)
    if activity.started_at is None:
        return {"events": []}

    activity_date = activity.started_at.date()

    # Find events where activity date is within event's date range
    result = await db.execute(
        select(RideEvent)
        .where(
            RideEvent.user_id == user.id,
            RideEvent.start_date <= activity_date,
            RideEvent.end_date >= activity_date,
        )
        .order_by(RideEvent.start_date.desc())
    )
    events = result.scalars().all()

    return {
        "events": [
            {
                "id": str(e.id),
                "title": e.title,
                "event_type": e.event_type,
                "start_date": e.start_date.isoformat(),
                "end_date": e.end_date.isoformat() if e.end_date else None,
            }
            for e in events
        ]
    }


class LinkToEventRequest(BaseModel):
    """Request body for linking an activity to an event."""

    event_id: UUID


@router.post("/activities/{activity_id}/event", status_code=201)
async def link_activity_to_event(
    db: DbSession,
    repo: ActivityRepoD,
    user: CurrentUser,
    activity_id: UUID,
    request: LinkToEventRequest,
):
    """
    Quick-link an activity to an event.

    The activity is added to a journal entry for its date within the event.
    If no entry exists for that date, one is auto-created.
    """
    from uuid import uuid4

    from trainingdash.repositories.postgres.models import JournalEntry, RideEvent
    from trainingdash.repositories.postgres.ride_event_repo import (
        PostgresJournalEntryActivityRepo,
        PostgresJournalEntryRepo,
    )

    activity = await _get_owned_activity(repo, user, activity_id)

    # Verify user owns the event
    result = await db.execute(select(RideEvent).where(RideEvent.id == request.event_id, RideEvent.user_id == user.id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    # Find or create journal entry for activity date
    entry_repo = PostgresJournalEntryRepo(db)
    activity_link_repo = PostgresJournalEntryActivityRepo(db)

    activity_date = activity.started_at.date() if activity.started_at else event.start_date
    entries = await entry_repo.list_for_event(request.event_id)
    entry = next((e for e in entries if e.entry_date == activity_date), None)

    if entry is None:
        entry = JournalEntry(
            id=uuid4(),
            ride_event_id=request.event_id,
            entry_date=activity_date,
        )
        entry = await entry_repo.save(entry)

    # Link activity to entry
    link = await activity_link_repo.link(entry.id, activity_id, sort_order=0)

    return {
        "event_id": str(request.event_id),
        "entry_id": str(entry.id),
        "activity_id": str(activity_id),
    }


@router.get("/activities/{activity_id}/fit")
async def download_activity_fit(
    repo: ActivityRepoD,
    user: CurrentUser,
    activity_id: UUID,
):
    """Download the original FIT file for an activity.

    Returns the raw FIT bytes with appropriate headers for file download.
    Returns 404 if the activity doesn't exist or has no stored FIT file.
    """
    from fastapi.responses import Response

    activity = await _get_owned_activity(repo, user, activity_id)

    if activity.raw_fit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No FIT file stored for this activity",
        )

    # Generate filename from activity date and ID
    date_str = activity.started_at.strftime("%Y-%m-%d")
    filename = f"{date_str}_{activity_id}.fit"

    return Response(
        content=activity.raw_fit,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.post("/activities/{activity_id}/upload")
async def upload_activity_to_provider(
    db: DbSession,
    user: CurrentUser,
    activity_id: UUID,
    request: UploadToProviderRequest,
):
    """Upload an activity's FIT file to an external provider.

    Supports optional device spoofing via device_product_id (e.g., 4062 for Edge 840).

    Returns:
        provider: The target provider name
        provider_activity_id: The activity ID on the target provider
    """
    # Build modifications if device spoofing is requested
    modifications = None
    if request.device_product_id is not None:
        modifications = FitModifications(device_product_id=request.device_product_id)

    use_case = UploadToProvider(db)

    try:
        result = await use_case.execute(
            user_id=user.id,
            activity_id=activity_id,
            provider=request.provider,
            modifications=modifications,
        )

        return {
            "provider": result.provider,
            "provider_activity_id": result.provider_activity_id,
        }

    except ActivityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )
    except NoFitFileError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No FIT file stored for this activity",
        )
    except CredentialsNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except CredentialsDecryptError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt provider credentials",
        )
    except FitModifyError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except ProviderUploadError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )


@router.get("/fit/devices")
async def list_fit_devices(user: CurrentUser):
    """List available FIT device types for device spoofing.

    Returns a list of devices with id, name, and display_name.
    The id is the Garmin product ID to use when uploading with device spoofing.

    Common devices:
    - Edge 840: id=4062
    - Edge 1040: id=3843
    - Edge 530: id=3121
    """
    from trainingdash.domain.fit_modifier import get_device_list

    devices = get_device_list()
    return {"devices": devices, "total": len(devices)}
