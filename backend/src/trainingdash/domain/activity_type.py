"""Activity type detection from FIT file sport/sub_sport fields.

Supports: road, gravel, mtb, virtual, indoor, commute, other.

Used for:
- Filtering activity list by type
- Excluding indoor/virtual from CdA/Crr calibration
- Analytics segmentation

Note: E-bike is a bike type, not an activity type. Activities ridden on an
e-bike are excluded from race planner input via the bike_type check, not
activity_type.
"""

# Valid activity types
ACTIVITY_TYPES = frozenset({"road", "gravel", "mtb", "virtual", "indoor", "commute", "other"})

# Types eligible for CdA/Crr calibration (outdoor rides only)
CALIBRATION_ELIGIBLE_TYPES = frozenset({"road", "gravel", "mtb", "commute"})


def detect_activity_type(sport: str | None, sub_sport: str | None) -> str:
    """Detect activity type from FIT file sport and sub_sport fields.

    Args:
        sport: FIT sport field (e.g., "cycling", "running")
        sub_sport: FIT sub_sport field (e.g., "virtual_activity", "indoor_cycling")

    Returns:
        Activity type string: road, gravel, mtb, virtual, indoor, commute, or other.
        Defaults to "road" for cycling activities without specific sub_sport.

    Note:
        The garmin-fit-sdk returns these as lowercase strings when using
        convert_types_to_strings=True.

        E-bike activities (sport="e_biking") are classified as "road" by default.
        E-bike exclusion from analysis is handled via bike_type, not activity_type.
    """
    # Normalize inputs
    sport = (sport or "").lower().strip()
    sub_sport = (sub_sport or "").lower().strip()

    # Non-cycling activities (e_biking is cycling-related, treat as cycling)
    if sport and sport not in ("cycling", "e_biking"):
        return "other"

    # Virtual/indoor detection (most specific, check first)
    if sub_sport in ("virtual_activity", "virtual"):
        return "virtual"

    if sub_sport in ("indoor_cycling", "indoor"):
        return "indoor"

    # Mountain biking
    if sub_sport in ("mountain", "mtb", "mountain_biking"):
        return "mtb"

    # Gravel/cyclocross
    if sub_sport in ("gravel_cycling", "gravel", "cyclocross", "cx"):
        return "gravel"

    # Commute/transportation
    if sub_sport in ("commuting", "cycling_transportation", "commute", "transport"):
        return "commute"

    # Default to road for generic cycling or unknown sub_sport
    # This covers: "road", "generic", "", or any unrecognized value
    return "road"


def is_calibration_eligible(activity_type: str | None) -> bool:
    """Check if an activity type is eligible for CdA/Crr calibration.

    Only explicitly outdoor types are eligible. Null/unknown types are
    excluded to avoid corrupting calibration data with indoor rides.

    Args:
        activity_type: The activity type, or None for unclassified.

    Returns:
        True if the activity type is eligible for calibration.
    """
    if activity_type is None:
        return False
    return activity_type in CALIBRATION_ELIGIBLE_TYPES


def validate_activity_type(activity_type: str) -> str | None:
    """Validate and normalize an activity type value.

    Args:
        activity_type: The activity type to validate. Empty string means
            "set to null/unclassified".

    Returns:
        The validated activity type, or None if empty string was passed.

    Raises:
        ValueError: If the activity type is not valid.
    """
    if activity_type == "":
        return None
    if activity_type in ACTIVITY_TYPES:
        return activity_type
    raise ValueError(f"Invalid activity_type '{activity_type}'. Must be one of: {', '.join(sorted(ACTIVITY_TYPES))}")
