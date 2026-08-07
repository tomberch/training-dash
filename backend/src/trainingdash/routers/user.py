"""User endpoints: /me/*, thresholds, zones, integrations, notifications."""

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, delete

from trainingdash.auth import CurrentUser, DbSession, hash_password
from trainingdash.crypto import encrypt, EncryptionError
from trainingdash.garmin import get_garmin_client, GarminAPIError, GarminMFARequired
from trainingdash.jobs import enqueue_recalculate_metrics_job
from trainingdash.models import (
    GarminCredentials,
    HrZone,
    Notification,
    PowerZone,
    RecalculationJob,
    ThresholdHistory,
    UserOAuthLink,
    XertCredentials,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from trainingdash.routers.serializers import (
    hr_zone_response,
    power_zone_response,
    recalculation_job_response,
    threshold_response,
    user_response,
)
from trainingdash.routers.datetime_utils import utc_str
from trainingdash.thresholds import (
    compute_hr_zones,
    compute_power_zones,
    ensure_default_thresholds,
    ensure_zones_exist,
    regenerate_zones_from_threshold,
)
from trainingdash.xert import get_xert_client, XertAPIError

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

    if request.hr_derived_power_enabled is not None:
        user.hr_derived_power_enabled = request.hr_derived_power_enabled

    await db.commit()
    await db.refresh(user)

    return user_response(user)


# --- Xert credentials ---


@router.get("/me/xert-credentials")
async def get_my_xert_credentials(db: DbSession, user: CurrentUser):
    """Get the current user's Xert credentials status. Never returns the password."""
    result = await db.execute(
        select(XertCredentials).where(XertCredentials.user_id == user.id)
    )
    creds = result.scalar_one_or_none()
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
    db: DbSession, user: CurrentUser, request: MyXertCredentialsRequest
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

    # Upsert credentials
    result = await db.execute(
        select(XertCredentials).where(XertCredentials.user_id == user.id)
    )
    creds = result.scalar_one_or_none()

    if creds is None:
        creds = XertCredentials(
            user_id=user.id,
            xert_email=request.xert_email,
            encrypted_password=encrypted_password,
            sync_since=sync_since_dt,
        )
        db.add(creds)
    else:
        creds.xert_email = request.xert_email
        creds.encrypted_password = encrypted_password
        creds.sync_since = sync_since_dt

    await db.commit()
    return {"success": True, "xert_email": request.xert_email}


@router.delete("/me/xert-credentials")
async def delete_my_xert_credentials(db: DbSession, user: CurrentUser):
    """Delete the current user's Xert credentials (disconnect Xert)."""
    result = await db.execute(
        select(XertCredentials).where(XertCredentials.user_id == user.id)
    )
    creds = result.scalar_one_or_none()
    if creds is not None:
        await db.delete(creds)
        await db.commit()
    return {"success": True}


# --- Garmin credentials ---


@router.get("/me/garmin-credentials")
async def get_my_garmin_credentials(db: DbSession, user: CurrentUser):
    """Get the current user's Garmin credentials status. Never returns the password."""
    result = await db.execute(
        select(GarminCredentials).where(GarminCredentials.user_id == user.id)
    )
    creds = result.scalar_one_or_none()
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
    db: DbSession, user: CurrentUser, request: MyGarminCredentialsRequest
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
        db, user, request.garmin_email, request.garmin_password, request.sync_since
    )


class GarminMFARequest(BaseModel):
    mfa_code: str


