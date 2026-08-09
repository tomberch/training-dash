"""Unit tests for W'bal computation."""

from trainingdash.domain.wbal import compute_wbal_series, estimate_w_prime


class TestWbalSeries:
    """Tests for compute_wbal_series."""

    def test_empty_array_returns_empty(self):
        result = compute_wbal_series([], cp_watts=250, w_prime_joules=20000)
        assert result["series"] == []
        assert result["min_wbal"] is None

    def test_zero_cp_returns_empty(self):
        result = compute_wbal_series([200, 300], cp_watts=0, w_prime_joules=20000)
        assert result["series"] == []

    def test_zero_w_prime_returns_empty(self):
        result = compute_wbal_series([200, 300], cp_watts=250, w_prime_joules=0)
        assert result["series"] == []

    def test_power_below_cp_no_depletion(self):
        """Power below CP should not deplete W'bal (should recover or stay full)."""
        power = [200] * 60  # 1 minute at 200W with CP=250
        result = compute_wbal_series(power, cp_watts=250, w_prime_joules=20000)

        # Should stay at full W'
        assert result["series"][-1] == 20000
        assert result["min_wbal"] == 20000

    def test_power_at_cp_no_change(self):
        """Power exactly at CP should maintain current W'bal."""
        power = [250] * 60  # 1 minute exactly at CP
        result = compute_wbal_series(power, cp_watts=250, w_prime_joules=20000)

        # Should stay at full W'
        assert result["series"][-1] == 20000
        assert result["min_wbal"] == 20000

    def test_power_above_cp_depletes(self):
        """Power above CP should deplete W'bal."""
        # 60 seconds at 350W (100W above CP=250)
        # Depletion = 100W * 60s = 6000J
        power = [350] * 60
        result = compute_wbal_series(power, cp_watts=250, w_prime_joules=20000)

        expected_final = 20000 - 6000  # 14000J
        assert result["series"][-1] == expected_final
        assert result["min_wbal"] == expected_final

    def test_full_depletion_stops_at_zero(self):
        """W'bal should not go negative."""
        # 300 seconds at 350W = 30000J depletion, but W' is only 20000J
        power = [350] * 300
        result = compute_wbal_series(power, cp_watts=250, w_prime_joules=20000)

        assert result["min_wbal"] == 0
        assert all(w >= 0 for w in result["series"])

    def test_recovery_after_depletion(self):
        """W'bal should recover when power drops below CP."""
        # First deplete: 60s at 350W (-6000J)
        # Then recover: 60s at 150W (100W below CP)
        power = [350] * 60 + [150] * 60
        result = compute_wbal_series(power, cp_watts=250, w_prime_joules=20000)

        # After depletion: 14000J
        assert result["series"][59] == 14000

        # After recovery: should be higher than 14000
        final_wbal = result["series"][-1]
        assert final_wbal > 14000
        # But not fully recovered in just 60s
        assert final_wbal < 20000

    def test_min_wbal_tracking(self):
        """Should track the minimum W'bal and its index."""
        # Deplete, then recover
        power = [400] * 60 + [100] * 60  # Hard then easy
        result = compute_wbal_series(power, cp_watts=250, w_prime_joules=20000)

        # Min should be at end of hard effort
        assert result["min_wbal_index"] == 59
        assert result["min_wbal"] == 20000 - (150 * 60)  # 11000J

    def test_min_wbal_percentage(self):
        """Should calculate minimum as percentage of W'."""
        power = [350] * 60  # Deplete by 6000J
        result = compute_wbal_series(power, cp_watts=250, w_prime_joules=20000)

        # 14000/20000 = 70%
        assert result["min_wbal_pct"] == 70.0

    def test_none_values_treated_as_zero(self):
        """None values should be treated as coasting (0W = recovery)."""
        power = [350] * 30 + [None] * 30 + [350] * 30
        result = compute_wbal_series(power, cp_watts=250, w_prime_joules=20000)

        # Should have some recovery in the middle
        assert len(result["series"]) == 90

    def test_sample_rate_affects_calculation(self):
        """Higher sample rate should give same result for same duration."""
        # 60 seconds at 350W, 1Hz
        power_1hz = [350] * 60
        result_1hz = compute_wbal_series(power_1hz, cp_watts=250, w_prime_joules=20000, sample_rate_hz=1.0)

        # 60 seconds at 350W, 2Hz (120 samples)
        power_2hz = [350] * 120
        result_2hz = compute_wbal_series(power_2hz, cp_watts=250, w_prime_joules=20000, sample_rate_hz=2.0)

        # Final W'bal should be approximately the same
        assert abs(result_1hz["series"][-1] - result_2hz["series"][-1]) < 100

    def test_series_length_matches_input(self):
        """Output series length should match input length."""
        power = [250] * 100
        result = compute_wbal_series(power, cp_watts=250, w_prime_joules=20000)
        assert len(result["series"]) == 100

    def test_golden_value_hard_interval(self):
        """Golden test: 5-minute VO2max interval."""
        # 5 minutes at 120% FTP (300W with CP=250)
        # Depletion = 50W * 300s = 15000J
        power = [300] * 300
        result = compute_wbal_series(power, cp_watts=250, w_prime_joules=20000)

        assert result["min_wbal"] == 5000
        assert result["min_wbal_pct"] == 25.0


class TestEstimateWPrime:
    """Tests for estimate_w_prime."""

    def test_missing_1min_returns_none(self):
        """Need 1-minute peak to estimate."""
        result = estimate_w_prime({300: 280}, cp_watts=250)
        assert result is None

    def test_1min_below_cp_returns_none(self):
        """1-minute peak must be above CP."""
        result = estimate_w_prime({60: 240}, cp_watts=250)
        assert result is None

    def test_estimate_from_1min_only(self):
        """Can estimate from 1-minute peak alone."""
        # 1 min at 400W with CP=250: W' = 150 * 60 = 9000J
        result = estimate_w_prime({60: 400}, cp_watts=250)
        assert result == 9000

    def test_estimate_from_1min_and_5min(self):
        """Uses both peaks for better estimate."""
        # 1 min at 400W: W' = 150 * 60 = 9000J
        # 5 min at 300W: W' = 50 * 300 = 15000J
        # Average = 12000J
        result = estimate_w_prime({60: 400, 300: 300}, cp_watts=250)
        assert result == 12000

    def test_clamps_to_minimum(self):
        """Should clamp W' to minimum 5000J."""
        # Very small estimate
        result = estimate_w_prime({60: 260}, cp_watts=250)  # Only 10 * 60 = 600J
        assert result == 5000

    def test_clamps_to_maximum(self):
        """Should clamp W' to maximum 50000J."""
        # Very large estimate
        result = estimate_w_prime({60: 1000}, cp_watts=250)  # 750 * 60 = 45000J
        assert result <= 50000
