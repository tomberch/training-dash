"""Unit tests for elevation processing module."""

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from trainingdash.domain.elevation import (
    air_density_from_altitude,
    calculate_grade,
    smooth_elevation,
)
from trainingdash.integrations.opentopodata import (
    DEM_BATCH_SIZE,
    fetch_dem_elevation,
)


class TestSmoothElevation:
    """Tests for Savitzky-Golay elevation smoothing."""

    def test_smooth_reduces_noise(self):
        """Smoothing should reduce noise while preserving trend."""
        # Create noisy elevation data with an upward trend
        np.random.seed(42)
        x = np.linspace(0, 100, 50)
        true_elevation = 100 + 0.5 * x  # Linear climb
        noise = np.random.normal(0, 2, len(x))  # ±2m noise
        noisy_elevation = true_elevation + noise

        smoothed = smooth_elevation(noisy_elevation)

        # Smoothed should be closer to true values than noisy
        noisy_error = np.mean(np.abs(noisy_elevation - true_elevation))
        smoothed_error = np.mean(np.abs(smoothed - true_elevation))
        assert smoothed_error < noisy_error

    def test_smooth_preserves_length(self):
        """Output array should have same length as input."""
        elevations = np.array([100, 105, 110, 108, 115, 120, 118, 125])
        smoothed = smooth_elevation(elevations)
        assert len(smoothed) == len(elevations)

    def test_smooth_preserves_major_features(self):
        """Smoothing should preserve peaks and valleys."""
        # Create data with a clear peak
        elevations = np.array([100, 110, 120, 150, 120, 110, 100])
        smoothed = smooth_elevation(elevations, window_length=3)

        # Peak should still be near index 3
        peak_idx = np.argmax(smoothed)
        assert peak_idx == 3

    def test_smooth_empty_array(self):
        """Empty input should return empty output."""
        result = smooth_elevation(np.array([]))
        assert len(result) == 0

    def test_smooth_short_array(self):
        """Arrays shorter than window should still work."""
        elevations = np.array([100, 105])
        result = smooth_elevation(elevations, window_length=11)
        assert len(result) == 2

    def test_smooth_accepts_list(self):
        """Should accept Python list as well as numpy array."""
        elevations = [100, 105, 110, 108, 115, 120]
        result = smooth_elevation(elevations)
        assert isinstance(result, np.ndarray)
        assert len(result) == 6

    def test_smooth_custom_window(self):
        """Custom window length should affect smoothing amount."""
        np.random.seed(42)
        elevations = 100 + np.random.normal(0, 5, 50)

        smooth_small = smooth_elevation(elevations, window_length=5)
        smooth_large = smooth_elevation(elevations, window_length=21)

        # Larger window should produce smoother result (lower variance)
        var_small = np.var(smooth_small)
        var_large = np.var(smooth_large)
        assert var_large < var_small


class TestAirDensityFromAltitude:
    """Tests for ISA air density calculation."""

    def test_sea_level_density(self):
        """Sea level should return ~1.225 kg/m³."""
        rho = air_density_from_altitude(0)
        assert 1.22 < rho < 1.23

    def test_density_decreases_with_altitude(self):
        """Air density should decrease with altitude."""
        rho_0 = air_density_from_altitude(0)
        rho_1000 = air_density_from_altitude(1000)
        rho_2000 = air_density_from_altitude(2000)

        assert rho_1000 < rho_0
        assert rho_2000 < rho_1000

    def test_known_altitude_values(self):
        """Test against ISA reference values."""
        # ISA standard values (approximate)
        # 1000m: ~1.112 kg/m³
        # 2000m: ~1.007 kg/m³
        # 3000m: ~0.909 kg/m³

        assert 1.10 < air_density_from_altitude(1000) < 1.12
        assert 1.00 < air_density_from_altitude(2000) < 1.02
        assert 0.90 < air_density_from_altitude(3000) < 0.92

    def test_high_altitude(self):
        """High altitude (mountain pass) should still work."""
        # Col du Galibier ~2645m
        rho = air_density_from_altitude(2645)
        assert 0.9 < rho < 1.0

    def test_negative_altitude_clamped(self):
        """Negative altitude should be clamped to 0."""
        rho_neg = air_density_from_altitude(-100)
        rho_zero = air_density_from_altitude(0)
        assert rho_neg == rho_zero

    def test_very_high_altitude_clamped(self):
        """Altitude above troposphere should be clamped."""
        rho_high = air_density_from_altitude(15000)
        rho_limit = air_density_from_altitude(11000)
        assert rho_high == rho_limit


