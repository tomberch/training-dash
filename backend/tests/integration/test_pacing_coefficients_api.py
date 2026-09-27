"""Integration tests for Pacing Coefficients API endpoints."""

from datetime import datetime

import pytest

from trainingdash.domain.pacing_calibration import (
    DEFAULT_CURVATURE_SPEED_COEFFICIENT,
    DEFAULT_DESCENT_POWER_MULTIPLIER,
    DEFAULT_GRADE_POWER_INTERCEPT,
    DEFAULT_GRADE_POWER_SLOPE,
    DEFAULT_MAX_DESCENT_SPEED_MPS,
)
from trainingdash.repositories.postgres.models import Bike, PacingCoefficients


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
async def sample_bike(db_session, seed_user):
    """Create a sample bike for testing."""
    bike = Bike(
        user_id=seed_user.id,
        name="Test Road Bike",
        bike_type="road",
        is_default=False,
    )
    db_session.add(bike)
    await db_session.commit()
    await db_session.refresh(bike)
    return bike


@pytest.fixture
async def user_coefficients(db_session, seed_user):
    """Create user-default pacing coefficients."""
    coefficients = PacingCoefficients(
        user_id=seed_user.id,
        bike_id=None,  # User default
        grade_power_intercept=1.12,
        grade_power_slope=0.038,
        max_descent_speed_mps=17.5,
        descent_power_multiplier=0.35,
        curvature_speed_coefficient=5.0,
        climb_sample_count=1000,
        descent_sample_count=500,
        activity_count=15,
        last_calibrated_at=datetime(2024, 3, 1, 10, 0, 0),  # Naive datetime for DB
    )
    db_session.add(coefficients)
    await db_session.commit()
    await db_session.refresh(coefficients)
    return coefficients


@pytest.fixture
async def bike_coefficients(db_session, seed_user, sample_bike):
    """Create bike-specific pacing coefficients."""
    coefficients = PacingCoefficients(
        user_id=seed_user.id,
        bike_id=sample_bike.id,
        grade_power_intercept=1.15,
        grade_power_slope=0.040,
        max_descent_speed_mps=18.5,
        descent_power_multiplier=0.40,
        curvature_speed_coefficient=5.5,
        climb_sample_count=800,
        descent_sample_count=400,
        activity_count=10,
        last_calibrated_at=datetime(2024, 3, 1, 10, 0, 0),  # Naive datetime for DB
    )
    db_session.add(coefficients)
    await db_session.commit()
    await db_session.refresh(coefficients)
    return coefficients


# =============================================================================
# Test Get All Coefficients
# =============================================================================


