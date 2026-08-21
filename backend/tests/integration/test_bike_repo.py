"""Integration tests for PostgresBikeRepo."""

import pytest

from trainingdash.repositories.postgres.bike_repo import PostgresBikeRepo
from trainingdash.repositories.postgres.models import Bike


class TestPostgresBikeRepo:
    """Tests for PostgresBikeRepo methods."""

    @pytest.mark.asyncio
    async def test_save_and_get_by_id(self, db_session, seed_user):
        """Can save a bike and retrieve it by ID."""
        repo = PostgresBikeRepo(db_session)

        bike = Bike(
            user_id=seed_user.id,
            name="Canyon Aeroad",
            bike_type="road",
        )
        saved = await repo.save(bike)

        assert saved.id is not None

        fetched = await repo.get_by_id(saved.id, seed_user.id)
        assert fetched is not None
        assert fetched.name == "Canyon Aeroad"
        assert fetched.bike_type == "road"

    @pytest.mark.asyncio
    async def test_get_by_id_wrong_user_returns_none(self, db_session, seed_user):
        """get_by_id returns None if bike belongs to different user."""
        repo = PostgresBikeRepo(db_session)

        bike = Bike(user_id=seed_user.id, name="Test", bike_type="road")
        saved = await repo.save(bike)

        # Try to fetch with wrong user_id
        fetched = await repo.get_by_id(saved.id, seed_user.id + 999)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_get_by_user_returns_sorted_by_name(self, db_session, seed_user):
        """get_by_user returns bikes sorted by name."""
        repo = PostgresBikeRepo(db_session)

        # Create bikes in non-alphabetical order
        await repo.save(Bike(user_id=seed_user.id, name="Zebra", bike_type="road"))
        await repo.save(Bike(user_id=seed_user.id, name="Alpha", bike_type="gravel"))
        await repo.save(Bike(user_id=seed_user.id, name="Beta", bike_type="mtb"))

        bikes = await repo.get_by_user(seed_user.id)
        names = [b.name for b in bikes]
        assert names == ["Alpha", "Beta", "Zebra"]

    @pytest.mark.asyncio
    async def test_get_by_user_excludes_retired_by_default(self, db_session, seed_user):
        """get_by_user excludes retired bikes by default."""
        from datetime import datetime

        repo = PostgresBikeRepo(db_session)

        active = Bike(user_id=seed_user.id, name="Active", bike_type="road")
        await repo.save(active)

        retired = Bike(
            user_id=seed_user.id,
            name="Retired",
            bike_type="road",
            retired_at=datetime.now(),
        )
        await repo.save(retired)

        bikes = await repo.get_by_user(seed_user.id)
        assert len(bikes) == 1
        assert bikes[0].name == "Active"

    @pytest.mark.asyncio
    async def test_get_by_user_includes_retired_when_requested(self, db_session, seed_user):
        """get_by_user includes retired bikes when include_retired=True."""
        from datetime import datetime

        repo = PostgresBikeRepo(db_session)

        await repo.save(Bike(user_id=seed_user.id, name="Active", bike_type="road"))
        await repo.save(
            Bike(
                user_id=seed_user.id,
                name="Retired",
                bike_type="road",
                retired_at=datetime.now(),
            )
        )

        bikes = await repo.get_by_user(seed_user.id, include_retired=True)
        assert len(bikes) == 2

    @pytest.mark.asyncio
    async def test_get_default_for_user(self, db_session, seed_user):
        """get_default_for_user returns the default bike."""
        repo = PostgresBikeRepo(db_session)

        non_default = Bike(user_id=seed_user.id, name="Regular", bike_type="road")
        await repo.save(non_default)

        default = Bike(
            user_id=seed_user.id,
            name="Default",
            bike_type="gravel",
            is_default=True,
        )
        await repo.save(default)

        result = await repo.get_default_for_user(seed_user.id)
        assert result is not None
        assert result.name == "Default"

    @pytest.mark.asyncio
    async def test_get_default_for_user_excludes_retired(self, db_session, seed_user):
        """get_default_for_user returns None if default is retired."""
        from datetime import datetime

        repo = PostgresBikeRepo(db_session)

        # Create a retired default bike
        retired_default = Bike(
            user_id=seed_user.id,
            name="Retired Default",
            bike_type="road",
            is_default=True,
            retired_at=datetime.now(),
        )
        await repo.save(retired_default)

        result = await repo.get_default_for_user(seed_user.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_default_for_user_no_default(self, db_session, seed_user):
        """get_default_for_user returns None if no default set."""
        repo = PostgresBikeRepo(db_session)

        await repo.save(Bike(user_id=seed_user.id, name="Bike", bike_type="road"))

        result = await repo.get_default_for_user(seed_user.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_distance(self, db_session, seed_user):
        """update_distance adds to total_distance_m."""
        repo = PostgresBikeRepo(db_session)

        bike = Bike(user_id=seed_user.id, name="Test", bike_type="road")
        saved = await repo.save(bike)
        assert saved.total_distance_m == 0

        await repo.update_distance(saved.id, seed_user.id, 50000.0)  # 50km

        # Re-fetch to see updated value
        updated = await repo.get_by_id(saved.id, seed_user.id)
        assert updated.total_distance_m == 50000.0

        # Add more
        await repo.update_distance(saved.id, seed_user.id, 25000.0)  # +25km
        updated = await repo.get_by_id(saved.id, seed_user.id)
        assert updated.total_distance_m == 75000.0

    @pytest.mark.asyncio
    async def test_update_distance_negative(self, db_session, seed_user):
        """update_distance can subtract (for corrections)."""
        repo = PostgresBikeRepo(db_session)

        bike = Bike(
            user_id=seed_user.id,
            name="Test",
            bike_type="road",
            total_distance_m=100000.0,
        )
        saved = await repo.save(bike)

        await repo.update_distance(saved.id, seed_user.id, -10000.0)  # -10km

        updated = await repo.get_by_id(saved.id, seed_user.id)
        assert updated.total_distance_m == 90000.0

    @pytest.mark.asyncio
    async def test_set_default(self, db_session, seed_user):
        """set_default sets a bike as default."""
        repo = PostgresBikeRepo(db_session)

        bike = Bike(user_id=seed_user.id, name="Test", bike_type="road")
        saved = await repo.save(bike)
        assert saved.is_default is False

        await repo.set_default(seed_user.id, saved.id)

        updated = await repo.get_by_id(saved.id, seed_user.id)
        assert updated.is_default is True

    @pytest.mark.asyncio
    async def test_set_default_clears_previous(self, db_session, seed_user):
        """set_default clears the previous default."""
        repo = PostgresBikeRepo(db_session)

        bike1 = Bike(user_id=seed_user.id, name="Bike 1", bike_type="road", is_default=True)
        saved1 = await repo.save(bike1)

        bike2 = Bike(user_id=seed_user.id, name="Bike 2", bike_type="gravel")
        saved2 = await repo.save(bike2)

        await repo.set_default(seed_user.id, saved2.id)

        updated1 = await repo.get_by_id(saved1.id, seed_user.id)
        updated2 = await repo.get_by_id(saved2.id, seed_user.id)

        assert updated1.is_default is False
        assert updated2.is_default is True

    @pytest.mark.asyncio
    async def test_set_default_ignores_retired(self, db_session, seed_user):
        """set_default does not set retired bike as default."""
        from datetime import datetime

        repo = PostgresBikeRepo(db_session)

        retired = Bike(
            user_id=seed_user.id,
            name="Retired",
            bike_type="road",
            retired_at=datetime.now(),
        )
        saved = await repo.save(retired)

        await repo.set_default(seed_user.id, saved.id)

        updated = await repo.get_by_id(saved.id, seed_user.id)
        assert updated.is_default is False

    @pytest.mark.asyncio
    async def test_clear_default(self, db_session, seed_user):
        """clear_default removes the default flag."""
        repo = PostgresBikeRepo(db_session)

        bike = Bike(user_id=seed_user.id, name="Test", bike_type="road", is_default=True)
        saved = await repo.save(bike)

        await repo.clear_default(seed_user.id)

        updated = await repo.get_by_id(saved.id, seed_user.id)
        assert updated.is_default is False

    @pytest.mark.asyncio
    async def test_retire(self, db_session, seed_user):
        """retire sets retired_at timestamp."""
        repo = PostgresBikeRepo(db_session)

        bike = Bike(user_id=seed_user.id, name="Test", bike_type="road")
        saved = await repo.save(bike)

        result = await repo.retire(saved.id, seed_user.id)
        assert result is True

        updated = await repo.get_by_id(saved.id, seed_user.id)
        assert updated.retired_at is not None

    @pytest.mark.asyncio
    async def test_retire_clears_default(self, db_session, seed_user):
        """retire clears is_default if bike was default."""
        repo = PostgresBikeRepo(db_session)

        bike = Bike(user_id=seed_user.id, name="Test", bike_type="road", is_default=True)
        saved = await repo.save(bike)

        await repo.retire(saved.id, seed_user.id)

        updated = await repo.get_by_id(saved.id, seed_user.id)
        assert updated.is_default is False
        assert updated.retired_at is not None

    @pytest.mark.asyncio
    async def test_retire_not_found(self, db_session, seed_user):
        """retire returns False if bike not found."""
        repo = PostgresBikeRepo(db_session)

        result = await repo.retire(99999, seed_user.id)
        assert result is False

    @pytest.mark.asyncio
    async def test_retire_already_retired(self, db_session, seed_user):
        """retire returns True if already retired (idempotent)."""
        from datetime import datetime

        repo = PostgresBikeRepo(db_session)

        bike = Bike(
            user_id=seed_user.id,
            name="Test",
            bike_type="road",
            retired_at=datetime.now(),
        )
        saved = await repo.save(bike)

        result = await repo.retire(saved.id, seed_user.id)
        assert result is True
