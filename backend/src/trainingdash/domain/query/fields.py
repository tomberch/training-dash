"""Field registry for the query DSL.

Defines queryable fields with their types, units, and user-friendly aliases.
"""

from dataclasses import dataclass
from enum import Enum


class FieldType(Enum):
    """Data types for queryable fields."""

    NUMBER = "number"  # Numeric values (int or float)
    STRING = "string"  # Text values
    DATE = "date"  # Date/datetime values
    BOOLEAN = "boolean"  # True/false values
    DURATION = "duration"  # Time duration (stored as seconds)


@dataclass(frozen=True)
class FieldDef:
    """Definition of a queryable field."""

    internal_name: str  # Column name in database
    field_type: FieldType
    nullable: bool = True
    internal_unit: str | None = None  # Unit the value is stored in (m, s, mps, etc.)
    computed: bool = False  # True if derived from other fields
    description: str = ""


# Unit conversion factors to internal units
# Usage: internal_value = external_value * UNIT_CONVERSIONS[from_unit][to_unit]
UNIT_CONVERSIONS: dict[str, dict[str, float]] = {
    # Distance → meters
    "km": {"m": 1000.0},
    "mi": {"m": 1609.344},
    "ft": {"m": 0.3048},
    "m": {"m": 1.0},
    # Speed → meters per second
    "kph": {"mps": 1 / 3.6},  # km/h to m/s
    "mph": {"mps": 0.44704},  # miles/h to m/s
    "mps": {"mps": 1.0},
    # Duration → seconds
    "h": {"s": 3600.0},
    "min": {"s": 60.0},
    "sec": {"s": 1.0},
    "s": {"s": 1.0},
}

# Map internal unit suffixes to the standard internal unit
INTERNAL_UNIT_MAP: dict[str, str] = {
    "_m": "m",  # meters
    "_s": "s",  # seconds
    "_mps": "mps",  # meters per second
    "_bpm": None,  # beats per minute (no conversion needed)
    "_w": None,  # watts (no conversion needed)
}


def get_conversion_factor(from_unit: str, to_unit: str) -> float | None:
    """Get the conversion factor from one unit to another.

    Returns None if conversion is not supported.
    """
    from_unit = from_unit.lower()
    to_unit = to_unit.lower()

    if from_unit == to_unit:
        return 1.0

    conversions = UNIT_CONVERSIONS.get(from_unit)
    if conversions:
        return conversions.get(to_unit)
    return None


