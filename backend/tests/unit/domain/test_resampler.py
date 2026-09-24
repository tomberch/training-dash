from trainingdash.domain.resampler import (
    compute_moving_time,
    compute_time_gap_series,
    compute_time_gap_series_dual,
    resample_by_distance,
)


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


class TestMovingTime:
    def test_compute_moving_time_all_moving(self):
        """All records have speed above threshold → moving time equals elapsed time."""
        records = [{"distance_m": i * 100, "timestamp_s": float(i * 10), "speed_mps": 10.0} for i in range(10)]
        result = compute_moving_time(records)
        assert len(result) == 10
        # First record has 0 moving time, subsequent ones accumulate
        assert result[0]["moving_time_s"] == 0.0
        for i in range(1, 10):
            # Each record adds 10s of moving time (since speed > threshold)
            assert abs(result[i]["moving_time_s"] - (i * 10)) < 0.01

    def test_compute_moving_time_with_stop(self):
        """Stop in the middle should not accumulate moving time."""
        records = [
            {"distance_m": 0, "timestamp_s": 0.0, "speed_mps": 10.0},
            {"distance_m": 100, "timestamp_s": 10.0, "speed_mps": 10.0},  # moving
            {"distance_m": 100, "timestamp_s": 20.0, "speed_mps": 0.0},  # stopped
            {"distance_m": 100, "timestamp_s": 30.0, "speed_mps": 0.0},  # still stopped
            {"distance_m": 200, "timestamp_s": 40.0, "speed_mps": 10.0},  # moving again
        ]
        result = compute_moving_time(records)
        # Record 0: moving_time = 0 (first record)
        # Record 1: moving_time = 10 (speed 10 > 0.5)
        # Record 2: moving_time = 10 (speed 0 <= 0.5, not moving)
        # Record 3: moving_time = 10 (speed 0 <= 0.5, not moving)
        # Record 4: moving_time = 20 (speed 10 > 0.5)
        assert result[0]["moving_time_s"] == 0.0
        assert result[1]["moving_time_s"] == 10.0
        assert result[2]["moving_time_s"] == 10.0  # stopped
        assert result[3]["moving_time_s"] == 10.0  # still stopped
        assert result[4]["moving_time_s"] == 20.0  # moving again

    def test_compute_moving_time_empty(self):
        """Empty input returns empty output."""
        assert compute_moving_time([]) == []

    def test_compute_moving_time_caps_intervals(self):
        """Long time gaps should be capped at 30s to avoid counting pauses."""
        records = [
            {"distance_m": 0, "timestamp_s": 0.0, "speed_mps": 10.0},
            {"distance_m": 100, "timestamp_s": 10.0, "speed_mps": 10.0},  # +10s
            {"distance_m": 200, "timestamp_s": 110.0, "speed_mps": 10.0},  # +100s gap, capped to 30s
        ]
        result = compute_moving_time(records)
        assert result[0]["moving_time_s"] == 0.0
        assert result[1]["moving_time_s"] == 10.0
        assert result[2]["moving_time_s"] == 40.0  # 10 + 30 (capped), not 10 + 100


class TestDualGapSeries:
    def test_dual_gap_series_with_stop(self):
        """Activity A has a stop, activity B doesn't — moving gap should be smaller than elapsed gap."""
        # Activity A: 100m total, with a 60s stop at 50m
        records_a = [
            {"distance_m": 0, "timestamp_s": 0.0, "speed_mps": 10.0},
            {"distance_m": 50, "timestamp_s": 5.0, "speed_mps": 10.0},
            {"distance_m": 50, "timestamp_s": 65.0, "speed_mps": 0.0},  # 60s stop (speed 0)
            {"distance_m": 100, "timestamp_s": 70.0, "speed_mps": 10.0},
        ]
        # Activity B: 100m in 10s, no stop
        records_b = [
            {"distance_m": 0, "timestamp_s": 0.0, "speed_mps": 10.0},
            {"distance_m": 50, "timestamp_s": 5.0, "speed_mps": 10.0},
            {"distance_m": 100, "timestamp_s": 10.0, "speed_mps": 10.0},
        ]

        input_a = compute_moving_time(records_a)
        input_b = compute_moving_time(records_b)
        elapsed, moving = compute_time_gap_series_dual(input_a, input_b)

        # Should have 3 buckets: 0m, 50m, 100m
        assert len(elapsed) == 3

        # At 0m: both start at 0, gap = 0
        assert elapsed[0]["gap_s"] == 0

        # At 100m:
        # Elapsed: A took 70s, B took 10s → elapsed gap = 60s (A is 60s behind)
        assert abs(elapsed[2]["gap_s"] - 60.0) < 1

        # Moving time: A's moving time = 5s (first segment) + 5s (last segment) = 10s
        # B's moving time = 5s + 5s = 10s
        # So moving gap at 100m should be ~0
        assert abs(moving[2]["gap_s"]) < 1

    def test_dual_gap_series_identical_returns_zero_for_both(self):
        """Identical rides should have zero gap in both series."""
        records = [{"distance_m": i * 10, "timestamp_s": float(i), "speed_mps": 10.0} for i in range(20)]
        input_records = compute_moving_time(records)
        elapsed, moving = compute_time_gap_series_dual(input_records, input_records)

        for g in elapsed:
            assert abs(g["gap_s"]) < 0.01
        for g in moving:
            assert abs(g["gap_s"]) < 0.01
