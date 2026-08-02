from datetime import datetime, timezone, timedelta
import json
import logging
from typing import Any

from geoalchemy2.functions import ST_SetSRID, ST_MakePoint
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.models import Activity, Lap, Record, ThresholdHistory, PowerZone, HrZone, ActivityPeakPower, FitnessHistory, Notification, User
from trainingdash.metrics import (
    compute_normalized_power,
    compute_intensity_factor,
    compute_tss,
    compute_zone_times,
)
from trainingdash.wbal import compute_wbal_series
from trainingdash.peaks import extract_peak_powers
from trainingdash.fitness import detect_breakthrough, get_all_time_bests, fit_cp_model
from trainingdash.hr_power import update_ef_model, estimate_power_from_hr

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
    batch_mode: bool = False,
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

    # Compute training metrics if user has thresholds
    await _compute_activity_metrics(db, activity, parsed["records"])

    # Update HR-derived power model if this is a dual-sensor ride
    await _update_hr_power_model(db, activity)

    # For HR-only activities, try to estimate power
    await _estimate_hr_derived_power(db, activity, parsed["records"])

    # Extract and store peak powers
    await _extract_activity_peaks(db, activity, parsed["records"])

    # Detect breakthroughs and update fitness model (skip in batch mode)
    if not batch_mode:
        await _detect_breakthrough_and_update_fitness(db, activity)

    # Route matching
    from trainingdash.route_matching import find_or_create_route_id
    route_id = await find_or_create_route_id(db, activity, parsed["records"])
    if route_id is not None:
        activity.route_id = route_id
        await db.commit()
        await db.refresh(activity)

    return activity


async def _compute_activity_metrics(
    db: AsyncSession,
    activity: Activity,
    records: list[dict],
) -> None:
    """
    Compute training metrics for an activity based on user's thresholds.
    
    Metrics computed:
    - Normalized Power (NP)
    - Intensity Factor (IF)
    - Training Stress Score (TSS)
    - Power zone times
    - HR zone times
    - W'bal minimum
    """
    # Get threshold effective at activity date
    activity_date = activity.started_at.date()
    result = await db.execute(
        select(ThresholdHistory)
        .where(
            ThresholdHistory.user_id == activity.user_id,
            ThresholdHistory.effective_date <= activity_date,
        )
        .order_by(ThresholdHistory.effective_date.desc())
        .limit(1)
    )
    threshold = result.scalar_one_or_none()
    
    if threshold is None:
        # No thresholds configured, can't compute metrics
        return
    
    # Extract power and HR arrays from records
    power_array = [r.get("power_w") for r in records]
    hr_array = [r.get("hr_bpm") for r in records]
    
    # Check if we have power data
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
                
                # Compute TSS
                duration_s = activity.moving_time_s or activity.elapsed_time_s
                tss = compute_tss(duration_s, np_watts, if_value, threshold.ftp_watts)
                if tss is not None:
                    activity.tss = tss
                    activity.training_load = tss  # Use TSS as training load
        
        # Compute power zone times
        power_zones_result = await db.execute(
            select(PowerZone)
            .where(PowerZone.user_id == activity.user_id)
            .order_by(PowerZone.zone_number)
        )
        power_zones = power_zones_result.scalars().all()
        
        if power_zones:
            zones_list = [
                {"zone_number": z.zone_number, "min_watts": z.min_watts, "max_watts": z.max_watts}
                for z in power_zones
            ]
            zone_times = compute_zone_times(power_array, zones_list)
            if zone_times:
                activity.power_zone_times = json.dumps(zone_times)
        
        # Compute W'bal
        # Estimate W' from FTP if not available (rough estimate: W' = FTP * 60)
        w_prime_joules = threshold.ftp_watts * 60  # Simple estimate
        cp_watts = int(threshold.ftp_watts * 0.95)  # CP is ~95% of FTP
        
        wbal_result = compute_wbal_series(power_array, cp_watts, w_prime_joules)
        if wbal_result["min_wbal"] is not None:
            activity.wbal_min_joules = wbal_result["min_wbal"]
            activity.wbal_min_pct = wbal_result["min_wbal_pct"]
    
    if has_hr:
        # Compute HR zone times
        hr_zones_result = await db.execute(
            select(HrZone)
            .where(HrZone.user_id == activity.user_id)
            .order_by(HrZone.zone_number)
        )
        hr_zones = hr_zones_result.scalars().all()
        
        if hr_zones:
            zones_list = [
                {"zone_number": z.zone_number, "min_bpm": z.min_bpm, "max_bpm": z.max_bpm}
                for z in hr_zones
            ]
            zone_times = compute_zone_times(
                hr_array, zones_list,
                value_key_min="min_bpm", value_key_max="max_bpm"
            )
            if zone_times:
                activity.hr_zone_times = json.dumps(zone_times)
    
    await db.commit()
    await db.refresh(activity)



