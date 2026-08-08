import pytest
from trainingdash.domain.resampler import compute_time_gap_series, resample_by_distance


class TestResampler:
    def test_resample_uniform_buckets(self):
        records = [{"distance_m": i * 10, "timestamp_s": float(i)} for i in range(20)]
        result = resample_by_distance(records)
        assert len(result) > 0
        for i, r in enumerate(result):
            assert abs(r["distance_m"] - i * 50) < 0.01

    def test_resample_empty(self):
        assert resample_by_distance([]) == []

    def test_resample_zero_distance(self):
        records = [{"distance_m": 0, "timestamp_s": 0.0}]
        result = resample_by_distance(records)
        assert len(result) == 1

    def test_time_gap_series_truncates_to_shorter(self):
        short = [{"distance_m": i * 10, "timestamp_s": float(i)} for i in range(10)]  # 0-90m
        long = [{"distance_m": i * 10, "timestamp_s": float(i)} for i in range(20)]  # 0-190m
        series = compute_time_gap_series(short, long)
        # Short has 90m → 2 buckets (0, 50). Long has 190m → 4 buckets.
        # Series should truncate to 2 (shorter)
        assert len(series) == 2
        assert series[0]["distance_m"] == 0
        assert series[1]["distance_m"] == 50

    def test_time_gap_identical_rides_zero_gap(self):
        records = [{"distance_m": i * 10, "timestamp_s": float(i)} for i in range(20)]
        series = compute_time_gap_series(records, records)
        for g in series:
            assert abs(g["gap_s"]) < 0.01

    def test_time_gap_signs(self):
        # Ride A is slower (more time per distance)
        slow = [{"distance_m": i * 10, "timestamp_s": float(i * 2)} for i in range(20)]
        # Ride B is faster (less time per distance)
        fast = [{"distance_m": i * 10, "timestamp_s": float(i)} for i in range(20)]
        series = compute_time_gap_series(slow, fast)
        # gap = A - B → positive (A is slower), except at 0m where both start at 0
        assert series[0]["gap_s"] == 0
        assert all(g["gap_s"] > 0 for g in series[1:])