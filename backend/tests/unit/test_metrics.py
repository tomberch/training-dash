"""Unit tests for training metrics computation functions."""

import pytest
from trainingdash.domain.metrics import (
    compute_normalized_power,
    compute_intensity_factor,
    compute_tss,
    compute_zone_times,
    compute_average_power,
    compute_max_power,
)


class TestNormalizedPower:
    """Tests for compute_normalized_power."""

    def test_empty_array_returns_none(self):
        assert compute_normalized_power([]) is None

    def test_all_none_values_returns_none(self):
        assert compute_normalized_power([None, None, None]) is None

    def test_constant_power_equals_that_power(self):
        """NP of constant power should equal that power."""
        # 60 samples at 200W (1 minute at 1Hz)
        power = [200] * 60
        np = compute_normalized_power(power, sample_rate_hz=1.0)
        assert np == 200.0

    def test_variable_power_higher_than_average(self):
        """NP should be higher than average for variable power due to 4th power weighting."""
        # Longer intervals: 30 seconds at 100W, 30 seconds at 300W
        # This creates variability that the rolling average won't smooth out
        power = [100] * 30 + [300] * 30 + [100] * 30 + [300] * 30  # 120 samples
        np = compute_normalized_power(power, sample_rate_hz=1.0)
        avg = sum(power) / len(power)
        assert np > avg  # NP penalizes variability

    def test_short_array_returns_average(self):
        """Arrays shorter than 30 samples should return average power."""
        power = [100, 200, 300]  # Only 3 samples
        np = compute_normalized_power(power, sample_rate_hz=1.0)
        assert np == 200.0  # Simple average

    def test_filters_none_values(self):
        """None values should be filtered out."""
        power = [200, None, 200, None, 200] * 12  # 60 samples with Nones
        np = compute_normalized_power(power, sample_rate_hz=1.0)
        # Should compute NP from the 36 valid 200W samples
        assert np is not None

    def test_filters_negative_values(self):
        """Negative values should be filtered out."""
        power = [200, -1, 200] * 20
        np = compute_normalized_power(power, sample_rate_hz=1.0)
        assert np is not None

    def test_sample_rate_affects_window(self):
        """Higher sample rate should use more samples for 30s window."""
        # 120 samples at 2Hz = 60 seconds of data
        power = [200] * 120
        np = compute_normalized_power(power, sample_rate_hz=2.0)
        assert np == 200.0

    def test_golden_value_steady_state(self):
        """Golden test: 1 hour at 200W should give NP of 200."""
        power = [200] * 3600  # 1 hour at 1Hz
        np = compute_normalized_power(power, sample_rate_hz=1.0)
        assert np == 200.0

    def test_golden_value_intervals(self):
        """Golden test: intervals produce higher NP than average."""
        # 5 min at 300W, 5 min at 100W, repeated 3 times = 30 min
        interval_high = [300] * 300  # 5 min at 300W
        interval_low = [100] * 300   # 5 min at 100W
        power = (interval_high + interval_low) * 3
        
        np = compute_normalized_power(power, sample_rate_hz=1.0)
        avg = sum(power) / len(power)  # 200W average
        
        # NP should be significantly higher due to high-intensity intervals
        assert np > avg
        assert np > 220  # Should be well above average


class TestIntensityFactor:
    """Tests for compute_intensity_factor."""

    def test_np_equals_ftp_gives_if_of_one(self):
        """IF should be 1.0 when NP equals FTP."""
        assert compute_intensity_factor(250.0, 250) == 1.0

    def test_np_below_ftp(self):
        """IF below 1.0 for endurance ride."""
        if_value = compute_intensity_factor(175.0, 250)
        assert if_value == 0.7

    def test_np_above_ftp(self):
        """IF above 1.0 for hard effort."""
        if_value = compute_intensity_factor(275.0, 250)
        assert if_value == 1.1

    def test_zero_ftp_returns_none(self):
        """Zero FTP should return None."""
        assert compute_intensity_factor(200.0, 0) is None

    def test_negative_ftp_returns_none(self):
        """Negative FTP should return None."""
        assert compute_intensity_factor(200.0, -100) is None