class TestFetchDemElevation:
    """Tests for DEM elevation fetching."""

    @pytest.mark.asyncio
    async def test_empty_points_returns_empty(self):
        """Empty input should return empty output."""
        result = await fetch_dem_elevation([])
        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        """Successful API response should return elevations."""
        mock_response = {
            "status": "OK",
            "results": [
                {"elevation": 100.5, "location": {"lat": 37.7749, "lng": -122.4194}},
                {"elevation": 150.2, "location": {"lat": 37.7759, "lng": -122.4184}},
            ],
        }

        with patch("trainingdash.integrations.opentopodata.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Create a mock response object with sync .json() method
            from unittest.mock import Mock

            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_instance.get.return_value = mock_response_obj

            result = await fetch_dem_elevation(
                [
                    (37.7749, -122.4194),
                    (37.7759, -122.4184),
                ]
            )

        assert result == [100.5, 150.2]

    @pytest.mark.asyncio
    async def test_fetch_api_error_returns_none(self):
        """API error should return None for failed points."""
        import httpx

        with patch("trainingdash.integrations.opentopodata.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance
            mock_instance.get.side_effect = httpx.HTTPError("Network error")

            result = await fetch_dem_elevation(
                [
                    (37.7749, -122.4194),
                    (37.7759, -122.4184),
                ]
            )

        assert result == [None, None]

    @pytest.mark.asyncio
    async def test_fetch_batches_large_requests(self):
        """Large requests should be batched."""
        from unittest.mock import Mock

        # Create more points than batch size
        points = [(37.0 + i * 0.001, -122.0) for i in range(DEM_BATCH_SIZE + 50)]

        mock_response_1 = {
            "status": "OK",
            "results": [{"elevation": 100.0}] * DEM_BATCH_SIZE,
        }
        mock_response_2 = {
            "status": "OK",
            "results": [{"elevation": 200.0}] * 50,
        }

        with patch("trainingdash.integrations.opentopodata.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_resp_1 = Mock()
            mock_resp_1.json.return_value = mock_response_1
            mock_resp_1.raise_for_status = Mock()

            mock_resp_2 = Mock()
            mock_resp_2.json.return_value = mock_response_2
            mock_resp_2.raise_for_status = Mock()

            mock_instance.get.side_effect = [mock_resp_1, mock_resp_2]

            result = await fetch_dem_elevation(points)

        # Should have made 2 API calls
        assert mock_instance.get.call_count == 2
        assert len(result) == len(points)

    @pytest.mark.asyncio
    async def test_fetch_uses_bilinear_interpolation(self):
        """Request should specify bilinear interpolation."""
        from unittest.mock import Mock

        mock_response = {
            "status": "OK",
            "results": [{"elevation": 100.0}],
        }

        with patch("trainingdash.integrations.opentopodata.httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_client.return_value.__aenter__.return_value = mock_instance

            mock_response_obj = Mock()
            mock_response_obj.json.return_value = mock_response
            mock_response_obj.raise_for_status = Mock()
            mock_instance.get.return_value = mock_response_obj

            await fetch_dem_elevation([(37.7749, -122.4194)])

            # Check the params included interpolation
            call_kwargs = mock_instance.get.call_args
            assert call_kwargs[1]["params"]["interpolation"] == "bilinear"


class TestCalculateGrade:
    """Tests for grade calculation."""

    def test_flat_terrain(self):
        """Flat terrain should have zero grade."""
        distances = np.array([0, 100, 200, 300])
        elevations = np.array([100, 100, 100, 100])

        grades = calculate_grade(distances, elevations)

        np.testing.assert_array_almost_equal(grades, [0, 0, 0, 0])

    def test_constant_climb(self):
        """Constant climb should have constant positive grade."""
        distances = np.array([0, 100, 200, 300])
        elevations = np.array([100, 110, 120, 130])  # 10m per 100m = 10%

        grades = calculate_grade(distances, elevations)

        # All grades should be 0.1 (10%)
        np.testing.assert_array_almost_equal(grades, [0.1, 0.1, 0.1, 0.1])

    def test_constant_descent(self):
        """Constant descent should have constant negative grade."""
        distances = np.array([0, 100, 200, 300])
        elevations = np.array([130, 120, 110, 100])  # -10m per 100m = -10%

        grades = calculate_grade(distances, elevations)

        np.testing.assert_array_almost_equal(grades, [-0.1, -0.1, -0.1, -0.1])

    def test_varying_grade(self):
        """Varying terrain should have varying grade."""
        distances = np.array([0, 100, 200, 300])
        elevations = np.array([100, 110, 110, 120])  # climb, flat, climb

        grades = calculate_grade(distances, elevations)

        assert grades[1] == pytest.approx(0.1)  # 10% climb
        assert grades[2] == pytest.approx(0.0)  # flat
        assert grades[3] == pytest.approx(0.1)  # 10% climb

    def test_short_array(self):
        """Single point should return zero grade."""
        distances = np.array([0])
        elevations = np.array([100])

        grades = calculate_grade(distances, elevations)

        assert len(grades) == 1
        assert grades[0] == 0

    def test_accepts_list(self):
        """Should accept Python lists."""
        distances = [0, 100, 200]
        elevations = [100, 110, 120]

        grades = calculate_grade(distances, elevations)

        assert isinstance(grades, np.ndarray)
        assert len(grades) == 3
