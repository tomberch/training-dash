"""Rider-behavior learning: the stop/coast baseline (ADR 0005 #635).

Learns what fraction of ride time a rider spends not pedaling — stopped
(complete stops: lights, junctions, breaks) and coasting (moving with no
cadence / no power) — per terrain type. This is the *baseline* measured
from activities; Plan-Type modulation (a later ticket) adjusts it at plan
time.

Extraction operates on primitive record streams; aggregation is
time-weighted across activities with a quality gate (thin buckets stay
unset rather than guessing).
"""

from dataclasses import dataclass
from itertools import pairwise

import numpy as np

# Quality gate: a terrain bucket needs this many activities before its
# baseline is trusted. Below it, the bucket stays unset.
MIN_ACTIVITIES_PER_BUCKET = 3

# Rides shorter than this carry too little behavior signal to matter.
MIN_RIDE_TIME_S = 600.0

# Records with gaps larger than this (recorder pauses) contribute no time.
MAX_RECORD_GAP_S = 60.0

# Speed thresholds separating "stopped" from "coasting" (m/s).
STOPPED_SPEED_MPS = 0.5


@dataclass
class RideBehaviorSample:
    """Non-pedaling fractions for one ride, classified to a terrain type."""

    terrain_type: str  # flat / rolling / hilly / mountain
    non_pedaling_pct: float  # stopped + coasting, % of ride time
    coasting_pct: float  # moving but not pedaling
    stopped_pct: float  # speed ~0 and not pedaling
    ride_time_s: float  # total analyzed ride time (weights the aggregate)


def _terrain_type_for_ride(grade_profile_pct: list[float], time_weights: list[float]) -> str:
    """Classify a RIDE into a terrain bucket by its character.

    Mirrors the validation harness's course_type: grade stddev through
    the punchiness VI model (VI = 1.12 + 0.028 × stddev), with the same
    thresholds (flat < 1.12, rolling < 1.18, hilly < 1.26, mountain
    above). Ride character, not second-by-second terrain: a mountain
    ride spends most time on shallow connectors yet must classify
    mountain (ADR 0005 #635 — the buckets the harness already uses).
    """
    if not grade_profile_pct:
        return "flat"
    weights = np.array(time_weights) if len(time_weights) == len(grade_profile_pct) else None
    grades = np.array(grade_profile_pct)
    if weights is not None and weights.sum() > 0:
        mean_g = np.sum(weights * grades) / weights.sum()
        var_g = np.sum(weights * (grades - mean_g) ** 2) / weights.sum()
    else:
        mean_g = grades.mean()
        var_g = grades.var()
    grade_stddev = float(np.sqrt(var_g))

    expected_vi = 1.12 + grade_stddev * 0.028
    if expected_vi < 1.12:
        return "flat"
    if expected_vi < 1.18:
        return "rolling"
    if expected_vi < 1.26:
        return "hilly"
    return "mountain"


def extract_ride_behavior(
    records: list,
    grade_profile_pct: list[float],
) -> RideBehaviorSample | None:
    """
    Extract the stop/coast behavior of one ride from its records.

    The ride is classified into one terrain bucket by its overall
    character (grade stddev → punchiness thresholds, the buckets the
    harness already uses), and its non-pedaling time is measured within
    that single bucket:
    - pedaling: cadence > 0 (or power > 0 when cadence is missing)
    - coasting: not pedaling, but moving (speed above stop threshold)
    - stopped: not pedaling and ~stationary

    Args:
        records: Activity records (timestamp, power_w, cadence_rpm,
            speed_mps, distance_m). Sorted by timestamp.
        grade_profile_pct: Per-record point grades (same ordinal stream as
            records; the harness computes these alongside elevation).
            Shorter profiles are extended by holding the last value.

    Returns:
        RideBehaviorSample for the ride's dominant terrain, or None when
        the ride is too short to carry signal.
    """
    valid = [r for r in records if r.timestamp is not None and r.distance_m is not None]
    if len(valid) < 2:
        return None
    valid = sorted(valid, key=lambda r: r.timestamp)

    total_time = 0.0
    coast_time = 0.0
    stop_time = 0.0
    interval_grades: list[float] = []
    interval_weights: list[float] = []

    for i, (prev, curr) in enumerate(pairwise(valid)):
        dt = (curr.timestamp - prev.timestamp).total_seconds()
        if dt <= 0 or dt > MAX_RECORD_GAP_S:
            continue
        total_time += dt

        interval_grades.append(_grade_at(grade_profile_pct, i))
        interval_weights.append(dt)

        pedaling = _is_pedaling(prev, curr)
        speed = _interval_speed(prev, curr, dt)
        if not pedaling:
            if speed <= STOPPED_SPEED_MPS:
                stop_time += dt
            else:
                coast_time += dt

    if total_time < MIN_RIDE_TIME_S:
        return None

    terrain = _terrain_type_for_ride(interval_grades, interval_weights)

    return RideBehaviorSample(
        terrain_type=terrain,
        non_pedaling_pct=100.0 * (coast_time + stop_time) / total_time,
        coasting_pct=100.0 * coast_time / total_time,
        stopped_pct=100.0 * stop_time / total_time,
        ride_time_s=total_time,
    )


