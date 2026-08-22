"""Admin endpoints: user management, credential management, sync triggers, nuke operations."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, func, select, update

from trainingdash.auth import AdminUser, DbSession, hash_password
from trainingdash.crypto import EncryptionError, encrypt
from trainingdash.dependencies import (
    EventRepoD,
    GarminCredentialsRepoD,
    UserRepoD,
    XertCredentialsRepoD,
)
from trainingdash.domain.events import EventOutcome, EventType
from trainingdash.repositories.postgres.models import (
    Activity,
    ActivityPeakPower,
    AppSettings,
    AuditLog,
    EFModel,
    FitnessHistory,
    GarminCredentials,
    Lap,
    MetricEntry,
    MetricType,
    Notification,
    Record,
    Route,
    User,
    XertCredentials,
)
from trainingdash.routers.serializers import user_summary

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _get_user_or_404(user_repo: UserRepoD, user_id: int) -> User:
    """Fetch a user by ID or raise 404."""
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# --- User management ---


@router.get("/users")
async def admin_list_users(user_repo: UserRepoD, admin: AdminUser):
    """List all users (admin only)."""
    users = await user_repo.list_all()
    return [user_summary(u) for u in users]


class CreateUserRequest(BaseModel):
    email: str
    password: str


@router.post("/users")
async def admin_create_user(user_repo: UserRepoD, admin: AdminUser, request: CreateUserRequest):
    """Create a new user account (admin only)."""
    # Check if email already exists
    if await user_repo.exists_by_email(request.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")

    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        is_admin=False,
        is_approved=True,  # Admin-created users are pre-approved
    )
    user = await user_repo.save(user)
    return user_summary(user)


class ResetPasswordRequest(BaseModel):
    password: str


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(
    db: DbSession, user_repo: UserRepoD, admin: AdminUser, user_id: int, request: ResetPasswordRequest
):
    """Reset a user's password (admin only)."""
    user = await _get_user_or_404(user_repo, user_id)
    user.password_hash = hash_password(request.password)
    await db.commit()
    return {"success": True}


@router.post("/users/{user_id}/sync")
async def admin_trigger_sync(
    xert_repo: XertCredentialsRepoD,
    garmin_repo: GarminCredentialsRepoD,
    user_repo: UserRepoD,
    admin: AdminUser,
    user_id: int,
):
    """Trigger sync for a user (admin only). Only syncs providers with sync_enabled=true."""
    await _get_user_or_404(user_repo, user_id)

    from trainingdash.jobs import enqueue_sync_garmin_job, enqueue_sync_xert_job

    job_ids = {}

    # Check if user has Xert credentials with sync enabled
    xert_creds = await xert_repo.get_by_user_id(user_id)
    if xert_creds and xert_creds.sync_enabled:
        job_id = await enqueue_sync_xert_job(user_id)
        if job_id:
            job_ids["xert"] = job_id

    # Check if user has Garmin credentials with sync enabled
    garmin_creds = await garmin_repo.get_by_user_id(user_id)
    if garmin_creds and garmin_creds.sync_enabled:
        job_id = await enqueue_sync_garmin_job(user_id)
        if job_id:
            job_ids["garmin"] = job_id

    if not job_ids:
        return {
            "success": True,
            "job_ids": None,
            "message": "No integrations with sync enabled or Redis not available",
        }
    return {"success": True, "job_ids": job_ids}


# --- Xert credentials management ---


class XertCredentialsRequest(BaseModel):
    xert_email: str
    xert_password: str


@router.get("/users/{user_id}/xert-credentials")
async def admin_get_xert_credentials(
    xert_repo: XertCredentialsRepoD, user_repo: UserRepoD, admin: AdminUser, user_id: int
):
    """Get Xert credentials status for a user (admin only). Never returns the password."""
    await _get_user_or_404(user_repo, user_id)
    creds = await xert_repo.get_by_user_id(user_id)
    if creds is None:
        return {"configured": False, "xert_email": None}
    return {"configured": True, "xert_email": creds.xert_email}