class TestGetAllCoefficients:
    """Tests for GET /api/pacing-coefficients."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_coefficients(self, auth_client):
        """Should return None for user_default and empty bikes when no coefficients."""
        response = await auth_client.get("/api/pacing-coefficients")

        assert response.status_code == 200
        data = response.json()

        assert data["user_default"] is None
        assert data["bikes"] == []

    @pytest.mark.asyncio
    async def test_returns_user_default(self, auth_client, user_coefficients):
        """Should return user default coefficients."""
        response = await auth_client.get("/api/pacing-coefficients")

        assert response.status_code == 200
        data = response.json()

        assert data["user_default"] is not None
        assert data["user_default"]["source"] == "user_default"
        assert data["user_default"]["grade_power_intercept"] == 1.12
        assert data["user_default"]["grade_power_slope"] == 0.038

    @pytest.mark.asyncio
    async def test_returns_bike_coefficients(
        self, auth_client, user_coefficients, bike_coefficients, sample_bike
    ):
        """Should return both user default and bike-specific coefficients."""
        response = await auth_client.get("/api/pacing-coefficients")

        assert response.status_code == 200
        data = response.json()

        assert data["user_default"] is not None
        assert len(data["bikes"]) == 1

        bike_coef = data["bikes"][0]
        assert bike_coef["source"] == "bike"
        assert bike_coef["bike_id"] == sample_bike.id
        assert bike_coef["bike_name"] == "Test Road Bike"
        assert bike_coef["grade_power_intercept"] == 1.15

    @pytest.mark.asyncio
    async def test_includes_confidence_level(self, auth_client, user_coefficients):
        """Should include confidence level and note."""
        response = await auth_client.get("/api/pacing-coefficients")

        assert response.status_code == 200
        data = response.json()

        assert "confidence_level" in data["user_default"]
        assert "confidence_note" in data["user_default"]
        # With 1000 climb samples and 500 descent samples, should be at least medium
        assert data["user_default"]["confidence_level"] in ["high", "medium"]

    @pytest.mark.asyncio
    async def test_requires_auth(self, app_client):
        """Should require authentication."""
        response = await app_client.get("/api/pacing-coefficients")
        assert response.status_code == 401


# =============================================================================
# Test Get Effective Coefficients
# =============================================================================


class TestGetEffectiveCoefficients:
    """Tests for GET /api/pacing-coefficients/effective."""

    @pytest.mark.asyncio
    async def test_returns_global_defaults_when_no_coefficients(self, auth_client):
        """Should return global defaults when no coefficients exist."""
        response = await auth_client.get("/api/pacing-coefficients/effective")

        assert response.status_code == 200
        data = response.json()

        assert data["source"] == "global_default"
        assert data["grade_power_intercept"] == DEFAULT_GRADE_POWER_INTERCEPT
        assert data["grade_power_slope"] == DEFAULT_GRADE_POWER_SLOPE
        assert data["max_descent_speed_mps"] == DEFAULT_MAX_DESCENT_SPEED_MPS
        assert data["descent_power_multiplier"] == DEFAULT_DESCENT_POWER_MULTIPLIER
        assert data["curvature_speed_coefficient"] == DEFAULT_CURVATURE_SPEED_COEFFICIENT
        assert data["confidence_level"] == "default"

    @pytest.mark.asyncio
    async def test_returns_user_default_when_exists(self, auth_client, user_coefficients):
        """Should return user default when no bike specified."""
        response = await auth_client.get("/api/pacing-coefficients/effective")

        assert response.status_code == 200
        data = response.json()

        assert data["source"] == "user_default"
        assert data["grade_power_intercept"] == 1.12

    @pytest.mark.asyncio
    async def test_returns_bike_coefficients_when_bike_specified(
        self, auth_client, user_coefficients, bike_coefficients, sample_bike
    ):
        """Should return bike-specific coefficients when bike_id specified."""
        response = await auth_client.get(
            "/api/pacing-coefficients/effective",
            params={"bike_id": sample_bike.id},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["source"] == "bike"
        assert data["bike_id"] == sample_bike.id
        assert data["grade_power_intercept"] == 1.15

    @pytest.mark.asyncio
    async def test_falls_back_to_user_default_for_uncalibrated_bike(
        self, auth_client, user_coefficients, sample_bike
    ):
        """Should fall back to user default when bike has no coefficients."""
        # sample_bike exists but has no coefficients (bike_coefficients not created)
        response = await auth_client.get(
            "/api/pacing-coefficients/effective",
            params={"bike_id": sample_bike.id},
        )

        assert response.status_code == 200
        data = response.json()

        # Should fall back to user default
        assert data["source"] == "user_default"
        assert data["grade_power_intercept"] == 1.12

    @pytest.mark.asyncio
    async def test_includes_speed_in_kmh(self, auth_client, user_coefficients):
        """Should include max_descent_speed_kmh alongside mps."""
        response = await auth_client.get("/api/pacing-coefficients/effective")

        assert response.status_code == 200
        data = response.json()

        assert "max_descent_speed_mps" in data
        assert "max_descent_speed_kmh" in data
        # km/h = m/s * 3.6
        expected_kmh = data["max_descent_speed_mps"] * 3.6
        assert data["max_descent_speed_kmh"] == pytest.approx(expected_kmh)

    @pytest.mark.asyncio
    async def test_requires_auth(self, app_client):
        """Should require authentication."""
        response = await app_client.get("/api/pacing-coefficients/effective")
        assert response.status_code == 401


# =============================================================================
# Test Calibration
# =============================================================================


class TestCalibrateCoefficients:
    """Tests for POST /api/pacing-coefficients/calibrate."""

    @pytest.mark.asyncio
    async def test_calibrate_returns_insufficient_data_message(self, auth_client):
        """Should return appropriate message when insufficient data."""
        response = await auth_client.post("/api/pacing-coefficients/calibrate")

        assert response.status_code == 200
        data = response.json()

        # With no activities, calibration should fail
        assert data["success"] is False
        assert data["coefficients_updated"] is False
        assert "Need at least" in data["message"] or "Insufficient" in data["message"]

    @pytest.mark.asyncio
    async def test_calibrate_for_specific_bike(self, auth_client, sample_bike):
        """Should allow calibration for specific bike."""
        response = await auth_client.post(
            "/api/pacing-coefficients/calibrate",
            params={"bike_id": sample_bike.id},
        )

        assert response.status_code == 200
        data = response.json()

        # Will fail due to no data, but shouldn't error
        assert "success" in data
        assert "activities_processed" in data
        assert "climb_samples" in data
        assert "descent_samples" in data

    @pytest.mark.asyncio
    async def test_calibrate_requires_auth(self, app_client):
        """Should require authentication."""
        response = await app_client.post("/api/pacing-coefficients/calibrate")
        assert response.status_code == 401


class TestCalibrateAllBikes:
    """Tests for POST /api/pacing-coefficients/calibrate-all."""

    @pytest.mark.asyncio
    async def test_calibrate_all_returns_dict(self, auth_client, sample_bike):
        """Should return dict with results for user_default and each bike."""
        response = await auth_client.post("/api/pacing-coefficients/calibrate-all")

        assert response.status_code == 200
        data = response.json()

        # Should have at least user_default key
        assert "user_default" in data
        assert "success" in data["user_default"]

    @pytest.mark.asyncio
    async def test_calibrate_all_requires_auth(self, app_client):
        """Should require authentication."""
        response = await app_client.post("/api/pacing-coefficients/calibrate-all")
        assert response.status_code == 401


# =============================================================================
# Test Response Model Fields
# =============================================================================


class TestCoefficientsResponseModel:
    """Tests for response model completeness."""

    @pytest.mark.asyncio
    async def test_effective_response_has_all_fields(self, auth_client, user_coefficients):
        """Should include all documented response fields."""
        response = await auth_client.get("/api/pacing-coefficients/effective")

        assert response.status_code == 200
        data = response.json()

        # Source info
        assert "source" in data
        assert "bike_id" in data
        assert "bike_name" in data

        # Climb coefficients
        assert "grade_power_intercept" in data
        assert "grade_power_slope" in data

        # Descent coefficients
        assert "max_descent_speed_mps" in data
        assert "max_descent_speed_kmh" in data
        assert "descent_power_multiplier" in data
        assert "curvature_speed_coefficient" in data

        # Confidence metrics
        assert "climb_sample_count" in data
        assert "descent_sample_count" in data
        assert "activity_count" in data
        assert "last_calibrated_at" in data

        # Confidence level
        assert "confidence_level" in data
        assert "confidence_note" in data

    @pytest.mark.asyncio
    async def test_terrain_behavior_field(self, auth_client, user_coefficients):
        """Should include terrain_behavior field (may be null)."""
        response = await auth_client.get("/api/pacing-coefficients/effective")

        assert response.status_code == 200
        data = response.json()

        # terrain_behavior should be present (can be null)
        assert "terrain_behavior" in data
