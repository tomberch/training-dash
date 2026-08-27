"""Golden output pins for the pacing model.

These tests pin the EXACT outputs of the pacing interfaces against
snapshots captured before the Phase A consolidation (ADR 0004).

They are deliberately repr-exact: any diff means the consolidation
changed behavior and must be investigated, never silently loosened.

Regenerating snapshots after an INTENDED behavior change (Phase B):
    uv run python tests/unit/domain/pacing_golden_pins.py --update
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trainingdash.domain.course_segmentation import CourseSegment
from trainingdash.domain.pacing import (
    PacingCoefficients,
    generate_heuristic_pacing,
    generate_terrain_adapted_pacing,
)
from trainingdash.domain.physics import EnvironmentParams, RiderParams

SNAPSHOTS = Path(__file__).parent / "pacing_golden_pins.json"
UPDATE = False  # flipped by __main__ regeneration below

# --- Deterministic inputs -------------------------------------------------


def _profile(points: list[tuple[float, float]]) -> list[dict]:
    """Build an elevation profile [{distance_m, elevation_m, grade_pct, lat, lon}].

    grade_pct is computed exactly as CreateCourse does (per-point delta),
    and lat/lon walk north so curvature is ~0 (straight road).
    """
    out = []
    lat = 47.0
    lon = 8.0
    for i in range(len(points)):
        d, elev = points[i]
        if i == 0:
            grade = 0.0
        else:
            d_prev, elev_prev = points[i - 1]
            grade = (elev - elev_prev) / max(1.0, (d - d_prev)) * 100.0
        out.append(
            {
                "distance_m": d,
                "elevation_m": elev,
                "grade_pct": round(grade, 4),
                "lat": lat,
                "lon": lon,
            }
        )
        lat += 0.0001  # ~11m north per step; keeps bearing constant
        lon += 0.0001
    return out


def _segments_from_profile(profile: list[dict], seg_len_m: float = 1000.0) -> list[CourseSegment]:
    """Split the profile into coarse CourseSegment objects (race planner shape)."""
    segs = []
    total = profile[-1]["distance_m"]
    d = 0.0
    while d < total:
        end = min(d + seg_len_m, total)
        inside = [p for p in profile if d <= p["distance_m"] < end]
        grades = [p["grade_pct"] for p in inside] or [0.0]
        elev_gain = sum(max(0.0, p["elevation_m"] - q["elevation_m"]) for p, q in zip(inside[1:], inside[:-1]))
        elev_loss = sum(max(0.0, q["elevation_m"] - p["elevation_m"]) for p, q in zip(inside[1:], inside[:-1]))
        avg_grade = sum(grades) / len(grades)
        if avg_grade > 3.0:
            terrain = "climb"
        elif avg_grade < -3.0:
            terrain = "descent"
        elif avg_grade < -0.5 or avg_grade > 0.5:
            terrain = "rolling"
        else:
            terrain = "flat"
        segs.append(
            CourseSegment(
                start_distance_m=d,
                end_distance_m=end,
                length_m=end - d,
                avg_grade_pct=avg_grade,
                elevation_gain_m=elev_gain,
                elevation_loss_m=elev_loss,
                terrain_type=terrain,
            )
        )
        d = end
    return segs


def _course(name: str, profile: list[dict]) -> dict:
    return {"name": name, "profile": profile, "segments": _segments_from_profile(profile)}


def _flat_course() -> dict:
    return _course("flat", _profile([(i * 50.0, 100.0) for i in range(200)]))


def _rolling_course() -> dict:
    import math

    pts = []
    for i in range(200):
        d = i * 50.0
        elev = 100.0 + 25.0 * math.sin(d / 400.0) + 10.0 * math.sin(d / 130.0)
        pts.append((d, elev))
    return _course("rolling", _profile(pts))


def _hc_climb_course() -> dict:
    pts = []
    for i in range(200):
        d = i * 50.0
        elev = 100.0 + (d / 10000.0) * 900.0  # 9% avg grade
        pts.append((d, elev))
    return _course("hc_climb", _profile(pts))


def _descent_course() -> dict:
    pts = []
    for i in range(200):
        d = i * 50.0
        # Steep first half, shallow second half — exercises descent caps
        grade = -8.0 if d < 5000 else -3.0
        pts.append((d, 900.0 + grade * d))
    return _course("descent", _profile(pts))


COURSES = {
    "flat": _flat_course(),
    "rolling": _rolling_course(),
    "hc_climb": _hc_climb_course(),
    "descent": _descent_course(),
}

RIDER = RiderParams(mass_kg=75 + 8 + 3, cda=0.32, crr=0.004)
ENV = EnvironmentParams(air_density=1.15)

COEFFICIENTS = {
    "defaults": PacingCoefficients(),  # dataclass defaults
    "calibrated": PacingCoefficients(
        grade_power_intercept=1.30,
        grade_power_slope=0.020,
        max_descent_speed_mps=14.5,
        descent_power_multiplier=0.45,
        curvature_speed_coefficient=0.015,
    ),
}

INTERFACES = ("terrain_adapted", "heuristic")


# --- Serialization ---------------------------------------------------------


def _plan_repr(plan) -> dict:
    """Exact repr of a PacingPlan: every field, full float fidelity."""
    return {
        "total_time_s": repr(plan.total_time_s),
        "total_distance_m": repr(plan.total_distance_m),
        "avg_power_w": repr(plan.avg_power_w),
        "normalized_power_w": repr(plan.normalized_power_w),
        "intensity_factor": repr(plan.intensity_factor),
        "targets": [
            {
                "segment_idx": t.segment_idx,
                "start_distance_m": repr(t.start_distance_m),
                "end_distance_m": repr(t.end_distance_m),
                "distance_m": repr(t.distance_m),
                "grade_pct": repr(t.grade_pct),
                "target_power_w": repr(t.target_power_w),
                "terrain_type": t.terrain_type,
                "estimated_speed_mps": repr(t.estimated_speed_mps),
                "estimated_time_s": repr(t.estimated_time_s),
            }
            for t in plan.targets
        ],
    }


def _run_all() -> dict:
    out: dict = {}
    for course_name, course in COURSES.items():
        for coeff_name, coefficients in COEFFICIENTS.items():
            for interface in INTERFACES:
                kwargs = {
                    "segments": course["segments"],
                    "rider_ftp": 280.0,
                    "target_intensity": 0.85,
                    "rider_params": RIDER,
                    "env_params": ENV,
                    "coefficients": coefficients,
                }
                if interface == "terrain_adapted":
                    kwargs["elevation_profile"] = course["profile"]
                    kwargs["max_descent_speed_mps"] = coefficients.max_descent_speed_mps
                    plan = generate_terrain_adapted_pacing(**kwargs)
                else:
                    # heuristic interface predates coefficients — drop them;
                    # its behavior is pinned across both coefficient sets anyway
                    del kwargs["coefficients"]
                    kwargs["max_descent_speed_mps"] = coefficients.max_descent_speed_mps
                    plan = generate_heuristic_pacing(**kwargs)
                key = f"{course_name}|{coeff_name}|{interface}"
                out[key] = _plan_repr(plan)
    return out


# --- Tests -----------------------------------------------------------------


@pytest.mark.skipif(
    not SNAPSHOTS.exists(),
    reason="run `python tests/unit/domain/pacing_golden_pins.py` once to generate snapshots",
)
class TestPacingGoldenPins:
    def test_pinned_outputs_unchanged(self):
        """Every pinned plan output is repr-exact unchanged."""
        import hashlib

        def _hash(d: dict) -> str:
            blob = json.dumps(d, sort_keys=True, ensure_ascii=True).encode()
            return hashlib.sha256(blob).hexdigest()

        pinned = json.loads(SNAPSHOTS.read_text())
        current = {k: _hash(v) for k, v in _run_all().items()}
        assert set(current) == set(pinned), "pin set changed"

        diffs = [k for k in pinned if current[k] != _hash(pinned[k])]
        assert diffs == [], (
            f"{len(diffs)} pinned plan(s) changed: {diffs[:5]}... "
            "If intended (Phase B), regenerate with "
            "`python tests/unit/domain/pacing_golden_pins.py --update`"
        )


# --- Snapshot regeneration --------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--update" in sys.argv:
        SNAPSHOTS.write_text(json.dumps(_run_all(), indent=1, sort_keys=True))
        print(f"wrote {SNAPSHOTS} ({len(_run_all())} pins)")
    else:
        print("use --update to regenerate")