# Field definitions with internal names and metadata
FIELD_DEFINITIONS: dict[str, FieldDef] = {
    # Core activity fields
    "id": FieldDef("id", FieldType.STRING, nullable=False, description="Activity UUID"),
    "started_at": FieldDef(
        "started_at", FieldType.DATE, nullable=False, description="Activity start time"
    ),
    "source": FieldDef(
        "source", FieldType.STRING, nullable=False, description="Data source (xert, garmin, upload)"
    ),
    "title": FieldDef("title", FieldType.STRING, nullable=True, description="Activity title"),
    # Distance and elevation
    "total_distance_m": FieldDef(
        "total_distance_m",
        FieldType.NUMBER,
        nullable=False,
        internal_unit="m",
        description="Total distance in meters",
    ),
    "elevation_gain_m": FieldDef(
        "elevation_gain_m",
        FieldType.NUMBER,
        nullable=False,
        internal_unit="m",
        description="Elevation gain in meters",
    ),
    # Duration fields
    "moving_time_s": FieldDef(
        "moving_time_s",
        FieldType.DURATION,
        nullable=False,
        internal_unit="s",
        description="Moving time in seconds",
    ),
    "elapsed_time_s": FieldDef(
        "elapsed_time_s",
        FieldType.DURATION,
        nullable=False,
        internal_unit="s",
        description="Elapsed time in seconds",
    ),
    # Speed fields
    "avg_speed_mps": FieldDef(
        "avg_speed_mps",
        FieldType.NUMBER,
        nullable=False,
        internal_unit="mps",
        description="Average speed in m/s",
    ),
    "max_speed_mps": FieldDef(
        "max_speed_mps",
        FieldType.NUMBER,
        nullable=False,
        internal_unit="mps",
        description="Max speed in m/s",
    ),
    # Heart rate fields
    "avg_hr_bpm": FieldDef(
        "avg_hr_bpm", FieldType.NUMBER, nullable=True, description="Average heart rate in bpm"
    ),
    "max_hr_bpm": FieldDef(
        "max_hr_bpm", FieldType.NUMBER, nullable=True, description="Max heart rate in bpm"
    ),
    # Power fields
    "avg_power_w": FieldDef(
        "avg_power_w", FieldType.NUMBER, nullable=True, description="Average power in watts"
    ),
    "np_power_w": FieldDef(
        "np_power_w", FieldType.NUMBER, nullable=True, description="Normalized power in watts"
    ),
    "power_source": FieldDef(
        "power_source",
        FieldType.STRING,
        nullable=True,
        description="Power source (measured, hr_derived)",
    ),
    "power_confidence": FieldDef(
        "power_confidence",
        FieldType.NUMBER,
        nullable=True,
        description="Power confidence for hr_derived (0-1)",
    ),
    # Training metrics
    "tss": FieldDef("tss", FieldType.NUMBER, nullable=True, description="Training Stress Score"),
    "intensity_factor": FieldDef(
        "intensity_factor", FieldType.NUMBER, nullable=True, description="Intensity Factor (IF)"
    ),
    "training_load": FieldDef(
        "training_load", FieldType.NUMBER, nullable=True, description="Training load"
    ),
    # W'bal metrics
    "wbal_min_joules": FieldDef(
        "wbal_min_joules",
        FieldType.NUMBER,
        nullable=True,
        description="Minimum W' balance in joules",
    ),
    "wbal_min_pct": FieldDef(
        "wbal_min_pct",
        FieldType.NUMBER,
        nullable=True,
        description="Minimum W' balance as percentage",
    ),
    # Boolean fields
    "is_breakthrough": FieldDef(
        "is_breakthrough",
        FieldType.BOOLEAN,
        nullable=False,
        description="Breakthrough activity flag",
    ),
    # Route-related
    "route_id": FieldDef("route_id", FieldType.NUMBER, nullable=True, description="Associated route"),
    "direction_bearing": FieldDef(
        "direction_bearing",
        FieldType.NUMBER,
        nullable=True,
        description="Direction bearing (0-359 degrees)",
    ),
}

# User-friendly aliases mapping to internal field names
FIELD_ALIASES: dict[str, str] = {
    # Distance aliases
    "distance": "total_distance_m",
    "dist": "total_distance_m",
    # Elevation aliases
    "elevation": "elevation_gain_m",
    "elev": "elevation_gain_m",
    "gain": "elevation_gain_m",
    "climbing": "elevation_gain_m",
    # Duration aliases
    "duration": "moving_time_s",
    "time": "moving_time_s",
    "moving_time": "moving_time_s",
    "elapsed": "elapsed_time_s",
    "elapsed_time": "elapsed_time_s",
    # Speed aliases
    "speed": "avg_speed_mps",
    "avg_speed": "avg_speed_mps",
    "max_speed": "max_speed_mps",
    # Heart rate aliases
    "hr": "avg_hr_bpm",
    "avg_hr": "avg_hr_bpm",
    "heart_rate": "avg_hr_bpm",
    "max_hr": "max_hr_bpm",
    # Power aliases
    "power": "avg_power_w",
    "avg_power": "avg_power_w",
    "watts": "avg_power_w",
    "np": "np_power_w",
    "normalized_power": "np_power_w",
    # Date aliases
    "date": "started_at",
    "start": "started_at",
    "started": "started_at",
    # Training metric aliases
    "if": "intensity_factor",
    "load": "training_load",
    # Boolean aliases
    "breakthrough": "is_breakthrough",
    # Other
    "title": "title",
    "name": "title",
    "source": "source",
    "route": "route_id",
}

