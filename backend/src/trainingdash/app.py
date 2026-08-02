import logging
import uuid
from datetime import datetime, timezone, timedelta, date
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload

from trainingdash.auth import AdminUser, CurrentUser, DbSession, LoginRequest, create_session_cookie, hash_password, verify_password
from trainingdash.db import Base, async_session, engine
from trainingdash.models import Activity, Lap, Record, User, XertCredentials, GarminCredentials
from trainingdash.xert import get_xert_client, XertAPIError
from trainingdash.garmin import get_garmin_client, GarminAPIError, GarminMFARequired
from trainingdash.crypto import encrypt, decrypt, EncryptionError

logger = logging.getLogger(__name__)


def generate_error_id() -> str:
    """Generate a short, unique error ID for tracking."""
    return uuid.uuid4().hex[:8]


def create_app() -> FastAPI:
    app = FastAPI(title="TrainingDash")
    
    # Global exception handler for unhandled errors
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # Don't intercept HTTPExceptions - let FastAPI handle those
        if isinstance(exc, HTTPException):
            raise exc
        
        error_id = generate_error_id()
        logger.error(
            f"Unhandled exception [error_id={error_id}] {request.method} {request.url.path}: {exc}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal error occurred",
                "error_id": error_id,
            },
        )
    
    # Enhanced HTTPException handler to include error_id for 500s
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        content = {"detail": exc.detail}
        if exc.status_code >= 500:
            error_id = generate_error_id()
            content["error_id"] = error_id
            logger.error(
                f"HTTP {exc.status_code} [error_id={error_id}] {request.method} {request.url.path}: {exc.detail}"
            )
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=getattr(exc, "headers", None),
        )
    
    app.post("/login")(login)
    app.post("/logout")(logout)
    app.get("/me")(get_me)
    app.patch("/me")(update_me)
    app.get("/activities")(list_activities)
    app.get("/activities/{activity_id}")(get_activity)
    app.get("/activities/{activity_id}/records")(get_activity_records)
    app.get("/activities/{activity_id}/same-route")(get_same_route_activities)
    app.get("/activities/{activity_id}/compare")(compare_activities)
    app.get("/records")(get_records)
    app.post("/upload")(upload_activity)
    app.get("/jobs/{job_id}")(get_job_status)
    # Admin routes
    app.get("/admin/users")(admin_list_users)
    app.post("/admin/users")(admin_create_user)
    app.post("/admin/users/{user_id}/reset-password")(admin_reset_password)
    app.post("/admin/users/{user_id}/sync")(admin_trigger_sync)
    app.get("/admin/users/{user_id}/xert-credentials")(admin_get_xert_credentials)
    app.put("/admin/users/{user_id}/xert-credentials")(admin_set_xert_credentials)
    app.delete("/admin/users/{user_id}/xert-credentials")(admin_delete_xert_credentials)
    # User Xert credentials (self-service)
    app.get("/me/xert-credentials")(get_my_xert_credentials)
    app.put("/me/xert-credentials")(put_my_xert_credentials)
    app.delete("/me/xert-credentials")(delete_my_xert_credentials)
    # User Garmin credentials (self-service)
    app.get("/me/garmin-credentials")(get_my_garmin_credentials)
    app.put("/me/garmin-credentials")(put_my_garmin_credentials)
    app.post("/me/garmin-credentials/mfa")(complete_garmin_mfa)
    app.delete("/me/garmin-credentials")(delete_my_garmin_credentials)
    return app


async def login(db: DbSession, request: LoginRequest):
    result = await db.execute(select(User).where(User.username == request.username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    cookie = create_session_cookie(user.id)
    response = JSONResponse({"user_id": user.id, "username": user.username, "is_admin": user.is_admin})
    response.set_cookie("session", cookie, httponly=True, samesite="lax")
    return response


async def logout(user: CurrentUser):
    """Log out the current user by clearing the session cookie."""
    response = JSONResponse({"success": True})
    response.delete_cookie("session")
    return response


def _user_response(user: User) -> dict:
    """Return a dict of user info for API responses."""
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "unit_system": user.unit_system,
        "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
        "weight_kg": float(user.weight_kg) if user.weight_kg else None,
    }


async def get_me(user: CurrentUser):
    """Get the current user's info."""
    return _user_response(user)


class UpdateMeRequest(BaseModel):
    unit_system: str | None = None
    date_of_birth: date | None = None
    weight_kg: float | None = None


async def update_me(db: DbSession, user: CurrentUser, request: UpdateMeRequest):
    """Update the current user's preferences."""
    if request.unit_system is not None:
        if request.unit_system not in ("metric", "imperial"):
            raise HTTPException(status_code=400, detail="unit_system must be 'metric' or 'imperial'")
        user.unit_system = request.unit_system
    
    if request.date_of_birth is not None:
        today = date.today()
        age = (today - request.date_of_birth).days // 365
        if request.date_of_birth > today:
            raise HTTPException(status_code=400, detail="date_of_birth cannot be in the future")
        if age < 10 or age > 100:
            raise HTTPException(status_code=400, detail="date_of_birth must represent an age between 10 and 100")
        user.date_of_birth = request.date_of_birth
    
    if request.weight_kg is not None:
        if request.weight_kg <= 0:
            raise HTTPException(status_code=400, detail="weight_kg must be positive")
        if request.weight_kg > 500:
            raise HTTPException(status_code=400, detail="weight_kg must be realistic (max 500)")
        user.weight_kg = request.weight_kg
    
    await db.commit()
    await db.refresh(user)
    
    return _user_response(user)


# User Xert credentials (self-service)

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
        "sync_since": (creds.sync_since.date() if hasattr(creds.sync_since, 'date') else creds.sync_since).isoformat() if creds.sync_since else None,
    }