@router.post("/me/garmin-credentials/mfa")
async def complete_garmin_mfa(
    db: DbSession, user: CurrentUser, request: GarminMFARequest
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

    return await _save_garmin_credentials(db, user, email, password, sync_since)


async def _save_garmin_credentials(
    db: DbSession,
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

    # Upsert credentials
    result = await db.execute(
        select(GarminCredentials).where(GarminCredentials.user_id == user.id)
    )
    creds = result.scalar_one_or_none()

    if creds is None:
        creds = GarminCredentials(
            user_id=user.id,
            garmin_email=email,
            encrypted_password=encrypted_password,
            sync_since=sync_since_dt,
        )
        db.add(creds)
    else:
        creds.garmin_email = email
        creds.encrypted_password = encrypted_password
        creds.sync_since = sync_since_dt

    await db.commit()
    return {"success": True, "garmin_email": email}


@router.delete("/me/garmin-credentials")
async def delete_my_garmin_credentials(db: DbSession, user: CurrentUser):
    """Delete the current user's Garmin credentials (disconnect Garmin)."""
    # Clean up any pending MFA session
    _pending_garmin_mfa.pop(user.id, None)

    result = await db.execute(
        select(GarminCredentials).where(GarminCredentials.user_id == user.id)
    )
    creds = result.scalar_one_or_none()
    if creds is not None:
        await db.delete(creds)
        await db.commit()
    return {"success": True}


# --- Thresholds ---


@router.get("/me/thresholds")
async def get_my_thresholds(db: DbSession, user: CurrentUser):
    """Get the current user's threshold history, most recent first."""
    # Ensure defaults exist if user has DOB
    await ensure_default_thresholds(db, user)

    result = await db.execute(
        select(ThresholdHistory)
        .where(ThresholdHistory.user_id == user.id)
        .order_by(ThresholdHistory.effective_date.desc())
    )
    thresholds = result.scalars().all()
    return [threshold_response(t) for t in thresholds]


class CreateThresholdRequest(BaseModel):
    effective_date: date | None = None
    ftp_watts: int | None = None
    lthr_bpm: int | None = None
    hrmax_bpm: int | None = None


@router.post("/me/thresholds")
async def create_threshold(
    db: DbSession, user: CurrentUser, request: CreateThresholdRequest
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

    # Get the most recent threshold to carry forward values
    result = await db.execute(
        select(ThresholdHistory)
        .where(ThresholdHistory.user_id == user.id)
        .order_by(ThresholdHistory.effective_date.desc())
        .limit(1)
    )
    previous = result.scalar_one_or_none()

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
    final_ftp = request.ftp_watts if request.ftp_watts is not None else (previous.ftp_watts if previous else None)
    final_lthr = request.lthr_bpm if request.lthr_bpm is not None else (previous.lthr_bpm if previous else None)
    final_hrmax = request.hrmax_bpm if request.hrmax_bpm is not None else (previous.hrmax_bpm if previous else None)
    
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

    # Upsert: check if there's already a threshold for this user on this date
    existing_result = await db.execute(
        select(ThresholdHistory).where(
            ThresholdHistory.user_id == user.id,
            ThresholdHistory.effective_date == effective,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        # Update existing row for today
        existing.ftp_watts = final_ftp
        existing.lthr_bpm = final_lthr
        existing.hrmax_bpm = final_hrmax
        threshold = existing
    else:
        # Create new row
        threshold = ThresholdHistory(
            user_id=user.id,
            effective_date=effective,
            ftp_watts=final_ftp,
            lthr_bpm=final_lthr,
            hrmax_bpm=final_hrmax,
        )
        db.add(threshold)

    await db.commit()
    await db.refresh(threshold)

    # Regenerate zones if they exist and are not custom (best-effort)
    try:
        await regenerate_zones_from_threshold(db, user.id, threshold)
    except Exception:
        logger.exception(
            "Zone regeneration failed after threshold save for user %s — zones may be stale",
            user.id,
        )

    # Enqueue async metric recalculation — observable via GET /me/recalculate-metrics
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        pg_insert(RecalculationJob)
        .values(user_id=user.id, status="pending", started_at=now)
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={"status": "pending", "started_at": now, "completed_at": None, "error_message": None},
        )
    )
    await db.commit()

    try:
        await enqueue_recalculate_metrics_job(user.id)
    except Exception:
        logger.exception(
            "Failed to enqueue metric recalculation for user %s after threshold save",
            user.id,
        )
        # Mark job as failed so user sees accurate state
        await db.execute(
            pg_insert(RecalculationJob)
            .values(user_id=user.id, status="failed", started_at=now)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "status": "failed",
                    "completed_at": now,
                    "error_message": "Failed to enqueue job. Please try again.",
                    "activities_updated": None,
                },
            )
        )
        await db.commit()

    return threshold_response(threshold)


# --- Zones ---


@router.get("/me/zones")
async def get_my_zones(db: DbSession, user: CurrentUser):
    """Get the current user's power and HR zones."""
    zones_exist = await ensure_zones_exist(db, user)

    if not zones_exist:
        return {"power_zones": [], "hr_zones": []}

    power_result = await db.execute(
        select(PowerZone)
        .where(PowerZone.user_id == user.id)
        .order_by(PowerZone.zone_number)
    )
    power_zones = power_result.scalars().all()

    hr_result = await db.execute(
        select(HrZone).where(HrZone.user_id == user.id).order_by(HrZone.zone_number)
    )
    hr_zones = hr_result.scalars().all()

    return {
        "power_zones": [power_zone_response(z) for z in power_zones],
        "hr_zones": [hr_zone_response(z) for z in hr_zones],
    }


class ZoneUpdate(BaseModel):
    zone_number: int
    name: str | None = None
    min_value: int | None = None
    max_value: int | None = None


class UpdateZonesRequest(BaseModel):
    power_zones: list[ZoneUpdate] | None = None
    hr_zones: list[ZoneUpdate] | None = None
    reset_to_defaults: bool = False


@router.put("/me/zones")
async def update_my_zones(db: DbSession, user: CurrentUser, request: UpdateZonesRequest):
    """Update the current user's zones or reset to defaults."""

    if request.reset_to_defaults:
        # Get current threshold
        result = await db.execute(
            select(ThresholdHistory)
            .where(ThresholdHistory.user_id == user.id)
            .order_by(ThresholdHistory.effective_date.desc())
            .limit(1)
        )
        threshold = result.scalar_one_or_none()
        if threshold is None:
            raise HTTPException(
                status_code=400, detail="No thresholds configured, cannot reset zones"
            )

        # Delete all zones and recreate
        await db.execute(delete(PowerZone).where(PowerZone.user_id == user.id))
        await db.execute(delete(HrZone).where(HrZone.user_id == user.id))

        for zone_data in compute_power_zones(threshold.ftp_watts):
            zone = PowerZone(
                user_id=user.id,
                zone_number=zone_data["zone_number"],
                name=zone_data["name"],
                min_watts=zone_data["min_watts"],
                max_watts=zone_data["max_watts"],
                is_custom=False,
            )
            db.add(zone)

        for zone_data in compute_hr_zones(threshold.lthr_bpm):
            zone = HrZone(
                user_id=user.id,
                zone_number=zone_data["zone_number"],
                name=zone_data["name"],
                min_bpm=zone_data["min_bpm"],
                max_bpm=zone_data["max_bpm"],
                is_custom=False,
            )
            db.add(zone)

        await db.commit()
        return await get_my_zones(db, user)

    # Ensure zones exist first
    zones_exist = await ensure_zones_exist(db, user)
    if not zones_exist:
        raise HTTPException(
            status_code=400, detail="No thresholds configured, cannot update zones"
        )

    # Update power zones
    if request.power_zones:
        for update in request.power_zones:
            result = await db.execute(
                select(PowerZone).where(
                    PowerZone.user_id == user.id,
                    PowerZone.zone_number == update.zone_number,
                )
            )
            zone = result.scalar_one_or_none()
            if zone is None:
                raise HTTPException(
                    status_code=400, detail=f"Power zone {update.zone_number} not found"
                )

            if update.name is not None:
                zone.name = update.name
            if update.min_value is not None:
                zone.min_watts = update.min_value
            if update.max_value is not None:
                zone.max_watts = update.max_value
            zone.is_custom = True

    # Update HR zones
    if request.hr_zones:
        for update in request.hr_zones:
            result = await db.execute(
                select(HrZone).where(
                    HrZone.user_id == user.id, HrZone.zone_number == update.zone_number
                )
            )
            zone = result.scalar_one_or_none()
            if zone is None:
                raise HTTPException(
                    status_code=400, detail=f"HR zone {update.zone_number} not found"
                )

            if update.name is not None:
                zone.name = update.name
            if update.min_value is not None:
                zone.min_bpm = update.min_value
            if update.max_value is not None:
                zone.max_bpm = update.max_value
            zone.is_custom = True

    await db.commit()
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
            # Get current threshold to copy LTHR and HRmax
            result = await db.execute(
                select(ThresholdHistory)
                .where(ThresholdHistory.user_id == user.id)
                .order_by(ThresholdHistory.effective_date.desc())
                .limit(1)
            )
            current = result.scalar_one_or_none()

            # Create new threshold with suggested FTP
            new_threshold = ThresholdHistory(
                user_id=user.id,
                effective_date=date.today(),
                ftp_watts=suggested_ftp,
                lthr_bpm=current.lthr_bpm if current else 165,
                hrmax_bpm=current.hrmax_bpm if current else 185,
            )
            db.add(new_threshold)

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


async def _trigger_user_sync(
    db: DbSession, 
    user_id: int, 
    cred_model: type, 
    job_name: str,
    integration_name: str
) -> dict:
    """Generic helper to trigger a sync job for a user's integration."""
    from trainingdash.jobs import create_redis_pool
    
    # Check if user has credentials for this integration
    result = await db.execute(
        select(cred_model).where(cred_model.user_id == user_id)
    )
    creds = result.scalar_one_or_none()
    if creds is None:
        raise HTTPException(
            status_code=400, detail=f"No {integration_name} credentials configured"
        )
    
    # Enqueue sync job
    pool = await create_redis_pool()
    try:
        job = await pool.enqueue_job(job_name, user_id)
        return {"success": True, "job_id": job.job_id}
    finally:
        await pool.close()


@router.post("/me/sync/garmin")
async def trigger_garmin_sync(db: DbSession, user: CurrentUser):
    """Trigger a Garmin sync for the current user."""
    return await _trigger_user_sync(
        db, user.id, GarminCredentials, "sync_garmin_job", "Garmin"
    )


@router.post("/me/sync/xert")
async def trigger_xert_sync(db: DbSession, user: CurrentUser):
    """Trigger a Xert sync for the current user."""
    return await _trigger_user_sync(
        db, user.id, XertCredentials, "sync_xert_job", "Xert"
    )



# --- OAuth Links ---


@router.get("/me/oauth-links")
async def list_oauth_links(db: DbSession, user: CurrentUser) -> list[dict]:
    """List connected OAuth providers for the current user.

    Returns a list of OAuth provider connections with their details.

    Args:
        db: Database session.
        user: The authenticated user.

    Returns:
        List of OAuth link objects with provider, email, display_name,
        avatar_url, and created_at fields.
    """
    result = await db.execute(
        select(UserOAuthLink).where(UserOAuthLink.user_id == user.id)
    )
    links = result.scalars().all()
    
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
    db: DbSession, user: CurrentUser, provider: str
) -> dict:
    """Disconnect an OAuth provider from the current user's account.

    Includes lockout protection: refuses to disconnect if it would leave
    the user with no way to sign in (no password and no other OAuth links).

    Args:
        db: Database session.
        user: The authenticated user.
        provider: The OAuth provider to disconnect ('github' or 'google').

    Returns:
        Success indicator.

    Raises:
        HTTPException: 404 if no such link exists, 400 if disconnecting
            would lock the user out.
    """
    # Check if the link exists
    result = await db.execute(
        select(UserOAuthLink).where(
            UserOAuthLink.user_id == user.id,
            UserOAuthLink.provider == provider,
        )
    )
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(status_code=404, detail=f"No {provider} account connected")
    
    # Lockout protection: check if user would be locked out
    # User needs at least one auth method: password OR another OAuth link
    has_password = user.password_hash is not None and user.password_hash != ""
    
    if not has_password:
        # Count other OAuth links
        other_links_result = await db.execute(
            select(UserOAuthLink).where(
                UserOAuthLink.user_id == user.id,
                UserOAuthLink.provider != provider,
            )
        )
        other_links = other_links_result.scalars().all()
        
        if len(other_links) == 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot disconnect: this is your only sign-in method. Set a password or connect another provider first.",
            )
    
    # Safe to delete
    await db.delete(link)
    await db.commit()
    
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
async def trigger_recalculate_metrics(db: DbSession, user: CurrentUser):
    """Enqueue an async job to recompute training metrics for all activities.

    Upserts a RecalculationJob row to status=pending and enqueues the ARQ
    job. The job transitions to running → completed | failed asynchronously.
    Poll GET /me/recalculate-metrics to observe progress.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        pg_insert(RecalculationJob)
        .values(user_id=user.id, status="pending", started_at=now)
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={"status": "pending", "started_at": now, "completed_at": None, "error_message": None},
        )
    )
    await db.commit()

    try:
        await enqueue_recalculate_metrics_job(user.id)
    except Exception:
        logger.exception(
            "Failed to enqueue metric recalculation for user %s", user.id
        )
        # Mark job as failed so user sees accurate state
        await db.execute(
            pg_insert(RecalculationJob)
            .values(user_id=user.id, status="failed", started_at=now)
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "status": "failed",
                    "completed_at": now,
                    "error_message": "Failed to enqueue job. Please try again.",
                    "activities_updated": None,
                },
            )
        )
        await db.commit()

    result = await db.execute(
        select(RecalculationJob).where(RecalculationJob.user_id == user.id)
    )
    job = result.scalar_one()
    return recalculation_job_response(job)


@router.get("/me/recalculate-metrics")
async def get_recalculate_metrics_status(db: DbSession, user: CurrentUser):
    """Return the current recalculation job status for the authenticated user.

    Returns null if no recalculation has ever been triggered.
    """
    result = await db.execute(
        select(RecalculationJob).where(RecalculationJob.user_id == user.id)
    )
    job = result.scalar_one_or_none()
    if job is None:
        return None
    return recalculation_job_response(job)
