"""Admin endpoints: user management, credential management, sync triggers, nuke operations."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func, delete

from trainingdash.auth import AdminUser, DbSession, hash_password
from trainingdash.crypto import encrypt, EncryptionError
from trainingdash.models import (
    Activity,
    ActivityPeakPower,
    AppSettings,
    AuditLog,
    EFModel,
    FitnessHistory,
    GarminCredentials,
    HrZone,
    Lap,
    Notification,
    PowerZone,
    Record,
    Route,
    ThresholdHistory,
    User,
    XertCredentials,
)
from trainingdash.routers.serializers import user_summary

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _get_user_or_404(db: DbSession, user_id: int) -> User:
    """Fetch a user by ID or raise 404."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


# --- User management ---


@router.get("/users")
async def admin_list_users(db: DbSession, admin: AdminUser):
    """List all users (admin only)."""
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    return [user_summary(u) for u in users]


class CreateUserRequest(BaseModel):
    email: str
    password: str


@router.post("/users")
async def admin_create_user(db: DbSession, admin: AdminUser, request: CreateUserRequest):
    """Create a new user account (admin only)."""
    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == request.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists"
        )

    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        is_admin=False,
        is_approved=True,  # Admin-created users are pre-approved
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user_summary(user)


class ResetPasswordRequest(BaseModel):
    password: str


@router.post("/users/{user_id}/reset-password")
async def admin_reset_password(
    db: DbSession, admin: AdminUser, user_id: int, request: ResetPasswordRequest
):
    """Reset a user's password (admin only)."""
    user = await _get_user_or_404(db, user_id)
    user.password_hash = hash_password(request.password)
    await db.commit()
    return {"success": True}


@router.post("/users/{user_id}/sync")
async def admin_trigger_sync(db: DbSession, admin: AdminUser, user_id: int):
    """Trigger sync for a user (admin only). Triggers both Xert and Garmin if configured."""
    await _get_user_or_404(db, user_id)

    from trainingdash.jobs import enqueue_sync_garmin_job, enqueue_sync_xert_job

    job_ids = {}

    # Check if user has Xert credentials and trigger sync
    xert_result = await db.execute(
        select(XertCredentials).where(XertCredentials.user_id == user_id)
    )
    if xert_result.scalar_one_or_none() is not None:
        job_id = await enqueue_sync_xert_job(user_id)
        if job_id:
            job_ids["xert"] = job_id

    # Check if user has Garmin credentials and trigger sync
    garmin_result = await db.execute(
        select(GarminCredentials).where(GarminCredentials.user_id == user_id)
    )
    if garmin_result.scalar_one_or_none() is not None:
        job_id = await enqueue_sync_garmin_job(user_id)
        if job_id:
            job_ids["garmin"] = job_id

    if not job_ids:
        return {
            "success": True,
            "job_ids": None,
            "message": "No integrations configured or Redis not available",
        }
    return {"success": True, "job_ids": job_ids}


# --- Xert credentials management ---


class XertCredentialsRequest(BaseModel):
    xert_email: str
    xert_password: str


@router.get("/users/{user_id}/xert-credentials")
async def admin_get_xert_credentials(db: DbSession, admin: AdminUser, user_id: int):
    """Get Xert credentials status for a user (admin only). Never returns the password."""
    await _get_user_or_404(db, user_id)
    result = await db.execute(
        select(XertCredentials).where(XertCredentials.user_id == user_id)
    )
    creds = result.scalar_one_or_none()
    if creds is None:
        return {"configured": False, "xert_email": None}
    return {"configured": True, "xert_email": creds.xert_email}


@router.put("/users/{user_id}/xert-credentials")
async def admin_set_xert_credentials(
    db: DbSession, admin: AdminUser, user_id: int, request: XertCredentialsRequest
):
    """Set or update Xert credentials for a user (admin only). Password is encrypted at rest."""
    await _get_user_or_404(db, user_id)

    try:
        encrypted_password = encrypt(request.xert_password)
    except EncryptionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

    result = await db.execute(
        select(XertCredentials).where(XertCredentials.user_id == user_id)
    )
    creds = result.scalar_one_or_none()

    if creds is None:
        creds = XertCredentials(
            user_id=user_id,
            xert_email=request.xert_email,
            encrypted_password=encrypted_password,
        )
        db.add(creds)
    else:
        creds.xert_email = request.xert_email
        creds.encrypted_password = encrypted_password

    await db.commit()
    return {"success": True, "xert_email": request.xert_email}


