"""Integration tests for Bike model and Activity.bike_id relationship."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from trainingdash.repositories.postgres.models import Activity, Bike, User


class TestBikeModel:
    """Tests for Bike model CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_bike(self, db_session, seed_user):
        """Can create a bike with required fields."""
        bike = Bike(
            user_id=seed_user.id,
            name="Canyon Aeroad",
            bike_type="road",
        )
        db_session.add(bike)
        await db_session.commit()
        await db_session.refresh(bike)

        assert bike.id is not None
        assert bike.name == "Canyon Aeroad"
        assert bike.bike_type == "road"
        assert bike.total_distance_m == 0
        assert bike.is_default is False
        assert bike.retired_at is None

    @pytest.mark.asyncio
    async def test_create_bike_with_all_fields(self, db_session, seed_user):
        """Can create a bike with all optional fields."""
        bike = Bike(
            user_id=seed_user.id,
            name="Cervelo P5",
            bike_type="tt",
            model_year=2023,
            weight_kg=Decimal("7.50"),
            cda=Decimal("0.240"),
            crr=Decimal("0.0030"),
            cda_source="manual",
            crr_source="default",
            is_default=True,
        )
        db_session.add(bike)
        await db_session.commit()
        await db_session.refresh(bike)

        assert bike.model_year == 2023
        assert bike.weight_kg == Decimal("7.50")
        assert bike.cda == Decimal("0.240")
        assert bike.crr == Decimal("0.0030")
        assert bike.cda_source == "manual"
        assert bike.crr_source == "default"
        assert bike.is_default is True

    @pytest.mark.asyncio
    async def test_bike_types_valid(self, db_session, seed_user):
        """All valid bike types can be created."""
        valid_types = ["road", "tt", "gravel", "mtb", "ebike"]
        for bike_type in valid_types:
            bike = Bike(
                user_id=seed_user.id,
                name=f"Test {bike_type}",
                bike_type=bike_type,
            )
            db_session.add(bike)
        await db_session.commit()

        result = await db_session.execute(select(Bike).where(Bike.user_id == seed_user.id))
        bikes = result.scalars().all()
        assert len(bikes) >= 5  # may include bikes from other tests in session

    @pytest.mark.asyncio
    async def test_bike_invalid_type_rejected(self, db_session, seed_user):
        """Invalid bike type is rejected by database constraint."""
        bike = Bike(
            user_id=seed_user.id,
            name="Invalid",
            bike_type="unicycle",  # not a valid type
        )
        db_session.add(bike)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_bike_cda_source_valid(self, db_session, seed_user):
        """Valid CdA sources are accepted."""
        valid_sources = ["default", "manual", "calibrated", None]
        for i, source in enumerate(valid_sources):
            bike = Bike(
                user_id=seed_user.id,
                name=f"CdA Test {i}",
                bike_type="road",
                cda_source=source,
            )
            db_session.add(bike)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_bike_invalid_cda_source_rejected(self, db_session, seed_user):
        """Invalid CdA source is rejected by database constraint."""
        bike = Bike(
            user_id=seed_user.id,
            name="Invalid CdA",
            bike_type="road",
            cda_source="guessed",  # not a valid source
        )
        db_session.add(bike)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_bike_deleted_with_user(self, db_session):
        """Bike is deleted when user is deleted (CASCADE)."""
        # Create a separate user for this test
        user = User(email="bike-cascade-test@example.com", password_hash="x")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        bike = Bike(user_id=user.id, name="Test", bike_type="road")
        db_session.add(bike)
        await db_session.commit()
        bike_id = bike.id

        # Delete user
        await db_session.delete(user)
        await db_session.commit()

        # Bike should be gone
        result = await db_session.execute(select(Bike).where(Bike.id == bike_id))
        assert result.scalar_one_or_none() is None


