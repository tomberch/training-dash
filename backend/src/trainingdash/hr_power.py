"""HR-derived power estimation using Efficiency Factor (EF) model."""

import math
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from trainingdash.repositories.postgres.models import Activity, EFModel, User

# Minimum rides needed to build EF model
MIN_RIDES_FOR_MODEL = 5

# Model staleness threshold (days since last dual-sensor ride)
STALENESS_THRESHOLD_DAYS = 30

# Half-life for decay weighting (days)
DECAY_HALF_LIFE_DAYS = 42


def compute_ef(np_watts: int, avg_hr: int) -> float:
    """Compute Efficiency Factor: NP / HR."""
    if avg_hr <= 0:
        return 0.0
    return np_watts / avg_hr


def compute_vi(np_watts: int, avg_watts: int) -> float:
    """Compute Variability Index: NP / avg power."""
    if avg_watts <= 0:
        return 1.25  # Default if no valid avg
    return np_watts / avg_watts


def compute_decay_weight(activity_date: datetime, reference_date: datetime) -> float:
    """
    Compute decay weight for an activity based on age.
    Uses exponential decay with 42-day half-life.
    """
    days_ago = (reference_date - activity_date).days
    if days_ago < 0:
        days_ago = 0
    return math.exp(-math.log(2) * days_ago / DECAY_HALF_LIFE_DAYS)


async def update_ef_model(db: AsyncSession, user_id: int) -> EFModel | None:
    """
    Update the EF model for a user based on their dual-sensor rides.

    Returns the updated model, or None if insufficient data.
    """
    # Check if user has HR-derived power enabled
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.hr_derived_power_enabled:
        return None

    # Get activities with both power and HR (dual-sensor rides)
    result = await db.execute(
        select(Activity)
        .where(
            Activity.user_id == user_id,
            Activity.np_power_w.isnot(None),
            Activity.avg_power_w.isnot(None),
            Activity.avg_power_w > 0,
            Activity.avg_hr_bpm.isnot(None),
            Activity.avg_hr_bpm > 0,
            Activity.power_source != "hr_derived",  # Only measured power
        )
        .order_by(Activity.started_at.desc())
    )
    dual_sensor_rides = result.scalars().all()

    if len(dual_sensor_rides) < MIN_RIDES_FOR_MODEL:
        return None

    # Compute weighted average EF and VI
    now = datetime.now(UTC).replace(tzinfo=None)
    total_weight = 0.0
    weighted_ef_sum = 0.0
    weighted_vi_sum = 0.0

    for activity in dual_sensor_rides:
        ef = compute_ef(activity.np_power_w, activity.avg_hr_bpm)
        vi = compute_vi(activity.np_power_w, activity.avg_power_w)
        weight = compute_decay_weight(activity.started_at, now)

        weighted_ef_sum += ef * weight
        weighted_vi_sum += vi * weight
        total_weight += weight

    if total_weight == 0:
        return None

    ef_value = weighted_ef_sum / total_weight
    vi_value = weighted_vi_sum / total_weight

    # Compute confidence score
    confidence = compute_confidence(dual_sensor_rides, now)

    # Upsert EF model
    result = await db.execute(select(EFModel).where(EFModel.user_id == user_id))
    existing = result.scalar_one_or_none()

    if existing:
        existing.ef_value = ef_value
        existing.vi_value = vi_value
        existing.computed_at = now
        existing.ride_count = len(dual_sensor_rides)
        existing.confidence = confidence
        model = existing
    else:
        model = EFModel(
            user_id=user_id,
            ef_value=ef_value,
            vi_value=vi_value,
            computed_at=now,
            ride_count=len(dual_sensor_rides),
            confidence=confidence,
        )
        db.add(model)

    await db.commit()
    await db.refresh(model)
    return model