@router.delete("/users/{user_id}/xert-credentials")
async def admin_delete_xert_credentials(db: DbSession, admin: AdminUser, user_id: int):
    """Delete Xert credentials for a user (admin only)."""
    await _get_user_or_404(db, user_id)
    result = await db.execute(
        select(XertCredentials).where(XertCredentials.user_id == user_id)
    )
    creds = result.scalar_one_or_none()
    if creds is not None:
        await db.delete(creds)
        await db.commit()
    return {"success": True}



# --- User approval ---


@router.get("/users/pending")
async def admin_list_pending_users(db: DbSession, admin: AdminUser):
    """List all users pending approval (admin only)."""
    result = await db.execute(
        select(User).where(User.is_approved == False).order_by(User.created_at)
    )
    users = result.scalars().all()
    return [user_summary(u) for u in users]


@router.post("/users/{user_id}/approve")
async def admin_approve_user(db: DbSession, admin: AdminUser, user_id: int):
    """Approve a pending user (admin only)."""
    user = await _get_user_or_404(db, user_id)
    if user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User is already approved"
        )
    user.is_approved = True
    await db.commit()
    return {"success": True}


@router.post("/users/{user_id}/reject")
async def admin_reject_user(db: DbSession, admin: AdminUser, user_id: int):
    """Reject and delete a pending user (admin only)."""
    user = await _get_user_or_404(db, user_id)
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
    return {
        s.key: s.as_bool() if s.key in BOOLEAN_SETTINGS else s.value
        for s in settings
    }


class UpdateSettingRequest(BaseModel):
    value: bool | str


@router.put("/settings/{key}")
async def admin_update_setting(
    db: DbSession, admin: AdminUser, key: str, request: UpdateSettingRequest
):
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
async def admin_nuke_preview(db: DbSession, admin: AdminUser, user_id: int):
    """Get counts of what would be deleted for each nuke action."""
    user = await _get_user_or_404(db, user_id)
    
    # Prevent admin from nuking themselves
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot nuke your own account",
        )
    
    # Count activities and related data
    activities_count = (await db.execute(
        select(func.count()).select_from(Activity).where(Activity.user_id == user_id)
    )).scalar() or 0
    
    records_count = (await db.execute(
        select(func.count()).select_from(Record)
        .join(Activity, Record.activity_id == Activity.id)
        .where(Activity.user_id == user_id)
    )).scalar() or 0
    
    laps_count = (await db.execute(
        select(func.count()).select_from(Lap)
        .join(Activity, Lap.activity_id == Activity.id)
        .where(Activity.user_id == user_id)
    )).scalar() or 0
    
    peaks_count = (await db.execute(
        select(func.count()).select_from(ActivityPeakPower)
        .join(Activity, ActivityPeakPower.activity_id == Activity.id)
        .where(Activity.user_id == user_id)
    )).scalar() or 0
    
    routes_count = (await db.execute(
        select(func.count()).select_from(Route).where(Route.user_id == user_id)
    )).scalar() or 0
    
    fitness_history_count = (await db.execute(
        select(func.count()).select_from(FitnessHistory).where(FitnessHistory.user_id == user_id)
    )).scalar() or 0
    
    notifications_count = (await db.execute(
        select(func.count()).select_from(Notification).where(Notification.user_id == user_id)
    )).scalar() or 0
    
    # Count credentials
    has_garmin = (await db.execute(
        select(func.count()).select_from(GarminCredentials).where(GarminCredentials.user_id == user_id)
    )).scalar() or 0
    
    has_xert = (await db.execute(
        select(func.count()).select_from(XertCredentials).where(XertCredentials.user_id == user_id)
    )).scalar() or 0
    
    # Count fitness settings
    thresholds_count = (await db.execute(
        select(func.count()).select_from(ThresholdHistory).where(ThresholdHistory.user_id == user_id)
    )).scalar() or 0
    
    power_zones_count = (await db.execute(
        select(func.count()).select_from(PowerZone).where(PowerZone.user_id == user_id)
    )).scalar() or 0
    
    hr_zones_count = (await db.execute(
        select(func.count()).select_from(HrZone).where(HrZone.user_id == user_id)
    )).scalar() or 0
    
    ef_model_count = (await db.execute(
        select(func.count()).select_from(EFModel).where(EFModel.user_id == user_id)
    )).scalar() or 0
    
    return {
        "user": user_summary(user),
        "activities": {
            "activities": activities_count,
            "records": records_count,
            "laps": laps_count,
            "peaks": peaks_count,
            "routes": routes_count,
            "fitness_history": fitness_history_count,
            "notifications": notifications_count,
        },
        "integrations": {
            "garmin": has_garmin,
            "xert": has_xert,
        },
        "account": {
            "thresholds": thresholds_count,
            "power_zones": power_zones_count,
            "hr_zones": hr_zones_count,
            "ef_model": ef_model_count,
        },
    }


