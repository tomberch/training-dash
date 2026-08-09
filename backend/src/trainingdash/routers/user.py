"""User endpoints: /me/*, thresholds, zones, integrations, notifications."""

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select

from trainingdash.auth import CurrentUser, DbSession, hash_password
from trainingdash.crypto import encrypt, EncryptionError
from trainingdash.dependencies import (
    GarminCredentialsRepoD,
    NotificationRepoD,
    OAuthLinkRepoD,
    RecalculationJobRepoD,
    XertCredentialsRepoD,
)
from trainingdash.integrations.garmin import get_garmin_client, GarminAPIError, GarminMFARequired
from trainingdash.jobs import enqueue_recalculate_metrics_job
from trainingdash.repositories.postgres.models import (
    GarminCredentials,
    Notification,
    XertCredentials,
)
from trainingdash.routers.serializers import (
    recalculation_job_response,
    user_response,
)
from trainingdash.routers.datetime_utils import utc_str
from trainingdash.domain.thresholds import (
    ensure_default_thresholds,
    get_all_threshold_entries,
    get_thresholds_for_date,
    create_threshold_entries,
)
from trainingdash.domain.zones import compute_power_zones, compute_hr_zones
from trainingdash.integrations.xert import get_xert_client, XertAPIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["user"])

# In-memory storage for pending MFA sessions (keyed by user_id)
# In production, this could be stored in Redis with TTL
_pending_garmin_mfa: dict[int, dict] = {}


# --- User profile ---


@router.get("/me")
async def get_me(db: DbSession, user: CurrentUser):
    """Get the current user's info including HR-derived power status."""
    from trainingdash.hr_power import get_ef_model_status

    response = user_response(user)
    response["hr_power_model"] = await get_ef_model_status(db, user.id)
    return response


class UpdateMeRequest(BaseModel):
    display_name: str | None = None
    unit_system: str | None = None
    sync_hour: int | None = None
    date_of_birth: date | None = None
    weight_kg: float | None = None
    height_cm: int | None = None
    gender: str | None = None
    power_zone_percentages: dict | None = None
    hr_zone_percentages: dict | None = None
    hr_derived_power_enabled: bool | None = None


@router.patch("/me")
async def update_me(db: DbSession, user: CurrentUser, request: UpdateMeRequest):
    """Update the current user's preferences."""
    if request.display_name is not None:
        user.display_name = request.display_name.strip() if request.display_name else None
    
    if request.unit_system is not None:
        if request.unit_system not in ("metric", "imperial"):
            raise HTTPException(
                status_code=400, detail="unit_system must be 'metric' or 'imperial'"
            )
        user.unit_system = request.unit_system

    if request.sync_hour is not None:
        if request.sync_hour < 0 or request.sync_hour > 23:
            raise HTTPException(
                status_code=400, detail="sync_hour must be between 0 and 23"
            )
        user.sync_hour = request.sync_hour

    if request.date_of_birth is not None:
        today = date.today()
        age = (today - request.date_of_birth).days // 365
        if request.date_of_birth > today:
            raise HTTPException(
                status_code=400, detail="date_of_birth cannot be in the future"
            )
        if age < 10 or age > 100:
            raise HTTPException(
                status_code=400,
                detail="date_of_birth must represent an age between 10 and 100",
            )
        user.date_of_birth = request.date_of_birth

    if request.weight_kg is not None:
        if request.weight_kg <= 0:
            raise HTTPException(status_code=400, detail="weight_kg must be positive")
        if request.weight_kg > 500:
            raise HTTPException(
                status_code=400, detail="weight_kg must be realistic (max 500)"
            )
        user.weight_kg = request.weight_kg

    if request.height_cm is not None:
        if request.height_cm < 100 or request.height_cm > 250:
            raise HTTPException(
                status_code=400, detail="height_cm must be between 100 and 250"
            )
        user.height_cm = request.height_cm

    if request.gender is not None:
        if request.gender not in ("male", "female"):
            raise HTTPException(
                status_code=400, detail="gender must be 'male' or 'female'"
            )
        user.gender = request.gender

    if request.power_zone_percentages is not None:
        user.power_zone_percentages = request.power_zone_percentages

    if request.hr_zone_percentages is not None:
        user.hr_zone_percentages = request.hr_zone_percentages

    if request.hr_derived_power_enabled is not None:
        user.hr_derived_power_enabled = request.hr_derived_power_enabled

    await db.commit()
    await db.refresh(user)

    return user_response(user)


