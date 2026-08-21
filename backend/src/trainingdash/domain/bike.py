"""Bike domain logic for CdA/Crr defaults and validation.

Provides:
- Default CdA/Crr values by bike type
- Functions to get effective CdA/Crr (user value or default)
- Calibration eligibility checks
- Bike type validation

This module is pure domain logic with no I/O dependencies.
"""

from decimal import Decimal

# Valid bike types
BIKE_TYPES = frozenset({"road", "tt", "gravel", "mtb", "ebike"})

# Types eligible for CdA/Crr calibration (excludes ebike - motor assistance skews data)
CALIBRATION_ELIGIBLE_BIKE_TYPES = frozenset({"road", "tt", "gravel", "mtb"})

# Default CdA (m²) and Crr by bike type
# Sources: cycling aerodynamics research, typical values for amateur cyclists
# - CdA: Coefficient of drag * frontal area (rider + bike combined)
# - Crr: Coefficient of rolling resistance (tire/surface dependent)
BIKE_TYPE_DEFAULTS: dict[str, dict[str, float]] = {
    "road": {"cda": 0.32, "crr": 0.004},  # Drops position, slick tires
    "tt": {"cda": 0.24, "crr": 0.003},  # Aero position, TT tires
    "gravel": {"cda": 0.35, "crr": 0.006},  # Relaxed position, wider tires
    "mtb": {"cda": 0.45, "crr": 0.012},  # Upright position, knobby tires
    "ebike": {"cda": 0.35, "crr": 0.005},  # Similar to gravel geometry
}


def get_effective_cda(bike_type: str, cda: Decimal | float | None) -> float:
    """Return the effective CdA, falling back to default for bike type.

    Args:
        bike_type: The bike type (road, tt, gravel, mtb, ebike).
        cda: User-specified CdA, or None to use default.

    Returns:
        CdA in m². Uses cda if set, otherwise the default for bike_type.
    """
    if cda is not None:
        return float(cda)
    return BIKE_TYPE_DEFAULTS[bike_type]["cda"]


def get_effective_crr(bike_type: str, crr: Decimal | float | None) -> float:
    """Return the effective Crr, falling back to default for bike type.

    Args:
        bike_type: The bike type (road, tt, gravel, mtb, ebike).
        crr: User-specified Crr, or None to use default.

    Returns:
        Crr (dimensionless). Uses crr if set, otherwise the default for bike_type.
    """
    if crr is not None:
        return float(crr)
    return BIKE_TYPE_DEFAULTS[bike_type]["crr"]


def is_calibration_eligible_type(bike_type: str) -> bool:
    """Check if a bike type is eligible for CdA/Crr calibration.

    Ebikes are excluded because motor assistance skews power-based
    aerodynamic calculations.

    Args:
        bike_type: The bike type to check.

    Returns:
        True if the bike type supports calibration.
    """
    return bike_type in CALIBRATION_ELIGIBLE_BIKE_TYPES


def validate_bike_type(bike_type: str) -> bool:
    """Validate that a bike type is in the allowed list.

    Args:
        bike_type: The bike type to validate.

    Returns:
        True if valid, False otherwise.
    """
    return bike_type in BIKE_TYPES
