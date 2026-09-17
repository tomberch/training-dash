"""Tests for the shared windowed max-grade algorithm."""

import pytest

from trainingdash.domain.grade_stats import compute_max_grade_pct


def _climb_records(
    total_m: float,
    step_m: float,
    grade_pct: float,
    start_alt: float = 100.0,
) -> list[tuple[float, float]]:
    """Build ascending (distance, altitude) records at a constant grade."""
    records = []
    dist = 0.0
    alt = start_alt
    n = int(total_m / step_m)
    for _ in range(n + 1):
        records.append((dist, alt))
        dist += step_m
        alt += step_m * grade_pct / 100
    return records


class TestComputeMaxGradePct:
    def test_steady_climb(self):
        records = _climb_records(total_m=1000, step_m=10, grade_pct=8)
        assert compute_max_grade_pct(records) == pytest.approx(8.0)

    def test_variable_grade_takes_steepest_window(self):
        # Gentle 2% for 500m, then steep 12% pitch for 260m, then flat
        records = _climb_records(total_m=500, step_m=10, grade_pct=2)
        alt = records[-1][1]
        dist = records[-1][0]
        for _ in range(26):
            dist += 10
            alt += 1.2
            records.append((dist, alt))
        dist = records[-1][0]
        for _ in range(26):
            dist += 10
            records.append((dist, alt))
        assert compute_max_grade_pct(records) == pytest.approx(12.0)

    def test_noise_spike_suppressed(self):
        # Gentle 2% climb with a +2m jump over 2m — raw-pair grade would be 100%
        records = _climb_records(total_m=1000, step_m=10, grade_pct=2)
        base = [(d, a) for d, a in records if d <= 500]
        rest = [(d + 2, a) for d, a in records if d > 500]
        spike_alt = [a for d, a in records if d == 500][0] + 2
        records = base + [(502, spike_alt)] + rest
        # Max over 200m windows should be ~2%, not 100%
        assert compute_max_grade_pct(records) < 5.0

    def test_fewer_than_min_records_returns_none(self):
        records = _climb_records(total_m=90, step_m=10, grade_pct=8)
        assert len(records) == 10
        assert compute_max_grade_pct(records) is None

    def test_no_full_window_returns_none(self):
        # 11 records but all within <200m
        records = _climb_records(total_m=110, step_m=10, grade_pct=8)
        assert compute_max_grade_pct(records) is None

    def test_descent_only_returns_none(self):
        records = _climb_records(total_m=1000, step_m=10, grade_pct=-5)
        assert compute_max_grade_pct(records) is None

    def test_empty_returns_none(self):
        assert compute_max_grade_pct([]) is None