# --- Xert credentials ---


@router.get("/me/xert-credentials")
async def get_my_xert_credentials(xert_repo: XertCredentialsRepoD, user: CurrentUser):
    """Get the current user's Xert credentials status. Never returns the password."""
    creds = await xert_repo.get_by_user_id(user.id)
    if creds is None:
        return {"configured": False, "xert_email": None, "sync_since": None}
    return {
        "configured": True,
        "xert_email": creds.xert_email,
        "sync_since": (
            creds.sync_since.date()
            if hasattr(creds.sync_since, "date")
            else creds.sync_since
        ).isoformat()
        if creds.sync_since
        else None,
    }


class MyXertCredentialsRequest(BaseModel):
    xert_email: str
    xert_password: str
    sync_since: date | None = None


@router.put("/me/xert-credentials")
async def put_my_xert_credentials(
    xert_repo: XertCredentialsRepoD, user: CurrentUser, request: MyXertCredentialsRequest
):
    """Set or update the current user's Xert credentials. Validates via login attempt."""
    # Validate credentials by attempting to log in
    client = get_xert_client()
    try:
        await client.login(request.xert_email, request.xert_password)
    except XertAPIError:
        raise HTTPException(status_code=400, detail="Invalid Xert credentials")
    finally:
        await client.close()

    # Encrypt the password
    try:
        encrypted_password = encrypt(request.xert_password)
    except EncryptionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

    # Determine sync_since: use provided date or default to 90 days ago
    if request.sync_since is not None:
        sync_since_dt = datetime.combine(request.sync_since, datetime.min.time())
    else:
        sync_since_dt = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=90
        )

    await xert_repo.save(
        user_id=user.id,
        xert_email=request.xert_email,
        encrypted_password=encrypted_password,
        sync_since=sync_since_dt,
    )
    return {"success": True, "xert_email": request.xert_email}


@router.delete("/me/xert-credentials")
async def delete_my_xert_credentials(xert_repo: XertCredentialsRepoD, user: CurrentUser):
    """Delete the current user's Xert credentials (disconnect Xert)."""
    await xert_repo.delete(user.id)
    return {"success": True}


# --- Garmin credentials ---


@router.get("/me/garmin-credentials")
async def get_my_garmin_credentials(garmin_repo: GarminCredentialsRepoD, user: CurrentUser):
    """Get the current user's Garmin credentials status. Never returns the password."""
    creds = await garmin_repo.get_by_user_id(user.id)
    if creds is None:
        return {"configured": False, "garmin_email": None, "sync_since": None}
    return {
        "configured": True,
        "garmin_email": creds.garmin_email,
        "sync_since": (
            creds.sync_since.date()
            if hasattr(creds.sync_since, "date")
            else creds.sync_since
        ).isoformat()
        if creds.sync_since
        else None,
    }


class MyGarminCredentialsRequest(BaseModel):
    garmin_email: str
    garmin_password: str
    sync_since: date | None = None