async def _update_hr_power_model(
    db: AsyncSession,
    activity: Activity,
) -> None:
    """
    Update the user's EF model if this is a dual-sensor ride (has both power and HR).
    """
    # Check if this is a dual-sensor ride
    if activity.np_power_w is None or activity.avg_hr_bpm is None:
        return
    
    if activity.avg_hr_bpm <= 0:
        return
    
    # Mark as measured power
    activity.power_source = "measured"
    await db.commit()
    
    # Update EF model
    await update_ef_model(db, activity.user_id)


async def _estimate_hr_derived_power(
    db: AsyncSession,
    activity: Activity,
    records: list[dict],
) -> None:
    """
    For HR-only activities, estimate power from HR using the EF model.
    
    Only applies if:
    - Activity has no measured power
    - Activity has HR data
    - User has HR-derived power enabled
    - EF model exists
    """
    # Skip if already has power
    if activity.avg_power_w is not None:
        return
    
    # Skip if no HR data
    if activity.avg_hr_bpm is None or activity.avg_hr_bpm <= 0:
        return
    
    # Check if user has HR-derived power enabled
    result = await db.execute(
        select(User).where(User.id == activity.user_id)
    )
    user = result.scalar_one_or_none()
    
    if user is None or not user.hr_derived_power_enabled:
        return
    
    # Try to estimate power
    estimated_power, confidence = await estimate_power_from_hr(
        db, activity.user_id, activity.avg_hr_bpm
    )
    
    if estimated_power is None:
        return
    
    # Update activity with estimated power
    activity.avg_power_w = estimated_power
    activity.power_source = "hr_derived"
    activity.power_confidence = confidence
    
    # Re-compute metrics with estimated power
    await _recompute_metrics_with_estimated_power(db, activity, records, estimated_power)
    
    await db.commit()
    await db.refresh(activity)


async def _recompute_metrics_with_estimated_power(
    db: AsyncSession,
    activity: Activity,
    records: list[dict],
    estimated_power: int,
) -> None:
    """
    Recompute NP, IF, TSS using estimated power for HR-only activities.
    
    For HR-derived power, we use a simplified approach:
    - Assume power was constant at estimated_power
    - This gives NP ≈ estimated_power (slightly lower due to variability assumption)
    """
    # Get threshold
    activity_date = activity.started_at.date()
    result = await db.execute(
        select(ThresholdHistory)
        .where(
            ThresholdHistory.user_id == activity.user_id,
            ThresholdHistory.effective_date <= activity_date,
        )
        .order_by(ThresholdHistory.effective_date.desc())
        .limit(1)
    )
    threshold = result.scalar_one_or_none()
    
    if threshold is None:
        return
    
    ftp = threshold.ftp_watts
    
    # For HR-derived power, estimate NP as slightly lower than avg power
    # (accounts for assumed variability)
    np_estimate = int(estimated_power * 0.95)
    activity.np_power_w = np_estimate
    
    # Compute IF and TSS
    if ftp > 0:
        intensity_factor = compute_intensity_factor(np_estimate, ftp)
        activity.intensity_factor = intensity_factor
        
        duration_seconds = activity.moving_time_s or activity.elapsed_time_s
        tss = compute_tss(np_estimate, ftp, duration_seconds)
        activity.tss = tss


