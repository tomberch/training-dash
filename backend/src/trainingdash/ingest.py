import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from geoalchemy2.functions import ST_MakePoint, ST_SetSRID
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.activity_pipeline import ActivityPipeline
from trainingdash.domain.fitness import fit_cp_model
from trainingdash.domain.metrics import (
    compute_intensity_factor,
    compute_normalized_power,
    compute_tss,
)
from trainingdash.domain.polyline import generate_map_polyline
from trainingdash.domain.wbal import compute_wbal_series
from trainingdash.domain.zones import compute_zone_times
from trainingdash.repositories.postgres.models import Activity, ActivityPeakPower, Lap, Record, User
from trainingdash.repositories.postgres.threshold_repo import PostgresThresholdRepo

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
        dt = dt.astimezone(UTC).replace(tzinfo=None)
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


# Speed threshold for determining "moving" (0.5 m/s ≈ 1.8 km/h)
MOVING_SPEED_THRESHOLD = 0.5


def _compute_moving_time(records: list[dict]) -> int:
    """Compute moving time by counting seconds where speed exceeds threshold."""
    if not records:
        return 0
    return sum(1 for r in records if (r.get("speed_mps") or 0) > MOVING_SPEED_THRESHOLD)


def _derive_utc_offset(
    local_timestamp: Any,
    utc_timestamp: Any,
) -> int | None:
    """
    Derive UTC offset in minutes from FIT Activity message timestamps.

    The FIT spec stores local_timestamp (device wall-clock time, naive) and
    timestamp (UTC, timezone-aware from fitdecode) in the Activity message.
    Their difference gives the UTC offset that was in effect when the ride ended.

    Validity checks:
    - Both values must be present and parseable as datetimes.
    - Computed offset must be within ±840 minutes (±14 hours) to reject
      epoch-1989 values (Zwift bug) and other bogus timestamps.

    Returns offset in minutes, or None if the value is absent or implausible.
    """
    if local_timestamp is None or utc_timestamp is None:
        return None
    try:
        # fitdecode returns local_timestamp as naive datetime, utc as aware
        if hasattr(utc_timestamp, "tzinfo") and utc_timestamp.tzinfo is not None:
            utc_naive = utc_timestamp.replace(tzinfo=None)
        else:
            utc_naive = utc_timestamp
        delta_seconds = (local_timestamp - utc_naive).total_seconds()
        offset_minutes = int(delta_seconds / 60)
        if -840 <= offset_minutes <= 840:
            return offset_minutes
        return None
    except (TypeError, AttributeError):
        return None