class TestActivityBikeRelationship:
    """Tests for Activity.bike_id foreign key relationship."""

    @pytest.mark.asyncio
    async def test_activity_can_reference_bike(self, db_session, seed_user):
        """Activity can be linked to a bike."""
        from datetime import datetime

        bike = Bike(user_id=seed_user.id, name="Test Bike", bike_type="road")
        db_session.add(bike)
        await db_session.commit()
        await db_session.refresh(bike)

        activity = Activity(
            user_id=seed_user.id,
            source="test",
            source_ref="bike-ref-test-1",
            started_at=datetime(2024, 1, 1, 10, 0, 0),
            bike_id=bike.id,
        )
        db_session.add(activity)
        await db_session.commit()
        await db_session.refresh(activity)

        assert activity.bike_id == bike.id

    @pytest.mark.asyncio
    async def test_activity_bike_relationship_navigation(self, db_session, seed_user):
        """Activity.bike relationship allows navigation to Bike object."""
        from datetime import datetime

        bike = Bike(user_id=seed_user.id, name="Relationship Test Bike", bike_type="gravel")
        db_session.add(bike)
        await db_session.commit()
        await db_session.refresh(bike)

        activity = Activity(
            user_id=seed_user.id,
            source="test",
            source_ref="bike-rel-test-1",
            started_at=datetime(2024, 1, 1, 12, 0, 0),
            bike_id=bike.id,
        )
        db_session.add(activity)
        await db_session.commit()
        await db_session.refresh(activity)

        # Test relationship navigation
        assert activity.bike is not None
        assert activity.bike.name == "Relationship Test Bike"
        assert activity.bike.bike_type == "gravel"

    @pytest.mark.asyncio
    async def test_activity_bike_id_set_null_on_bike_delete(self, db_session):
        """Activity.bike_id is set to NULL when bike is deleted (SET NULL)."""
        from datetime import datetime

        # Create separate user for this test
        user = User(email="bike-setnull-test@example.com", password_hash="x")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        bike = Bike(user_id=user.id, name="Test Bike", bike_type="road")
        db_session.add(bike)
        await db_session.commit()
        await db_session.refresh(bike)

        activity = Activity(
            user_id=user.id,
            source="test",
            source_ref="setnull-test-1",
            started_at=datetime(2024, 1, 1, 10, 0, 0),
            bike_id=bike.id,
        )
        db_session.add(activity)
        await db_session.commit()
        activity_id = activity.id

        # Delete the bike
        await db_session.delete(bike)
        await db_session.commit()

        # Expire the cached activity state and re-fetch from DB
        db_session.expire_all()
        result = await db_session.execute(select(Activity).where(Activity.id == activity_id))
        activity = result.scalar_one()
        assert activity.bike_id is None

    @pytest.mark.asyncio
    async def test_activity_without_bike(self, db_session, seed_user):
        """Activity can exist without a bike (bike_id=NULL)."""
        from datetime import datetime

        activity = Activity(
            user_id=seed_user.id,
            source="test",
            source_ref="no-bike-test-2",
            started_at=datetime(2024, 1, 1, 11, 0, 0),
            bike_id=None,
        )
        db_session.add(activity)
        await db_session.commit()
        await db_session.refresh(activity)

        assert activity.bike_id is None


class TestDefaultBikeConstraint:
    """Tests for the unique default bike constraint."""

    @pytest.mark.asyncio
    async def test_only_one_default_bike_per_user(self, db_session):
        """Only one active (non-retired) default bike per user is allowed."""
        # Create a separate user for isolation
        user = User(email="default-constraint-test@example.com", password_hash="x")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        bike1 = Bike(user_id=user.id, name="Bike 1", bike_type="road", is_default=True)
        db_session.add(bike1)
        await db_session.commit()

        bike2 = Bike(user_id=user.id, name="Bike 2", bike_type="gravel", is_default=True)
        db_session.add(bike2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    @pytest.mark.asyncio
    async def test_retired_default_allows_new_default(self, db_session):
        """A retired default bike allows a new default bike."""
        from datetime import datetime

        # Create a separate user for isolation
        user = User(email="retired-default-test@example.com", password_hash="x")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        bike1 = Bike(
            user_id=user.id,
            name="Old Default",
            bike_type="road",
            is_default=True,
            retired_at=datetime.now(),  # retired
        )
        db_session.add(bike1)
        await db_session.commit()

        # New default should be allowed since old one is retired
        bike2 = Bike(user_id=user.id, name="New Default", bike_type="gravel", is_default=True)
        db_session.add(bike2)
        await db_session.commit()

        assert bike2.is_default is True

    @pytest.mark.asyncio
    async def test_multiple_non_default_bikes_allowed(self, db_session):
        """Multiple non-default bikes are allowed."""
        # Create a separate user for isolation
        user = User(email="multi-bike-test@example.com", password_hash="x")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        for i in range(5):
            bike = Bike(
                user_id=user.id,
                name=f"Bike {i}",
                bike_type="road",
                is_default=False,
            )
            db_session.add(bike)
        await db_session.commit()

        result = await db_session.execute(select(Bike).where(Bike.user_id == user.id))
        bikes = result.scalars().all()
        assert len(bikes) == 5
