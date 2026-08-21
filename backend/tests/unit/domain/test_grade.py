"""Unit tests for grade calculation module."""

import numpy as np

from trainingdash.domain.grade import (
    calculate_grade,
    classify_terrain,
    classify_terrain_array,
)


class TestCalculateGrade:
    """Tests for window-based grade calculation."""

    def test_constant_climb(self):
        """Constant climb should produce constant grade."""
        distances = np.array([0, 100, 200, 300, 400, 500])
        elevations = np.array([100, 105, 110, 115, 120, 125])  # 5m per 100m = 5%

        grades = calculate_grade(distances, elevations, window_m=100)

        # All grades should be approximately 0.05 (5%)
        np.testing.assert_array_almost_equal(grades, [0.05] * 6, decimal=2)

    def test_constant_descent(self):
        """Constant descent should produce constant negative grade."""
        distances = np.array([0, 100, 200, 300, 400])
        elevations = np.array([120, 110, 100, 90, 80])  # -10m per 100m = -10%

        grades = calculate_grade(distances, elevations, window_m=100)

        np.testing.assert_array_almost_equal(grades, [-0.10] * 5, decimal=2)

    def test_flat_terrain(self):
        """Flat terrain should have zero grade."""
        distances = np.array([0, 50, 100, 150, 200])
        elevations = np.array([100, 100, 100, 100, 100])

        grades = calculate_grade(distances, elevations, window_m=50)

        np.testing.assert_array_almost_equal(grades, [0.0] * 5)

    def test_varying_grade(self):
        """Profile with climb then descent should show varying grade."""
        distances = np.array([0, 100, 200, 300, 400])
        elevations = np.array([100, 110, 120, 110, 100])  # Up then down

        grades = calculate_grade(distances, elevations, window_m=100)

        # First half should be positive, second half negative
        assert grades[1] > 0
        assert grades[3] < 0

    def test_edge_handling_start(self):
        """Start of course should still produce reasonable grade."""
        distances = np.array([0, 10, 20, 30, 100, 200])
        elevations = np.array([100, 101, 102, 103, 110, 120])

        grades = calculate_grade(distances, elevations, window_m=50)

        # First point should have a valid grade (not NaN or inf)
        assert np.isfinite(grades[0])
        assert grades[0] > 0  # Should be climbing

    def test_edge_handling_end(self):
        """End of course should still produce reasonable grade."""
        distances = np.array([0, 100, 190, 195, 200])
        elevations = np.array([100, 110, 119, 119.5, 120])

        grades = calculate_grade(distances, elevations, window_m=50)

        # Last point should have a valid grade
        assert np.isfinite(grades[-1])

    def test_short_array(self):
        """Very short arrays should still work."""
        distances = np.array([0, 100])
        elevations = np.array([100, 110])

        grades = calculate_grade(distances, elevations, window_m=50)

        assert len(grades) == 2
        np.testing.assert_array_almost_equal(grades, [0.1, 0.1])

    def test_single_point(self):
        """Single point should return zero grade."""
        distances = np.array([0])
        elevations = np.array([100])

        grades = calculate_grade(distances, elevations, window_m=50)

        assert len(grades) == 1
        assert grades[0] == 0.0

    def test_empty_array(self):
        """Empty input should return empty output."""
        distances = np.array([])
        elevations = np.array([])

        grades = calculate_grade(distances, elevations, window_m=50)

        assert len(grades) == 0

    def test_accepts_list(self):
        """Should accept Python lists."""
        distances = [0, 100, 200]
        elevations = [100, 110, 120]

        grades = calculate_grade(distances, elevations, window_m=100)

        assert isinstance(grades, np.ndarray)
        assert len(grades) == 3

    def test_window_size_affects_smoothness(self):
        """Larger window should produce smoother grades."""
        # Create noisy data
        np.random.seed(42)
        distances = np.arange(0, 1000, 10)
        base_elevation = 100 + distances * 0.05  # 5% base grade
        noise = np.random.normal(0, 0.5, len(distances))
        elevations = base_elevation + noise

        grades_small = calculate_grade(distances, elevations, window_m=20)
        grades_large = calculate_grade(distances, elevations, window_m=100)

        # Larger window should have less variance
        var_small = np.var(grades_small)
        var_large = np.var(grades_large)
        assert var_large < var_small

    def test_known_profile(self):
        """Test against a known hill profile."""
        # 1km climb at 8%, then 500m flat, then 500m descent at 6%
        distances = np.array([0, 500, 1000, 1250, 1500, 1750, 2000])
        elevations = np.array([0, 40, 80, 80, 80, 65, 50])

        grades = calculate_grade(distances, elevations, window_m=200)

        # Check approximate grades (with some tolerance for windowing)
        assert 0.06 < grades[1] < 0.10  # Climbing section
        assert -0.02 < grades[3] < 0.02  # Flat section
        assert -0.08 < grades[5] < -0.04  # Descent section


