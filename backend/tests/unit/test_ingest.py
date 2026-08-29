"""Unit tests for ingest module functions."""

import sys
from pathlib import Path

# Add fixtures directory to path for FIT generator
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))

from trainingdash.ingest import _compute_extended_metrics, _compute_moving_time


class TestComputeMovingTime:
    """Tests for _compute_moving_time function.

    The function computes moving time from timestamp intervals between records,
    not by counting records. This handles "smart recording" where intervals vary.
    """

    def test_empty_records_returns_zero(self):
        """Empty records list returns 0."""
        assert _compute_moving_time([]) == 0

    def test_single_moving_record_returns_one(self):
        """Single moving record returns 1 (no interval to compute)."""
        from datetime import datetime

        records = [{"speed_mps": 5.0, "timestamp": datetime(2024, 1, 1, 10, 0, 0)}]
        assert _compute_moving_time(records) == 1

    def test_single_stopped_record_returns_zero(self):
        """Single stopped record returns 0."""
        from datetime import datetime

        records = [{"speed_mps": 0.3, "timestamp": datetime(2024, 1, 1, 10, 0, 0)}]
        assert _compute_moving_time(records) == 0

    def test_one_second_intervals_moving(self):
        """1-second intervals with all moving records sums correctly."""
        from datetime import datetime

        records = [
            {"speed_mps": 5.0, "timestamp": datetime(2024, 1, 1, 10, 0, 0)},
            {"speed_mps": 6.0, "timestamp": datetime(2024, 1, 1, 10, 0, 1)},
            {"speed_mps": 7.0, "timestamp": datetime(2024, 1, 1, 10, 0, 2)},
            {"speed_mps": 8.0, "timestamp": datetime(2024, 1, 1, 10, 0, 3)},
        ]
        # Intervals: 1s (moving) + 1s (moving) + 1s (moving) = 3s
        assert _compute_moving_time(records) == 3

    def test_variable_intervals_smart_recording(self):
        """Variable intervals (smart recording) sums actual time deltas."""
        from datetime import datetime

        records = [
            {"speed_mps": 5.0, "timestamp": datetime(2024, 1, 1, 10, 0, 0)},
            {"speed_mps": 6.0, "timestamp": datetime(2024, 1, 1, 10, 0, 5)},  # 5s gap
            {"speed_mps": 7.0, "timestamp": datetime(2024, 1, 1, 10, 0, 8)},  # 3s gap
            {"speed_mps": 8.0, "timestamp": datetime(2024, 1, 1, 10, 0, 18)},  # 10s gap
        ]
        # All moving: 5 + 3 + 10 = 18s
        assert _compute_moving_time(records) == 18

    def test_all_stopped_records(self):
        """All records below speed threshold return 0."""
        from datetime import datetime

        records = [
            {"speed_mps": 0.0, "timestamp": datetime(2024, 1, 1, 10, 0, 0)},
            {"speed_mps": 0.3, "timestamp": datetime(2024, 1, 1, 10, 0, 1)},
            {"speed_mps": 0.5, "timestamp": datetime(2024, 1, 1, 10, 0, 2)},  # Exactly at threshold, not counted
        ]
        assert _compute_moving_time(records) == 0

    def test_mixed_moving_and_stopped(self):
        """Mix of moving and stopped records counts only moving intervals."""
        from datetime import datetime

        records = [
            {"speed_mps": 0.0, "timestamp": datetime(2024, 1, 1, 10, 0, 0)},  # stopped
            {"speed_mps": 5.0, "timestamp": datetime(2024, 1, 1, 10, 0, 5)},  # moving, 5s interval
            {"speed_mps": 0.3, "timestamp": datetime(2024, 1, 1, 10, 0, 10)},  # stopped
            {"speed_mps": 8.0, "timestamp": datetime(2024, 1, 1, 10, 0, 15)},  # moving, 5s interval
            {"speed_mps": 0.0, "timestamp": datetime(2024, 1, 1, 10, 0, 20)},  # stopped
            {"speed_mps": 6.0, "timestamp": datetime(2024, 1, 1, 10, 0, 25)},  # moving, 5s interval
        ]
        # Moving intervals: 5 + 5 + 5 = 15s
        assert _compute_moving_time(records) == 15

    def test_long_gap_capped_at_30_seconds(self):
        """Long gaps (pauses) are capped at 30 seconds."""
        from datetime import datetime

        records = [
            {"speed_mps": 5.0, "timestamp": datetime(2024, 1, 1, 10, 0, 0)},
            {"speed_mps": 6.0, "timestamp": datetime(2024, 1, 1, 10, 2, 0)},  # 120s gap, capped to 30s
        ]
        assert _compute_moving_time(records) == 30

    def test_none_speed_treated_as_stopped(self):
        """Records with None speed are treated as stopped."""
        from datetime import datetime

        records = [
            {"speed_mps": None, "timestamp": datetime(2024, 1, 1, 10, 0, 0)},
            {"speed_mps": 5.0, "timestamp": datetime(2024, 1, 1, 10, 0, 5)},
            {"speed_mps": None, "timestamp": datetime(2024, 1, 1, 10, 0, 10)},
        ]
        # Only the second record is moving: 5s interval
        assert _compute_moving_time(records) == 5

    def test_missing_speed_key_treated_as_stopped(self):
        """Records missing speed_mps key are treated as stopped."""
        from datetime import datetime

        records = [
            {"timestamp": datetime(2024, 1, 1, 10, 0, 0)},
            {"speed_mps": 5.0, "timestamp": datetime(2024, 1, 1, 10, 0, 5)},
            {"other_field": 10, "timestamp": datetime(2024, 1, 1, 10, 0, 10)},
        ]
        # Only the second record is moving: 5s interval
        assert _compute_moving_time(records) == 5

    def test_missing_timestamps_falls_back_to_one_second(self):
        """Records without timestamps fall back to counting as 1 second each."""
        records = [
            {"speed_mps": 5.0},
            {"speed_mps": 6.0},
            {"speed_mps": 7.0},
        ]
        # No timestamps, falls back to 1s per moving record: 2s (first record has no interval)
        assert _compute_moving_time(records) == 2