class MyXertCredentialsRequest(BaseModel):
    xert_email: str
    xert_password: str
    sync_since: date | None = None


async def put_my_xert_credentials(db: DbSession, user: CurrentUser, request: MyXertCredentialsRequest):
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
    # Determine sync_since: use provided date or default to 90 days ago
    if request.sync_since is not None:
        sync_since_dt = datetime.combine(request.sync_since, datetime.min.time())
    else:
        sync_since_dt = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=90)
    
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


# User Garmin credentials (self-service)

# In-memory storage for pending MFA sessions (keyed by user_id)
# In production, this could be stored in Redis with TTL
_pending_garmin_mfa: dict[int, dict] = {}


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
        "sync_since": (creds.sync_since.date() if hasattr(creds.sync_since, 'date') else creds.sync_since).isoformat() if creds.sync_since else None,
    }


class MyGarminCredentialsRequest(BaseModel):
    garmin_email: str
    garmin_password: str
    sync_since: date | None = None


async def put_my_garmin_credentials(db: DbSession, user: CurrentUser, request: MyGarminCredentialsRequest):
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


async def complete_garmin_mfa(db: DbSession, user: CurrentUser, request: GarminMFARequest):
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
    # Determine sync_since: use provided date or default to 90 days ago
    if sync_since is not None:
        sync_since_dt = datetime.combine(sync_since, datetime.min.time())
    else:
        sync_since_dt = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=90)
    
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to parse FIT file")
    return {"id": activity.id, "started_at": activity.started_at.isoformat()}


async def get_job_status(user: CurrentUser, job_id: str):
    """Get the status of an ingest job."""
    from trainingdash.jobs import get_job_status as _get_job_status
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

    from trainingdash.resampler import compute_time_gap_series
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


# Admin endpoints

class CreateUserRequest(BaseModel):
    username: str
    password: str


class ResetPasswordRequest(BaseModel):
    password: str


async def _get_user_or_404(db: DbSession, user_id: int) -> User:
    """Fetch a user by ID or raise 404."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _user_summary(user: User) -> dict:
    """Return a dict summary of a user for admin responses."""
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
    }


async def admin_list_users(db: DbSession, admin: AdminUser):
    """List all users (admin only)."""
    result = await db.execute(select(User).order_by(User.id))
    users = result.scalars().all()
    return [_user_summary(u) for u in users]


async def admin_create_user(db: DbSession, admin: AdminUser, request: CreateUserRequest):
    """Create a new user account (admin only)."""
    # Check if username already exists
    existing = await db.execute(select(User).where(User.username == request.username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    
    user = User(
        username=request.username,
        password_hash=hash_password(request.password),
        is_admin=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _user_summary(user)


async def admin_reset_password(db: DbSession, admin: AdminUser, user_id: int, request: ResetPasswordRequest):
    """Reset a user's password (admin only)."""
    user = await _get_user_or_404(db, user_id)
    user.password_hash = hash_password(request.password)
    await db.commit()
    return {"success": True}


async def admin_trigger_sync(db: DbSession, admin: AdminUser, user_id: int):
    """Trigger sync for a user (admin only). Triggers both Xert and Garmin if configured."""
    await _get_user_or_404(db, user_id)
    
    from trainingdash.jobs import enqueue_sync_xert_job, enqueue_sync_garmin_job
    
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
        return {"success": True, "job_ids": None, "message": "No integrations configured or Redis not available"}
    return {"success": True, "job_ids": job_ids}


class XertCredentialsRequest(BaseModel):
    xert_email: str
    xert_password: str


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


async def admin_set_xert_credentials(db: DbSession, admin: AdminUser, user_id: int, request: XertCredentialsRequest):
    """Set or update Xert credentials for a user (admin only). Password is encrypted at rest."""
    await _get_user_or_404(db, user_id)
    
    from trainingdash.crypto import encrypt, EncryptionError
    
    try:
        encrypted_password = encrypt(request.xert_password)
    except EncryptionError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
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


app = create_app()