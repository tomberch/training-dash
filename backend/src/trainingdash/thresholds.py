"""Threshold business logic.

Handles FTP, LTHR, HRmax threshold management using metric_entries.
Zone computation has moved to trainingdash.zones module.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.models import MetricEntry, MetricType, User


# Cache metric type IDs to avoid repeated lookups
_METRIC_TYPE_IDS: dict[str, int] = {}


async def _get_metric_type_id(db: AsyncSession, key: str) -> int | None:
    """Get metric_type id by key, with caching."""
    if key in _METRIC_TYPE_IDS:
        return _METRIC_TYPE_IDS[key]
    
    result = await db.execute(
        select(MetricType.id).where(MetricType.key == key)
    )
    type_id = result.scalar_one_or_none()
    if type_id:
        _METRIC_TYPE_IDS[key] = type_id
    return type_id


async def _get_metric_for_date(
    db: AsyncSession, user_id: int, metric_key: str, target_date: date
) -> int | None:
    """Get a metric value effective on a given date."""
    type_id = await _get_metric_type_id(db, metric_key)
    if not type_id:
        return None
    
    result = await db.execute(
        select(MetricEntry.value)
        .where(
            MetricEntry.user_id == user_id,
            MetricEntry.metric_type_id == type_id,
            MetricEntry.effective_date <= target_date,
        )
        .order_by(MetricEntry.effective_date.desc())
        .limit(1)
    )
    value = result.scalar_one_or_none()
    return int(value) if value is not None else None


@dataclass
class ThresholdValues:
    """Container for threshold values (replaces ThresholdHistory for queries)."""
    ftp_watts: int | None = None
    lthr_bpm: int | None = None
    hrmax_bpm: int | None = None
    
    # For compatibility with existing code that checks effective_date
    effective_date: date | None = None


async def get_ftp_for_date(
    db: AsyncSession, user_id: int, target_date: date
) -> int | None:
    """Get FTP value effective on a given date."""
    return await _get_metric_for_date(db, user_id, "ftp", target_date)


async def get_lthr_for_date(
    db: AsyncSession, user_id: int, target_date: date
) -> int | None:
    """Get LTHR value effective on a given date."""
    return await _get_metric_for_date(db, user_id, "lthr", target_date)


async def get_hrmax_for_date(
    db: AsyncSession, user_id: int, target_date: date
) -> int | None:
    """Get HRmax value effective on a given date."""
    return await _get_metric_for_date(db, user_id, "hrmax", target_date)


async def get_thresholds_for_date(
    db: AsyncSession, user_id: int, target_date: date
) -> ThresholdValues:
    """
    Get all threshold values (FTP, LTHR, HRmax) effective on a given date.
    Each value may come from a different effective_date.
    """
    ftp = await get_ftp_for_date(db, user_id, target_date)
    lthr = await get_lthr_for_date(db, user_id, target_date)
    hrmax = await get_hrmax_for_date(db, user_id, target_date)
    
    return ThresholdValues(
        ftp_watts=ftp,
        lthr_bpm=lthr,
        hrmax_bpm=hrmax,
        effective_date=target_date,
    )


async def get_all_threshold_entries(
    db: AsyncSession, user_id: int
) -> list[dict]:
    """
    Get all threshold metric entries for a user, grouped by date.
    Returns a list of dicts with effective_date, ftp_watts, lthr_bpm, hrmax_bpm.
    """
    # Get all threshold metric types
    ftp_id = await _get_metric_type_id(db, "ftp")
    lthr_id = await _get_metric_type_id(db, "lthr")
    hrmax_id = await _get_metric_type_id(db, "hrmax")
    
    type_ids = [t for t in [ftp_id, lthr_id, hrmax_id] if t]
    if not type_ids:
        return []
    
    result = await db.execute(
        select(MetricEntry)
        .where(
            MetricEntry.user_id == user_id,
            MetricEntry.metric_type_id.in_(type_ids),
        )
        .order_by(MetricEntry.effective_date.desc())
    )
    entries = result.scalars().all()
    
    # Group by date
    by_date: dict[date, dict] = {}
    for entry in entries:
        d = entry.effective_date
        if d not in by_date:
            by_date[d] = {
                "effective_date": d,
                "ftp_watts": None,
                "lthr_bpm": None,
                "hrmax_bpm": None,
                "source": entry.source,
                "created_at": entry.created_at,
            }
        
        if entry.metric_type_id == ftp_id:
            by_date[d]["ftp_watts"] = int(entry.value)
        elif entry.metric_type_id == lthr_id:
            by_date[d]["lthr_bpm"] = int(entry.value)
        elif entry.metric_type_id == hrmax_id:
            by_date[d]["hrmax_bpm"] = int(entry.value)
    
    # Sort by date descending
    return sorted(by_date.values(), key=lambda x: x["effective_date"], reverse=True)


async def create_metric_entry(
    db: AsyncSession,
    user_id: int,
    metric_key: str,
    value: int | float,
    effective_date: date,
    source: str = "manual",
    source_detail: str | None = None,
) -> MetricEntry | None:
    """Create a new metric entry."""
    type_id = await _get_metric_type_id(db, metric_key)
    if not type_id:
        return None
    
    entry = MetricEntry(
        user_id=user_id,
        metric_type_id=type_id,
        effective_date=effective_date,
        value=Decimal(str(value)),
        source=source,
        source_detail=source_detail,
    )
    db.add(entry)
    return entry


async def create_threshold_entries(
    db: AsyncSession,
    user_id: int,
    effective_date: date,
    ftp_watts: int | None = None,
    lthr_bpm: int | None = None,
    hrmax_bpm: int | None = None,
    source: str = "manual",
    source_detail: str | None = None,
) -> list[MetricEntry]:
    """
    Create threshold metric entries for FTP, LTHR, and/or HRmax.
    Returns list of created entries.
    """
    entries = []
    
    if ftp_watts is not None:
        entry = await create_metric_entry(
            db, user_id, "ftp", ftp_watts, effective_date, source, source_detail
        )
        if entry:
            entries.append(entry)
    
    if lthr_bpm is not None:
        entry = await create_metric_entry(
            db, user_id, "lthr", lthr_bpm, effective_date, source, source_detail
        )
        if entry:
            entries.append(entry)
    
    if hrmax_bpm is not None:
        entry = await create_metric_entry(
            db, user_id, "hrmax", hrmax_bpm, effective_date, source, source_detail
        )
        if entry:
            entries.append(entry)
    
    return entries


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


async def ensure_default_thresholds(db: AsyncSession, user: User) -> bool:
    """
    Ensure user has at least one threshold entry. Creates defaults if none exist.
    Requires user to have date_of_birth set.
    Returns True if defaults were created, False otherwise.
    """
    if user.date_of_birth is None:
        return False
    
    # Check if any threshold metrics exist
    ftp_id = await _get_metric_type_id(db, "ftp")
    if not ftp_id:
        return False
    
    result = await db.execute(
        select(MetricEntry.id)
        .where(
            MetricEntry.user_id == user.id,
            MetricEntry.metric_type_id == ftp_id,
        )
        .limit(1)
    )
    if result.scalar_one_or_none() is not None:
        return False  # Already has thresholds
    
    # Create default thresholds
    defaults = compute_default_thresholds(
        user.date_of_birth, float(user.weight_kg) if user.weight_kg else None
    )
    
    await create_threshold_entries(
        db,
        user.id,
        date.today(),
        ftp_watts=defaults["ftp_watts"],
        lthr_bpm=defaults["lthr_bpm"],
        hrmax_bpm=defaults["hrmax_bpm"],
        source="calculated",
        source_detail="default_from_age_weight",
    )
    
    await db.commit()
    return True


# Backward compatibility alias
async def get_threshold_for_date(
    db: AsyncSession, user_id: int, target_date: date
) -> ThresholdValues | None:
    """
    Get threshold values effective on a given date.
    Returns ThresholdValues or None if no thresholds exist.
    
    Note: This is a compatibility wrapper. New code should use get_thresholds_for_date.
    """
    values = await get_thresholds_for_date(db, user_id, target_date)
    if values.ftp_watts is None and values.lthr_bpm is None and values.hrmax_bpm is None:
        return None
    return values
