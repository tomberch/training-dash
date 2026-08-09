"""Unit tests for fitness model computation functions."""

from datetime import datetime


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

    def test_fit_cp_model_insufficient_data(self):
        """Model returns None with insufficient data."""
        from trainingdash.domain.fitness import fit_cp_model

        # Less than 3 points
        result = fit_cp_model([{5: 400, 60: 350}])
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