class TestComputeExtendedMetricsCadence:
    """Tests for cadence computation in _compute_extended_metrics."""

    def test_no_cadence_data_returns_none(self):
        """No cadence records returns None for all cadence metrics."""
        records = [{"speed_mps": 5.0}, {"speed_mps": 6.0}]
        result = _compute_extended_metrics(records, 1000.0, 100)

        assert result["avg_cadence_rpm"] is None
        assert result["avg_cadence_pedaling_rpm"] is None
        assert result["max_cadence_rpm"] is None

    def test_all_pedaling_cadence(self):
        """All positive cadence values - avg equals pedaling avg."""
        records = [
            {"cadence_rpm": 80},
            {"cadence_rpm": 90},
            {"cadence_rpm": 100},
        ]
        result = _compute_extended_metrics(records, 1000.0, 100)

        assert result["avg_cadence_rpm"] == 90
        assert result["avg_cadence_pedaling_rpm"] == 90
        assert result["max_cadence_rpm"] == 100

    def test_mixed_pedaling_and_coasting(self):
        """Mix of pedaling and coasting - avg includes zeros, pedaling avg excludes."""
        records = [
            {"cadence_rpm": 0},  # coasting
            {"cadence_rpm": 80},  # pedaling
            {"cadence_rpm": 0},  # coasting
            {"cadence_rpm": 100},  # pedaling
            {"cadence_rpm": 0},  # coasting
        ]
        result = _compute_extended_metrics(records, 1000.0, 100)

        # avg_cadence_rpm: (0 + 80 + 0 + 100 + 0) / 5 = 36
        assert result["avg_cadence_rpm"] == 36
        # avg_cadence_pedaling_rpm: (80 + 100) / 2 = 90
        assert result["avg_cadence_pedaling_rpm"] == 90
        assert result["max_cadence_rpm"] == 100

    def test_all_coasting_no_pedaling_avg(self):
        """All zero cadence - no pedaling avg but avg is 0."""
        records = [
            {"cadence_rpm": 0},
            {"cadence_rpm": 0},
            {"cadence_rpm": 0},
        ]
        result = _compute_extended_metrics(records, 1000.0, 100)

        assert result["avg_cadence_rpm"] == 0
        assert result["avg_cadence_pedaling_rpm"] is None  # No pedaling samples
        assert result["max_cadence_rpm"] == 0

    def test_realistic_ride_cadence_distribution(self):
        """Realistic distribution mimicking a ride with descents."""
        # Simulate: 70% pedaling at ~85 rpm, 30% coasting (0 rpm)
        pedaling_records = [{"cadence_rpm": 85} for _ in range(70)]
        coasting_records = [{"cadence_rpm": 0} for _ in range(30)]
        # Add some high cadence sprints
        sprint_records = [{"cadence_rpm": 110}]

        records = pedaling_records + coasting_records + sprint_records
        result = _compute_extended_metrics(records, 50000.0, 7200)

        # avg_cadence_rpm: (70*85 + 30*0 + 1*110) / 101 ≈ 60
        assert 58 <= result["avg_cadence_rpm"] <= 62
        # avg_cadence_pedaling_rpm: (70*85 + 1*110) / 71 ≈ 85.4
        assert 85 <= result["avg_cadence_pedaling_rpm"] <= 86
        assert result["max_cadence_rpm"] == 110


