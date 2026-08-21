"""Integration tests for PostgresRacePlanRepo."""

from decimal import Decimal

import pytest

from trainingdash.repositories.postgres.models import RaceCourse, RacePlan, User
from trainingdash.repositories.postgres.race_plan_repo import PostgresRacePlanRepo


@pytest.fixture
async def seed_course(db_session, seed_user):
    """Create a race course for testing."""
    wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 200, 2 2 150)"
    course = RaceCourse(
        user_id=seed_user.id,
        name="Test Course",
        source_type="gpx",
        distance_m=10000.0,
        elevation_gain_m=100.0,
        elevation_loss_m=50.0,
        geometry=wkt,
    )
    db_session.add(course)
    await db_session.commit()
    await db_session.refresh(course)
    return course


def make_plan(user_id: int, course_id: int, name: str = "Test Plan") -> RacePlan:
    """Create a RacePlan instance with required fields."""
    return RacePlan(
        user_id=user_id,
        course_id=course_id,
        name=name,
        rider_weight_kg=Decimal("75.00"),
        ftp_watts=280,
        cp_watts=270,
        w_prime_joules=20000,
        bike_weight_kg=Decimal("8.50"),
        cda=Decimal("0.320"),
        crr=Decimal("0.0040"),
        target_intensity=Decimal("0.85"),
        optimization_method="heuristic",
        total_time_s=3600.0,
        total_distance_m=10000.0,
        avg_power_w=238.0,
        normalized_power_w=245.0,
        intensity_factor=Decimal("0.88"),
        segment_targets=[
            {"segment_idx": 0, "power_w": 240, "time_s": 1800, "speed_mps": 8.5},
            {"segment_idx": 1, "power_w": 235, "time_s": 1800, "speed_mps": 9.0},
        ],
        wbal_min=8000.0,
        wbal_min_distance_m=5500.0,
    )