async def _extract_activity_peaks(
    db: AsyncSession,
    activity: Activity,
    records: list[dict],
) -> None:
    """
    Extract peak powers at standard durations and store in ActivityPeakPower table.
    
    Only stores peaks for durations where the ride was long enough.
    """
    # Extract power array from records
    power_array = [r.get("power_w") for r in records]
    
    # Check if we have any power data
    has_power = any(p is not None and p > 0 for p in power_array)
    if not has_power:
        return
    
    # Extract peaks at all standard durations
    peaks = extract_peak_powers(power_array)
    
    # Store each peak (only if ride was long enough for that duration)
    for duration_seconds, watts in peaks.items():
        if watts is not None:
            peak = ActivityPeakPower(
                activity_id=activity.id,
                duration_seconds=duration_seconds,
                watts=watts,
            )
            db.add(peak)
    
    await db.commit()




async def _detect_breakthrough_and_update_fitness(
    db: AsyncSession,
    activity: Activity,
) -> None:
    """
    Detect if activity is a breakthrough and update fitness model if so.
    
    A breakthrough occurs when the activity sets PRs at key durations
    (5s, 1min, 5min, 20min).
    """
    # Get this activity's peaks
    result = await db.execute(
        select(ActivityPeakPower)
        .where(ActivityPeakPower.activity_id == activity.id)
    )
    activity_peaks_rows = result.scalars().all()
    
    if not activity_peaks_rows:
        return
    
    activity_peaks = {p.duration_seconds: p.watts for p in activity_peaks_rows}
    
    # Get all previous activities' peaks for this user (before this activity)
    result = await db.execute(
        select(ActivityPeakPower)
        .join(Activity, ActivityPeakPower.activity_id == Activity.id)
        .where(
            Activity.user_id == activity.user_id,
            Activity.id != activity.id,
        )
    )
    previous_peaks_rows = result.scalars().all()
    
    # Group by activity
    peaks_by_activity: dict[int, dict[int, int]] = {}
    for p in previous_peaks_rows:
        if p.activity_id not in peaks_by_activity:
            peaks_by_activity[p.activity_id] = {}
        peaks_by_activity[p.activity_id][p.duration_seconds] = p.watts
    
    # Get all-time bests before this activity
    all_time_bests = get_all_time_bests(list(peaks_by_activity.values()))
    
    # Check if this is a breakthrough
    is_breakthrough = detect_breakthrough(activity_peaks, all_time_bests)
    
    if is_breakthrough:
        activity.is_breakthrough = True
        await db.commit()
        await db.refresh(activity)
        
        # Update fitness model with new data
        await _update_fitness_model(db, activity.user_id)


async def _update_fitness_model(
    db: AsyncSession,
    user_id: int,
) -> None:
    """
    Recalculate and store the user's fitness model.
    """
    # Get all activities with peaks for this user
    result = await db.execute(
        select(Activity)
        .where(Activity.user_id == user_id)
        .order_by(Activity.started_at.desc())
    )
    activities = result.scalars().all()
    
    if not activities:
        return
    
    # Get peaks for all activities
    activity_ids = [a.id for a in activities]
    result = await db.execute(
        select(ActivityPeakPower)
        .where(ActivityPeakPower.activity_id.in_(activity_ids))
    )
    all_peaks = result.scalars().all()
    
    # Group peaks by activity
    peaks_by_activity: dict[int, dict[int, int]] = {}
    for p in all_peaks:
        if p.activity_id not in peaks_by_activity:
            peaks_by_activity[p.activity_id] = {}
        peaks_by_activity[p.activity_id][p.duration_seconds] = p.watts
    
    # Build lists for model fitting
    peak_powers = []
    activity_dates = []
    for a in activities:
        if a.id in peaks_by_activity:
            peak_powers.append(peaks_by_activity[a.id])
            activity_dates.append(a.started_at)
    
    if not peak_powers:
        return
    
    # Fit the model
    model = fit_cp_model(peak_powers, activity_dates)
    
    if model is None:
        return
    
    # Store new fitness snapshot
    fitness = FitnessHistory(
        user_id=user_id,
        computed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        pp_watts=model["pp_watts"],
        w_prime_joules=model["w_prime_joules"],
        cp_watts=model["cp_watts"],
    )
    db.add(fitness)
    await db.commit()
    
    # Check if CP diverges from current FTP and create notification
    await _check_ftp_notification(db, user_id, model["cp_watts"])