@router.put("/me/garmin-credentials")
async def put_my_garmin_credentials(
    garmin_repo: GarminCredentialsRepoD, user: CurrentUser, request: MyGarminCredentialsRequest
):
    """
    Set or update the current user's Garmin credentials.

    Returns:
        - {"success": true, "garmin_email": ...} if login succeeded without MFA
        - {"mfa_required": true} if MFA is needed (call POST /me/garmin-credentials/mfa next)
    """
    client = get_garmin_client()
    try:
        client.login(request.garmin_email, request.garmin_password)
    except GarminMFARequired:
        # Store pending credentials for MFA completion
        _pending_garmin_mfa[user.id] = {
            "email": request.garmin_email,
            "password": request.garmin_password,
            "sync_since": request.sync_since,
        }
        return {"mfa_required": True}
    except GarminAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Login succeeded without MFA - save credentials
    return await _save_garmin_credentials(
        garmin_repo, user, request.garmin_email, request.garmin_password, request.sync_since
    )


class GarminMFARequest(BaseModel):
    mfa_code: str


@router.post("/me/garmin-credentials/mfa")
async def complete_garmin_mfa(
    garmin_repo: GarminCredentialsRepoD, user: CurrentUser, request: GarminMFARequest
):
    """Complete Garmin MFA authentication and save credentials."""
    pending = _pending_garmin_mfa.get(user.id)
    if pending is None:
        raise HTTPException(status_code=400, detail="No pending MFA session")

    client = get_garmin_client()
    try:
        # Re-attempt login - this will trigger MFA callback
        client.login(pending["email"], pending["password"])
    except GarminMFARequired:
        # Now complete with MFA code
        try:
            client.complete_mfa(request.mfa_code)
        except GarminAPIError as e:
            raise HTTPException(status_code=400, detail=str(e))
    except GarminAPIError as e:
        # Clean up pending session on failure
        _pending_garmin_mfa.pop(user.id, None)
        raise HTTPException(status_code=400, detail=str(e))

    # MFA succeeded - save credentials and clean up
    email = pending["email"]
    password = pending["password"]
    sync_since = pending.get("sync_since")
    _pending_garmin_mfa.pop(user.id, None)

    return await _save_garmin_credentials(garmin_repo, user, email, password, sync_since)


async def _save_garmin_credentials(
    garmin_repo: GarminCredentialsRepoD,
    user: CurrentUser,
    email: str,
    password: str,
    sync_since: date | None,
) -> dict:
    """Helper to encrypt and save Garmin credentials."""
    try:
        encrypted_password = encrypt(password)
    except EncryptionError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )

    # Determine sync_since: use provided date or default to 90 days ago
    if sync_since is not None:
        sync_since_dt = datetime.combine(sync_since, datetime.min.time())
    else:
        sync_since_dt = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=90
        )

    await garmin_repo.save(
        user_id=user.id,
        garmin_email=email,
        encrypted_password=encrypted_password,
        sync_since=sync_since_dt,
    )
    return {"success": True, "garmin_email": email}


@router.delete("/me/garmin-credentials")
async def delete_my_garmin_credentials(garmin_repo: GarminCredentialsRepoD, user: CurrentUser):
    """Delete the current user's Garmin credentials (disconnect Garmin)."""
    # Clean up any pending MFA session
    _pending_garmin_mfa.pop(user.id, None)
    await garmin_repo.delete(user.id)
    return {"success": True}


# --- Thresholds ---


@router.get("/me/thresholds")
async def get_my_thresholds(db: DbSession, user: CurrentUser):
    """Get the current user's threshold history, most recent first."""
    # Ensure defaults exist if user has DOB
    await ensure_default_thresholds(db, user)

    thresholds = await get_all_threshold_entries(db, user.id)
    return thresholds


class CreateThresholdRequest(BaseModel):
    effective_date: date | None = None
    ftp_watts: int | None = None
    lthr_bpm: int | None = None
    hrmax_bpm: int | None = None


