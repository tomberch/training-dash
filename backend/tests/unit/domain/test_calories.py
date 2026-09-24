"""Unit tests for calories computation functions."""

from datetime import datetime, timedelta

from trainingdash.domain.calories import (
    compute_calories_from_power,
    resolve_calories,
)


class TestComputeCaloriesFromPower:
    """Tests for compute_calories_from_power()."""

    def test_empty_records_returns_none(self):
        """Empty records list returns None."""
        assert compute_calories_from_power([]) is None

    def test_single_record_returns_none(self):
        """Single record can't compute intervals."""
        records = [{"timestamp": datetime(2024, 1, 1, 10, 0, 0), "power_w": 200}]
        assert compute_calories_from_power(records) is None

    def test_no_power_records_returns_none(self):
        """Records without power data return None."""
        records = [
            {"timestamp": datetime(2024, 1, 1, 10, 0, 0), "power_w": None},
            {"timestamp": datetime(2024, 1, 1, 10, 0, 1), "power_w": None},
            {"timestamp": datetime(2024, 1, 1, 10, 0, 2), "power_w": None},
        ]
        assert compute_calories_from_power(records) is None

    def test_constant_power_one_hour(self):
        """200W for 1 hour = 720 kJ ≈ 720 kcal."""
        base = datetime(2024, 1, 1, 10, 0, 0)
        records = [
            {"timestamp": base + timedelta(seconds=i), "power_w": 200}
            for i in range(3601)  # 0 to 3600 seconds = 1 hour
        ]
        result = compute_calories_from_power(records)
        # 200W × 3600s = 720,000 J = 720 kJ ≈ 720 kcal
        assert result == 720

    def test_constant_power_one_minute(self):
        """200W for 1 minute = 12 kJ ≈ 12 kcal."""
        base = datetime(2024, 1, 1, 10, 0, 0)
        records = [
            {"timestamp": base + timedelta(seconds=i), "power_w": 200}
            for i in range(61)  # 0 to 60 seconds
        ]
        result = compute_calories_from_power(records)
        # 200W × 60s = 12,000 J = 12 kJ ≈ 12 kcal
        assert result == 12

    def test_variable_power(self):
        """Variable power accumulates correctly."""
        base = datetime(2024, 1, 1, 10, 0, 0)
        records = [
            {"timestamp": base, "power_w": 100},
            {"timestamp": base + timedelta(seconds=10), "power_w": 200},  # 200W × 10s = 2000J
            {"timestamp": base + timedelta(seconds=20), "power_w": 300},  # 300W × 10s = 3000J
            {"timestamp": base + timedelta(seconds=30), "power_w": 100},  # 100W × 10s = 1000J
        ]
        result = compute_calories_from_power(records)
        # Total = 6000J = 6 kJ ≈ 6 kcal
        assert result == 6

    def test_missing_power_records_skipped(self):
        """Records without power contribute nothing but don't break computation."""
        base = datetime(2024, 1, 1, 10, 0, 0)
        records = [
            {"timestamp": base, "power_w": 200},
            {"timestamp": base + timedelta(seconds=10), "power_w": None},  # skipped
            {"timestamp": base + timedelta(seconds=20), "power_w": 200},  # 200W × 10s = 2000J
            {"timestamp": base + timedelta(seconds=30), "power_w": 200},  # 200W × 10s = 2000J
        ]
        result = compute_calories_from_power(records)
        # Only last two intervals count: 4000J = 4 kJ ≈ 4 kcal
        assert result == 4

    def test_gap_capped_at_max_interval(self):
        """Gaps > 30s are capped to avoid counting pauses."""
        base = datetime(2024, 1, 1, 10, 0, 0)
        records = [
            {"timestamp": base, "power_w": 200},
            {"timestamp": base + timedelta(seconds=60), "power_w": 200},  # 60s gap, capped to 30s
        ]
        result = compute_calories_from_power(records)
        # 200W × 30s (capped) = 6000J = 6 kJ ≈ 6 kcal
        assert result == 6

    def test_negative_power_ignored(self):
        """Negative power values are treated as missing."""
        base = datetime(2024, 1, 1, 10, 0, 0)
        records = [
            {"timestamp": base, "power_w": 200},
            {"timestamp": base + timedelta(seconds=10), "power_w": -50},  # ignored
            {"timestamp": base + timedelta(seconds=20), "power_w": 200},
        ]
        result = compute_calories_from_power(records)
        # Only second interval: 200W × 10s = 2000J = 2 kJ
        assert result == 2

    def test_smart_recording_variable_intervals(self):
        """Handles variable-interval 'smart recording' correctly."""
        base = datetime(2024, 1, 1, 10, 0, 0)
        # Simulate smart recording: more samples during hard efforts
        records = [
            {"timestamp": base, "power_w": 150},
            {"timestamp": base + timedelta(seconds=5), "power_w": 300},  # 5s × 300W = 1500J
            {"timestamp": base + timedelta(seconds=6), "power_w": 350},  # 1s × 350W = 350J
            {"timestamp": base + timedelta(seconds=7), "power_w": 320},  # 1s × 320W = 320J
            {"timestamp": base + timedelta(seconds=12), "power_w": 150},  # 5s × 150W = 750J
        ]
        result = compute_calories_from_power(records)
        # Total = 2920J ≈ 3 kJ ≈ 3 kcal
        assert result == 3

    def test_no_timestamp_falls_back_to_one_second(self):
        """Missing timestamps assume 1-second intervals."""
        records = [
            {"power_w": 200},
            {"power_w": 200},
            {"power_w": 200},
        ]
        result = compute_calories_from_power(records)
        # 2 intervals × 200W × 1s = 400J ≈ 0 kcal (rounds down)
        assert result == 0

    def test_karoo_style_ride_approximation(self):
        """Sanity check against the analyzed Karoo ride: 574 kJ work ≈ 574 kcal."""
        # Simulate ~1 hour at ~160W average (574 kJ total)
        # 574,000 J / 3600s ≈ 159.4W
        base = datetime(2024, 1, 1, 10, 0, 0)
        duration_s = 3600
        avg_power = 159.4
        records = [{"timestamp": base + timedelta(seconds=i), "power_w": avg_power} for i in range(duration_s + 1)]
        result = compute_calories_from_power(records)
        # Should be approximately 574 kcal
        assert 570 <= result <= 578