class NukeRequest(BaseModel):
    confirm_email: str


async def _log_nuke_action(
    db: DbSession, 
    admin: AdminUser, 
    action: str, 
    target_user: User, 
    summary: str
) -> None:
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
    db: DbSession, admin: AdminUser, user_id: int, request: NukeRequest
):
    """Delete all activities and related data for a user (keeps account and credentials)."""
    user = await _get_user_or_404(db, user_id)
    
    # Safety checks
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot nuke your own account",
        )
    if request.confirm_email.lower() != user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation email does not match",
        )
    
    # Get counts for audit log
    activities_count = (await db.execute(
        select(func.count()).select_from(Activity).where(Activity.user_id == user_id)
    )).scalar() or 0
    records_count = (await db.execute(
        select(func.count()).select_from(Record)
        .join(Activity, Record.activity_id == Activity.id)
        .where(Activity.user_id == user_id)
    )).scalar() or 0
    routes_count = (await db.execute(
        select(func.count()).select_from(Route).where(Route.user_id == user_id)
    )).scalar() or 0
    
    # Delete in order (children first due to FK constraints)
    # Records, Laps, Peaks are CASCADE deleted with Activity
    await db.execute(delete(Route).where(Route.user_id == user_id))
    await db.execute(delete(FitnessHistory).where(FitnessHistory.user_id == user_id))
    await db.execute(delete(Notification).where(Notification.user_id == user_id))
    await db.execute(delete(EFModel).where(EFModel.user_id == user_id))
    await db.execute(delete(Activity).where(Activity.user_id == user_id))
    
    # Log the action
    summary = f"{activities_count} activities, {records_count} records, {routes_count} routes"
    await _log_nuke_action(db, admin, "nuke_activities", user, summary)
    
    await db.commit()
    return {"success": True, "deleted": summary}


@router.post("/users/{user_id}/nuke/integrations")
async def admin_nuke_integrations(
    db: DbSession, admin: AdminUser, user_id: int, request: NukeRequest
):
    """Delete all integration credentials for a user."""
    user = await _get_user_or_404(db, user_id)
    
    # Safety checks
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot nuke your own account",
        )
    if request.confirm_email.lower() != user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation email does not match",
        )
    
    # Count for audit log
    garmin_count = (await db.execute(
        select(func.count()).select_from(GarminCredentials).where(GarminCredentials.user_id == user_id)
    )).scalar() or 0
    xert_count = (await db.execute(
        select(func.count()).select_from(XertCredentials).where(XertCredentials.user_id == user_id)
    )).scalar() or 0
    
    # Delete credentials
    await db.execute(delete(GarminCredentials).where(GarminCredentials.user_id == user_id))
    await db.execute(delete(XertCredentials).where(XertCredentials.user_id == user_id))
    
    # Log the action
    parts = []
    if garmin_count:
        parts.append("Garmin credentials")
    if xert_count:
        parts.append("Xert credentials")
    summary = ", ".join(parts) if parts else "no credentials"
    await _log_nuke_action(db, admin, "nuke_integrations", user, summary)
    
    await db.commit()
    return {"success": True, "deleted": summary}


@router.post("/users/{user_id}/nuke/account")
async def admin_nuke_account(
    db: DbSession, admin: AdminUser, user_id: int, request: NukeRequest
):
    """Delete a user account and all associated data."""
    user = await _get_user_or_404(db, user_id)
    
    # Safety checks
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot nuke your own account",
        )
    if request.confirm_email.lower() != user.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation email does not match",
        )
    
    # Get counts for audit log
    activities_count = (await db.execute(
        select(func.count()).select_from(Activity).where(Activity.user_id == user_id)
    )).scalar() or 0
    
    # Log BEFORE deleting user (so we have the email)
    summary = f"user account, {activities_count} activities, all associated data"
    await _log_nuke_action(db, admin, "nuke_account", user, summary)
    
    # Delete user (CASCADE will handle most related data)
    await db.execute(delete(User).where(User.id == user_id))
    
    await db.commit()
    return {"success": True, "deleted": summary}