class TestTSS:
    """Tests for compute_tss."""

    def test_one_hour_at_ftp_gives_100_tss(self):
        """One hour at FTP (IF=1.0) should give TSS of 100."""
        tss = compute_tss(
            duration_seconds=3600,
            np_watts=250.0,
            intensity_factor=1.0,
            ftp_watts=250,
        )
        assert tss == 100.0

    def test_one_hour_at_half_ftp(self):
        """One hour at 50% FTP should give TSS of ~25."""
        tss = compute_tss(
            duration_seconds=3600,
            np_watts=125.0,
            intensity_factor=0.5,
            ftp_watts=250,
        )
        assert tss == 25.0

    def test_two_hours_doubles_tss(self):
        """Double duration should double TSS."""
        tss_1h = compute_tss(3600, 250.0, 1.0, 250)
        tss_2h = compute_tss(7200, 250.0, 1.0, 250)
        assert tss_2h == tss_1h * 2

    def test_zero_duration_returns_none(self):
        assert compute_tss(0, 200.0, 0.8, 250) is None

    def test_zero_ftp_returns_none(self):
        assert compute_tss(3600, 200.0, 0.8, 0) is None

    def test_golden_value_endurance_ride(self):
        """Golden test: 2 hour endurance ride at IF 0.7."""
        # 2 hours, NP=175, IF=0.7, FTP=250
        # TSS = (7200 * 175 * 0.7) / (250 * 3600) * 100 = 98
        tss = compute_tss(7200, 175.0, 0.7, 250)
        assert tss == 98.0

    def test_golden_value_threshold_workout(self):
        """Golden test: 1 hour threshold intervals at IF 0.95."""
        # 1 hour, NP=237.5, IF=0.95, FTP=250
        # TSS = (3600 * 237.5 * 0.95) / (250 * 3600) * 100 = 90.25
        tss = compute_tss(3600, 237.5, 0.95, 250)
        assert tss == 90.2


class TestZoneTimes:
    """Tests for compute_zone_times."""

    @pytest.fixture
    def power_zones(self):
        """Standard Coggan power zones for 200W FTP."""
        return [
            {"zone_number": 1, "min_watts": 0, "max_watts": 110},
            {"zone_number": 2, "min_watts": 110, "max_watts": 150},
            {"zone_number": 3, "min_watts": 150, "max_watts": 180},
            {"zone_number": 4, "min_watts": 180, "max_watts": 210},
            {"zone_number": 5, "min_watts": 210, "max_watts": 240},
            {"zone_number": 6, "min_watts": 240, "max_watts": 300},
            {"zone_number": 7, "min_watts": 300, "max_watts": None},
        ]

    def test_empty_array_returns_empty(self, power_zones):
        result = compute_zone_times([], power_zones)
        assert result == {}

    def test_empty_zones_returns_empty(self):
        result = compute_zone_times([100, 200, 300], [])
        assert result == {}

    def test_all_in_one_zone(self, power_zones):
        """All samples in zone 2 (110-150W)."""
        power = [130] * 60  # 60 seconds at 130W
        result = compute_zone_times(power, power_zones)
        assert result[2] == 60
        assert result[1] == 0
        assert result[3] == 0

    def test_split_between_zones(self, power_zones):
        """30 seconds in zone 2, 30 seconds in zone 4."""
        power = [130] * 30 + [190] * 30
        result = compute_zone_times(power, power_zones)
        assert result[2] == 30
        assert result[4] == 30

    def test_above_max_zone_counts_in_highest(self, power_zones):
        """Power above zone 7 minimum counts in zone 7."""
        power = [400] * 10  # 10 seconds at 400W
        result = compute_zone_times(power, power_zones)
        assert result[7] == 10

    def test_filters_none_values(self, power_zones):
        """None values should not be counted."""
        power = [130, None, 130, None]  # Only 2 valid samples
        result = compute_zone_times(power, power_zones)
        assert result[2] == 2

    def test_sample_rate_affects_seconds(self, power_zones):
        """Higher sample rate means each sample is less time."""
        power = [130] * 120  # 120 samples at 2Hz = 60 seconds
        result = compute_zone_times(power, power_zones, sample_rate_hz=2.0)
        assert result[2] == 60

    def test_hr_zones(self):
        """Test with HR zones using different keys."""
        hr_zones = [
            {"zone_number": 1, "min_bpm": 0, "max_bpm": 130},
            {"zone_number": 2, "min_bpm": 130, "max_bpm": 150},
            {"zone_number": 3, "min_bpm": 150, "max_bpm": 165},
            {"zone_number": 4, "min_bpm": 165, "max_bpm": 175},
            {"zone_number": 5, "min_bpm": 175, "max_bpm": None},
        ]
        hr = [140] * 60  # 60 seconds at 140 bpm
        result = compute_zone_times(
            hr, hr_zones,
            value_key_min="min_bpm",
            value_key_max="max_bpm",
        )
        assert result[2] == 60


class TestAveragePower:
    """Tests for compute_average_power."""

    def test_empty_returns_none(self):
        assert compute_average_power([]) is None

    def test_all_none_returns_none(self):
        assert compute_average_power([None, None]) is None

    def test_simple_average(self):
        assert compute_average_power([100, 200, 300]) == 200.0

    def test_filters_none(self):
        assert compute_average_power([100, None, 300]) == 200.0

    def test_filters_negative(self):
        assert compute_average_power([100, -50, 300]) == 200.0


class TestMaxPower:
    """Tests for compute_max_power."""

    def test_empty_returns_none(self):
        assert compute_max_power([]) is None

    def test_all_none_returns_none(self):
        assert compute_max_power([None, None]) is None

    def test_finds_max(self):
        assert compute_max_power([100, 500, 300]) == 500

    def test_filters_none(self):
        assert compute_max_power([100, None, 300]) == 300

    def test_filters_negative(self):
        assert compute_max_power([100, -999, 300]) == 300
