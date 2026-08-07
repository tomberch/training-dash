"""
Tests for the FIT file generator with power profiles.

Verifies that make_test_fit_with_profile() generates valid FIT files
that produce predictable peak power values when analyzed.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit_with_profile  # noqa: E402

from trainingdash.ingest import parse_records  # noqa: E402
from trainingdash.peaks import extract_peak_powers  # noqa: E402


class TestMakeTestFitWithProfile:
    """Tests for make_test_fit_with_profile()."""

    def test_empty_intervals_raises_error(self):
        """Empty intervals list should raise ValueError."""
        with pytest.raises(ValueError, match="intervals must not be empty"):
            make_test_fit_with_profile([])

    def test_single_interval_creates_valid_fit(self):
        """Single interval should create a parseable FIT file."""
        fit_bytes = make_test_fit_with_profile([(60, 200)])
        parsed = parse_records(fit_bytes)
        
        assert len(parsed["records"]) == 60
        assert all(r["power_w"] == 200 for r in parsed["records"])

    def test_multiple_intervals_correct_power_values(self):
        """Multiple intervals should have correct power at each section."""
        fit_bytes = make_test_fit_with_profile([
            (30, 150),  # 30s at 150W
            (30, 250),  # 30s at 250W
            (30, 100),  # 30s at 100W
        ])
        parsed = parse_records(fit_bytes)
        
        assert len(parsed["records"]) == 90
        
        # First 30 records at 150W
        for i in range(30):
            assert parsed["records"][i]["power_w"] == 150
        
        # Next 30 records at 250W
        for i in range(30, 60):
            assert parsed["records"][i]["power_w"] == 250
        
        # Last 30 records at 100W
        for i in range(60, 90):
            assert parsed["records"][i]["power_w"] == 100

    def test_peak_power_extraction_matches_profile(self):
        """Peak power extraction should return values matching the profile."""
        # Create a ride with a specific 5-minute effort
        fit_bytes = make_test_fit_with_profile([
            (300, 150),  # 5 min warmup at 150W
            (300, 270),  # 5 min effort at 270W
            (300, 120),  # 5 min cooldown at 120W
        ])
        parsed = parse_records(fit_bytes)
        
        power_array = [r["power_w"] for r in parsed["records"]]
        peaks = extract_peak_powers(power_array)
        
        # Peak 5-min (300s) power should be 270W
        assert peaks[300] == 270
        
        # Peak 1-min (60s) power should also be 270W (within the 5-min effort)
        assert peaks[60] == 270
        
        # Peak 10-min (600s) power should be ~210W (average of 270 + 150 or 270 + 120)
        # Actually it's the best 10-min window, which spans 270W + partial other intervals
        assert peaks[600] is not None
        assert 190 <= peaks[600] <= 210  # Approximate range

    def test_cp_model_verification_profile(self):
        """
        Generate a FIT file designed for CP model verification.
        
        Target: CP = 220W, W' = 15000J
        Formula: P(t) = CP + W'/t
        
        - P(120s) = 220 + 15000/120 = 345W
        - P(300s) = 220 + 15000/300 = 270W
        - P(600s) = 220 + 15000/600 = 245W
        
        Note: Each effort must be isolated so peak extraction finds exactly
        that power value. Recovery intervals must be long enough and low enough
        power that they don't improve the peak for longer durations.
        """
        fit_bytes = make_test_fit_with_profile([
            (60, 80),     # 1 min warmup (low power)
            (120, 345),   # 2 min at 345W (peak 2-min)
            (120, 80),    # 2 min recovery (low power buffer)
            (300, 270),   # 5 min at 270W (peak 5-min)
            (120, 80),    # 2 min recovery (low power buffer)
            (600, 245),   # 10 min at 245W (peak 10-min)
            (60, 80),     # 1 min cooldown
        ])
        parsed = parse_records(fit_bytes)
        
        power_array = [r["power_w"] for r in parsed["records"]]
        peaks = extract_peak_powers(power_array)
        
        # Verify peak powers match our profile
        assert peaks[120] == 345, f"Expected 345W at 2min, got {peaks[120]}W"
        assert peaks[300] == 270, f"Expected 270W at 5min, got {peaks[300]}W"
        assert peaks[600] == 245, f"Expected 245W at 10min, got {peaks[600]}W"

    def test_gps_coordinates_progress_linearly(self):
        """GPS coordinates should progress linearly."""
        fit_bytes = make_test_fit_with_profile(
            [(100, 200)],
            start_lat=47.0,
            start_lon=8.0,
        )
        parsed = parse_records(fit_bytes)
        
        first = parsed["records"][0]
        last = parsed["records"][-1]
        
        assert abs(first["lat"] - 47.0) < 0.001
        assert abs(first["lon"] - 8.0) < 0.001
        assert last["lat"] > first["lat"]
        assert last["lon"] > first["lon"]

    def test_no_gps_option(self):
        """include_gps=False should omit GPS data."""
        fit_bytes = make_test_fit_with_profile(
            [(60, 200)],
            include_gps=False,
        )
        parsed = parse_records(fit_bytes)
        
        assert all(r["lat"] is None for r in parsed["records"])
        assert all(r["lon"] is None for r in parsed["records"])

    def test_no_hr_option(self):
        """include_hr=False should omit heart rate data."""
        fit_bytes = make_test_fit_with_profile(
            [(60, 200)],
            include_hr=False,
        )
        parsed = parse_records(fit_bytes)
        
        assert all(r["hr_bpm"] is None for r in parsed["records"])

    def test_no_cadence_option(self):
        """include_cadence=False should omit cadence data."""
        fit_bytes = make_test_fit_with_profile(
            [(60, 200)],
            include_cadence=False,
        )
        parsed = parse_records(fit_bytes)
        
        assert all(r["cadence_rpm"] is None for r in parsed["records"])

    def test_timestamps_are_sequential(self):
        """Timestamps should be 1 second apart."""
        fit_bytes = make_test_fit_with_profile([(10, 200)])
        parsed = parse_records(fit_bytes)
        
        for i in range(1, len(parsed["records"])):
            prev = parsed["records"][i - 1]["timestamp"]
            curr = parsed["records"][i]["timestamp"]
            delta = (curr - prev).total_seconds()
            assert delta == 1.0, f"Expected 1s gap, got {delta}s"

    def test_session_summary_reflects_profile(self):
        """Session summary should reflect the power profile."""
        fit_bytes = make_test_fit_with_profile([
            (50, 100),  # 50s at 100W
            (50, 300),  # 50s at 300W
        ])
        parsed = parse_records(fit_bytes)
        
        # Average power should be 200W
        assert parsed["avg_power_w"] == 200
        
        # Max power should be 300W
        # Note: session message stores max_power, check if parsed
        assert parsed.get("max_power_w") is None or parsed.get("max_power_w") == 300

    def test_long_ride_generates_correct_record_count(self):
        """Long rides should have correct number of records."""
        # 1 hour ride
        fit_bytes = make_test_fit_with_profile([(3600, 180)])
        parsed = parse_records(fit_bytes)
        
        assert len(parsed["records"]) == 3600

    def test_high_power_values(self):
        """High power values (sprints) should be preserved."""
        fit_bytes = make_test_fit_with_profile([
            (10, 1200),  # 10s sprint at 1200W
            (50, 150),   # recovery
        ])
        parsed = parse_records(fit_bytes)
        
        power_array = [r["power_w"] for r in parsed["records"]]
        peaks = extract_peak_powers(power_array)
        
        assert peaks[1] == 1200
        assert peaks[5] == 1200
        assert peaks[10] == 1200

    def test_zero_power_values(self):
        """Zero power (coasting) should be preserved."""
        fit_bytes = make_test_fit_with_profile([
            (30, 200),
            (30, 0),   # coasting
            (30, 200),
        ])
        parsed = parse_records(fit_bytes)
        
        # Records 30-59 should have 0 power
        for i in range(30, 60):
            assert parsed["records"][i]["power_w"] == 0