@router.put("/users/{user_id}/xert-credentials")
async def admin_set_xert_credentials(
    xert_repo: XertCredentialsRepoD,
    user_repo: UserRepoD,
    admin: AdminUser,
    user_id: int,
    request: XertCredentialsRequest,
):
    """Set or update Xert credentials for a user (admin only). Password is encrypted at rest."""
    await _get_user_or_404(user_repo, user_id)

    try:
        encrypted_password = encrypt(request.xert_password)
    except EncryptionError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    await xert_repo.save(
        user_id=user_id,
        xert_email=request.xert_email,
        encrypted_password=encrypted_password,
    )
    return {"success": True, "xert_email": request.xert_email}


@router.delete("/users/{user_id}/xert-credentials")
async def admin_delete_xert_credentials(
    xert_repo: XertCredentialsRepoD, user_repo: UserRepoD, admin: AdminUser, user_id: int
):
    """Delete Xert credentials for a user (admin only)."""
    await _get_user_or_404(user_repo, user_id)
    await xert_repo.delete(user_id)
    return {"success": True}


# --- User approval ---


@router.get("/users/pending")
async def admin_list_pending_users(user_repo: UserRepoD, admin: AdminUser):
    """List all users pending approval (admin only)."""
    users = await user_repo.list_pending_approval()
    return [user_summary(u) for u in users]


@router.post("/users/{user_id}/approve")
async def admin_approve_user(db: DbSession, user_repo: UserRepoD, admin: AdminUser, user_id: int):
    """Approve a pending user (admin only)."""
    user = await _get_user_or_404(user_repo, user_id)
    if user.is_approved:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already approved")
    user.is_approved = True
    await db.commit()
    return {"success": True}


@router.post("/users/{user_id}/reject")
async def admin_reject_user(db: DbSession, user_repo: UserRepoD, admin: AdminUser, user_id: int):
    """Reject and delete a pending user (admin only)."""
    user = await _get_user_or_404(user_repo, user_id)
    if user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject an already approved user",
        )
    await db.delete(user)
    await db.commit()
    return {"success": True}


# --- App settings ---

# Settings that should be treated as booleans
BOOLEAN_SETTINGS = {"require_approval"}


@router.get("/settings")
async def admin_get_settings(db: DbSession, admin: AdminUser):
    """Get all app settings (admin only)."""
    result = await db.execute(select(AppSettings))
    settings = result.scalars().all()
    # Return booleans for boolean settings, strings for others
    return {s.key: s.as_bool() if s.key in BOOLEAN_SETTINGS else s.value for s in settings}


class UpdateSettingRequest(BaseModel):
    value: bool | str


@router.put("/settings/{key}")
async def admin_update_setting(db: DbSession, admin: AdminUser, key: str, request: UpdateSettingRequest):
    """Update an app setting (admin only)."""
    allowed_keys = {"require_approval"}
    if key not in allowed_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown setting key: {key}",
        )

    # Convert boolean to string for storage
    if key in BOOLEAN_SETTINGS and isinstance(request.value, bool):
        str_value = AppSettings.bool_to_str(request.value)
    else:
        str_value = str(request.value)

    result = await db.execute(select(AppSettings).where(AppSettings.key == key))
    setting = result.scalar_one_or_none()

    if setting is None:
        setting = AppSettings(key=key, value=str_value)
        db.add(setting)
    else:
        setting.value = str_value

    await db.commit()
    return {"key": key, "value": request.value}


# --- Nuke operations ---


@router.get("/users/{user_id}/nuke-preview")
async def admin_nuke_preview(db: DbSession, user_repo: UserRepoD, admin: AdminUser, user_id: int):
    """Get counts of what would be deleted for each nuke action."""
    user = await _get_user_or_404(user_repo, user_id)

    counts = await _get_user_data_counts(db, user_id)

    # Flag if this is self-nuke (only activities/integrations allowed)
    is_self = user.id == admin.id

    return {
        "user": user_summary(user),
        "is_self": is_self,
        "activities": {
            "activities": counts["activities"],
            "records": counts["records"],
            "laps": counts["laps"],
            "peaks": counts["peaks"],
            "routes": counts["routes"],
            "fitness_history": counts["fitness_history"],
            "notifications": counts["notifications"],
        },
        "integrations": {
            "garmin": counts["garmin"],
            "xert": counts["xert"],
        },
        "account": {
            "thresholds": counts["thresholds"],
            "ef_model": counts["ef_model"],
        },
    }


class NukeRequest(BaseModel):
    confirm_email: str


