"""Unit tests for fitness model computation functions."""

from datetime import UTC, datetime

import numpy as np
import pytest


class TestFitnessModelUnit:
    """Unit tests for fitness model computation functions."""

    def test_detect_breakthrough_first_activity(self):
        """First activity is always a breakthrough."""
        from trainingdash.domain.fitness import detect_breakthrough

        activity_peaks = {5: 400, 60: 350, 300: 280, 1200: 250}
        all_time_bests = {}  # No previous data

        assert detect_breakthrough(activity_peaks, all_time_bests) is True

    def test_detect_breakthrough_new_pr(self):
        """Activity with new PR at key duration is breakthrough."""
        from trainingdash.domain.fitness import detect_breakthrough

        activity_peaks = {5: 450, 60: 350, 300: 280, 1200: 250}  # 5s PR
        all_time_bests = {5: 400, 60: 360, 300: 290, 1200: 260}

        assert detect_breakthrough(activity_peaks, all_time_bests) is True

    def test_detect_breakthrough_no_pr(self):
        """Activity without PRs at key durations is not breakthrough."""
        from trainingdash.domain.fitness import detect_breakthrough

        activity_peaks = {5: 380, 60: 340, 300: 270, 1200: 240}  # All below best
        all_time_bests = {5: 400, 60: 360, 300: 290, 1200: 260}

        assert detect_breakthrough(activity_peaks, all_time_bests) is False

    def test_detect_breakthrough_only_checks_key_durations(self):
        """Only checks BREAKTHROUGH_DURATIONS (5, 60, 300, 1200)."""
        from trainingdash.domain.fitness import detect_breakthrough

        # PR at 120s (not a key duration)
        activity_peaks = {120: 500}
        all_time_bests = {120: 400}

        assert detect_breakthrough(activity_peaks, all_time_bests) is False

    def test_detect_breakthrough_at_20min(self):
        """PR at 1200s (20min) triggers breakthrough."""
        from trainingdash.domain.fitness import detect_breakthrough

        activity_peaks = {1200: 300}
        all_time_bests = {1200: 280}

        assert detect_breakthrough(activity_peaks, all_time_bests) is True

    def test_fit_cp_model_insufficient_data(self):
        """Model returns None with insufficient data."""
        from trainingdash.domain.fitness import fit_cp_model

        # Less than 3 points
        result = fit_cp_model([{5: 400, 60: 350}])
        assert result is None

    def test_fit_cp_model_empty_input(self):
        """Model returns None with empty input."""
        from trainingdash.domain.fitness import fit_cp_model

        result = fit_cp_model([])
        assert result is None

    def test_fit_cp_model_basic(self):
        """Model fits with sufficient data."""
        from trainingdash.domain.fitness import fit_cp_model

        peak_powers = [
            {1: 800, 5: 600, 60: 400, 300: 320, 1200: 280},
        ]

        result = fit_cp_model(peak_powers)

        assert result is not None
        assert "pp_watts" in result
        assert "w_prime_joules" in result
        assert "cp_watts" in result
        assert result["pp_watts"] >= result["cp_watts"]

    def test_fit_cp_model_with_activity_dates(self):
        """Model uses decay weights when activity dates provided."""
        from trainingdash.domain.fitness import fit_cp_model

        peak_powers = [
            {120: 380, 300: 320, 600: 290},
            {120: 400, 300: 340, 600: 300},  # More recent
        ]
        dates = [
            datetime(2024, 1, 1),  # Old
            datetime(2024, 6, 1),  # Recent
        ]
        reference = datetime(2024, 6, 15)

        result = fit_cp_model(peak_powers, dates, reference)

        assert result is not None
        # Recent activity should be weighted higher

    def test_fit_cp_model_multiple_activities(self):
        """Model aggregates best powers across activities."""
        from trainingdash.domain.fitness import fit_cp_model

        peak_powers = [
            {120: 380, 300: 350, 600: 300},
            {120: 400, 300: 330, 600: 290},  # Better 120s
            {120: 370, 300: 360, 600: 310},  # Better 300s and 600s
        ]

        result = fit_cp_model(peak_powers)

        assert result is not None
        assert result["cp_watts"] > 0
        assert result["w_prime_joules"] > 0

    def test_fit_cp_model_with_none_values(self):
        """Model handles None values in peak powers."""
        from trainingdash.domain.fitness import fit_cp_model

        peak_powers = [
            {120: 380, 300: None, 600: 290},
            {120: 400, 300: 340, 600: 300},
        ]

        result = fit_cp_model(peak_powers)

        assert result is not None

    def test_fit_cp_model_fallback_to_heuristic(self):
        """Model falls back to heuristic when curve fit fails."""
        from trainingdash.domain.fitness import fit_cp_model

        # Data only in longer durations (outside 2-12 min range)
        peak_powers = [
            {60: 400, 1200: 280, 1800: 260},
        ]

        result = fit_cp_model(peak_powers)

        # Should still return something using fallback
        assert result is not None

    def test_fit_cp_model_w_prime_bounds(self):
        """W' should be bounded between 5000 and 40000."""
        from trainingdash.domain.fitness import fit_cp_model

        peak_powers = [
            {120: 380, 300: 320, 600: 290},
        ]

        result = fit_cp_model(peak_powers)

        assert result is not None
        assert 5000 <= result["w_prime_joules"] <= 40000

    def test_decay_weight(self):
        """Decay weight is higher for recent activities."""
        from trainingdash.domain.fitness import compute_decay_weight

        reference = datetime(2024, 6, 1)
        recent = datetime(2024, 5, 25)  # 7 days ago
        old = datetime(2024, 3, 1)  # 92 days ago

        recent_weight = compute_decay_weight(recent, reference)
        old_weight = compute_decay_weight(old, reference)

        assert recent_weight > old_weight
        assert 0 < old_weight < recent_weight <= 1

    def test_decay_weight_same_day(self):
        """Same day activity has weight 1.0."""
        from trainingdash.domain.fitness import compute_decay_weight

        reference = datetime(2024, 6, 1)
        same_day = datetime(2024, 6, 1)

        weight = compute_decay_weight(same_day, reference)
        assert weight == 1.0

    def test_decay_weight_half_life(self):
        """Activity at half-life (42 days) has weight 0.5."""
        from trainingdash.domain.fitness import compute_decay_weight

        reference = datetime(2024, 6, 15)
        half_life_ago = datetime(2024, 5, 4)  # 42 days before

        weight = compute_decay_weight(half_life_ago, reference)
        assert weight == pytest.approx(0.5, rel=0.01)

    def test_decay_weight_future_date(self):
        """Future activity date clamps to weight 1.0."""
        from trainingdash.domain.fitness import compute_decay_weight

        reference = datetime(2024, 6, 1)
        future = datetime(2024, 7, 1)  # After reference

        weight = compute_decay_weight(future, reference)
        assert weight == 1.0

    def test_decay_weight_timezone_aware(self):
        """Handles timezone-aware datetimes."""
        from trainingdash.domain.fitness import compute_decay_weight

        reference = datetime(2024, 6, 1, tzinfo=UTC)
        activity = datetime(2024, 5, 25, tzinfo=UTC)

        weight = compute_decay_weight(activity, reference)
        assert 0 < weight <= 1

    def test_get_all_time_bests(self):
        """Get all-time bests aggregates across activities."""
        from trainingdash.domain.fitness import get_all_time_bests

        peak_powers = [
            {5: 400, 60: 350},
            {5: 420, 60: 340},  # Higher 5s
            {5: 380, 60: 360},  # Higher 60s
        ]

        bests = get_all_time_bests(peak_powers)

        assert bests[5] == 420
        assert bests[60] == 360

    def test_get_all_time_bests_empty(self):
        """Returns empty dict for empty input."""
        from trainingdash.domain.fitness import get_all_time_bests

        bests = get_all_time_bests([])
        assert bests == {}

    def test_get_all_time_bests_with_none(self):
        """Handles None values in peaks."""
        from trainingdash.domain.fitness import get_all_time_bests

        peak_powers = [
            {5: 400, 60: None},
            {5: None, 60: 360},
        ]

        bests = get_all_time_bests(peak_powers)

        assert bests[5] == 400
        assert bests[60] == 360

    def test_get_all_time_bests_single_activity(self):
        """Works with single activity."""
        from trainingdash.domain.fitness import get_all_time_bests

        peak_powers = [{5: 400, 60: 350, 300: 280}]

        bests = get_all_time_bests(peak_powers)

        assert bests[5] == 400
        assert bests[60] == 350
        assert bests[300] == 280