class TestComputeExtendedMetricsMovingSpeed:
    """Tests for moving speed computation in _compute_extended_metrics."""

    def test_moving_speed_computed_from_distance_and_time(self):
        """Moving speed equals distance / moving_time."""
        records = [{"speed_mps": 5.0}]  # Need at least one record
        result = _compute_extended_metrics(records, 10000.0, 1000)  # 10km in 1000s

        assert result["avg_speed_moving_mps"] == 10.0  # 10000 / 1000

    def test_zero_moving_time_returns_none(self):
        """Zero moving time returns None for moving speed."""
        records = [{"speed_mps": 5.0}]
        result = _compute_extended_metrics(records, 10000.0, 0)

        assert result["avg_speed_moving_mps"] is None

    def test_zero_distance_returns_none(self):
        """Zero distance returns None for moving speed."""
        records = [{"speed_mps": 5.0}]
        result = _compute_extended_metrics(records, 0.0, 1000)

        assert result["avg_speed_moving_mps"] is None


class TestComputeExtendedMetricsTemperature:
    """Tests for temperature computation in _compute_extended_metrics."""

    def test_no_temperature_data(self):
        """No temperature records returns None for all temp metrics."""
        records = [{"speed_mps": 5.0}]
        result = _compute_extended_metrics(records, 1000.0, 100)

        assert result["avg_temperature_c"] is None
        assert result["min_temperature_c"] is None
        assert result["max_temperature_c"] is None

    def test_temperature_stats(self):
        """Temperature min/max/avg computed correctly."""
        records = [
            {"temperature_c": 20},
            {"temperature_c": 25},
            {"temperature_c": 22},
            {"temperature_c": 18},
        ]
        result = _compute_extended_metrics(records, 1000.0, 100)

        assert result["avg_temperature_c"] == 21.2  # (20+25+22+18) / 4
        assert result["min_temperature_c"] == 18
        assert result["max_temperature_c"] == 25