@router.post("/me/thresholds")
async def create_threshold(
    db: DbSession,
    user: CurrentUser,
    recalculation_job_repo: RecalculationJobRepoD,
    request: CreateThresholdRequest,
):
    """Create a new threshold entry for the current user.
    
    All fields are optional. At least one of ftp_watts, lthr_bpm, or hrmax_bpm
    must be provided. Once a value is set, it cannot be removed in subsequent
    entries (only changed).
    """
    # Check at least one value provided
    if request.ftp_watts is None and request.lthr_bpm is None and request.hrmax_bpm is None:
        raise HTTPException(
            status_code=400, 
            detail="At least one threshold value (ftp_watts, lthr_bpm, or hrmax_bpm) is required"
        )
    
    # Validation for provided values
    if request.ftp_watts is not None:
        if request.ftp_watts <= 0:
            raise HTTPException(status_code=400, detail="ftp_watts must be positive")
        if request.ftp_watts > 2000:
            raise HTTPException(
                status_code=400, detail="ftp_watts must be realistic (max 2000)"
            )
    if request.lthr_bpm is not None:
        if request.lthr_bpm <= 0:
            raise HTTPException(status_code=400, detail="lthr_bpm must be positive")
        if request.lthr_bpm > 250:
            raise HTTPException(
                status_code=400, detail="lthr_bpm must be realistic (max 250)"
            )
    if request.hrmax_bpm is not None:
        if request.hrmax_bpm <= 0:
            raise HTTPException(status_code=400, detail="hrmax_bpm must be positive")
        if request.hrmax_bpm > 250:
            raise HTTPException(
                status_code=400, detail="hrmax_bpm must be realistic (max 250)"
            )
    if request.lthr_bpm is not None and request.hrmax_bpm is not None:
        if request.lthr_bpm > request.hrmax_bpm:
            raise HTTPException(
                status_code=400, detail="lthr_bpm cannot exceed hrmax_bpm"
            )

    # Get the most recent thresholds to carry forward values
    all_thresholds = await get_all_threshold_entries(db, user.id)
    previous = all_thresholds[0] if all_thresholds else None

    # When no explicit date is given and this is the user's very first threshold,
    # set effective_date far in the past so all existing historical activities are covered.
    if request.effective_date is not None:
        effective = request.effective_date
    elif previous is None:
        effective = date(2000, 1, 1)
    else:
        effective = date.today()
    
    # Determine final values - use new value if provided, else carry forward
    # Note: Once a threshold value is set, it cannot be removed - only changed.
    # Omitting a field preserves the previous value.
    final_ftp = request.ftp_watts if request.ftp_watts is not None else (previous.get("ftp_watts") if previous else None)
    final_lthr = request.lthr_bpm if request.lthr_bpm is not None else (previous.get("lthr_bpm") if previous else None)
    final_hrmax = request.hrmax_bpm if request.hrmax_bpm is not None else (previous.get("hrmax_bpm") if previous else None)
    
    # If user has previous thresholds but provided no new values, reject
    # (they should use the existing values or provide updates)
    if previous is not None:
        has_any_new_value = (
            request.ftp_watts is not None or 
            request.lthr_bpm is not None or 
            request.hrmax_bpm is not None
        )
        if not has_any_new_value:
            raise HTTPException(
                status_code=400,
                detail="You already have thresholds set. Provide at least one value to update."
            )
    
    # Validate lthr doesn't exceed hrmax after merging with previous
    if final_lthr is not None and final_hrmax is not None:
        if final_lthr > final_hrmax:
            raise HTTPException(
                status_code=400, detail="lthr_bpm cannot exceed hrmax_bpm"
            )

    # Create threshold metric entries
    await create_threshold_entries(
        db,
        user.id,
        effective,
        ftp_watts=final_ftp,
        lthr_bpm=final_lthr,
        hrmax_bpm=final_hrmax,
        source="manual",
    )
    await db.commit()

    # Enqueue async metric recalculation — observable via GET /me/recalculate-metrics
    await recalculation_job_repo.upsert_pending(user.id)
    await db.commit()

    try:
        await enqueue_recalculate_metrics_job(user.id)
    except Exception:
        logger.exception(
            "Failed to enqueue metric recalculation for user %s after threshold save",
            user.id,
        )
        # Mark job as failed so user sees accurate state
        await recalculation_job_repo.mark_failed(
            user.id, "Failed to enqueue job. Please try again."
        )
        await db.commit()

    # Return the new thresholds for this date
    return {
        "effective_date": effective.isoformat(),
        "ftp_watts": final_ftp,
        "lthr_bpm": final_lthr,
        "hrmax_bpm": final_hrmax,
        "source": "manual",
    }


