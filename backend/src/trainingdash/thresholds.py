"""Threshold and zone business logic.

Handles FTP, LTHR, HRmax thresholds and power/HR zone computation.
"""

from datetime import date

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.models import HrZone, PowerZone, ThresholdHistory, User


# Coggan 7-zone power zones (% of FTP)
COGGAN_POWER_ZONES = [
    (1, "Recovery", 0, 55),
    (2, "Endurance", 55, 75),
    (3, "Tempo", 75, 90),
    (4, "Threshold", 90, 105),
    (5, "VO2max", 105, 120),
    (6, "Anaerobic", 120, 150),
    (7, "Neuromuscular", 150, None),  # None = no upper limit
]

# Friel 5-zone HR zones (% of LTHR)
FRIEL_HR_ZONES = [
    (1, "Zone 1", 0, 81),
    (2, "Zone 2", 81, 89),
    (3, "Zone 3", 90, 93),
    (4, "Zone 4", 94, 99),
    (5, "Zone 5", 100, None),  # None = no upper limit (up to HRmax)
]


def compute_default_thresholds(dob: date, weight_kg: float | None) -> dict:
    """
    Compute default threshold values based on age and weight.
    
    - HRmax: Tanaka formula (208 - 0.7 × age)
    - LTHR: 93% of HRmax
    - FTP: weight × 2.5 (or 200W if no weight)
    """
    today = date.today()
    age = (today - dob).days // 365
    
    hrmax = int(208 - 0.7 * age)
    lthr = int(hrmax * 0.93)
    
    if weight_kg is not None and weight_kg > 0:
        ftp = int(float(weight_kg) * 2.5)
    else:
        ftp = 200
    
    return {"ftp_watts": ftp, "lthr_bpm": lthr, "hrmax_bpm": hrmax}


def compute_power_zones(ftp_watts: int) -> list[dict]:
    """Compute Coggan 7-zone power zones from FTP."""
    zones = []
    for zone_num, name, min_pct, max_pct in COGGAN_POWER_ZONES:
        min_watts = int(ftp_watts * min_pct / 100)
        max_watts = int(ftp_watts * max_pct / 100) if max_pct else None
        zones.append({
            "zone_number": zone_num,
            "name": name,
            "min_watts": min_watts,
            "max_watts": max_watts,
        })
    return zones


def compute_hr_zones(lthr_bpm: int) -> list[dict]:
    """Compute Friel 5-zone HR zones from LTHR."""
    zones = []
    for zone_num, name, min_pct, max_pct in FRIEL_HR_ZONES:
        min_bpm = int(lthr_bpm * min_pct / 100)
        max_bpm = int(lthr_bpm * max_pct / 100) if max_pct else None
        zones.append({
            "zone_number": zone_num,
            "name": name,
            "min_bpm": min_bpm,
            "max_bpm": max_bpm,
        })
    return zones


async def get_threshold_for_date(
    db: AsyncSession, user_id: int, target_date: date
) -> ThresholdHistory | None:
    """
    Get the threshold values effective on a given date.
    Returns the most recent threshold entry with effective_date <= target_date.
    """
    result = await db.execute(
        select(ThresholdHistory)
        .where(
            ThresholdHistory.user_id == user_id,
            ThresholdHistory.effective_date <= target_date,
        )
        .order_by(ThresholdHistory.effective_date.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def ensure_default_thresholds(db: AsyncSession, user: User) -> ThresholdHistory | None:
    """
    Ensure user has at least one threshold entry. Creates defaults if none exist.
    Requires user to have date_of_birth set.
    Returns the created/existing threshold or None if DOB not set.
    """
    if user.date_of_birth is None:
        return None
    
    # Check if any thresholds exist
    result = await db.execute(
        select(ThresholdHistory)
        .where(ThresholdHistory.user_id == user.id)
        .limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return None  # Already has thresholds
    
    # Create default thresholds
    defaults = compute_default_thresholds(
        user.date_of_birth, float(user.weight_kg) if user.weight_kg else None
    )
    threshold = ThresholdHistory(
        user_id=user.id,
        effective_date=date.today(),
        ftp_watts=defaults["ftp_watts"],
        lthr_bpm=defaults["lthr_bpm"],
        hrmax_bpm=defaults["hrmax_bpm"],
    )
    db.add(threshold)
    await db.commit()
    await db.refresh(threshold)
    return threshold


async def ensure_zones_exist(db: AsyncSession, user: User) -> bool:
    """
    Ensure user has zones. Creates defaults from current thresholds if none exist.
    Returns True if zones exist or were created, False if no thresholds available.
    """
    # Check if zones already exist
    result = await db.execute(
        select(PowerZone).where(PowerZone.user_id == user.id).limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return True  # Already has zones
    
    # Need thresholds to create zones
    await ensure_default_thresholds(db, user)
    
    result = await db.execute(
        select(ThresholdHistory)
        .where(ThresholdHistory.user_id == user.id)
        .order_by(ThresholdHistory.effective_date.desc())
        .limit(1)
    )
    threshold = result.scalar_one_or_none()
    if threshold is None:
        return False  # No thresholds, can't create zones
    
    # Create power zones
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
    
    # Create HR zones
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
    return True


async def regenerate_zones_from_threshold(
    db: AsyncSession, user_id: int, threshold: ThresholdHistory
) -> None:
    """
    Regenerate zones from a new threshold, but only if zones are not custom.
    """
    # Check if any zones are custom
    result = await db.execute(
        select(PowerZone)
        .where(PowerZone.user_id == user_id, PowerZone.is_custom == True)
        .limit(1)
    )
    has_custom_power = result.scalar_one_or_none() is not None
    
    result = await db.execute(
        select(HrZone)
        .where(HrZone.user_id == user_id, HrZone.is_custom == True)
        .limit(1)
    )
    has_custom_hr = result.scalar_one_or_none() is not None
    
    # Regenerate power zones if not custom
    if not has_custom_power:
        await db.execute(delete(PowerZone).where(PowerZone.user_id == user_id))
        for zone_data in compute_power_zones(threshold.ftp_watts):
            zone = PowerZone(
                user_id=user_id,
                zone_number=zone_data["zone_number"],
                name=zone_data["name"],
                min_watts=zone_data["min_watts"],
                max_watts=zone_data["max_watts"],
                is_custom=False,
            )
            db.add(zone)
    
    # Regenerate HR zones if not custom
    if not has_custom_hr:
        await db.execute(delete(HrZone).where(HrZone.user_id == user_id))
        for zone_data in compute_hr_zones(threshold.lthr_bpm):
            zone = HrZone(
                user_id=user_id,
                zone_number=zone_data["zone_number"],
                name=zone_data["name"],
                min_bpm=zone_data["min_bpm"],
                max_bpm=zone_data["max_bpm"],
                is_custom=False,
            )
            db.add(zone)
    
    await db.commit()