class TestComputeExtendedMetricsAltitude:
    """Tests for altitude/elevation computation in _compute_extended_metrics."""

    def test_no_altitude_data(self):
        """No altitude records returns None for altitude metrics."""
        records = [{"speed_mps": 5.0}]
        result = _compute_extended_metrics(records, 1000.0, 100)

        assert result["min_altitude_m"] is None
        assert result["max_altitude_m"] is None
        assert result["elevation_loss_m"] is None

    def test_altitude_min_max(self):
        """Altitude min/max computed correctly."""
        records = [
            {"altitude_m": 500},
            {"altitude_m": 550},
            {"altitude_m": 480},
            {"altitude_m": 520},
        ]
        result = _compute_extended_metrics(records, 1000.0, 100)

        assert result["min_altitude_m"] == 480
        assert result["max_altitude_m"] == 550

    def test_elevation_loss_computed(self):
        """Elevation loss computed from altitude decreases."""
        # Simulate a longer descent with more data points to avoid smoothing artifacts
        # Climb from 500m to 600m, then descend to 450m
        records = []
        # Climb: 500 -> 600 (20 points)
        for i in range(20):
            records.append({"altitude_m": 500 + i * 5})
        # Descent: 600 -> 450 (30 points)
        for i in range(30):
            records.append({"altitude_m": 600 - i * 5})

        result = _compute_extended_metrics(records, 5000.0, 500)

        # Elevation loss should be approximately 150m (600 - 450)
        # Allow some tolerance due to smoothing
        assert result["elevation_loss_m"] is not None
        assert 130 <= result["elevation_loss_m"] <= 170


class TestComputeExtendedMetricsPower:
    """Tests for max power computation in _compute_extended_metrics."""

    def test_no_power_data(self):
        """No power records returns None for max power."""
        records = [{"speed_mps": 5.0}]
        result = _compute_extended_metrics(records, 1000.0, 100)

        assert result["max_power_w"] is None

    def test_max_power_computed(self):
        """Max power is the highest power value."""
        records = [
            {"power_w": 200},
            {"power_w": 350},
            {"power_w": 280},
            {"power_w": 150},
        ]
        result = _compute_extended_metrics(records, 1000.0, 100)

        assert result["max_power_w"] == 350

    def test_zero_power_ignored(self):
        """Zero power values are ignored for max."""
        records = [
            {"power_w": 0},
            {"power_w": 200},
            {"power_w": 0},
        ]
        result = _compute_extended_metrics(records, 1000.0, 100)

        assert result["max_power_w"] == 200


class TestParseRecordsIntegration:
    """Integration tests for parse_records with real FIT data."""

    def test_moving_time_computed_when_fit_lacks_total_moving_time(self):
        """
        When FIT file lacks total_moving_time, moving_time is computed from records.

        This tests the fix for the bug where we used timer_time as fallback,
        which included time when the rider was stopped but timer was running.
        """
        from generate_fit import make_test_fit

        # Create a FIT file with speed data
        fit_bytes = make_test_fit(num_records=100)

        from trainingdash.ingest import parse_records

        result = parse_records(fit_bytes)

        # Verify moving_time is computed
        # (the test FIT generator creates records with speed, so all should be "moving")
        assert result["moving_time_s"] is not None
        assert result["moving_time_s"] > 0

    def test_cadence_metrics_computed_correctly(self):
        """
        Cadence metrics: avg includes zeros, pedaling avg excludes zeros.

        This tests the fix for the bug where both metrics showed the same value.
        """
        from generate_fit import make_test_fit

        # Create a FIT file with cadence data
        fit_bytes = make_test_fit(num_records=100)

        from trainingdash.ingest import parse_records

        result = parse_records(fit_bytes)

        # Verify cadence metrics are present
        assert result["avg_cadence_rpm"] is not None
        assert result["avg_cadence_pedaling_rpm"] is not None
        assert result["max_cadence_rpm"] is not None

        # max_cadence should be >= pedaling_avg
        assert result["max_cadence_rpm"] >= result["avg_cadence_pedaling_rpm"]

    def test_max_cadence_captured(self):
        """max_cadence_rpm captures the highest cadence value."""
        from generate_fit import make_test_fit

        fit_bytes = make_test_fit(num_records=100)

        from trainingdash.ingest import parse_records

        result = parse_records(fit_bytes)

        # Verify max cadence is in reasonable range for cycling
        # make_test_fit uses cadence = 80 + (i % 20), so max should be 99
        assert result["max_cadence_rpm"] is not None
        assert 80 <= result["max_cadence_rpm"] <= 100
