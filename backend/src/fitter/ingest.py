from datetime import datetime, timezone, timedelta
import logging
from typing import Any

from geoalchemy2.functions import ST_SetSRID, ST_MakePoint
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from fitter.models import Activity, Lap, Record

logger = logging.getLogger(__name__)

# Conversion factor: semicircles to degrees
SEMICIRCLES_TO_DEGREES = 180.0 / (2**31)


def _get_field(frame, name: str, fallback_name: str | None = None) -> Any:
    """Get a field value from a fitdecode frame, with optional fallback field name."""
    try:
        field = frame.get_field(name)
        if field is not None and field.value is not None:
            return field.value
    except KeyError:
        pass
    if fallback_name:
        try:
            field = frame.get_field(fallback_name)
            if field is not None and field.value is not None:
                return field.value
        except KeyError:
            pass
    return None


def _semicircles_to_degrees(semicircles: int | None) -> float | None:
    """Convert FIT semicircles to degrees."""
    if semicircles is None:
        return None
    return semicircles * SEMICIRCLES_TO_DEGREES


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    """Convert a datetime to naive UTC (remove timezone info)."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _safe_int(val: Any) -> int | None:
    """Convert value to int, returning None for invalid values like 0xFFFF."""
    if val is None:
        return None
    try:
        ival = int(val)
        # 0xFFFF and 0xFFFFFFFF are invalid markers in FIT files
        if ival == 0xFFFF or ival == 0xFFFFFFFF or ival == 0x7FFFFFFF:
            return None
        return ival
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> float | None:
    """Convert value to float, returning None for invalid values."""
    if val is None:
        return None
    try:
        fval = float(val)
        # Check for invalid marker values
        if fval > 1e9 or fval < -1e9:
            return None
        return fval
    except (ValueError, TypeError):
        return None


def parse_records(fit_bytes: bytes) -> dict[str, Any]:
    """Parse a FIT file and extract activity data using fitdecode."""
    import fitdecode
    
    records = []
    laps = []
    session_data = None
    
    with fitdecode.FitReader(fit_bytes) as fit:
        for frame in fit:
            if not isinstance(frame, fitdecode.FitDataMessage):
                continue
                
            if frame.name == "record":
                # Get position (convert from semicircles to degrees)
                lat = _semicircles_to_degrees(_get_field(frame, "position_lat"))
                lon = _semicircles_to_degrees(_get_field(frame, "position_long"))
                
                # Get timestamp
                ts = _to_naive_utc(_get_field(frame, "timestamp"))
                
                # Get metrics - prefer enhanced versions for newer FIT files
                speed = _safe_float(_get_field(frame, "enhanced_speed", "speed"))
                altitude = _safe_float(_get_field(frame, "enhanced_altitude", "altitude"))
                distance = _safe_float(_get_field(frame, "distance"))
                hr = _safe_int(_get_field(frame, "heart_rate"))
                power = _safe_int(_get_field(frame, "power"))
                cadence = _safe_int(_get_field(frame, "cadence"))
                
                records.append({
                    "timestamp": ts,
                    "lat": lat,
                    "lon": lon,
                    "distance_m": distance if distance is not None else 0,
                    "hr_bpm": hr,
                    "power_w": power,
                    "speed_mps": speed,
                    "altitude_m": altitude,
                    "cadence_rpm": cadence,
                })
                
            elif frame.name == "lap":
                start = _to_naive_utc(_get_field(frame, "start_time"))
                end = _to_naive_utc(_get_field(frame, "timestamp"))
                laps.append({
                    "start_time": start,
                    "end_time": end,
                    "total_distance_m": _safe_float(_get_field(frame, "total_distance")) or 0,
                    "avg_hr_bpm": _safe_int(_get_field(frame, "avg_heart_rate")),
                    "avg_power_w": _safe_int(_get_field(frame, "avg_power")),
                    "max_hr_bpm": _safe_int(_get_field(frame, "max_heart_rate")),
                })
                
            elif frame.name == "session":
                # Extract session summary data
                session_data = {
                    "started_at": _to_naive_utc(_get_field(frame, "start_time")),
                    "total_distance_m": _safe_float(_get_field(frame, "total_distance")) or 0,
                    "total_timer_time": _safe_float(_get_field(frame, "total_timer_time")),
                    "total_elapsed_time": _safe_float(_get_field(frame, "total_elapsed_time")),
                    "total_ascent": _safe_int(_get_field(frame, "total_ascent")),
                    "avg_speed": _safe_float(_get_field(frame, "enhanced_avg_speed", "avg_speed")),
                    "max_speed": _safe_float(_get_field(frame, "enhanced_max_speed", "max_speed")),
                    "avg_hr": _safe_int(_get_field(frame, "avg_heart_rate")),
                    "max_hr": _safe_int(_get_field(frame, "max_heart_rate")),
                    "avg_power": _safe_int(_get_field(frame, "avg_power")),
                }
    
    # Build result from session or compute from records
    if session_data and session_data["started_at"]:
        started_at = session_data["started_at"]
        total_distance = session_data["total_distance_m"]
        moving_time = int(session_data["total_timer_time"] or 0)
        elapsed_time = int(session_data["total_elapsed_time"] or 0)
        elev_gain = session_data["total_ascent"] or 0
        avg_speed = session_data["avg_speed"] or 0
        avg_hr = session_data["avg_hr"]
        avg_power = session_data["avg_power"]
        max_speed = session_data["max_speed"] or 0
        max_hr = session_data["max_hr"]
    else:
        # Fallback: compute from records
        started_at = records[0]["timestamp"] if records else datetime.utcnow()
        total_distance = records[-1]["distance_m"] if records else 0
        moving_time = 0
        elapsed_time = 0
        elev_gain = 0
        avg_speed = 0
        avg_hr = None
        avg_power = None
        max_speed = 0
        max_hr = None
    
    return {
        "started_at": started_at,
        "total_distance_m": float(total_distance),
        "moving_time_s": moving_time,
        "elapsed_time_s": elapsed_time,
        "elevation_gain_m": float(elev_gain),
        "avg_speed_mps": float(avg_speed),
        "avg_hr_bpm": avg_hr,
        "avg_power_w": avg_power,
        "max_speed_mps": float(max_speed),
        "max_hr_bpm": max_hr,
        "records": records,
        "laps": laps,
    }


async def is_duplicate_activity(
    db: AsyncSession,
    user_id: int,
    started_at: datetime,
    total_distance_m: float,
    source: str,
) -> bool:
    """
    Check if an activity is a duplicate based on:
    - Same user
    - started_at within 60 seconds
    - total_distance_m within 1%
    
    Used to prevent duplicate imports when user syncs from both Xert and Garmin,
    or re-syncs the same source. First activity wins (kept), duplicates are skipped.
    
    Args:
        db: Database session
        user_id: The user's ID
        started_at: Activity start time
        total_distance_m: Total distance in meters
        source: Source identifier (for logging only)
    
    Returns:
        True if a matching activity already exists, False otherwise
    """
    # Define time window: +/- 60 seconds
    time_start = started_at - timedelta(seconds=60)
    time_end = started_at + timedelta(seconds=60)
    
    # Query for activities in the time window
    result = await db.execute(
        select(Activity).where(
            and_(
                Activity.user_id == user_id,
                Activity.started_at >= time_start,
                Activity.started_at <= time_end,
            )
        )
    )
    candidates = result.scalars().all()
    
    for candidate in candidates:
        # Check distance within 1%
        if total_distance_m > 0 and candidate.total_distance_m > 0:
            distance_ratio = candidate.total_distance_m / total_distance_m
            if 0.99 <= distance_ratio <= 1.01:
                logger.info(
                    f"Duplicate activity detected: {source} activity at {started_at} "
                    f"({total_distance_m:.0f}m) matches existing activity {candidate.id} "
                    f"from {candidate.source} at {candidate.started_at} ({candidate.total_distance_m:.0f}m)"
                )
                return True
        elif total_distance_m == 0 and candidate.total_distance_m == 0:
            # Both have zero distance (indoor/stationary) - treat as duplicate by time only
            logger.info(
                f"Duplicate activity detected: {source} activity at {started_at} "
                f"(0m) matches existing activity {candidate.id} from {candidate.source}"
            )
            return True
    
    return False


async def ingest_fit(
    db: AsyncSession,
    user_id: int,
    fit_bytes: bytes,
    source: str,
    source_ref: str,
) -> Activity | None:
    try:
        parsed = parse_records(fit_bytes)
    except Exception:
        return None

    activity = Activity(
        user_id=user_id,
        source=source,
        source_ref=source_ref,
        started_at=parsed["started_at"],
        total_distance_m=parsed["total_distance_m"],
        moving_time_s=parsed["moving_time_s"],
        elapsed_time_s=parsed["elapsed_time_s"],
        elevation_gain_m=parsed["elevation_gain_m"],
        avg_speed_mps=parsed["avg_speed_mps"],
        avg_hr_bpm=parsed["avg_hr_bpm"],
        avg_power_w=parsed["avg_power_w"],
        max_speed_mps=parsed["max_speed_mps"],
        max_hr_bpm=parsed["max_hr_bpm"],
        raw_fit=fit_bytes,
    )
    db.add(activity)
    await db.flush()

    for i, lap_data in enumerate(parsed["laps"]):
        lap = Lap(
            activity_id=activity.id,
            lap_index=i,
            start_time=lap_data["start_time"],
            end_time=lap_data["end_time"],
            total_distance_m=lap_data["total_distance_m"],
            avg_hr_bpm=lap_data["avg_hr_bpm"],
            avg_power_w=lap_data["avg_power_w"],
            max_hr_bpm=lap_data["max_hr_bpm"],
        )
        db.add(lap)

    for r in parsed["records"]:
        geom = None
        if r["lat"] is not None and r["lon"] is not None:
            geom = ST_SetSRID(ST_MakePoint(r["lon"], r["lat"]), 4326)
        record = Record(
            activity_id=activity.id,
            timestamp=r["timestamp"],
            lat=r["lat"],
            lon=r["lon"],
            distance_m=r["distance_m"],
            hr_bpm=r["hr_bpm"],
            power_w=r["power_w"],
            speed_mps=r["speed_mps"],
            altitude_m=r["altitude_m"],
            cadence_rpm=r["cadence_rpm"],
            geom=geom,
        )
        db.add(record)

    await db.commit()
    await db.refresh(activity)

    from fitter.route_matching import find_or_create_route_id
    route_id = await find_or_create_route_id(db, activity, parsed["records"])
    if route_id is not None:
        activity.route_id = route_id
        await db.commit()
        await db.refresh(activity)

    return activity