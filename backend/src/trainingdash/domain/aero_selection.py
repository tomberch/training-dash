"""CdA/Crr selection strategy for race planning.

Selects aerodynamic parameters for race planning based on available data,
with graceful fallback when data is sparse.

Priority order:
1. User-provided manual override (highest priority, per-request)
2. Bike's calibrated values (wind tunnel, velodrome - known good)
3. Bike's estimated aggregates from activity data (if available)
4. Bike's manually entered values (user guesses)
5. Bike type defaults (fallback)

The selection includes uncertainty information (stddev) when available,
allowing the race planner to communicate confidence to users.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AeroSource(StrEnum):
    """Source of the selected CdA/Crr values."""

    USER_OVERRIDE = "user_override"  # User provided explicit values per-request
    CALIBRATED = "calibrated"  # From professional calibration (wind tunnel, velodrome)
    ESTIMATED = "estimated"  # From activity-based estimation
    MANUAL = "manual"  # From bike's manually entered values (user guess)
    DEFAULT = "default"  # From bike type defaults


@dataclass(frozen=True, slots=True)
class AeroSelection:
    """Selected CdA/Crr values with metadata.

    Attributes:
        cda: Aerodynamic drag area in m².
        crr: Rolling resistance coefficient.
        source: Where the values came from.
        cda_stddev: Standard deviation of CdA (if estimated).
        crr_stddev: Standard deviation of Crr (if estimated).
        sample_count: Number of activities used for estimation.
        confidence_note: Human-readable note about data quality.
    """

    cda: float
    crr: float
    source: AeroSource
    cda_stddev: float | None = None
    crr_stddev: float | None = None
    sample_count: int | None = None
    confidence_note: str | None = None


@dataclass
class BikeAeroData:
    """Bike aerodynamic data for selection.

    Mirrors the relevant fields from the Bike model.
    """

    bike_type: str
    # Manually configured values
    cda: float | None = None
    crr: float | None = None
    cda_source: str | None = None  # "manual" or "calibrated"
    crr_source: str | None = None  # "manual" or "calibrated"
    # Estimated aggregates from activities
    estimated_cda_avg: float | None = None
    estimated_crr_avg: float | None = None
    estimated_cda_stddev: float | None = None
    estimated_crr_stddev: float | None = None
    aero_sample_count: int | None = None


def select_aero_params(
    bike: BikeAeroData | None = None,
    user_cda: float | None = None,
    user_crr: float | None = None,
    bike_type_fallback: str = "road",
) -> AeroSelection:
    """Select CdA/Crr values for race planning.

    Uses the priority order:
    1. User override (if both cda and crr provided) - per-request
    2. Bike's calibrated values (wind tunnel, velodrome) - known good
    3. Bike's manually entered values (user entry takes precedence)
    4. Bike's estimated aggregates (if sample_count > 0)
    5. Bike type defaults

    Args:
        bike: Bike aerodynamic data, or None if no bike selected.
        user_cda: User-provided CdA override.
        user_crr: User-provided Crr override.
        bike_type_fallback: Bike type to use for defaults if no bike.

    Returns:
        AeroSelection with chosen values and metadata.
    """
    from trainingdash.domain.bike import BIKE_TYPE_DEFAULTS

    # 1. User override (requires both values)
    if user_cda is not None and user_crr is not None:
        return AeroSelection(
            cda=user_cda,
            crr=user_crr,
            source=AeroSource.USER_OVERRIDE,
            confidence_note="Using user-provided values",
        )

    # If no bike, go straight to defaults
    if bike is None:
        defaults = BIKE_TYPE_DEFAULTS.get(bike_type_fallback, BIKE_TYPE_DEFAULTS["road"])
        return AeroSelection(
            cda=defaults["cda"],
            crr=defaults["crr"],
            source=AeroSource.DEFAULT,
            confidence_note=f"Using {bike_type_fallback} defaults (no bike selected)",
        )

    # 2. Calibrated values (wind tunnel, velodrome - highest priority bike data)
    if (
        bike.cda is not None
        and bike.crr is not None
        and bike.cda_source == "calibrated"
        and bike.crr_source == "calibrated"
    ):
        return AeroSelection(
            cda=bike.cda,
            crr=bike.crr,
            source=AeroSource.CALIBRATED,
            confidence_note="Using calibrated values (wind tunnel/velodrome)",
        )

    # 3. Manually entered values on the bike (user entry takes precedence over estimates)
    if bike.cda is not None and bike.crr is not None:
        return AeroSelection(
            cda=bike.cda,
            crr=bike.crr,
            source=AeroSource.MANUAL,
            confidence_note="Using bike's manually entered values",
        )

    # 4. Estimated aggregates from activities
    if (
        bike.aero_sample_count is not None
        and bike.aero_sample_count > 0
        and bike.estimated_cda_avg is not None
        and bike.estimated_crr_avg is not None
    ):
        confidence_note = _build_confidence_note(
            bike.aero_sample_count,
            bike.estimated_cda_stddev,
            bike.estimated_crr_stddev,
        )
        return AeroSelection(
            cda=bike.estimated_cda_avg,
            crr=bike.estimated_crr_avg,
            source=AeroSource.ESTIMATED,
            cda_stddev=bike.estimated_cda_stddev,
            crr_stddev=bike.estimated_crr_stddev,
            sample_count=bike.aero_sample_count,
            confidence_note=confidence_note,
        )

    # 5. Bike type defaults
    defaults = BIKE_TYPE_DEFAULTS.get(bike.bike_type, BIKE_TYPE_DEFAULTS["road"])
    return AeroSelection(
        cda=defaults["cda"],
        crr=defaults["crr"],
        source=AeroSource.DEFAULT,
        confidence_note=f"Using {bike.bike_type} defaults (no activity data yet)",
    )


def _build_confidence_note(
    sample_count: int,
    cda_stddev: float | None,
    crr_stddev: float | None,
) -> str:
    """Build a human-readable confidence note.

    Args:
        sample_count: Number of activities used.
        cda_stddev: CdA standard deviation.
        crr_stddev: Crr standard deviation.

    Returns:
        Confidence description string.
    """
    # Assess sample size
    if sample_count >= 10:
        size_quality = "good"
    elif sample_count >= 5:
        size_quality = "moderate"
    else:
        size_quality = "limited"

    # Assess consistency (CV < 5% is good, < 10% is moderate)
    consistency = "unknown"
    if cda_stddev is not None:
        # Typical CdA is ~0.3, so stddev of 0.015 (5%) is good
        if cda_stddev < 0.015:
            consistency = "consistent"
        elif cda_stddev < 0.03:
            consistency = "moderate"
        else:
            consistency = "variable"

    if size_quality == "good" and consistency == "consistent":
        return f"Based on {sample_count} activities with consistent results"
    elif size_quality == "limited":
        return f"Based on {sample_count} activities (more data recommended)"
    else:
        return f"Based on {sample_count} activities"