async def _check_ftp_notification(
    db: AsyncSession,
    user_id: int,
    cp_watts: int,
) -> None:
    """
    Check if CP diverges from current FTP by >5% and create notification.
    """
    # Get current threshold
    result = await db.execute(
        select(ThresholdHistory)
        .where(ThresholdHistory.user_id == user_id)
        .order_by(ThresholdHistory.effective_date.desc())
        .limit(1)
    )
    threshold = result.scalar_one_or_none()
    
    if threshold is None:
        return
    
    current_ftp = threshold.ftp_watts
    
    # Check for >5% divergence
    ratio = cp_watts / current_ftp
    if 0.95 <= ratio <= 1.05:
        # Within 5%, no notification needed
        return
    
    # Check if there's already a pending FTP notification
    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.type == "ftp_suggestion",
            Notification.status == "pending",
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing is not None:
        # Update existing notification with new suggestion
        existing.message = f"Your fitness model suggests updating your FTP from {current_ftp}W to {cp_watts}W"
        existing.payload = json.dumps({
            "current_ftp": current_ftp,
            "suggested_ftp": cp_watts,
            "divergence_pct": round((ratio - 1) * 100, 1),
        })
        await db.commit()
        return
    
    # Create new notification
    notification = Notification(
        user_id=user_id,
        type="ftp_suggestion",
        message=f"Your fitness model suggests updating your FTP from {current_ftp}W to {cp_watts}W",
        payload=json.dumps({
            "current_ftp": current_ftp,
            "suggested_ftp": cp_watts,
            "divergence_pct": round((ratio - 1) * 100, 1),
        }),
        status="pending",
    )
    db.add(notification)
    await db.commit()



async def finalize_batch_import(
    db: AsyncSession,
    user_id: int,
    activity_count: int,
) -> None:
    """
    Finalize a batch import: detect breakthroughs, update fitness model once,
    and create a single summary notification instead of per-activity notifications.
    
    Called after ingesting multiple activities in batch_mode=True.
    """
    # Get all activities for this user to check for breakthroughs
    result = await db.execute(
        select(Activity)
        .where(Activity.user_id == user_id)
        .order_by(Activity.started_at.asc())
    )
    activities = result.scalars().all()
    
    if not activities:
        return
    
    # Get all peaks grouped by activity
    activity_ids = [a.id for a in activities]
    result = await db.execute(
        select(ActivityPeakPower)
        .where(ActivityPeakPower.activity_id.in_(activity_ids))
    )
    all_peaks = result.scalars().all()
    
    peaks_by_activity: dict[int, dict[int, int]] = {}
    for p in all_peaks:
        if p.activity_id not in peaks_by_activity:
            peaks_by_activity[p.activity_id] = {}
        peaks_by_activity[p.activity_id][p.duration_seconds] = p.watts
    
    # Walk through activities chronologically, marking breakthroughs
    all_time_bests: dict[int, int] = {}
    breakthroughs_detected = 0
    
    for activity in activities:
        if activity.id not in peaks_by_activity:
            continue
        
        activity_peaks = peaks_by_activity[activity.id]
        
        # Check if this is a breakthrough vs all-time bests so far
        is_breakthrough = detect_breakthrough(activity_peaks, all_time_bests)
        
        if is_breakthrough and not activity.is_breakthrough:
            activity.is_breakthrough = True
            breakthroughs_detected += 1
        
        # Update all-time bests
        for duration, watts in activity_peaks.items():
            if duration not in all_time_bests or watts > all_time_bests[duration]:
                all_time_bests[duration] = watts
    
    await db.commit()
    
    # If any breakthroughs, update fitness model once
    if breakthroughs_detected > 0:
        await _update_fitness_model_batch(db, user_id, activity_count)


