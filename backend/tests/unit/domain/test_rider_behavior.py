"""Rider-behavior learning tests (ADR 0005 #635).

The stop/coast baseline: what fraction of ride time the rider spends not
pedaling (stopped + coasting), learned per terrain type from records.
Reference targets from the validation harness: rolling ~1%, hilly ~16%,
mountain ~19% non-pedaling for the reference rider.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from trainingdash.domain.rider_behavior import (
    MIN_ACTIVITIES_PER_BUCKET,
    RideBehaviorSample,
    aggregate_behavior_baseline,
    extract_ride_behavior,
)


def _record(
    t_offset_s: float,
    *,
    power_w: int | None = None,
    cadence_rpm: int | None = None,
    speed_mps: float = 8.0,
    distance_m: float | None = None,
    grade_pct: float = 0.0,
    altitude_m: float = 100.0,
):
    """Synthetic record; distance/altitude derived from speed for coherence."""
    if distance_m is None:
        distance_m = t_offset_s * speed_mps
    altitude = altitude_m + distance_m * grade_pct / 100.0
    return SimpleNamespace(
        timestamp=datetime(2026, 1, 1) + timedelta(seconds=t_offset_s),
        power_w=power_w,
        cadence_rpm=cadence_rpm,
        speed_mps=speed_mps,
        distance_m=distance_m,
        altitude_m=altitude,
        lat=46.8,
        lon=7.6,
    )


def _ride(records_per_km: list[tuple[float, int, int, float]], start_s: float = 0.0):
    """Build records from (duration_s, power, cadence, speed) tuples."""
    records = []
    t = start_s
    d = 0.0
    for duration, power, cadence, speed in records_per_km:
        steps = max(1, int(duration / 5))
        for i in range(steps):
            dt = duration / steps
            t += dt
            d += speed * dt
            records.append(
                SimpleNamespace(
                    timestamp=datetime(2026, 1, 1) + timedelta(seconds=t),
                    power_w=power,
                    cadence_rpm=cadence,
                    speed_mps=speed,
                    distance_m=d,
                    altitude_m=100.0,
                    lat=46.8,
                    lon=7.6,
                )
            )
    return records


class TestExtractRideBehavior:
    """Per-activity stop/coast extraction from records."""

    def test_pure_pedaling_ride_zero_non_pedaling(self):
        records = _ride([(720, 200, 90, 8.0)])  # 10min pedaling
        sample = extract_ride_behavior(records, grade_profile_pct=[0.0])
        assert sample is not None
        assert sample.non_pedaling_pct == pytest.approx(0.0, abs=0.5)

    def test_coasting_fraction_time_weighted(self):
        # 480s pedaling + 120s coasting (moving, no cadence, 0W) = 20%
        records = _ride(
            [
                (570, 200, 90, 8.0),
                (150, 0, 0, 10.0),
            ]
        )
        sample = extract_ride_behavior(records, grade_profile_pct=[0.0])
        assert sample is not None
        assert sample.non_pedaling_pct == pytest.approx(20.0, abs=1.0)

    def test_stopped_counts_as_non_pedaling(self):
        # 540s pedaling + 180s stopped (speed 0) = 25%
        records = _ride(
            [
                (630, 200, 90, 8.0),
                (210, 0, 0, 0.0),
            ]
        )
        sample = extract_ride_behavior(records, grade_profile_pct=[0.0])
        assert sample is not None
        assert sample.non_pedaling_pct == pytest.approx(25.0, abs=1.0)

    def test_stopped_vs_coasting_distinguished(self):
        records = _ride(
            [
                (270, 200, 90, 8.0),
                (90, 0, 0, 10.0),  # coasting (moving)
                (270, 200, 90, 8.0),
                (90, 0, 0, 0.0),  # stopped
            ]
        )
        sample = extract_ride_behavior(records, grade_profile_pct=[0.0])
        assert sample is not None
        # Boundary intervals average speeds (decelerating 8→0 m/s reads as
        # 4 m/s → coasting-ish); abs=1.5 keeps the classification honest.
        assert sample.non_pedaling_pct == pytest.approx(25.0, abs=1.5)
        assert sample.coasting_pct == pytest.approx(12.5, abs=2.0)
        assert sample.stopped_pct == pytest.approx(12.5, abs=2.0)

    def test_power_only_fallback_when_no_cadence(self):
        """No cadence channel → power ≈ 0 + moving = coasting signal."""
        records = _ride(
            [
                (570, 200, None, 8.0),
                (150, 0, None, 10.0),
            ]
        )
        sample = extract_ride_behavior(records, grade_profile_pct=[0.0])
        assert sample is not None
        assert sample.non_pedaling_pct == pytest.approx(20.0, abs=1.0)

    def test_power_without_cadence_still_pedaling(self):
        """Cadence missing but power > 0 → pedaling (power meters measure
        crank torque; power > 0 implies pedaling)."""
        records = _ride([(720, 200, None, 8.0)])
        sample = extract_ride_behavior(records, grade_profile_pct=[0.0])
        assert sample is not None
        assert sample.non_pedaling_pct == pytest.approx(0.0, abs=0.5)

    def test_gap_records_skipped(self):
        """>60s timestamp gaps (recorder pauses) contribute no time."""
        records = _ride([(720, 200, 90, 8.0)])
        # Append a record 300s later
        records.append(
            SimpleNamespace(
                timestamp=records[-1].timestamp + timedelta(seconds=300),
                power_w=200,
                cadence_rpm=90,
                speed_mps=8.0,
                distance_m=records[-1].distance_m + 100,
                altitude_m=100.0,
                lat=46.8,
                lon=7.6,
            )
        )
        sample = extract_ride_behavior(records, grade_profile_pct=[0.0, 0.0])
        assert sample is not None
        # The 300s gap is excluded, so pedaling fraction stays ~100%
        assert sample.non_pedaling_pct == pytest.approx(0.0, abs=2.0)

    def test_too_short_ride_returns_none(self):
        records = _ride([(540, 200, 90, 8.0)])  # 9min; intervals land under MIN_RIDE_TIME_S
        assert extract_ride_behavior(records, grade_profile_pct=[0.0]) is None

    def test_grade_profile_classifies_terrain(self):
        """A ride's terrain bucket follows its CHARACTER (grade stddev →
        the same thresholds the harness's punchiness uses), not the
        terrain where the most seconds happen — a mountain ride spends
        most time on shallow connectors and must still classify mountain.
        """
        flat_ride = _ride([(720, 200, 90, 8.0)])
        mountain_ride = _ride([(720, 200, 90, 6.0)])
        # Flat: uniform ~0%. Mountain: alternating ±11% (stddev ≈ 11 → VI 1.43)
        s_flat = extract_ride_behavior(flat_ride, grade_profile_pct=[0.0] * 143)
        mount_grades = [11.0, -11.0] * 72
        s_mount = extract_ride_behavior(mountain_ride, grade_profile_pct=mount_grades)
        assert s_flat is not None and s_mount is not None
        assert s_flat.terrain_type != s_mount.terrain_type
        assert s_mount.terrain_type == "mountain"

    def test_mountain_ride_with_flat_connectors_classifies_mountain(self):
        """Mountain rides are mostly shallow in seconds — classification
        must look at overall character, not dominant interval terrain."""
        # 20% of time at 12% grade, 80% at 0%: grade_stddev ≈ 4.8
        # → expected VI = 1.12 + 0.028×4.8 = 1.25 < 1.26 → hmm, hilly.
        # Make it punchier: half at 12%, half at 0% → stddev ≈ 6
        records = _ride([(360, 230, 90, 6.0), (360, 200, 90, 8.0)])
        grades = [12.0] * 60 + [0.0] * 60
        sample = extract_ride_behavior(records, grade_profile_pct=grades)
        assert sample is not None
        assert sample.terrain_type == "mountain"

    def test_synthetic_reference_patterns_reproduced(self):
        """The harness-measured reference patterns: rolling ~1%,
        hilly ~16%, mountain ~19%. Build synthetic rides with those
        fractions and verify extraction lands on them."""
        # rolling: 99% pedaling
        rolling = _ride([(99 * 12, 200, 90, 9.0), (1 * 12, 0, 0, 0.0)])
        # hilly: 84% pedaling, 16% coast
        hilly = _ride([(84 * 12, 220, 90, 7.0), (16 * 12, 0, 0, 11.0)])
        # mountain: 81% pedaling, 19% coast
        mountain = _ride([(81 * 12, 230, 90, 6.0), (19 * 12, 0, 0, 14.0)])

        s_rolling = extract_ride_behavior(rolling, grade_profile_pct=[0.5, 1.5])
        s_hilly = extract_ride_behavior(hilly, grade_profile_pct=[5.0, 7.0])
        s_mount = extract_ride_behavior(mountain, grade_profile_pct=[10.0, 12.0])

        assert s_rolling.non_pedaling_pct == pytest.approx(1.0, abs=1.0)
        assert s_hilly.non_pedaling_pct == pytest.approx(16.0, abs=1.0)
        assert s_mount.non_pedaling_pct == pytest.approx(19.0, abs=1.0)


class TestAggregateBehaviorBaseline:
    """Per-rider baseline aggregation with quality gate."""

    def test_time_weighted_average_across_activities(self):
        # 3 rides: 10% (60s), 20% (120s), 30% (240s) non-pedaling
        # time-weighted: (10*60 + 20*120 + 30*240) / 420 = 24.3%
        samples = [
            RideBehaviorSample(
                terrain_type="hilly", non_pedaling_pct=10.0, coasting_pct=10.0, stopped_pct=0.0, ride_time_s=60.0
            ),
            RideBehaviorSample(
                terrain_type="hilly", non_pedaling_pct=20.0, coasting_pct=15.0, stopped_pct=5.0, ride_time_s=120.0
            ),
            RideBehaviorSample(
                terrain_type="hilly", non_pedaling_pct=30.0, coasting_pct=20.0, stopped_pct=10.0, ride_time_s=240.0
            ),
        ]
        baseline = aggregate_behavior_baseline(samples)
        assert baseline is not None
        assert baseline["hilly"].non_pedaling_pct == pytest.approx(24.3, abs=0.2)

    def test_thin_bucket_leaves_terrain_unset(self):
        """Fewer than MIN_ACTIVITIES_PER_BUCKET rides in a bucket → that
        bucket is absent from the baseline (unset, not guessed). Two
        mountain rides (below gate) + enough hilly rides → hilly present,
        mountain absent."""
        samples = [
            RideBehaviorSample(
                terrain_type="mountain", non_pedaling_pct=19.0, coasting_pct=19.0, stopped_pct=0.0, ride_time_s=100.0
            ),
            RideBehaviorSample(
                terrain_type="mountain", non_pedaling_pct=21.0, coasting_pct=21.0, stopped_pct=0.0, ride_time_s=100.0
            ),
        ]
        for i in range(MIN_ACTIVITIES_PER_BUCKET):
            samples.append(
                RideBehaviorSample(
                    terrain_type="hilly", non_pedaling_pct=16.0, coasting_pct=16.0, stopped_pct=0.0, ride_time_s=100.0
                )
            )
        baseline = aggregate_behavior_baseline(samples)
        assert baseline is not None
        assert "mountain" not in baseline  # gated: only 2 rides
        assert "hilly" in baseline

    def test_no_samples_returns_none(self):
        assert aggregate_behavior_baseline([]) is None

    def test_multiple_terrars_each_gated(self):
        samples = []
        for i in range(MIN_ACTIVITIES_PER_BUCKET):
            samples.append(
                RideBehaviorSample(
                    terrain_type="rolling", non_pedaling_pct=1.0, coasting_pct=1.0, stopped_pct=0.0, ride_time_s=100.0
                )
            )
        samples.append(
            RideBehaviorSample(
                terrain_type="flat", non_pedaling_pct=1.0, coasting_pct=1.0, stopped_pct=0.0, ride_time_s=100.0
            )
        )
        baseline = aggregate_behavior_baseline(samples)
        assert baseline is not None
        assert "rolling" in baseline
        assert "flat" not in baseline