def parse_records(fit_bytes: bytes) -> dict[str, Any]:
    """Parse a FIT file and extract activity data using fitdecode."""
    import fitdecode

    records = []
    laps = []
    session_data = None
    utc_offset_minutes: int | None = None

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

                records.append(
                    {
                        "timestamp": ts,
                        "lat": lat,
                        "lon": lon,
                        "distance_m": distance if distance is not None else 0,
                        "hr_bpm": hr,
                        "power_w": power,
                        "speed_mps": speed,
                        "altitude_m": altitude,
                        "cadence_rpm": cadence,
                    }
                )

            elif frame.name == "lap":
                start = _to_naive_utc(_get_field(frame, "start_time"))
                end = _to_naive_utc(_get_field(frame, "timestamp"))
                laps.append(
                    {
                        "start_time": start,
                        "end_time": end,
                        "total_distance_m": _safe_float(_get_field(frame, "total_distance")) or 0,
                        "avg_hr_bpm": _safe_int(_get_field(frame, "avg_heart_rate")),
                        "avg_power_w": _safe_int(_get_field(frame, "avg_power")),
                        "max_hr_bpm": _safe_int(_get_field(frame, "max_heart_rate")),
                    }
                )

            elif frame.name == "session":
                # Extract session summary data
                timer_time = _safe_float(_get_field(frame, "total_timer_time"))
                elapsed_time = _safe_float(_get_field(frame, "total_elapsed_time"))
                logger.debug(f"FIT session: timer_time={timer_time}, elapsed_time={elapsed_time}")
                session_data = {
                    "started_at": _to_naive_utc(_get_field(frame, "start_time")),
                    "total_distance_m": _safe_float(_get_field(frame, "total_distance")) or 0,
                    "total_timer_time": timer_time,
                    "total_elapsed_time": elapsed_time,
                    "total_ascent": _safe_int(_get_field(frame, "total_ascent")),
                    "avg_speed": _safe_float(_get_field(frame, "enhanced_avg_speed", "avg_speed")),
                    "max_speed": _safe_float(_get_field(frame, "enhanced_max_speed", "max_speed")),
                    "avg_hr": _safe_int(_get_field(frame, "avg_heart_rate")),
                    "max_hr": _safe_int(_get_field(frame, "max_heart_rate")),
                    "avg_power": _safe_int(_get_field(frame, "avg_power")),
                }

            elif frame.name == "activity":
                # The Activity message contains local_timestamp (device wall-clock)
                # alongside timestamp (UTC). Their difference gives the UTC offset
                # that was in effect when and where the ride ended.
                local_ts = _get_field(frame, "local_timestamp")
                utc_ts = _get_field(frame, "timestamp")
                utc_offset_minutes = _derive_utc_offset(local_ts, utc_ts)

    # Build result from session or compute from records
    if session_data and session_data["started_at"]:
        started_at = session_data["started_at"]
        total_distance = session_data["total_distance_m"]
        moving_time = int(session_data["total_timer_time"] or 0)
        elapsed_time = int(session_data["total_elapsed_time"] or 0)

        # If moving_time is 0 but we have records, compute from records
        if moving_time == 0 and records:
            computed_moving = _compute_moving_time(records)
            if computed_moving > 0:
                moving_time = computed_moving
                logger.debug(f"Computed moving_time from records: {moving_time}s (elapsed: {elapsed_time}s)")

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
        moving_time = _compute_moving_time(records)
        elapsed_time = len(records) if records else 0
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
        "utc_offset_minutes": utc_offset_minutes,
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


async def _store_parsed_fit(
    db: AsyncSession,
    user_id: int,
    source: str,
    source_ref: str,
    fit_bytes: bytes,
    parsed: dict,
) -> Activity:
    """
    Persist a parsed FIT dict as Activity, Lap, and Record rows.

    Handles the ORM construction and flush so ingest_fit() stays at three
    readable steps: parse → store → pipeline.
    """
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
        map_polyline=generate_map_polyline(parsed["records"]),
        raw_fit=fit_bytes,
        utc_offset_minutes=parsed["utc_offset_minutes"],
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


async def ingest_fit(
    db: AsyncSession,
    user_id: int,
    fit_bytes: bytes,
    source: str,
    source_ref: str,
    batch_mode: bool = False,
) -> Activity | None:
    """
    Ingest a FIT file and process through the activity pipeline.

    Steps:
    1. Parse FIT file to extract records, laps, and summary data
    2. Create Activity, Lap, and Record models
    3. Run activity through the pipeline for metrics, peaks, routes, and titles

    Args:
        db: Database session
        user_id: User ID to attribute the activity to
        fit_bytes: Raw FIT file bytes
        source: Source identifier (e.g., "garmin", "xert")
        source_ref: Unique reference from the source
        batch_mode: If True, skip per-activity fitness updates and geocoding

    Returns:
        Created Activity or None if parsing failed
    """
    try:
        parsed = parse_records(fit_bytes)
    except Exception:
        return None

    activity = await _store_parsed_fit(db, user_id, source, source_ref, fit_bytes, parsed)

    pipeline = ActivityPipeline(
        db=db,
        activity=activity,
        records=parsed["records"],
        batch_mode=batch_mode,
    )
    await pipeline.run()

    return activity


