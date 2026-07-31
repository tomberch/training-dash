from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
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
    app.post("/upload")(upload_activity)
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


async def list_activities(db: DbSession, user: CurrentUser):
    result = await db.execute(
        select(Activity)
        .where(Activity.user_id == user.id)
        .order_by(Activity.started_at.desc())
    )
    activities = result.scalars().all()
    return [_activity_summary(a) for a in activities]


async def get_activity(db: DbSession, user: CurrentUser, activity_id: int):
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == user.id)
    )
    activity = result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    return _activity_summary(activity)


async def get_activity_records(db: DbSession, user: CurrentUser, activity_id: int):
    result = await db.execute(
        select(Activity).where(Activity.id == activity_id, Activity.user_id == user.id)
    )
    activity = result.scalar_one_or_none()
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    result = await db.execute(
        select(Record).where(Record.activity_id == activity_id).order_by(Record.timestamp)
    )
    records = result.scalars().all()

    features = []
    for r in records:
        props = {
            "timestamp": r.timestamp.isoformat(),
            "distance_m": r.distance_m,
            "hr_bpm": r.hr_bpm,
            "power_w": r.power_w,
            "speed_mps": r.speed_mps,
            "altitude_m": r.altitude_m,
            "cadence_rpm": r.cadence_rpm,
        }
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

    return {
        "type": "FeatureCollection",
        "activity_id": activity_id,
        "features": features,
    }


async def upload_activity(db: DbSession, user: CurrentUser, file: UploadFile = File(...)):
    fit_bytes = await file.read()
    from fitter.ingest import ingest_fit
    activity = await ingest_fit(db, user.id, fit_bytes, "upload", file.filename or "upload.fit")
    if activity is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to parse FIT file")
    return {"id": activity.id, "started_at": activity.started_at.isoformat()}


app = create_app()