def compute_confidence(dual_sensor_rides: list[Activity], reference_date: datetime) -> float:
    """
    Compute confidence score for the EF model.

    Factors:
    - Number of rides (more = higher confidence, up to 20)
    - Recency of last ride (< 30 days = higher confidence)
    - Consistency of EF values (lower variance = higher confidence)
    """
    if not dual_sensor_rides:
        return 0.0

    # Factor 1: Ride count (0.0-0.4)
    ride_count = len(dual_sensor_rides)
    count_factor = min(ride_count / 20, 1.0) * 0.4

    # Factor 2: Recency (0.0-0.3)
    most_recent = dual_sensor_rides[0].started_at
    days_since_last = (reference_date - most_recent).days
    if days_since_last <= STALENESS_THRESHOLD_DAYS:
        recency_factor = 0.3 * (1 - days_since_last / STALENESS_THRESHOLD_DAYS)
    else:
        recency_factor = 0.0

    # Factor 3: Consistency (0.0-0.3)
    ef_values = [compute_ef(a.np_power_w, a.avg_hr_bpm) for a in dual_sensor_rides if a.np_power_w and a.avg_hr_bpm]

    if len(ef_values) >= 2:
        mean_ef = sum(ef_values) / len(ef_values)
        variance = sum((ef - mean_ef) ** 2 for ef in ef_values) / len(ef_values)
        std_dev = math.sqrt(variance)
        # Lower coefficient of variation = more consistent
        cv = std_dev / mean_ef if mean_ef > 0 else 1.0
        # CV of 0.1 or less = full consistency score
        consistency_factor = max(0, 0.3 * (1 - min(cv / 0.2, 1.0)))
    else:
        consistency_factor = 0.0

    return round(count_factor + recency_factor + consistency_factor, 3)


async def estimate_power_from_hr(
    db: AsyncSession,
    user_id: int,
    avg_hr: int,
) -> tuple[int | None, int | None, float | None]:
    """
    Estimate power from heart rate using the EF model.

    Since EF = NP / HR, the formula EF × HR gives us NP (Normalized Power).
    We derive average power using the user's personal Variability Index (VI = NP / avg).

    Returns (estimated_avg_power, estimated_np, confidence) or (None, None, None) if no model.
    """
    # Get EF model
    result = await db.execute(select(EFModel).where(EFModel.user_id == user_id))
    model = result.scalar_one_or_none()

    if model is None:
        return None, None, None

    # Check staleness
    now = datetime.now(UTC).replace(tzinfo=None)
    days_since_update = (now - model.computed_at).days

    if days_since_update > STALENESS_THRESHOLD_DAYS:
        # Model is stale - reduce confidence
        staleness_penalty = min(days_since_update / (STALENESS_THRESHOLD_DAYS * 2), 0.5)
        adjusted_confidence = max(0.1, model.confidence - staleness_penalty)
    else:
        adjusted_confidence = model.confidence

    # Estimate NP: since EF = NP / HR, then NP = EF × HR
    estimated_np = int(round(float(model.ef_value) * avg_hr))

    # Derive average power using user's personal VI
    # VI = NP / avg, so avg = NP / VI
    vi = float(model.vi_value) if model.vi_value else 1.25
    estimated_avg = int(round(estimated_np / vi))

    return estimated_avg, estimated_np, round(adjusted_confidence, 3)


async def get_ef_model_status(db: AsyncSession, user_id: int) -> dict:
    """
    Get the status of the user's EF model for display in /me endpoint.
    """
    from sqlalchemy import func

    # Check if enabled
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    enabled = user.hr_derived_power_enabled if user else False

    # Get model if exists
    result = await db.execute(select(EFModel).where(EFModel.user_id == user_id))
    model = result.scalar_one_or_none()

    if model is None:
        # Count eligible dual-sensor activities even when model doesn't exist yet
        # This lets the UI show progress toward the 5-ride minimum
        result = await db.execute(
            select(func.count())
            .select_from(Activity)
            .where(
                Activity.user_id == user_id,
                Activity.np_power_w.isnot(None),
                Activity.avg_hr_bpm.isnot(None),
                Activity.avg_hr_bpm > 0,
                Activity.power_source != "hr_derived",
            )
        )
        eligible_count = result.scalar() or 0

        return {
            "enabled": enabled,
            "model_exists": False,
            "ef_value": None,
            "vi_value": None,
            "confidence": None,
            "ride_count": eligible_count,
            "computed_at": None,
            "is_stale": None,
        }

    now = datetime.now(UTC).replace(tzinfo=None)
    days_since_update = (now - model.computed_at).days
    is_stale = days_since_update > STALENESS_THRESHOLD_DAYS

    return {
        "enabled": enabled,
        "model_exists": True,
        "ef_value": float(model.ef_value),
        "vi_value": float(model.vi_value) if model.vi_value else 1.25,
        "confidence": float(model.confidence),
        "ride_count": model.ride_count,
        "computed_at": model.computed_at.isoformat(),
        "is_stale": is_stale,
    }