async def finalize_batch_import(
    db: AsyncSession,
    user_id: int,
    activity_count: int,
) -> None:
    """
    Finalize a batch import: detect breakthroughs, update fitness model once,
    auto-create threshold if needed, backfill metrics, and create summary notification.

    Called after ingesting multiple activities in batch_mode=True.
    """
    from trainingdash.use_cases.breakthrough_evaluator import BreakthroughEvaluator
    from trainingdash.use_cases.fitness_model_updater import FitnessModelUpdater

    # Re-evaluate breakthrough flags across all activities
    await BreakthroughEvaluator(db).execute(user_id)
    await db.commit()

    # Recompute fitness model (CP model snapshot) — batch mode: pass
    # activity_count so the FTP-divergence notification carries the
    # batch-summary shape (replaces existing pending FTP notifications).
    await FitnessModelUpdater(db).execute(user_id, activity_count=activity_count)
    await db.commit()

    # Load activities + peaks for the threshold helper below
    result = await db.execute(select(Activity).where(Activity.user_id == user_id).order_by(Activity.started_at.asc()))
    activities = result.scalars().all()

    if not activities:
        return

    activity_ids = [a.id for a in activities]
    result = await db.execute(select(ActivityPeakPower).where(ActivityPeakPower.activity_id.in_(activity_ids)))
    all_peaks = result.scalars().all()

    peaks_by_activity: dict[int, dict[int, int]] = {}
    for p in all_peaks:
        peaks_by_activity.setdefault(p.activity_id, {})[p.duration_seconds] = p.watts

    # Auto-create threshold for historical activities if needed
    await _auto_create_threshold_if_needed(db, user_id, activities, peaks_by_activity)

    # Backfill metrics for activities that are missing them
    await backfill_activity_metrics(db, user_id)


async def _auto_create_threshold_if_needed(
    db: AsyncSession,
    user_id: int,
    activities: list[Activity],
    peaks_by_activity: dict[int, dict[int, int]],
) -> None:
    """
    Auto-create a threshold from CP model if historical activities lack coverage.

    This ensures activities imported before any manual threshold was set
    still get their metrics calculated.
    """

    if not activities:
        return

    # Find earliest activity date
    earliest_date = min(a.started_at.date() for a in activities)

    # Check if there's already a threshold covering the earliest activity
    threshold_repo = PostgresThresholdRepo(db)
    existing_ftp = (await threshold_repo.get_for_date(user_id, earliest_date)).ftp_watts

    if existing_ftp is not None:
        # Already have coverage for historical activities
        return

    # Check if there's any threshold at all (user may have set one for "today")
    all_thresholds = await threshold_repo.get_history(user_id)
    any_threshold = all_thresholds[0] if all_thresholds else None

    # Build peak powers list for CP model
    peak_powers = list(peaks_by_activity.values())
    if not peak_powers:
        return

    activity_dates = [a.started_at for a in activities if a.id in peaks_by_activity]

    # Fit CP model
    model = fit_cp_model(peak_powers, activity_dates)
    if model is None:
        return

    cp_watts = model["cp_watts"]

    # Estimate LTHR and HRmax from activities if possible, otherwise use defaults
    lthr_bpm, hrmax_bpm = _estimate_hr_thresholds(activities)

    # If user has a manual threshold, copy HR values from it
    if any_threshold is not None:
        if any_threshold.lthr_bpm:
            lthr_bpm = any_threshold.lthr_bpm
        if any_threshold.hrmax_bpm:
            hrmax_bpm = any_threshold.hrmax_bpm

    # Create auto-calculated threshold entries for historical activities
    await threshold_repo.create(
        user_id,
        earliest_date,
        ftp_watts=cp_watts,
        lthr_bpm=lthr_bpm,
        hrmax_bpm=hrmax_bpm,
        source="calculated",
        source_detail="auto_from_cp_model",
    )
    await db.commit()


def _estimate_hr_thresholds(activities: list[Activity]) -> tuple[int, int]:
    """
    Estimate LTHR and HRmax from activity data.

    Returns (lthr_bpm, hrmax_bpm) with reasonable defaults if no HR data.
    """
    max_hr_seen = 0
    avg_hrs = []

    for a in activities:
        if a.max_hr_bpm is not None and a.max_hr_bpm > max_hr_seen:
            max_hr_seen = a.max_hr_bpm
        if a.avg_hr_bpm is not None and a.avg_hr_bpm > 0:
            avg_hrs.append(a.avg_hr_bpm)

    if max_hr_seen > 0:
        hrmax = max_hr_seen
        # LTHR is typically 93% of HRmax
        lthr = int(hrmax * 0.93)
    else:
        # Default values (180 HRmax, 167 LTHR for ~40 year old)
        hrmax = 180
        lthr = 167

    return lthr, hrmax


