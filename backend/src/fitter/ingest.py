from datetime import datetime, timezone
from typing import Any

from geoalchemy2.functions import ST_SetSRID, ST_MakePoint
from sqlalchemy.ext.asyncio import AsyncSession

from fitter.models import Activity, Lap, Record

FIT_EPOCH = datetime(1989, 12, 31, tzinfo=timezone.utc)


def _field(msg: Any, name: str) -> Any:
    field = msg.get_field_by_name(name)
    if field is None or not field.is_valid():
        return None
    return field.get_value()


def _fit_timestamp_to_datetime(ts: float | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).replace(tzinfo=None)


def parse_records(fit_bytes: bytes) -> dict[str, Any]:
    from fit_tool.fit_file import FitFile

    fit = FitFile.from_bytes(fit_bytes)

    record_msgs = []
    lap_msgs = []
    session_msg = None

    for rec in fit.records:
        msg = rec.message
        if not hasattr(msg, "name"):
            continue
        if msg.name == "record":
            record_msgs.append(msg)
        elif msg.name == "lap":
            lap_msgs.append(msg)
        elif msg.name == "session":
            session_msg = msg

    records = []
    for rm in record_msgs:
        lat = _field(rm, "position_lat")
        lon = _field(rm, "position_long")
        ts = _fit_timestamp_to_datetime(_field(rm, "timestamp"))
        distance = _field(rm, "distance")
        hr = _field(rm, "heart_rate")
        power = _field(rm, "power")
        speed = _field(rm, "speed")
        altitude = _field(rm, "altitude")
        cadence = _field(rm, "cadence")
        records.append(
            {
                "timestamp": ts,
                "lat": float(lat) if lat is not None else None,
                "lon": float(lon) if lon is not None else None,
                "distance_m": float(distance) if distance is not None else 0,
                "hr_bpm": int(hr) if hr is not None else None,
                "power_w": int(power) if power is not None else None,
                "speed_mps": float(speed) if speed is not None else None,
                "altitude_m": float(altitude) if altitude is not None else None,
                "cadence_rpm": int(cadence) if cadence is not None else None,
            }
        )

    laps = []
    for lm in lap_msgs:
        start = _fit_timestamp_to_datetime(_field(lm, "start_time"))
        end = _fit_timestamp_to_datetime(_field(lm, "timestamp"))
        laps.append(
            {
                "start_time": start,
                "end_time": end,
                "total_distance_m": _field(lm, "total_distance") or 0,
                "avg_hr_bpm": int(_field(lm, "avg_heart_rate") or 0) or None,
                "avg_power_w": int(_field(lm, "avg_power") or 0) or None,
                "max_hr_bpm": int(_field(lm, "max_heart_rate") or 0) or None,
            }
        )

    if session_msg:
        started_at = _fit_timestamp_to_datetime(_field(session_msg, "start_time"))
        total_distance = _field(session_msg, "total_distance") or 0
        moving_time = int(_field(session_msg, "total_moving_time") or _field(session_msg, "total_timer_time") or 0)
        elapsed_time = int(_field(session_msg, "total_elapsed_time") or 0)
        elev_gain = _field(session_msg, "total_ascent") or 0
        avg_speed = _field(session_msg, "avg_speed") or 0
        avg_hr = int(_field(session_msg, "avg_heart_rate") or 0) or None
        avg_power = int(_field(session_msg, "avg_power") or 0) or None
        max_speed = _field(session_msg, "max_speed") or 0
        max_hr = int(_field(session_msg, "max_heart_rate") or 0) or None
    else:
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
        "moving_time_s": int(moving_time),
        "elapsed_time_s": int(elapsed_time),
        "elevation_gain_m": float(elev_gain),
        "avg_speed_mps": float(avg_speed),
        "avg_hr_bpm": avg_hr,
        "avg_power_w": avg_power,
        "max_speed_mps": float(max_speed),
        "max_hr_bpm": max_hr,
        "records": records,
        "laps": laps,
    }


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
    return activity