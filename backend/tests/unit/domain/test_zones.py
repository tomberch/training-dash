"""Unit tests for zone computation functions."""

import pytest

from trainingdash.domain.zones import (
    compute_power_zones,
    compute_hr_zones,
    get_zone_for_power,
    get_zone_for_hr,
    compute_zone_times,
    DEFAULT_POWER_ZONES,
    DEFAULT_HR_ZONES,
)


class TestComputePowerZones:
    """Tests for compute_power_zones function."""

    def test_computes_default_zones_from_ftp(self):
        """Should compute 7 Coggan zones from FTP."""
        zones = compute_power_zones(200)
        
        assert len(zones) == 7
        assert zones[0]["zone"] == 1
        assert zones[0]["name"] == "Active Recovery"
        assert zones[0]["min_watts"] == 0  # 0% of 200
        assert zones[0]["max_watts"] == 110  # 55% of 200
        
        assert zones[3]["zone"] == 4
        assert zones[3]["name"] == "Threshold"
        assert zones[3]["min_watts"] == 182  # 91% of 200
        assert zones[3]["max_watts"] == 210  # 105% of 200
        
        assert zones[6]["zone"] == 7
        assert zones[6]["name"] == "Neuromuscular"
        assert zones[6]["min_watts"] == 302  # 151% of 200
        assert zones[6]["max_watts"] is None  # No upper limit

    def test_custom_percentages(self):
        """Should use custom percentages when provided."""
        custom = {
            "1": [0, 50],
            "2": [50, 100],
            "3": [100, None],
        }
        zones = compute_power_zones(200, custom)
        
        assert len(zones) == 3
        assert zones[0]["min_watts"] == 0
        assert zones[0]["max_watts"] == 100  # 50% of 200
        assert zones[1]["min_watts"] == 100
        assert zones[1]["max_watts"] == 200
        assert zones[2]["min_watts"] == 200
        assert zones[2]["max_watts"] is None

    def test_invalid_custom_percentages_uses_defaults(self):
        """Should fall back to defaults if custom format is invalid."""
        zones = compute_power_zones(200, {"invalid": "data"})
        assert len(zones) == 7  # Falls back to default 7 zones


class TestComputeHrZones:
    """Tests for compute_hr_zones function."""

    def test_computes_default_zones_from_lthr(self):
        """Should compute 5 HR zones from LTHR."""
        zones = compute_hr_zones(170)
        
        assert len(zones) == 5
        assert zones[0]["zone"] == 1
        assert zones[0]["name"] == "Recovery"
        assert zones[0]["min_bpm"] == 0
        assert zones[0]["max_bpm"] == 137  # 81% of 170
        
        assert zones[3]["zone"] == 4
        assert zones[3]["name"] == "Threshold"
        assert zones[3]["min_bpm"] == 159  # 94% of 170
        assert zones[3]["max_bpm"] == 170  # 100% of 170
        
        assert zones[4]["zone"] == 5
        assert zones[4]["name"] == "Anaerobic"
        assert zones[4]["max_bpm"] is None  # No upper limit

    def test_custom_percentages(self):
        """Should use custom percentages when provided."""
        custom = {
            "1": [0, 80],
            "2": [80, 100],
            "3": [100, None],
        }
        zones = compute_hr_zones(170, custom)
        
        assert len(zones) == 3
        assert zones[0]["max_bpm"] == 136  # 80% of 170
        assert zones[1]["min_bpm"] == 136
        assert zones[2]["max_bpm"] is None


class TestGetZoneForPower:
    """Tests for get_zone_for_power function."""

    def test_zone_1_recovery(self):
        """Power in zone 1 (recovery)."""
        assert get_zone_for_power(100, 200) == 1  # 50% of FTP

    def test_zone_4_threshold(self):
        """Power at threshold (zone 4)."""
        assert get_zone_for_power(200, 200) == 4  # 100% of FTP

    def test_zone_5_vo2max(self):
        """Power in VO2max zone."""
        assert get_zone_for_power(220, 200) == 5  # 110% of FTP

    def test_zone_7_neuromuscular(self):
        """Power in neuromuscular zone."""
        assert get_zone_for_power(400, 200) == 7  # 200% of FTP

    def test_zero_power_returns_zone_1(self):
        """Zero power should return zone 1."""
        assert get_zone_for_power(0, 200) == 1

    def test_zero_ftp_returns_zone_1(self):
        """Zero FTP should return zone 1."""
        assert get_zone_for_power(100, 0) == 1

    def test_custom_percentages(self):
        """Should use custom percentages."""
        custom = {"1": [0, 50], "2": [50, None]}
        assert get_zone_for_power(80, 200, custom) == 1  # 40% < 50%
        assert get_zone_for_power(120, 200, custom) == 2  # 60% >= 50%


