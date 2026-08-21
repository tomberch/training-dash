"""Unit tests for W'bal prediction functions."""

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from trainingdash.domain.wbal import (
    WbalPrediction,
    check_wbal_feasibility,
    compute_wbal_series,
    predict_wbal_for_plan,
)


class TestPredictWbalForPlan:
    """Tests for predict_wbal_for_plan."""

    def test_empty_arrays_returns_full_wbal(self):
        """Empty input should return full W'bal."""
        result = predict_wbal_for_plan(
            powers=np.array([]),
            times=np.array([]),
            cp=250,
            w_prime=20000,
        )
        assert result.min_wbal == 20000
        assert result.final_wbal == 20000
        assert len(result.wbal_series) == 0

    def test_mismatched_array_lengths_raises(self):
        """Powers and times must have same length."""
        with pytest.raises(ValueError, match="same length"):
            predict_wbal_for_plan(
                powers=np.array([200, 300]),
                times=np.array([60]),
                cp=250,
                w_prime=20000,
            )

    def test_constant_power_below_cp_no_depletion(self):
        """Power below CP should not deplete W'bal."""
        result = predict_wbal_for_plan(
            powers=np.array([200]),
            times=np.array([60]),
            cp=250,
            w_prime=20000,
        )
        assert result.min_wbal == 20000
        assert result.final_wbal == 20000
        assert result.time_in_deficit == 0

    def test_constant_power_above_cp_depletes_linearly(self):
        """Power above CP should deplete W'bal linearly."""
        # 60 seconds at 350W (100W above CP=250)
        # Depletion = 100W * 60s = 6000J
        result = predict_wbal_for_plan(
            powers=np.array([350]),
            times=np.array([60]),
            cp=250,
            w_prime=20000,
        )
        expected_final = 20000 - 6000  # 14000J
        assert result.final_wbal == expected_final
        assert result.min_wbal == expected_final

    def test_recovery_during_below_cp_segments(self):
        """W'bal should recover when power drops below CP."""
        # First deplete: 60s at 350W (-6000J) -> 14000J
        # Then recover: 60s at 150W (100W below CP)
        result = predict_wbal_for_plan(
            powers=np.array([350, 150]),
            times=np.array([60, 60]),
            cp=250,
            w_prime=20000,
        )
        # After recovery should be higher than depleted value
        assert result.final_wbal > 14000
        # But not fully recovered
        assert result.final_wbal < 20000
        # Minimum was at end of hard segment
        assert result.min_wbal == 14000

    def test_matches_existing_wbal_calculation(self):
        """Prediction should match existing compute_wbal_series for same data."""
        powers = np.array([300, 200, 350])
        times = np.array([30, 30, 30])
        cp = 250
        w_prime = 20000

        # Expand to per-second for comparison
        power_series = [300] * 30 + [200] * 30 + [350] * 30
        existing_result = compute_wbal_series(power_series, cp, w_prime)

        prediction = predict_wbal_for_plan(powers, times, cp, w_prime)

        assert prediction.final_wbal == existing_result["series"][-1]
        assert prediction.min_wbal == existing_result["min_wbal"]
        assert len(prediction.wbal_series) == len(existing_result["series"])

    def test_series_length_matches_total_time(self):
        """Output series should have one value per second."""
        result = predict_wbal_for_plan(
            powers=np.array([250, 300]),
            times=np.array([30, 45]),
            cp=250,
            w_prime=20000,
        )
        assert len(result.wbal_series) == 75  # 30 + 45

    def test_distance_tracking(self):
        """Should track distance where minimum occurs."""
        # 1000m at 350W, then 500m at 150W
        result = predict_wbal_for_plan(
            powers=np.array([350, 150]),
            times=np.array([60, 60]),
            cp=250,
            w_prime=20000,
            distances=np.array([1000, 500]),
        )
        # Minimum should be at end of first segment (~1000m)
        assert 990 < result.min_wbal_distance_m < 1010

    def test_time_in_deficit_counting(self):
        """Should count seconds where W'bal < threshold."""
        # Deplete below 5000J threshold
        result = predict_wbal_for_plan(
            powers=np.array([400]),  # 150W above CP
            times=np.array([120]),  # 120s -> 18000J depletion
            cp=250,
            w_prime=20000,
            deficit_threshold=5000,
        )
        # W'bal drops below 5000 after ~100s (150*100=15000J depletion)
        # Should be in deficit for ~20 seconds
        assert result.time_in_deficit > 0
        assert result.min_wbal < 5000


class TestCheckWbalFeasibility:
    """Tests for check_wbal_feasibility."""

    def test_feasible_plan_returns_true(self):
        """Plan that stays above threshold is feasible."""
        is_feasible, min_wbal = check_wbal_feasibility(
            powers=np.array([280]),  # 30W above CP
            times=np.array([60]),  # 1800J depletion
            cp=250,
            w_prime=20000,
            min_wbal_threshold=0,
        )
        assert is_feasible is True
        assert min_wbal > 0

    def test_infeasible_plan_returns_false(self):
        """Plan that depletes W' completely is infeasible."""
        # Use threshold > 0 since W'bal floors at 0 (never negative)
        is_feasible, min_wbal = check_wbal_feasibility(
            powers=np.array([450]),  # 200W above CP
            times=np.array([120]),  # 24000J depletion > 20000J W'
            cp=250,
            w_prime=20000,
            min_wbal_threshold=1000,  # Require at least 1000J remaining
        )
        assert is_feasible is False
        assert min_wbal == 0

    def test_custom_threshold(self):
        """Should check against custom threshold."""
        # Plan that depletes to 10000J (50% of W')
        is_feasible, min_wbal = check_wbal_feasibility(
            powers=np.array([350]),  # 100W above CP
            times=np.array([100]),  # 10000J depletion
            cp=250,
            w_prime=20000,
            min_wbal_threshold=15000,  # Require at least 75% remaining
        )
        assert is_feasible is False
        assert min_wbal == 10000

    def test_exactly_at_threshold_is_feasible(self):
        """W'bal exactly at threshold should be feasible."""
        # Deplete exactly 10000J
        is_feasible, min_wbal = check_wbal_feasibility(
            powers=np.array([350]),
            times=np.array([100]),
            cp=250,
            w_prime=20000,
            min_wbal_threshold=10000,
        )
        assert is_feasible is True
        assert min_wbal == 10000


class TestWbalPredictionDataclass:
    """Tests for WbalPrediction dataclass."""

    def test_dataclass_is_frozen(self):
        """WbalPrediction should be immutable."""
        prediction = WbalPrediction(
            wbal_series=np.array([20000, 19000]),
            min_wbal=19000,
            min_wbal_distance_m=100,
            time_in_deficit=0,
            final_wbal=19000,
        )
        with pytest.raises(FrozenInstanceError):
            prediction.min_wbal = 0

    def test_dataclass_fields(self):
        """Should have all required fields."""
        prediction = WbalPrediction(
            wbal_series=np.array([20000]),
            min_wbal=20000,
            min_wbal_distance_m=0,
            time_in_deficit=0,
            final_wbal=20000,
        )
        assert hasattr(prediction, "wbal_series")
        assert hasattr(prediction, "min_wbal")
        assert hasattr(prediction, "min_wbal_distance_m")
        assert hasattr(prediction, "time_in_deficit")
        assert hasattr(prediction, "final_wbal")