# --- Zones ---


@router.get("/me/zones")
async def get_my_zones(db: DbSession, user: CurrentUser):
    """Get the current user's power and HR zones (computed from thresholds)."""
    # Get current thresholds
    threshold = await get_thresholds_for_date(db, user.id, date.today())

    power_zones = []
    hr_zones = []

    if threshold:
        if threshold.ftp_watts:
            power_zones = compute_power_zones(threshold.ftp_watts, user.power_zone_percentages)
        if threshold.lthr_bpm:
            hr_zones = compute_hr_zones(threshold.lthr_bpm, user.hr_zone_percentages)

    return {
        "power_zones": power_zones,
        "hr_zones": hr_zones,
    }


class UpdateZonePercentagesRequest(BaseModel):
    """Update custom zone percentages. Set to null to reset to defaults."""
    power_zone_percentages: dict | None = None
    hr_zone_percentages: dict | None = None
    reset_power_zones: bool = False
    reset_hr_zones: bool = False


@router.put("/me/zones")
async def update_my_zones(db: DbSession, user: CurrentUser, request: UpdateZonePercentagesRequest):
    """Update the current user's zone percentages or reset to defaults."""

    if request.reset_power_zones:
        user.power_zone_percentages = None
    elif request.power_zone_percentages is not None:
        user.power_zone_percentages = request.power_zone_percentages

    if request.reset_hr_zones:
        user.hr_zone_percentages = None
    elif request.hr_zone_percentages is not None:
        user.hr_zone_percentages = request.hr_zone_percentages

    await db.commit()
    await db.refresh(user)
    return await get_my_zones(db, user)


# --- Notifications ---


@router.get("/me/notifications")
async def get_notifications(db: DbSession, user: CurrentUser):
    """Get pending notifications for the current user."""
    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.status == "pending",
        )
        .order_by(Notification.created_at.desc())
    )
    notifications = result.scalars().all()

    return [
        {
            "id": n.id,
            "type": n.type,
            "message": n.message,
            "payload": json.loads(n.payload) if n.payload else None,
            "created_at": utc_str(n.created_at),
        }
        for n in notifications
    ]


@router.post("/me/notifications/{notification_id}/accept")
async def accept_notification(
    db: DbSession, user: CurrentUser, notification_id: int
):
    """Accept a notification (e.g., apply FTP suggestion)."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    notification = result.scalar_one_or_none()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )

    if notification.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notification already processed",
        )

    # Handle FTP suggestion
    if notification.type == "ftp_suggestion" and notification.payload:
        payload = json.loads(notification.payload)
        suggested_ftp = payload.get("suggested_ftp")

        if suggested_ftp:
            # Get current thresholds to copy LTHR and HRmax
            current = await get_thresholds_for_date(db, user.id, date.today())

            # Create new threshold entries with suggested FTP
            await create_threshold_entries(
                db,
                user.id,
                date.today(),
                ftp_watts=suggested_ftp,
                lthr_bpm=current.lthr_bpm if current else 165,
                hrmax_bpm=current.hrmax_bpm if current else 185,
                source="calculated",
                source_detail="ftp_suggestion_accepted",
            )

    # Mark notification as accepted
    notification.status = "accepted"
    await db.commit()

    return {"success": True}


@router.post("/me/notifications/{notification_id}/dismiss")
async def dismiss_notification(
    db: DbSession, user: CurrentUser, notification_id: int
):
    """Dismiss a notification."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    notification = result.scalar_one_or_none()

    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )

    if notification.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notification already processed",
        )

    notification.status = "dismissed"
    await db.commit()

    return {"success": True}