class TestResolveCalories:
    """Tests for resolve_calories()."""

    def test_device_value_takes_precedence(self):
        """Device-reported calories win over computed."""
        base = datetime(2024, 1, 1, 10, 0, 0)
        records = [
            {"timestamp": base, "power_w": 200},
            {"timestamp": base + timedelta(hours=1), "power_w": 200},
        ]
        # Device says 600, power would compute ~720
        calories, source = resolve_calories(600, records)
        assert calories == 600
        assert source == "device"

    def test_falls_back_to_computed_when_no_device(self):
        """Computes from power when no device value."""
        base = datetime(2024, 1, 1, 10, 0, 0)
        records = [{"timestamp": base + timedelta(seconds=i), "power_w": 200} for i in range(61)]
        calories, source = resolve_calories(None, records)
        assert calories == 12  # 200W × 60s = 12 kJ
        assert source == "computed_power"

    def test_zero_device_value_falls_back_to_computed(self):
        """Zero device value is treated as missing."""
        base = datetime(2024, 1, 1, 10, 0, 0)
        records = [{"timestamp": base + timedelta(seconds=i), "power_w": 200} for i in range(61)]
        calories, source = resolve_calories(0, records)
        assert calories == 12
        assert source == "computed_power"

    def test_returns_none_when_no_data(self):
        """Returns (None, None) when neither device nor power available."""
        records = [
            {"timestamp": datetime(2024, 1, 1, 10, 0, 0), "power_w": None},
            {"timestamp": datetime(2024, 1, 1, 10, 0, 1), "power_w": None},
        ]
        calories, source = resolve_calories(None, records)
        assert calories is None
        assert source is None

    def test_empty_records_with_no_device(self):
        """Empty records and no device value returns None."""
        calories, source = resolve_calories(None, [])
        assert calories is None
        assert source is None

    def test_device_value_with_empty_records(self):
        """Device value works even with empty records."""
        calories, source = resolve_calories(500, [])
        assert calories == 500
        assert source == "device"