class TestRacePlanRepoGetById:
    """Tests for RacePlanRepo.get_by_id."""

    @pytest.mark.asyncio
    async def test_get_existing_plan(self, db_session, seed_user, seed_course):
        """Can retrieve a plan by ID."""
        plan = make_plan(seed_user.id, seed_course.id)
        db_session.add(plan)
        await db_session.commit()
        await db_session.refresh(plan)

        repo = PostgresRacePlanRepo(db_session)
        result = await repo.get_by_id(plan.id, seed_user.id)

        assert result is not None
        assert result.id == plan.id
        assert result.name == "Test Plan"
        assert result.ftp_watts == 280

    @pytest.mark.asyncio
    async def test_get_nonexistent_plan(self, db_session, seed_user):
        """Returns None for nonexistent plan."""
        repo = PostgresRacePlanRepo(db_session)
        result = await repo.get_by_id(99999, seed_user.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_other_users_plan(self, db_session, seed_user, seed_course):
        """Cannot access another user's plan."""
        other_user = User(email="other-plan-test@example.com", password_hash="x")
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        plan = make_plan(other_user.id, seed_course.id)
        db_session.add(plan)
        await db_session.commit()

        repo = PostgresRacePlanRepo(db_session)
        result = await repo.get_by_id(plan.id, seed_user.id)
        assert result is None


class TestRacePlanRepoGetByCourse:
    """Tests for RacePlanRepo.get_by_course."""

    @pytest.mark.asyncio
    async def test_get_plans_for_course(self, db_session, seed_user, seed_course):
        """Can list plans for a course."""
        for i in range(3):
            plan = make_plan(seed_user.id, seed_course.id, f"Plan {i}")
            db_session.add(plan)
        await db_session.commit()

        repo = PostgresRacePlanRepo(db_session)
        plans = await repo.get_by_course(seed_course.id, seed_user.id)

        assert len(plans) == 3
        names = {p.name for p in plans}
        assert names == {"Plan 0", "Plan 1", "Plan 2"}

    @pytest.mark.asyncio
    async def test_get_plans_for_course_empty(self, db_session, seed_user, seed_course):
        """Returns empty list for course with no plans."""
        repo = PostgresRacePlanRepo(db_session)
        plans = await repo.get_by_course(seed_course.id, seed_user.id)
        assert plans == []


class TestRacePlanRepoGetByUser:
    """Tests for RacePlanRepo.get_by_user."""

    @pytest.mark.asyncio
    async def test_get_user_plans(self, db_session, seed_user, seed_course):
        """Can list plans for a user."""
        for i in range(5):
            plan = make_plan(seed_user.id, seed_course.id, f"User Plan {i}")
            db_session.add(plan)
        await db_session.commit()

        repo = PostgresRacePlanRepo(db_session)
        plans = await repo.get_by_user(seed_user.id, limit=10)

        assert len(plans) == 5

    @pytest.mark.asyncio
    async def test_get_user_plans_respects_limit(self, db_session, seed_user, seed_course):
        """Respects limit parameter."""
        for i in range(5):
            plan = make_plan(seed_user.id, seed_course.id, f"Limited Plan {i}")
            db_session.add(plan)
        await db_session.commit()

        repo = PostgresRacePlanRepo(db_session)
        plans = await repo.get_by_user(seed_user.id, limit=3)

        assert len(plans) == 3

    @pytest.mark.asyncio
    async def test_get_user_plans_empty(self, db_session):
        """Returns empty list for user with no plans."""
        user = User(email="no-plans@example.com", password_hash="x")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        repo = PostgresRacePlanRepo(db_session)
        plans = await repo.get_by_user(user.id)
        assert plans == []


class TestRacePlanRepoSave:
    """Tests for RacePlanRepo.save."""

    @pytest.mark.asyncio
    async def test_save_new_plan(self, db_session, seed_user, seed_course):
        """Can save a new plan."""
        plan = make_plan(seed_user.id, seed_course.id, "New Plan")

        repo = PostgresRacePlanRepo(db_session)
        saved = await repo.save(plan)

        assert saved.id is not None
        assert saved.name == "New Plan"
        assert saved.created_at is not None
        assert saved.segment_targets is not None
        assert len(saved.segment_targets) == 2

    @pytest.mark.asyncio
    async def test_save_plan_jsonb_serializes_correctly(self, db_session, seed_user, seed_course):
        """JSONB segment_targets serializes and deserializes correctly."""
        plan = RacePlan(
            user_id=seed_user.id,
            course_id=seed_course.id,
            name="JSONB Test",
            rider_weight_kg=Decimal("70.00"),
            ftp_watts=250,
            cda=Decimal("0.300"),
            crr=Decimal("0.0045"),
            total_time_s=7200.0,
            total_distance_m=50000.0,
            avg_power_w=200.0,
            segment_targets=[
                {"segment_idx": 0, "power_w": 220, "time_s": 3600, "speed_mps": 10.0},
                {"segment_idx": 1, "power_w": 180, "time_s": 3600, "speed_mps": 12.0},
            ],
        )

        repo = PostgresRacePlanRepo(db_session)
        saved = await repo.save(plan)

        # Re-fetch to ensure JSONB round-trips correctly
        fetched = await repo.get_by_id(saved.id, seed_user.id)
        assert fetched.segment_targets[0]["power_w"] == 220
        assert fetched.segment_targets[1]["speed_mps"] == 12.0


class TestRacePlanRepoDelete:
    """Tests for RacePlanRepo.delete."""

    @pytest.mark.asyncio
    async def test_delete_existing_plan(self, db_session, seed_user, seed_course):
        """Can delete a plan."""
        plan = make_plan(seed_user.id, seed_course.id, "To Delete")
        db_session.add(plan)
        await db_session.commit()
        plan_id = plan.id

        repo = PostgresRacePlanRepo(db_session)
        result = await repo.delete(plan_id, seed_user.id)

        assert result is True

        # Verify deleted
        fetched = await repo.get_by_id(plan_id, seed_user.id)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_plan(self, db_session, seed_user):
        """Returns False for nonexistent plan."""
        repo = PostgresRacePlanRepo(db_session)
        result = await repo.delete(99999, seed_user.id)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_other_users_plan(self, db_session, seed_user, seed_course):
        """Cannot delete another user's plan."""
        other_user = User(email="delete-other-plan@example.com", password_hash="x")
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        plan = make_plan(other_user.id, seed_course.id, "Other's Plan")
        db_session.add(plan)
        await db_session.commit()

        repo = PostgresRacePlanRepo(db_session)
        result = await repo.delete(plan.id, seed_user.id)
        assert result is False
