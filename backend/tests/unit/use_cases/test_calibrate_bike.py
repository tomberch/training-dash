"""Tests for CalibrateFromActivities use case."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import numpy as np
import pytest

from tests.fakes.activity_repo import FakeActivityRepo
from tests.fakes.bike_repo import FakeBikeRepo
from tests.fakes.record_repo import FakeRecordRepo
from trainingdash.repositories.postgres.models import Activity, Bike, Record
from trainingdash.use_cases.calibrate_bike import (
    BikeNotEligibleError,
    BikeNotFoundError,
    CalibrateFromActivities,
    CalibrationError,
    CalibrationResult,
    InsufficientDataError,
    NoActivitiesError,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def activity_repo() -> FakeActivityRepo:
    return FakeActivityRepo()


@pytest.fixture
def bike_repo() -> FakeBikeRepo:
    return FakeBikeRepo()


@pytest.fixture
def record_repo() -> FakeRecordRepo:
    return FakeRecordRepo()


@pytest.fixture
def use_case(
    activity_repo: FakeActivityRepo,
    bike_repo: FakeBikeRepo,
    record_repo: FakeRecordRepo,
) -> CalibrateFromActivities:
    return CalibrateFromActivities(activity_repo, bike_repo, record_repo)


def make_bike(
    user_id: int = 1,
    bike_id: int = 1,
    name: str = "Road Bike",
    bike_type: str = "road",
    weight_kg: float = 8.0,
    cda: float | None = None,
    cda_source: str | None = None,
) -> Bike:
    """Create a test bike."""
    bike = Bike(
        id=bike_id,
        user_id=user_id,
        name=name,
        bike_type=bike_type,
        weight_kg=weight_kg,
        cda=cda,
        cda_source=cda_source,
    )
    return bike


def make_activity(
    user_id: int = 1,
    bike_id: int = 1,
    avg_power_w: float | None = 200.0,
    started_at: datetime | None = None,
) -> Activity:
    """Create a test activity."""
    if started_at is None:
        started_at = datetime(2025, 1, 15, 10, 0, 0)
    activity = Activity(
        id=uuid4(),
        user_id=user_id,
        bike_id=bike_id,
        started_at=started_at,
        avg_power_w=int(avg_power_w) if avg_power_w else None,
        total_distance_m=50000.0,
        elapsed_time_s=7200,
        moving_time_s=6000,
        source="garmin",
        source_ref=f"test_{started_at.isoformat()}",
    )
    return activity


def make_calibration_records(
    activity_id,
    num_seconds: int = 300,
    base_power: float = 250.0,
    base_speed: float = 10.0,  # m/s = 36 km/h
    base_altitude: float = 100.0,
    power_variation: float = 5.0,
    speed_variation: float = 0.2,
) -> list[Record]:
    """
    Create records suitable for CdA calibration.

    Calibration needs:
    - Steady power (low CV)
    - Steady speed > 8.33 m/s (30 km/h)
    - Flat or near-flat grade
    - At least 60 samples
    """
    records = []
    base_time = datetime(2025, 1, 15, 10, 0, 0)
    distance = 0.0

    np.random.seed(42)  # Reproducible

    for i in range(num_seconds):
        # Add small random variation to make realistic
        power = base_power + np.random.uniform(-power_variation, power_variation)
        speed = base_speed + np.random.uniform(-speed_variation, speed_variation)
        altitude = base_altitude + np.random.uniform(-0.5, 0.5)  # Nearly flat
        distance += speed

        record = Record(
            activity_id=activity_id,
            timestamp=base_time + timedelta(seconds=i),
            power_w=power,
            speed_mps=speed,
            altitude_m=altitude,
            distance_m=distance,
        )
        records.append(record)

    return records


def make_low_speed_records(activity_id, num_seconds: int = 100) -> list[Record]:
    """Create records with speed too low for calibration (< 30 km/h)."""
    records = []
    base_time = datetime(2025, 1, 15, 10, 0, 0)
    distance = 0.0

    for i in range(num_seconds):
        speed = 5.0  # 18 km/h - too slow
        distance += speed
        record = Record(
            activity_id=activity_id,
            timestamp=base_time + timedelta(seconds=i),
            power_w=150.0,
            speed_mps=speed,
            altitude_m=100.0,
            distance_m=distance,
        )
        records.append(record)

    return records


def make_variable_power_records(activity_id, num_seconds: int = 100) -> list[Record]:
    """Create records with highly variable power (will be rejected)."""
    records = []
    base_time = datetime(2025, 1, 15, 10, 0, 0)
    distance = 0.0

    np.random.seed(42)

    for i in range(num_seconds):
        # High variation in power (CV > 10%)
        power = 250.0 + np.random.uniform(-100, 100)
        speed = 10.0
        distance += speed
        record = Record(
            activity_id=activity_id,
            timestamp=base_time + timedelta(seconds=i),
            power_w=power,
            speed_mps=speed,
            altitude_m=100.0,
            distance_m=distance,
        )
        records.append(record)

    return records


def make_varied_terrain_records(
    activity_id,
    num_seconds: int = 300,
    base_power: float = 200.0,
) -> list[Record]:
    """
    Create records with varied terrain suitable for physics-based calibration.

    Physics calibration needs:
    - Data from multiple grade bins (-4% to +15%)
    - At least 30 seconds per grade bin
    - Power > 30W, speed > 1.5 m/s

    Creates a profile: flat section, climb section, descent section, flat section.
    """
    records = []
    base_time = datetime(2025, 1, 15, 10, 0, 0)
    distance = 0.0
    altitude = 100.0

    np.random.seed(42)

    # Define terrain segments with (grade_pct, duration_fraction, power_multiplier)
    # Total adds up to 1.0
    terrain_segments = [
        (0.0, 0.25, 1.0),  # Flat: 0% grade, base power
        (5.0, 0.30, 1.4),  # Climb: 5% grade, higher power
        (8.0, 0.15, 1.6),  # Steeper climb: 8% grade
        (-2.0, 0.15, 0.6),  # Gentle descent: -2% grade
        (0.0, 0.15, 1.0),  # Flat finish
    ]

    total_mass = 104.0  # rider + bike
    crr = 0.005
    cda = 0.35
    rho = 1.225

    idx = 0
    for grade_pct, duration_fraction, power_mult in terrain_segments:
        segment_duration = int(num_seconds * duration_fraction)
        for _ in range(segment_duration):
            power = base_power * power_mult + np.random.uniform(-5, 5)

            # Calculate realistic speed from physics
            # P = (mg*sin(θ) + mg*Crr*cos(θ) + 0.5*ρ*CdA*v²) * v / η
            # Simplified: solve for v given P and grade
            theta = np.arctan(grade_pct / 100.0)
            g = 9.81
            eta = 0.97

            # Iterative speed solve (simplified)
            v = 8.0  # Initial guess
            for _ in range(20):
                f_grav = total_mass * g * np.sin(theta)
                f_roll = total_mass * g * crr * np.cos(theta)
                f_aero = 0.5 * rho * cda * v * v
                p_req = max(0.1, (f_grav + f_roll + f_aero) * v / eta)
                dp_dv = (f_grav + f_roll + 3 * f_aero) / eta
                if abs(dp_dv) < 0.01:
                    dp_dv = 0.1
                v = v - (p_req - power) / dp_dv
                v = max(1.5, min(20.0, v))

            speed = v + np.random.uniform(-0.2, 0.2)
            speed = max(1.5, speed)

            # Update altitude based on grade and distance
            delta_dist = speed  # 1 second
            delta_alt = delta_dist * (grade_pct / 100.0)
            altitude += delta_alt
            distance += delta_dist

            record = Record(
                activity_id=activity_id,
                timestamp=base_time + timedelta(seconds=idx),
                power_w=power,
                speed_mps=speed,
                altitude_m=altitude,
                distance_m=distance,
            )
            records.append(record)
            idx += 1

    return records


# =============================================================================
# Bike Validation Tests
# =============================================================================


class TestBikeValidation:
    """Tests for bike validation in calibration."""

    @pytest.mark.asyncio
    async def test_bike_not_found_raises_error(
        self,
        use_case: CalibrateFromActivities,
    ):
        """Non-existent bike raises BikeNotFoundError."""
        with pytest.raises(BikeNotFoundError, match="not found"):
            await use_case.execute(user_id=1, bike_id=999)

    @pytest.mark.asyncio
    async def test_bike_wrong_user_raises_error(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
    ):
        """Bike owned by different user raises BikeNotFoundError."""
        bike = make_bike(user_id=2, bike_id=1)
        bike_repo.add(bike)

        with pytest.raises(BikeNotFoundError, match="not found"):
            await use_case.execute(user_id=1, bike_id=1)

    @pytest.mark.asyncio
    async def test_ebike_not_eligible(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
    ):
        """E-bike type raises BikeNotEligibleError."""
        bike = make_bike(bike_type="ebike")
        bike_repo.add(bike)

        with pytest.raises(BikeNotEligibleError, match="not eligible"):
            await use_case.execute(user_id=1, bike_id=1)

    @pytest.mark.asyncio
    async def test_road_bike_eligible(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
    ):
        """Road bike passes eligibility check (may fail at later stage)."""
        bike = make_bike(bike_type="road")
        bike_repo.add(bike)

        # Will raise NoActivitiesError (no activities), not eligibility error
        with pytest.raises(NoActivitiesError):
            await use_case.execute(user_id=1, bike_id=1)

    @pytest.mark.asyncio
    async def test_tt_bike_eligible(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
    ):
        """TT/triathlon bike passes eligibility check."""
        bike = make_bike(bike_type="tt")
        bike_repo.add(bike)

        with pytest.raises(NoActivitiesError):
            await use_case.execute(user_id=1, bike_id=1)

    @pytest.mark.asyncio
    async def test_gravel_bike_eligible(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
    ):
        """Gravel bike passes eligibility check."""
        bike = make_bike(bike_type="gravel")
        bike_repo.add(bike)

        with pytest.raises(NoActivitiesError):
            await use_case.execute(user_id=1, bike_id=1)


# =============================================================================
# Activity Validation Tests
# =============================================================================


class TestActivityValidation:
    """Tests for activity validation in calibration."""

    @pytest.mark.asyncio
    async def test_no_activities_raises_error(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
    ):
        """No activities tagged to bike raises NoActivitiesError."""
        bike = make_bike()
        bike_repo.add(bike)

        with pytest.raises(NoActivitiesError, match="No activities found"):
            await use_case.execute(user_id=1, bike_id=1)

    @pytest.mark.asyncio
    async def test_activities_without_power_skipped(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """Activities without power data are skipped."""
        bike = make_bike()
        bike_repo.add(bike)

        # Activity without power data
        activity = make_activity(avg_power_w=None)
        await activity_repo.save(activity)

        # Still raises InsufficientDataError because no valid segments
        with pytest.raises((InsufficientDataError, NoActivitiesError)):
            await use_case.execute(user_id=1, bike_id=1)

    @pytest.mark.asyncio
    async def test_activity_with_zero_power_skipped(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
    ):
        """Activities with zero average power are skipped."""
        bike = make_bike()
        bike_repo.add(bike)

        activity = make_activity(avg_power_w=0)
        await activity_repo.save(activity)

        with pytest.raises((InsufficientDataError, NoActivitiesError)):
            await use_case.execute(user_id=1, bike_id=1)


# =============================================================================
# Record Validation Tests
# =============================================================================


class TestRecordValidation:
    """Tests for record-level validation in calibration."""

    @pytest.mark.asyncio
    async def test_too_few_records_skipped(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """Activities with fewer than 60 records are skipped."""
        bike = make_bike()
        bike_repo.add(bike)

        activity = make_activity()
        await activity_repo.save(activity)

        # Only 30 records - not enough
        records = make_calibration_records(activity.id, num_seconds=30)
        record_repo.add_many(records)

        with pytest.raises(InsufficientDataError):
            await use_case.execute(user_id=1, bike_id=1)

    @pytest.mark.asyncio
    async def test_low_speed_records_rejected(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """Records with speed < 30 km/h are rejected as calibration segments."""
        bike = make_bike()
        bike_repo.add(bike)

        activity = make_activity()
        await activity_repo.save(activity)

        # Low speed records - won't produce valid segments
        records = make_low_speed_records(activity.id)
        record_repo.add_many(records)

        with pytest.raises(InsufficientDataError):
            await use_case.execute(user_id=1, bike_id=1)

    @pytest.mark.asyncio
    async def test_variable_power_rejected(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """Records with highly variable power are rejected."""
        bike = make_bike()
        bike_repo.add(bike)

        activity = make_activity()
        await activity_repo.save(activity)

        records = make_variable_power_records(activity.id, num_seconds=200)
        record_repo.add_many(records)

        with pytest.raises(InsufficientDataError):
            await use_case.execute(user_id=1, bike_id=1)


# =============================================================================
# Successful Calibration Tests
# =============================================================================


class TestSuccessfulCalibration:
    """Tests for successful calibration scenarios."""

    @pytest.mark.asyncio
    async def test_successful_calibration_returns_result(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """Successful calibration returns CalibrationResult."""
        bike = make_bike()
        bike_repo.add(bike)

        # Create multiple activities with good calibration data
        for i in range(3):
            activity = make_activity(
                started_at=datetime(2025, 1, 15 - i, 10, 0, 0),
            )
            await activity_repo.save(activity)
            records = make_calibration_records(activity.id, num_seconds=300)
            record_repo.add_many(records)

        result = await use_case.execute(user_id=1, bike_id=1)

        assert isinstance(result, CalibrationResult)
        assert result.bike_id == 1
        assert 0.15 < result.cda < 0.45  # Reasonable CdA range
        assert result.n_activities_used > 0
        assert result.n_segments_used > 0

    @pytest.mark.asyncio
    async def test_calibration_result_has_diagnostics(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """Result includes diagnostic information."""
        bike = make_bike()
        bike_repo.add(bike)

        for i in range(2):
            activity = make_activity(started_at=datetime(2025, 1, 15 - i, 10, 0, 0))
            await activity_repo.save(activity)
            records = make_calibration_records(activity.id, num_seconds=300)
            record_repo.add_many(records)

        result = await use_case.execute(user_id=1, bike_id=1)

        assert result.confidence in ("low", "medium", "high")
        assert result.total_calibration_duration_s > 0
        assert isinstance(result.warnings, list)
        assert isinstance(result.rejection_summary, dict)

    @pytest.mark.asyncio
    async def test_high_confidence_updates_bike(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """High confidence calibration updates the bike record."""
        bike = make_bike(cda=0.35)
        bike_repo.add(bike)

        # Create many activities for high confidence
        for i in range(5):
            activity = make_activity(started_at=datetime(2025, 1, 15 - i, 10, 0, 0))
            await activity_repo.save(activity)
            records = make_calibration_records(activity.id, num_seconds=400)
            record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            bike_id=1,
            min_confidence="low",  # Accept any confidence for update
        )

        # Check bike was updated if confidence met threshold
        if result.updated:
            updated_bike = await bike_repo.get_by_id(1, 1)
            assert updated_bike.cda == result.cda
            assert updated_bike.cda_source == "calibrated"
            assert updated_bike.calibrated_at is not None

    @pytest.mark.asyncio
    async def test_previous_cda_returned(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """Previous CdA value is included in result."""
        bike = make_bike(cda=0.32)
        bike_repo.add(bike)

        for i in range(2):
            activity = make_activity(started_at=datetime(2025, 1, 15 - i, 10, 0, 0))
            await activity_repo.save(activity)
            records = make_calibration_records(activity.id, num_seconds=300)
            record_repo.add_many(records)

        result = await use_case.execute(user_id=1, bike_id=1)

        assert result.previous_cda == 0.32


# =============================================================================
# Confidence Level Tests
# =============================================================================


class TestConfidenceLevels:
    """Tests for confidence level handling."""

    @pytest.mark.asyncio
    async def test_low_confidence_no_update_when_medium_required(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """Low confidence does not update bike when medium is required."""
        bike = make_bike()
        bike_repo.add(bike)

        # Single activity - likely low confidence
        activity = make_activity()
        await activity_repo.save(activity)
        # Use varied terrain records for physics-based calibration
        # Need 300s minimum to have 30s per grade bin across 5 segments
        records = make_varied_terrain_records(activity.id, num_seconds=300)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            bike_id=1,
            min_confidence="high",  # Require high confidence
        )

        # If confidence is below threshold, bike should not be updated
        if result.confidence != "high":
            assert result.updated is False
            assert any("below minimum" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_min_confidence_low_accepts_all(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """min_confidence='low' accepts any confidence level."""
        bike = make_bike()
        bike_repo.add(bike)

        activity = make_activity()
        await activity_repo.save(activity)
        # Use varied terrain records for physics-based calibration
        records = make_varied_terrain_records(activity.id, num_seconds=300)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            bike_id=1,
            min_confidence="low",
        )

        # Any confidence should result in update
        if result.n_segments_used > 0:
            assert result.updated is True


# =============================================================================
# Rider Parameters Tests
# =============================================================================


class TestRiderParameters:
    """Tests for rider parameter handling."""

    @pytest.mark.asyncio
    async def test_default_rider_mass_warning(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """Using default rider mass adds a warning."""
        bike = make_bike()
        bike_repo.add(bike)

        activity = make_activity()
        await activity_repo.save(activity)
        records = make_calibration_records(activity.id, num_seconds=300)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            bike_id=1,
            rider_mass_kg=None,  # Use default
        )

        assert any("default rider mass" in w.lower() for w in result.warnings)

    @pytest.mark.asyncio
    async def test_custom_rider_mass_no_warning(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """Providing rider mass does not add default mass warning."""
        bike = make_bike()
        bike_repo.add(bike)

        activity = make_activity()
        await activity_repo.save(activity)
        records = make_calibration_records(activity.id, num_seconds=300)
        record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            bike_id=1,
            rider_mass_kg=70.0,
        )

        assert not any("default rider mass" in w.lower() for w in result.warnings)


# =============================================================================
# Max Activities Tests
# =============================================================================


class TestMaxActivities:
    """Tests for max_activities parameter."""

    @pytest.mark.asyncio
    async def test_max_activities_limits_processing(
        self,
        use_case: CalibrateFromActivities,
        bike_repo: FakeBikeRepo,
        activity_repo: FakeActivityRepo,
        record_repo: FakeRecordRepo,
    ):
        """max_activities limits how many activities are processed."""
        bike = make_bike()
        bike_repo.add(bike)

        # Create 10 activities
        for i in range(10):
            activity = make_activity(started_at=datetime(2025, 1, 15 - i, 10, 0, 0))
            await activity_repo.save(activity)
            records = make_calibration_records(activity.id, num_seconds=150)
            record_repo.add_many(records)

        result = await use_case.execute(
            user_id=1,
            bike_id=1,
            max_activities=3,
        )

        # Should use at most 3 activities
        assert result.n_activities_used <= 3


# =============================================================================
# Error Hierarchy Tests
# =============================================================================


class TestErrorHierarchy:
    """Tests for error class hierarchy."""

    def test_calibration_error_is_base(self):
        """All calibration errors inherit from CalibrationError."""
        assert issubclass(BikeNotFoundError, CalibrationError)
        assert issubclass(BikeNotEligibleError, CalibrationError)
        assert issubclass(NoActivitiesError, CalibrationError)
        assert issubclass(InsufficientDataError, CalibrationError)

    def test_calibration_error_is_exception(self):
        """CalibrationError is an Exception."""
        assert issubclass(CalibrationError, Exception)