def _validate_nuke_request(user: User, admin: AdminUser, confirm_email: str, allow_self: bool = False) -> None:
    """Validate nuke request: optionally prevent self-nuke and verify email confirmation."""
    if not allow_self and user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot nuke your own account",
        )
    if confirm_email.lower() != user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation email does not match",
        )


async def _get_user_data_counts(db: DbSession, user_id: int) -> dict:
    """Get counts of user data for preview and audit logging."""
    activities_count = (
        await db.execute(select(func.count()).select_from(Activity).where(Activity.user_id == user_id))
    ).scalar() or 0

    records_count = (
        await db.execute(
            select(func.count())
            .select_from(Record)
            .join(Activity, Record.activity_id == Activity.id)
            .where(Activity.user_id == user_id)
        )
    ).scalar() or 0

    laps_count = (
        await db.execute(
            select(func.count())
            .select_from(Lap)
            .join(Activity, Lap.activity_id == Activity.id)
            .where(Activity.user_id == user_id)
        )
    ).scalar() or 0

    peaks_count = (
        await db.execute(
            select(func.count())
            .select_from(ActivityPeakPower)
            .join(Activity, ActivityPeakPower.activity_id == Activity.id)
            .where(Activity.user_id == user_id)
        )
    ).scalar() or 0

    routes_count = (
        await db.execute(select(func.count()).select_from(Route).where(Route.user_id == user_id))
    ).scalar() or 0

    fitness_history_count = (
        await db.execute(select(func.count()).select_from(FitnessHistory).where(FitnessHistory.user_id == user_id))
    ).scalar() or 0

    notifications_count = (
        await db.execute(select(func.count()).select_from(Notification).where(Notification.user_id == user_id))
    ).scalar() or 0

    garmin_count = (
        await db.execute(
            select(func.count()).select_from(GarminCredentials).where(GarminCredentials.user_id == user_id)
        )
    ).scalar() or 0

    xert_count = (
        await db.execute(select(func.count()).select_from(XertCredentials).where(XertCredentials.user_id == user_id))
    ).scalar() or 0

    # Count threshold metrics (ftp, lthr, hrmax)
    ftp_type_result = await db.execute(select(MetricType.id).where(MetricType.key == "ftp"))
    ftp_type_id = ftp_type_result.scalar_one_or_none()

    thresholds_count = 0
    if ftp_type_id:
        thresholds_count = (
            await db.execute(
                select(func.count())
                .select_from(MetricEntry)
                .where(MetricEntry.user_id == user_id, MetricEntry.metric_type_id == ftp_type_id)
            )
        ).scalar() or 0

    ef_model_count = (
        await db.execute(select(func.count()).select_from(EFModel).where(EFModel.user_id == user_id))
    ).scalar() or 0

    return {
        "activities": activities_count,
        "records": records_count,
        "laps": laps_count,
        "peaks": peaks_count,
        "routes": routes_count,
        "fitness_history": fitness_history_count,
        "notifications": notifications_count,
        "garmin": garmin_count,
        "xert": xert_count,
        "thresholds": thresholds_count,
        "ef_model": ef_model_count,
    }


async def _log_nuke_action(db: DbSession, admin: AdminUser, action: str, target_user: User, summary: str) -> None:
    """Record a nuke action in the audit log."""
    log_entry = AuditLog(
        admin_id=admin.id,
        action=action,
        target_user_id=target_user.id,
        target_user_email=target_user.email,
        summary=summary,
    )
    db.add(log_entry)


