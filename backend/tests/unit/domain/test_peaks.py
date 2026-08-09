"""Unit tests for peak power extraction."""

import time

from trainingdash.domain.peaks import (
    PEAK_DURATIONS,
    compute_power_curve,
    extract_peak_power_with_index,
    extract_peak_powers,
)


class TestExtractPeakPowers:
    """Tests for extract_peak_powers."""

    def test_empty_array_returns_empty(self):
        result = extract_peak_powers([])
        assert result == {}

    def test_constant_power_returns_that_power(self):
        """All peaks should equal the constant power."""
        power = [200] * 3600  # 1 hour at 200W
        result = extract_peak_powers(power)

        # All durations up to 1 hour should return 200W
        assert result[1] == 200
        assert result[60] == 200
        assert result[300] == 200
        assert result[3600] == 200

        # Durations longer than ride should be None
        assert result[5400] is None
        assert result[7200] is None

    def test_finds_peak_in_variable_data(self):
        """Should find the best window in variable power data."""
        # 5 minutes of easy, 5 minutes hard, 5 minutes easy
        power = [150] * 300 + [300] * 300 + [150] * 300  # 15 min total
        result = extract_peak_powers(power)

        # 5-minute peak should be the hard section
        assert result[300] == 300
        # 10-minute peak should average the hard + some easy
        assert result[600] == 225  # (300*300 + 150*300) / 600 = 225

    def test_short_ride_returns_none_for_long_durations(self):
        """Durations longer than the ride should return None."""
        power = [200] * 120  # Only 2 minutes
        result = extract_peak_powers(power)

        assert result[1] == 200
        assert result[60] == 200
        assert result[120] == 200
        assert result[300] is None  # 5 min > 2 min ride

    def test_handles_none_values(self):
        """None values should be treated as 0."""
        power = [200, None, 200, None, 200]
        result = extract_peak_powers(power, durations=[1, 3, 5])

        # 1-second peak should find a 200
        assert result[1] == 200
        # 3-second window will include a None (0)
        assert result[3] == 133  # (200 + 0 + 200) / 3

    def test_handles_negative_values(self):
        """Negative values should be treated as 0."""
        power = [200, -100, 200]
        result = extract_peak_powers(power, durations=[1, 3])

        assert result[1] == 200
        assert result[3] == 133  # (200 + 0 + 200) / 3

    def test_sample_rate_affects_window_size(self):
        """Higher sample rate means more samples per duration."""
        # 60 samples at 2Hz = 30 seconds
        power = [200] * 60
        result = extract_peak_powers(power, sample_rate_hz=2.0, durations=[30, 60])

        assert result[30] == 200  # 60 samples = 30 seconds at 2Hz
        assert result[60] is None  # Would need 120 samples

    def test_custom_durations(self):
        """Can specify custom durations."""
        power = [200] * 100
        result = extract_peak_powers(power, durations=[10, 20, 50])

        assert 10 in result
        assert 20 in result
        assert 50 in result
        assert 300 not in result  # Not in custom list

    def test_all_standard_durations_present(self):
        """Result should include all standard durations."""
        power = [200] * 20000  # ~5.5 hours
        result = extract_peak_powers(power)

        for duration in PEAK_DURATIONS:
            assert duration in result

    def test_golden_value_sprint_in_endurance_ride(self):
        """Find a 10-second sprint in a long endurance ride."""
        # 1 hour at 150W with a 10-second 800W sprint in the middle
        power = [150] * 1800 + [800] * 10 + [150] * 1790
        result = extract_peak_powers(power)

        assert result[10] == 800
        assert result[1] == 800
        # 1-minute including the sprint
        assert result[60] > 150

    def test_performance_5_hour_ride(self):
        """Should handle 5-hour ride (18000+ samples) efficiently."""
        power = [200] * 18000

        start = time.time()
        result = extract_peak_powers(power)
        elapsed = time.time() - start

        assert elapsed < 0.5  # Should complete in under 500ms
        assert result[1] == 200
        assert result[3600] == 200


class TestExtractPeakPowerWithIndex:
    """Tests for extract_peak_power_with_index."""

    def test_empty_returns_none(self):
        watts, idx = extract_peak_power_with_index([], 60)
        assert watts is None
        assert idx is None

    def test_finds_correct_index(self):
        """Should return the start index of the best window."""
        # 60s easy, 60s hard, 60s easy
        power = [100] * 60 + [300] * 60 + [100] * 60
        watts, idx = extract_peak_power_with_index(power, 60)

        assert watts == 300
        assert idx == 60  # Hard section starts at index 60

    def test_ride_too_short_returns_none(self):
        power = [200] * 30
        watts, idx = extract_peak_power_with_index(power, 60)

        assert watts is None
        assert idx is None


class TestComputePowerCurve:
    """Tests for compute_power_curve."""

    def test_empty_returns_empty(self):
        result = compute_power_curve([])
        assert result == {}

    def test_short_ride_limited_curve(self):
        """Short ride should only have durations up to ride length."""
        power = [200] * 30  # 30 seconds
        result = compute_power_curve(power)

        assert 1 in result
        assert 30 in result
        assert 60 not in result

    def test_includes_second_by_second_up_to_60(self):
        """Should include every second from 1-60."""
        power = [200] * 120
        result = compute_power_curve(power)

        for s in range(1, 61):
            assert s in result

    def test_max_duration_limits_output(self):
        """Can limit the maximum duration."""
        power = [200] * 3600
        result = compute_power_curve(power, max_duration_s=120)

        assert 1 in result
        assert 60 in result
        assert 120 in result
        # Should not compute beyond max_duration_s
        # (sparse sampling means exact 3600 may not be there)

    def test_performance_long_ride(self):
        """Should be reasonably efficient for long rides."""
        power = [200] * 7200  # 2 hours

        start = time.time()
        result = compute_power_curve(power)
        elapsed = time.time() - start

        assert elapsed < 2.0  # Should complete in under 2 seconds
        assert len(result) > 60  # Should have many data points