# --- Avatar ---


@router.post("/me/avatar")
async def upload_avatar(db: DbSession, user: CurrentUser, request: Request):
    """Upload a new avatar image for the current user."""
    # Read the raw body (image bytes)
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Content-Type must be an image")
    
    body = await request.body()
    if len(body) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")
    
    # Determine file extension from content type
    ext_map = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }
    ext = ext_map.get(content_type, ".jpg")
    
    # Ensure uploads directory exists
    uploads_base = Path(os.environ.get("TRAININGDASH_UPLOADS_DIR", "/app/uploads"))
    uploads_dir = uploads_base / "avatars"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    
    # Delete old avatar if exists
    if user.avatar_path:
        old_path = uploads_base.parent / user.avatar_path.lstrip("/")
        if old_path.exists():
            old_path.unlink()
    
    # Save new avatar
    filename = f"{user.id}{ext}"
    filepath = uploads_dir / filename
    with open(filepath, "wb") as f:
        f.write(body)
    
    # Update user record
    user.avatar_path = f"/uploads/avatars/{filename}"
    await db.commit()
    await db.refresh(user)
    
    return {"avatar_path": user.avatar_path}


@router.delete("/me/avatar")
async def delete_avatar(db: DbSession, user: CurrentUser):
    """Delete the current user's avatar."""
    if user.avatar_path:
        uploads_base = Path(os.environ.get("TRAININGDASH_UPLOADS_DIR", "/app/uploads"))
        filepath = uploads_base.parent / user.avatar_path.lstrip("/")
        if filepath.exists():
            filepath.unlink()
        user.avatar_path = None
        await db.commit()
    
    return {"success": True}


# --- User Sync ---


@router.post("/me/sync/garmin")
async def trigger_garmin_sync(garmin_repo: GarminCredentialsRepoD, user: CurrentUser):
    """Trigger a Garmin sync for the current user."""
    from trainingdash.jobs import create_redis_pool
    
    if not await garmin_repo.exists(user.id):
        raise HTTPException(
            status_code=400, detail="No Garmin credentials configured"
        )
    
    pool = await create_redis_pool()
    try:
        job = await pool.enqueue_job("sync_garmin_job", user.id)
        return {"success": True, "job_id": job.job_id}
    finally:
        await pool.close()


@router.post("/me/sync/xert")
async def trigger_xert_sync(xert_repo: XertCredentialsRepoD, user: CurrentUser):
    """Trigger a Xert sync for the current user."""
    from trainingdash.jobs import create_redis_pool
    
    if not await xert_repo.exists(user.id):
        raise HTTPException(
            status_code=400, detail="No Xert credentials configured"
        )
    
    pool = await create_redis_pool()
    try:
        job = await pool.enqueue_job("sync_xert_job", user.id)
        return {"success": True, "job_id": job.job_id}
    finally:
        await pool.close()



# --- OAuth Links ---


@router.get("/me/oauth-links")
async def list_oauth_links(oauth_repo: OAuthLinkRepoD, user: CurrentUser) -> list[dict]:
    """List connected OAuth providers for the current user.

    Returns a list of OAuth provider connections with their details.

    Args:
        oauth_repo: OAuth link repository.
        user: The authenticated user.

    Returns:
        List of OAuth link objects with provider, email, display_name,
        avatar_url, and created_at fields.
    """
    links = await oauth_repo.list_for_user(user.id)
    
    return [
        {
            "provider": link.provider,
            "provider_email": link.provider_email,
            "display_name": link.display_name,
            "avatar_url": link.avatar_url,
            "created_at": utc_str(link.created_at) if link.created_at else None,
        }
        for link in links
    ]