# All valid field names (internal names + aliases)
ALL_FIELD_NAMES: set[str] = set(FIELD_DEFINITIONS.keys()) | set(FIELD_ALIASES.keys())


def resolve_field_name(name: str) -> str | None:
    """Resolve a field name or alias to the internal field name.

    Returns None if the field is not found.
    """
    name_lower = name.lower()

    # Check if it's an internal name (case-insensitive)
    for internal in FIELD_DEFINITIONS:
        if internal.lower() == name_lower:
            return internal

    # Check aliases (case-insensitive)
    for alias, internal in FIELD_ALIASES.items():
        if alias.lower() == name_lower:
            return internal

    return None


def get_field_def(name: str) -> FieldDef | None:
    """Get the field definition for a field name or alias.

    Returns None if the field is not found.
    """
    internal = resolve_field_name(name)
    if internal:
        return FIELD_DEFINITIONS.get(internal)
    return None


def suggest_field_name(name: str, max_suggestions: int = 3) -> list[str]:
    """Suggest similar field names for a typo.

    Uses simple Levenshtein-like distance for suggestions.
    """
    name_lower = name.lower()
    candidates: list[tuple[int, str]] = []

    # Check all field names and aliases
    for field in ALL_FIELD_NAMES:
        dist = _edit_distance(name_lower, field.lower())
        if dist <= 3:  # Only suggest if reasonably close
            candidates.append((dist, field))

    # Sort by distance, then alphabetically
    candidates.sort(key=lambda x: (x[0], x[1]))

    # Return the best suggestions (prefer aliases over internal names)
    suggestions = []
    seen_internal = set()
    for _, field in candidates:
        internal = resolve_field_name(field)
        if internal and internal not in seen_internal:
            # Prefer the alias if it exists
            if field in FIELD_ALIASES:
                suggestions.append(field)
            else:
                suggestions.append(internal)
            seen_internal.add(internal)
        if len(suggestions) >= max_suggestions:
            break

    return suggestions


def _edit_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


# Operators valid for each field type
VALID_OPERATORS: dict[FieldType, set[str]] = {
    FieldType.NUMBER: {"=", "!=", ">", ">=", "<", "<="},
    FieldType.STRING: {"=", "!="},
    FieldType.DATE: {"=", "!=", ">", ">=", "<", "<="},
    FieldType.BOOLEAN: {"=", "!="},
    FieldType.DURATION: {"=", "!=", ">", ">=", "<", "<="},
}

# Text match operators only valid for STRING type
TEXT_MATCH_OPERATORS = {"CONTAINS", "STARTS_WITH", "ENDS_WITH"}


def is_valid_operator(field_type: FieldType, operator: str) -> bool:
    """Check if an operator is valid for a field type."""
    return operator in VALID_OPERATORS.get(field_type, set())


def is_text_match_valid(field_type: FieldType) -> bool:
    """Check if text matching is valid for a field type."""
    return field_type == FieldType.STRING


# Fields valid for aggregation
AGGREGATABLE_FIELDS: set[str] = {
    "total_distance_m",
    "elevation_gain_m",
    "moving_time_s",
    "elapsed_time_s",
    "avg_speed_mps",
    "max_speed_mps",
    "avg_hr_bpm",
    "max_hr_bpm",
    "avg_power_w",
    "np_power_w",
    "tss",
    "intensity_factor",
    "training_load",
    "wbal_min_joules",
    "wbal_min_pct",
}


def is_aggregatable(field_name: str) -> bool:
    """Check if a field can be used in aggregation functions."""
    internal = resolve_field_name(field_name)
    return internal in AGGREGATABLE_FIELDS if internal else False