class TestHyperbolicModel:
    """Tests for the internal hyperbolic model."""

    def test_hyperbolic_model_shape(self):
        """P(t) = CP + W'/t decreases with time."""
        from trainingdash.domain.fitness import _hyperbolic_model

        cp = 250
        w_prime = 20000
        t = np.array([60, 120, 300, 600, 1200])

        powers = _hyperbolic_model(t, cp, w_prime)

        # Power should decrease with duration
        assert all(powers[i] > powers[i + 1] for i in range(len(powers) - 1))

        # Should approach CP at long durations
        assert powers[-1] > cp
        assert powers[-1] < powers[0]

    def test_hyperbolic_model_at_infinity(self):
        """Power approaches CP as duration increases."""
        from trainingdash.domain.fitness import _hyperbolic_model

        cp = 250
        w_prime = 20000
        t = np.array([36000])  # 10 hours

        power = _hyperbolic_model(t, cp, w_prime)[0]

        # Should be very close to CP
        assert power == pytest.approx(cp, rel=0.01)


class TestLinearWorkModel:
    """Tests for the fallback linear work model."""

    def test_linear_work_model_basic(self):
        """Linear model fits W = CP*t + W'."""
        from trainingdash.domain.fitness import _fit_linear_work_model

        # Synthetic data following the model
        cp = 250
        w_prime = 20000
        durations = np.array([120, 300, 600])
        powers = cp + w_prime / durations

        result = _fit_linear_work_model(durations, powers)

        assert result is not None
        fitted_cp, fitted_w_prime = result
        assert fitted_cp == pytest.approx(cp, rel=0.1)
        assert fitted_w_prime == pytest.approx(w_prime, rel=0.1)

    def test_linear_work_model_insufficient_data(self):
        """Returns None with fewer than 2 points."""
        from trainingdash.domain.fitness import _fit_linear_work_model

        result = _fit_linear_work_model(np.array([120]), np.array([350]))
        assert result is None