async def backfill_activity_metrics(
    db: AsyncSession,
    user_id: int,
    activity_ids: list[int] | None = None,
) -> int:
    """
    Backfill training metrics for activities that are missing them.

    This is used after creating an auto-calculated threshold to compute
    metrics for historical activities that were imported before any
    threshold existed.

    Args:
        db: Database session
        user_id: User ID to backfill metrics for
        activity_ids: Optional list of specific activity IDs to process.
                      If None, processes all activities missing metrics.

    Returns:
        Number of activities updated
    """
    from trainingdash.repositories.postgres.models import Record

    # Find activities missing metrics (NP is the indicator - if NP is null but has power, needs backfill)
    if activity_ids:
        result = await db.execute(
            select(Activity)
            .where(
                Activity.user_id == user_id,
                Activity.id.in_(activity_ids),
                Activity.np_power_w.is_(None),
                Activity.avg_power_w.isnot(None),  # Has power data
            )
            .order_by(Activity.started_at)
        )
    else:
        result = await db.execute(
            select(Activity)
            .where(
                Activity.user_id == user_id,
                Activity.np_power_w.is_(None),
                Activity.avg_power_w.isnot(None),  # Has power data
            )
            .order_by(Activity.started_at)
        )

    activities = result.scalars().all()

    if not activities:
        return 0

    # Get user for zone percentages
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    updated_count = 0

    for activity in activities:
        # Get thresholds effective at activity date
        activity_date = activity.started_at.date()
        threshold = await PostgresThresholdRepo(db).get_for_date(user_id, activity_date)

        if threshold is None or threshold.ftp_watts is None:
            continue

        # Load records for this activity
        records_result = await db.execute(
            select(Record).where(Record.activity_id == activity.id).order_by(Record.timestamp)
        )
        records = records_result.scalars().all()

        if not records:
            continue

        # Extract power and HR arrays
        power_array = [r.power_w for r in records]
        hr_array = [r.hr_bpm for r in records]

        has_power = any(p is not None and p > 0 for p in power_array)
        has_hr = any(h is not None and h > 0 for h in hr_array)

        if has_power:
            # Compute NP
            np_watts = compute_normalized_power(power_array)
            if np_watts is not None:
                activity.np_power_w = int(np_watts)

                # Compute IF and TSS
                if_value = compute_intensity_factor(np_watts, threshold.ftp_watts)
                if if_value is not None:
                    activity.intensity_factor = if_value

                    duration_s = activity.moving_time_s or activity.elapsed_time_s
                    tss = compute_tss(duration_s, np_watts, if_value, threshold.ftp_watts)
                    if tss is not None:
                        activity.tss = tss
                        activity.training_load = tss

            # Compute power zone times using computed zones
            if threshold.ftp_watts and threshold.ftp_watts > 0:
                power_zone_times, _ = compute_zone_times(
                    power_array,
                    threshold.ftp_watts,
                    power_zone_pct=user.power_zone_percentages if user else None,
                )
                if power_zone_times:
                    activity.power_zone_times = json.dumps(power_zone_times)

            # Compute W'bal
            w_prime_joules = threshold.ftp_watts * 60
            cp_watts = int(threshold.ftp_watts * 0.95)
            wbal_result = compute_wbal_series(power_array, cp_watts, w_prime_joules)
            if wbal_result["min_wbal"] is not None:
                activity.wbal_min_joules = wbal_result["min_wbal"]
                activity.wbal_min_pct = wbal_result["min_wbal_pct"]

        if has_hr and threshold.lthr_bpm and threshold.lthr_bpm > 0:
            _, hr_zone_times = compute_zone_times(
                [],  # no power data needed
                None,  # no FTP needed
                hr_array,
                threshold.lthr_bpm,
                hr_zone_pct=user.hr_zone_percentages if user else None,
            )
            if hr_zone_times:
                activity.hr_zone_times = json.dumps(hr_zone_times)

        updated_count += 1

    await db.commit()
    return updated_count