async def _update_fitness_model_batch(
    db: AsyncSession,
    user_id: int,
    activity_count: int,
) -> None:
    """
    Update fitness model after batch import with a summary notification.
    """
    # Get all activities with peaks for this user
    result = await db.execute(
        select(Activity)
        .where(Activity.user_id == user_id)
        .order_by(Activity.started_at.desc())
    )
    activities = result.scalars().all()
    
    if not activities:
        return
    
    # Get peaks for all activities
    activity_ids = [a.id for a in activities]
    result = await db.execute(
        select(ActivityPeakPower)
        .where(ActivityPeakPower.activity_id.in_(activity_ids))
    )
    all_peaks = result.scalars().all()
    
    # Group peaks by activity
    peaks_by_activity: dict[int, dict[int, int]] = {}
    for p in all_peaks:
        if p.activity_id not in peaks_by_activity:
            peaks_by_activity[p.activity_id] = {}
        peaks_by_activity[p.activity_id][p.duration_seconds] = p.watts
    
    # Build lists for model fitting
    peak_powers = []
    activity_dates = []
    for a in activities:
        if a.id in peaks_by_activity:
            peak_powers.append(peaks_by_activity[a.id])
            activity_dates.append(a.started_at)
    
    if not peak_powers:
        return
    
    # Fit the model
    model = fit_cp_model(peak_powers, activity_dates)
    
    if model is None:
        return
    
    # Store new fitness snapshot
    fitness = FitnessHistory(
        user_id=user_id,
        computed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        pp_watts=model["pp_watts"],
        w_prime_joules=model["w_prime_joules"],
        cp_watts=model["cp_watts"],
    )
    db.add(fitness)
    await db.commit()
    
    # Check for FTP notification with batch summary
    await _check_ftp_notification_batch(db, user_id, model["cp_watts"], activity_count)


async def _check_ftp_notification_batch(
    db: AsyncSession,
    user_id: int,
    cp_watts: int,
    activity_count: int,
) -> None:
    """
    Check if CP diverges from current FTP and create a batch summary notification.
    """
    # Get current threshold
    result = await db.execute(
        select(ThresholdHistory)
        .where(ThresholdHistory.user_id == user_id)
        .order_by(ThresholdHistory.effective_date.desc())
        .limit(1)
    )
    threshold = result.scalar_one_or_none()
    
    if threshold is None:
        return
    
    current_ftp = threshold.ftp_watts
    
    # Check for >5% divergence
    ratio = cp_watts / current_ftp
    if 0.95 <= ratio <= 1.05:
        return
    
    # Remove any existing pending FTP notifications (will be replaced with summary)
    result = await db.execute(
        select(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.type == "ftp_suggestion",
            Notification.status == "pending",
        )
    )
    existing = result.scalars().all()
    for n in existing:
        await db.delete(n)
    
    # Create batch summary notification
    notification = Notification(
        user_id=user_id,
        type="ftp_suggestion",
        message=f"After importing {activity_count} activities, your fitness model suggests updating your FTP from {current_ftp}W to {cp_watts}W",
        payload=json.dumps({
            "current_ftp": current_ftp,
            "suggested_ftp": cp_watts,
            "divergence_pct": round((ratio - 1) * 100, 1),
            "batch_import": True,
            "activity_count": activity_count,
        }),
        status="pending",
    )
    db.add(notification)
    await db.commit()



