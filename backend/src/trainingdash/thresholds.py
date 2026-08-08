"""Threshold business logic.

Handles FTP, LTHR, HRmax threshold management.
Zone computation has moved to trainingdash.zones module.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.models import ThresholdHistory, User


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