class TestClassifyTerrain:
    """Tests for terrain classification."""

    def test_steep_descent(self):
        """Grade < -6% should be steep_descent."""
        assert classify_terrain(-7.0) == "steep_descent"
        assert classify_terrain(-10.0) == "steep_descent"
        assert classify_terrain(-6.1) == "steep_descent"

    def test_descent(self):
        """Grade -6% to -2% should be descent."""
        assert classify_terrain(-6.0) == "descent"
        assert classify_terrain(-4.0) == "descent"
        assert classify_terrain(-2.1) == "descent"

    def test_flat(self):
        """Grade -2% to 2% should be flat."""
        assert classify_terrain(-2.0) == "flat"
        assert classify_terrain(0.0) == "flat"
        assert classify_terrain(1.9) == "flat"

    def test_false_flat(self):
        """Grade 2% to 4% should be false_flat."""
        assert classify_terrain(2.0) == "false_flat"
        assert classify_terrain(3.0) == "false_flat"
        assert classify_terrain(3.9) == "false_flat"

    def test_climb(self):
        """Grade 4% to 8% should be climb."""
        assert classify_terrain(4.0) == "climb"
        assert classify_terrain(6.0) == "climb"
        assert classify_terrain(7.9) == "climb"

    def test_steep_climb(self):
        """Grade >= 8% should be steep_climb."""
        assert classify_terrain(8.0) == "steep_climb"
        assert classify_terrain(10.0) == "steep_climb"
        assert classify_terrain(20.0) == "steep_climb"

    def test_boundary_values(self):
        """Test exact boundary values."""
        assert classify_terrain(-6.0) == "descent"  # Not steep_descent
        assert classify_terrain(-2.0) == "flat"  # Not descent
        assert classify_terrain(2.0) == "false_flat"  # Not flat
        assert classify_terrain(4.0) == "climb"  # Not false_flat
        assert classify_terrain(8.0) == "steep_climb"  # Not climb


class TestClassifyTerrainArray:
    """Tests for array terrain classification."""

    def test_mixed_terrain(self):
        """Array with mixed grades should produce mixed classifications."""
        # Grades as decimals: -10%, -4%, 0%, 3%, 6%, 12%
        grades = np.array([-0.10, -0.04, 0.0, 0.03, 0.06, 0.12])

        classifications = classify_terrain_array(grades)

        assert classifications == [
            "steep_descent",
            "descent",
            "flat",
            "false_flat",
            "climb",
            "steep_climb",
        ]

    def test_empty_array(self):
        """Empty input should return empty list."""
        grades = np.array([])
        classifications = classify_terrain_array(grades)
        assert classifications == []

    def test_accepts_list(self):
        """Should accept Python list."""
        grades = [0.0, 0.05, -0.05]
        classifications = classify_terrain_array(grades)
        assert len(classifications) == 3