class TestFit2ParameterModel:
    """Tests for the 2-parameter CP model fitting."""

    def test_fit_2_parameter_model_basic(self):
        """Model fits synthetic data correctly."""
        from trainingdash.domain.fitness import _fit_2_parameter_model

        # Synthetic data following P = CP + W'/t
        true_cp = 250
        true_w_prime = 18000
        durations = np.array([120, 180, 300, 480, 720])
        powers = true_cp + true_w_prime / durations

        result = _fit_2_parameter_model(durations, powers)

        assert result is not None
        fitted_cp, fitted_w_prime = result
        assert fitted_cp == pytest.approx(true_cp, rel=0.05)
        assert fitted_w_prime == pytest.approx(true_w_prime, rel=0.1)

    def test_fit_2_parameter_model_with_weights(self):
        """Model uses weights in fitting."""
        from trainingdash.domain.fitness import _fit_2_parameter_model

        durations = np.array([120, 300, 600])
        powers = np.array([380, 320, 290])
        weights = np.array([0.5, 1.0, 1.0])  # Less weight on first point

        result = _fit_2_parameter_model(durations, powers, weights)

        assert result is not None

    def test_fit_2_parameter_model_insufficient_data(self):
        """Returns None with fewer than 2 points."""
        from trainingdash.domain.fitness import _fit_2_parameter_model

        result = _fit_2_parameter_model(np.array([120]), np.array([350]))
        assert result is None