class TestGetZoneForHr:
    """Tests for get_zone_for_hr function."""

    def test_zone_1_recovery(self):
        """HR in zone 1 (recovery)."""
        assert get_zone_for_hr(120, 170) == 1  # ~71% of LTHR

    def test_zone_4_threshold(self):
        """HR at threshold (zone 4)."""
        assert get_zone_for_hr(165, 170) == 4  # ~97% of LTHR

    def test_zone_5_anaerobic(self):
        """HR above LTHR (zone 5)."""
        assert get_zone_for_hr(180, 170) == 5  # 106% of LTHR

    def test_zero_hr_returns_zone_1(self):
        """Zero HR should return zone 1."""
        assert get_zone_for_hr(0, 170) == 1


class TestComputeZoneTimes:
    """Tests for compute_zone_times function."""

    def test_power_zone_times_basic(self):
        """Should compute time in each power zone."""
        # 10 seconds at different power levels
        power_data = [
            100, 100, 100,  # Zone 1 (50% FTP) - 3 seconds
            150, 150,       # Zone 2 (75% FTP) - 2 seconds
            200, 200, 200,  # Zone 4 (100% FTP) - 3 seconds
            300, 300,       # Zone 6 (150% FTP) - 2 seconds
        ]
        
        power_times, hr_times = compute_zone_times(power_data, 200)
        
        assert power_times is not None
        assert hr_times is None
        assert power_times[1] == 3
        assert power_times[2] == 2
        assert power_times[4] == 3
        assert power_times[6] == 2

    def test_hr_zone_times_basic(self):
        """Should compute time in each HR zone."""
        hr_data = [
            120, 120, 120,  # Zone 1 (~71% LTHR) - 3 seconds
            155, 155,       # Zone 3 (~91% LTHR) - 2 seconds
            170, 170,       # Zone 5 (100% LTHR) - 2 seconds
        ]
        
        power_times, hr_times = compute_zone_times([], None, hr_data, 170)
        
        assert power_times is None
        assert hr_times is not None
        assert hr_times[1] == 3
        assert hr_times[3] == 2
        assert hr_times[5] == 2

    def test_both_power_and_hr(self):
        """Should compute both power and HR zone times."""
        power_data = [200, 200, 200]
        hr_data = [170, 170, 170]
        
        power_times, hr_times = compute_zone_times(power_data, 200, hr_data, 170)
        
        assert power_times is not None
        assert hr_times is not None
        assert power_times[4] == 3  # Threshold
        assert hr_times[5] == 3  # Anaerobic

    def test_skips_none_values(self):
        """Should skip None values in data."""
        power_data = [200, None, 200, None, 200]
        
        power_times, _ = compute_zone_times(power_data, 200)
        
        assert sum(power_times.values()) == 3  # Only 3 valid samples

    def test_skips_zero_values(self):
        """Should skip zero values in data."""
        power_data = [200, 0, 200, 0, 200]
        
        power_times, _ = compute_zone_times(power_data, 200)
        
        assert sum(power_times.values()) == 3  # Only 3 non-zero samples

    def test_no_ftp_returns_none_power_zones(self):
        """Should return None for power zones if no FTP."""
        power_times, _ = compute_zone_times([200, 200], None)
        assert power_times is None

    def test_no_lthr_returns_none_hr_zones(self):
        """Should return None for HR zones if no LTHR."""
        _, hr_times = compute_zone_times([], None, [170, 170], None)
        assert hr_times is None

    def test_custom_zone_percentages(self):
        """Should use custom zone percentages."""
        power_data = [100, 100, 200, 200]  # 50% and 100% of FTP
        custom = {"1": [0, 75], "2": [75, None]}
        
        power_times, _ = compute_zone_times(
            power_data, 200, power_zone_pct=custom
        )
        
        assert power_times[1] == 2  # 100W = 50% < 75%
        assert power_times[2] == 2  # 200W = 100% >= 75%