def _is_pedaling(prev, curr) -> bool:
    """True when the rider actively pedals across the interval.

    Cadence is the primary signal (it distinguishes soft-pedaling from
    genuine coasting); power > 0 is the fallback when cadence is missing —
    power > 0 implies crank rotation by definition.
    """
    if prev.cadence_rpm is not None or curr.cadence_rpm is not None:
        return (prev.cadence_rpm or 0) > 0 or (curr.cadence_rpm or 0) > 0
    return (prev.power_w or 0) > 0 or (curr.power_w or 0) > 0


def _interval_speed(prev, curr, dt: float) -> float:
    """Ground speed across the interval; record speed as fallback."""
    dist = (curr.distance_m or 0) - (prev.distance_m or 0)
    if dt > 0 and dist >= 0:
        return dist / dt
    return curr.speed_mps or prev.speed_mps or 0.0


def _grade_at(grade_profile_pct: list[float], idx: int) -> float:
    """Point grade for record ordinal idx; holds last value past the end."""
    if not grade_profile_pct:
        return 0.0
    return grade_profile_pct[min(idx, len(grade_profile_pct) - 1)]


@dataclass
class TerrainBehaviorBaseline:
    """Learned non-pedaling baseline for one terrain type."""

    non_pedaling_pct: float
    coasting_pct: float
    stopped_pct: float
    activity_count: int


def aggregate_behavior_baseline(
    samples: list[RideBehaviorSample],
) -> dict[str, TerrainBehaviorBaseline] | None:
    """
    Aggregate per-ride samples into a per-rider baseline, per terrain.

    Time-weighted across activities: a 4-hour mountain ride informs the
    mountain baseline more than a 40-minute one. Quality gate: a terrain
    bucket needs MIN_ACTIVITIES_PER_BUCKET rides or it stays unset
    (absent from the result), never guessed.

    Returns:
        Dict of terrain_type → TerrainBehaviorBaseline, or None when no
        bucket has enough data.
    """
    by_terrain: dict[str, list[RideBehaviorSample]] = {}
    for s in samples:
        by_terrain.setdefault(s.terrain_type, []).append(s)

    baseline: dict[str, TerrainBehaviorBaseline] = {}
    for terrain, terrain_samples in by_terrain.items():
        if len(terrain_samples) < MIN_ACTIVITIES_PER_BUCKET:
            continue
        total_time = sum(s.ride_time_s for s in terrain_samples)
        if total_time <= 0:
            continue
        non_ped = sum(s.non_pedaling_pct * s.ride_time_s for s in terrain_samples) / total_time
        coast = sum(s.coasting_pct * s.ride_time_s for s in terrain_samples) / total_time
        stop = sum(s.stopped_pct * s.ride_time_s for s in terrain_samples) / total_time
        baseline[terrain] = TerrainBehaviorBaseline(
            non_pedaling_pct=non_ped,
            coasting_pct=coast,
            stopped_pct=stop,
            activity_count=len(terrain_samples),
        )

    return baseline if baseline else None