async def ingest_xert_activity(
    db: AsyncSession,
    user_id: int,
    detail: Any,  # XertActivityDetail
    source_ref: str,
    batch_mode: bool = False,
) -> Activity | None:
    """
    Ingest an activity from Xert session_data, routing through the same
    metric pipeline as FIT file ingestion.
    
    This replaces the old _create_activity_from_xert() that was in worker.py
    and didn't compute NP, IF, TSS, zone times, peaks, or breakthrough detection.
    
    Args:
        db: Database session
        user_id: User ID to attribute the activity to
        detail: XertActivityDetail with session_data
        source_ref: Source reference (e.g., "xert:12345")
        batch_mode: If True, skip per-activity fitness updates (for bulk imports)
    
    Returns:
        Created Activity or None if ingestion failed
    """
    from geoalchemy2.functions import ST_SetSRID, ST_MakePoint
    
    if not detail.session_data:
        logger.warning(f"ingest_xert_activity: No session_data for {source_ref}")
        return None
    
    # Convert Xert session_data to our records format
    records = _convert_xert_session_data(detail)
    
    # Calculate summary stats from session_data
    total_distance_m = detail.distance * 1000 if detail.distance else 0
    elapsed_time_s = int(detail.duration) if detail.duration else 0
    
    # Extract arrays for averages/max
    hr_values = [r["hr_bpm"] for r in records if r["hr_bpm"] is not None]
    power_values = [r["power_w"] for r in records if r["power_w"] is not None and r["power_w"] > 0]
    speed_values = [r["speed_mps"] for r in records if r["speed_mps"] is not None]
    altitudes = [r["altitude_m"] for r in records if r["altitude_m"] is not None]
    
    # Calculate averages and max values
    avg_hr = int(sum(hr_values) / len(hr_values)) if hr_values else None
    max_hr = max(hr_values) if hr_values else None
    avg_power = int(sum(power_values) / len(power_values)) if power_values else None
    avg_speed = sum(speed_values) / len(speed_values) if speed_values else None
    max_speed = max(speed_values) if speed_values else None
    
    # Calculate elevation gain (sum of positive altitude changes)
    elevation_gain = 0.0
    if len(altitudes) >= 2:
        for i in range(1, len(altitudes)):
            diff = altitudes[i] - altitudes[i-1]
            if diff > 0:
                elevation_gain += diff
    
    # Normalize started_at to naive UTC
    started_at = detail.started_at
    if started_at.tzinfo is not None:
        started_at = started_at.replace(tzinfo=None)
    
    # Create Activity
    activity = Activity(
        user_id=user_id,
        started_at=started_at,
        total_distance_m=total_distance_m,
        moving_time_s=elapsed_time_s,  # Xert doesn't distinguish moving vs elapsed
        elapsed_time_s=elapsed_time_s,
        elevation_gain_m=elevation_gain if elevation_gain > 0 else None,
        avg_speed_mps=avg_speed,
        avg_hr_bpm=avg_hr,
        avg_power_w=avg_power,
        max_speed_mps=max_speed,
        max_hr_bpm=max_hr,
        source="xert",
        source_ref=source_ref,
        # Store XSS as training_load initially (may be overwritten by TSS computation)
        training_load=detail.xss,
    )
    db.add(activity)
    await db.flush()
    
    # Create Records
    for r in records:
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
    
    # Now run the same metric pipeline as ingest_fit()
    
    # Compute training metrics (NP, IF, TSS, zone times, W'bal)
    await _compute_activity_metrics(db, activity, records)
    
    # Update HR-derived power model if this is a dual-sensor ride
    await _update_hr_power_model(db, activity)
    
    # For HR-only activities, try to estimate power
    await _estimate_hr_derived_power(db, activity, records)
    
    # Extract and store peak powers
    await _extract_activity_peaks(db, activity, records)
    
    # Detect breakthroughs and update fitness model (skip in batch mode)
    if not batch_mode:
        await _detect_breakthrough_and_update_fitness(db, activity)
    
    # Route matching
    from trainingdash.route_matching import find_or_create_route_id
    route_id = await find_or_create_route_id(db, activity, records)
    if route_id is not None:
        activity.route_id = route_id
        await db.commit()
        await db.refresh(activity)
    
    return activity


def _convert_xert_session_data(detail: Any) -> list[dict]:
    """
    Convert Xert session_data to the records format used by our metric pipeline.
    
    Xert session_data format:
    - unix_time: milliseconds since epoch
    - lat, lng: coordinates (nullable)
    - dist: cumulative distance in meters
    - hr: heart rate
    - power: power in watts
    - spd: speed in m/s * 1000 (needs conversion)
    - alt: altitude in meters
    - cad: cadence
    
    Our records format:
    - timestamp: datetime
    - lat, lon: coordinates
    - distance_m: cumulative distance
    - hr_bpm, power_w, speed_mps, altitude_m, cadence_rpm
    """
    from datetime import timedelta
    
    if not detail.session_data:
        return []
    
    # Get started_at for timestamp calculation
    started_at = detail.started_at
    if started_at.tzinfo is not None:
        started_at = started_at.replace(tzinfo=None)
    
    first_time = detail.session_data[0].unix_time if detail.session_data else 0
    records = []
    
    for point in detail.session_data:
        # Calculate timestamp from unix_time offset
        elapsed_secs = (point.unix_time - first_time) / 1000.0 if first_time else 0
        timestamp = started_at + timedelta(seconds=elapsed_secs)
        
        # Speed: Xert stores as m/s * 1000, convert to m/s
        speed_mps = point.spd / 1000.0 if point.spd is not None else None
        
        records.append({
            "timestamp": timestamp,
            "lat": point.lat,
            "lon": point.lng,
            "distance_m": point.dist if point.dist is not None else 0,
            "hr_bpm": point.hr,
            "power_w": int(point.power) if point.power is not None else None,
            "speed_mps": speed_mps,
            "altitude_m": point.alt,
            "cadence_rpm": int(point.cad) if point.cad is not None else None,
        })
    
    return records