@router.post("/users/{user_id}/nuke/activities")
async def admin_nuke_activities(
    db: DbSession,
    user_repo: UserRepoD,
    event_repo: EventRepoD,
    admin: AdminUser,
    user_id: int,
    request: NukeRequest,
):
    """Delete all activities and related data for a user (keeps account, credentials, and fitness settings)."""
    user = await _get_user_or_404(user_repo, user_id)
    _validate_nuke_request(user, admin, request.confirm_email, allow_self=True)

    # Get counts for audit log
    counts = await _get_user_data_counts(db, user_id)

    # Delete in order respecting FK constraints:
    # 1. Clear activity.route_id (nullable FK to routes)
    # 2. Delete routes (first_seen_activity_id FK will be satisfied since we delete all user activities)
    # 3. Delete activities (CASCADE deletes Records, Laps, Peaks)
    # NOTE: EFModel is NOT deleted - it's a fitness setting that survives Reset Activities
    await db.execute(update(Activity).where(Activity.user_id == user_id).values(route_id=None))
    await db.execute(delete(Route).where(Route.user_id == user_id))
    await db.execute(delete(Activity).where(Activity.user_id == user_id))
    await db.execute(delete(FitnessHistory).where(FitnessHistory.user_id == user_id))
    await db.execute(delete(Notification).where(Notification.user_id == user_id))

    # Log the action
    summary = f"{counts['activities']} activities, {counts['records']} records, {counts['routes']} routes"
    await _log_nuke_action(db, admin, "nuke_activities", user, summary)

    # Emit admin.nuke_activities event
    await event_repo.log(
        event_type=EventType.ADMIN_NUKE_ACTIVITIES.value,
        outcome=EventOutcome.INFO.value,
        user_id=user_id,
        payload={
            "admin_id": admin.id,
            "activities_deleted": counts["activities"],
            "records_deleted": counts["records"],
            "routes_deleted": counts["routes"],
        },
    )

    await db.commit()
    return {"success": True, "deleted": summary}


@router.post("/users/{user_id}/nuke/integrations")
async def admin_nuke_integrations(
    db: DbSession,
    user_repo: UserRepoD,
    event_repo: EventRepoD,
    admin: AdminUser,
    user_id: int,
    request: NukeRequest,
):
    """Delete all integration credentials for a user."""
    user = await _get_user_or_404(user_repo, user_id)
    _validate_nuke_request(user, admin, request.confirm_email, allow_self=True)

    # Get counts for audit log
    counts = await _get_user_data_counts(db, user_id)

    # Delete credentials
    await db.execute(delete(GarminCredentials).where(GarminCredentials.user_id == user_id))
    await db.execute(delete(XertCredentials).where(XertCredentials.user_id == user_id))

    # Log the action
    parts = []
    if counts["garmin"]:
        parts.append("Garmin credentials")
    if counts["xert"]:
        parts.append("Xert credentials")
    summary = ", ".join(parts) if parts else "no credentials"
    await _log_nuke_action(db, admin, "nuke_integrations", user, summary)

    # Emit admin.nuke_integrations event
    await event_repo.log(
        event_type=EventType.ADMIN_NUKE_INTEGRATIONS.value,
        outcome=EventOutcome.INFO.value,
        user_id=user_id,
        payload={
            "admin_id": admin.id,
            "garmin_deleted": counts["garmin"],
            "xert_deleted": counts["xert"],
        },
    )

    await db.commit()
    return {"success": True, "deleted": summary}


@router.post("/users/{user_id}/nuke/account")
async def admin_nuke_account(
    db: DbSession,
    user_repo: UserRepoD,
    event_repo: EventRepoD,
    admin: AdminUser,
    user_id: int,
    request: NukeRequest,
):
    """Delete a user account and all associated data."""
    user = await _get_user_or_404(user_repo, user_id)
    _validate_nuke_request(user, admin, request.confirm_email)

    # Get counts for audit log
    counts = await _get_user_data_counts(db, user_id)

    # Log BEFORE deleting user (so we have the email)
    summary = f"user account, {counts['activities']} activities, all associated data"
    await _log_nuke_action(db, admin, "nuke_account", user, summary)

    # Emit admin.nuke_account event BEFORE deleting user
    await event_repo.log(
        event_type=EventType.ADMIN_NUKE_ACCOUNT.value,
        outcome=EventOutcome.INFO.value,
        user_id=user_id,
        payload={
            "admin_id": admin.id,
            "user_email": user.email,
            "activities_deleted": counts["activities"],
        },
    )

    # Delete user (CASCADE will handle most related data)
    await db.execute(delete(User).where(User.id == user_id))

    await db.commit()
    return {"success": True, "deleted": summary}



# --- Weather backfill ---


class WeatherBackfillResponse(BaseModel):
    """Response for weather backfill operation."""

    success: bool
    activities_needing_backfill: int
    activities_queued: int
    job_ids: list[str] | None = None
    message: str | None = None