@router.delete("/me/oauth-links/{provider}")
async def disconnect_oauth_provider(
    oauth_repo: OAuthLinkRepoD, user: CurrentUser, provider: str
) -> dict:
    """Disconnect an OAuth provider from the current user's account.

    Includes lockout protection: refuses to disconnect if it would leave
    the user with no way to sign in (no password and no other OAuth links).

    Args:
        oauth_repo: OAuth link repository.
        user: The authenticated user.
        provider: The OAuth provider to disconnect ('github' or 'google').

    Returns:
        Success indicator.

    Raises:
        HTTPException: 404 if no such link exists, 400 if disconnecting
            would lock the user out.
    """
    # Check if the link exists
    link = await oauth_repo.get_for_user(user.id, provider)
    
    if not link:
        raise HTTPException(status_code=404, detail=f"No {provider} account connected")
    
    # Lockout protection: check if user would be locked out
    # User needs at least one auth method: password OR another OAuth link
    has_password = user.password_hash is not None and user.password_hash != ""
    
    if not has_password:
        # Count other OAuth links (total - 1 for current provider)
        total_links = await oauth_repo.count_for_user(user.id)
        
        if total_links <= 1:
            raise HTTPException(
                status_code=400,
                detail="Cannot disconnect: this is your only sign-in method. Set a password or connect another provider first.",
            )
    
    # Safe to delete
    await oauth_repo.delete(user.id, provider)
    
    return {"success": True}


class SetPasswordRequest(BaseModel):
    """Request body for setting a password."""

    password: str


@router.post("/me/set-password")
async def set_password(
    db: DbSession, user: CurrentUser, request: SetPasswordRequest
) -> dict:
    """Set a password for OAuth-only users who don't have one.

    Allows users who signed up via OAuth to add a password so they can
    also sign in with email/password.

    Args:
        db: Database session.
        user: The authenticated user.
        request: The password to set.

    Returns:
        Success indicator.

    Raises:
        HTTPException: 400 if user already has a password or password
            is too short.
    """
    # Only allow if user has no password
    if user.password_hash is not None and user.password_hash != "":
        raise HTTPException(
            status_code=400,
            detail="Password already set. Use change password instead.",
        )
    
    # Validate password
    if len(request.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long.",
        )
    
    # Set password
    user.password_hash = hash_password(request.password)
    await db.commit()
    
    return {"success": True}


@router.get("/me/has-password")
async def has_password(user: CurrentUser) -> dict:
    """Check if the current user has a password set.

    Used by the frontend to determine whether to show the
    'Set Password' option for OAuth-only users.

    Args:
        user: The authenticated user.

    Returns:
        Object with has_password boolean.
    """
    return {"has_password": user.password_hash is not None and user.password_hash != ""}



# --- Metric recalculation ---


@router.post("/me/recalculate-metrics")
async def trigger_recalculate_metrics(
    db: DbSession, recalc_repo: RecalculationJobRepoD, user: CurrentUser
):
    """Enqueue an async job to recompute training metrics for all activities.

    Upserts a RecalculationJob row to status=pending and enqueues the SAQ
    job. The job transitions to running → completed | failed asynchronously.
    Poll GET /me/recalculate-metrics to observe progress.
    """
    await recalc_repo.upsert_pending(user.id)
    await db.commit()

    try:
        await enqueue_recalculate_metrics_job(user.id)
    except Exception:
        logger.exception(
            "Failed to enqueue metric recalculation for user %s", user.id
        )
        # Mark job as failed so user sees accurate state
        await recalc_repo.upsert_failed(user.id)
        await db.commit()

    job = await recalc_repo.get_by_user_id(user.id)
    return recalculation_job_response(job)


@router.get("/me/recalculate-metrics")
async def get_recalculate_metrics_status(recalc_repo: RecalculationJobRepoD, user: CurrentUser):
    """Return the current recalculation job status for the authenticated user.

    Returns null if no recalculation has ever been triggered.
    """
    job = await recalc_repo.get_by_user_id(user.id)
    if job is None:
        return None
    return recalculation_job_response(job)