@router.get("/users/{user_id}/weather-backfill/status")
async def admin_get_weather_backfill_status(
    db: DbSession,
    user_repo: UserRepoD,
    admin: AdminUser,
    user_id: int,
):
    """
    Get weather backfill status for a user (admin only).

    Returns counts of activities by weather_status, showing how many
    need backfill (NULL or 'pending' status). Also shows aero estimation
    progress for activities with weather data.
    """
    await _get_user_or_404(user_repo, user_id)

    # Count activities by weather status
    result = await db.execute(
        select(
            func.count().filter(Activity.weather_status.is_(None)).label("null_status"),
            func.count().filter(Activity.weather_status == "pending").label("pending"),
            func.count().filter(Activity.weather_status == "fetched").label("fetched"),
            func.count().filter(Activity.weather_status == "failed").label("failed"),
            func.count().filter(Activity.weather_status == "not_applicable").label("not_applicable"),
            func.count().label("total"),
        ).where(Activity.user_id == user_id)
    )
    row = result.one()

    # Count aero estimation status for activities with weather
    aero_result = await db.execute(
        select(
            func.count().filter(Activity.estimated_cda.isnot(None)).label("with_aero"),
            func.count().filter(
                Activity.weather_status == "fetched",
                Activity.estimated_cda.is_(None),
            ).label("pending_aero"),
        ).where(Activity.user_id == user_id)
    )
    aero_row = aero_result.one()

    return {
        "user_id": user_id,
        "weather_status_counts": {
            "null": row.null_status,
            "pending": row.pending,
            "fetched": row.fetched,
            "failed": row.failed,
            "not_applicable": row.not_applicable,
        },
        "total_activities": row.total,
        "needing_backfill": row.null_status + row.pending,
        "aero_estimation": {
            "with_estimates": aero_row.with_aero,
            "pending_estimation": aero_row.pending_aero,
        },
    }


@router.post("/users/{user_id}/weather-backfill")
async def admin_trigger_weather_backfill(
    db: DbSession,
    user_repo: UserRepoD,
    event_repo: EventRepoD,
    admin: AdminUser,
    user_id: int,
) -> WeatherBackfillResponse:
    """
    Trigger weather backfill for a user's historical activities (admin only).

    This endpoint:
    1. Finds activities with NULL weather_status (pre-integration activities)
    2. Sets them to 'pending' status
    3. Queues weather fetch jobs (batched, 10 activities per job)

    Weather fetch will also trigger CdA/Crr estimation for eligible activities.
    """
    from trainingdash.jobs import enqueue_fetch_weather_job

    await _get_user_or_404(user_repo, user_id)

    # Count activities needing backfill (NULL status = historical, never processed)
    count_result = await db.execute(
        select(func.count())
        .select_from(Activity)
        .where(Activity.user_id == user_id, Activity.weather_status.is_(None))
    )
    null_count = count_result.scalar() or 0

    if null_count == 0:
        return WeatherBackfillResponse(
            success=True,
            activities_needing_backfill=0,
            activities_queued=0,
            message="No activities need weather backfill",
        )

    # Update NULL weather_status to 'pending'
    await db.execute(
        update(Activity)
        .where(Activity.user_id == user_id, Activity.weather_status.is_(None))
        .values(weather_status="pending")
    )
    await db.commit()

    # Queue weather fetch jobs (process in batches of 10)
    # Each job processes up to 10 pending activities
    num_jobs = (null_count + 9) // 10  # Ceiling division
    job_ids = []

    for _ in range(min(num_jobs, 5)):  # Max 5 concurrent jobs per user
        job_id = await enqueue_fetch_weather_job(user_id)
        if job_id:
            job_ids.append(job_id)

    # Log the backfill action
    await event_repo.log(
        event_type=EventType.ADMIN_TRIGGER_SYNC.value,  # Reuse existing event type
        outcome=EventOutcome.INFO.value,
        user_id=user_id,
        payload={
            "admin_id": admin.id,
            "action": "weather_backfill",
            "activities_queued": null_count,
            "jobs_queued": len(job_ids),
        },
    )

    return WeatherBackfillResponse(
        success=True,
        activities_needing_backfill=null_count,
        activities_queued=null_count,
        job_ids=job_ids if job_ids else None,
        message=f"Queued {null_count} activities for weather backfill across {len(job_ids)} jobs",
    )
