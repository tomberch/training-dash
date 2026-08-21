"""Unit tests for BikeRepo using FakeBikeRepo."""

from datetime import datetime

import pytest

from tests.fakes.bike_repo import FakeBikeRepo
from trainingdash.repositories.postgres.models import Bike


class TestFakeBikeRepo:
    """Unit tests for BikeRepo protocol behavior using the fake implementation."""

    @pytest.fixture
    def repo(self) -> FakeBikeRepo:
        return FakeBikeRepo()

    @pytest.mark.asyncio
    async def test_save_assigns_id(self, repo: FakeBikeRepo) -> None:
        """save() assigns an ID to a new bike."""
        bike = Bike(user_id=1, name="Test Bike", bike_type="road")
        assert bike.id is None

        saved = await repo.save(bike)

        assert saved.id is not None
        assert saved.id == 1

    @pytest.mark.asyncio
    async def test_save_increments_id(self, repo: FakeBikeRepo) -> None:
        """save() assigns incrementing IDs."""
        bike1 = await repo.save(Bike(user_id=1, name="Bike 1", bike_type="road"))
        bike2 = await repo.save(Bike(user_id=1, name="Bike 2", bike_type="road"))

        assert bike1.id == 1
        assert bike2.id == 2

    @pytest.mark.asyncio
    async def test_save_requires_user_id(self, repo: FakeBikeRepo) -> None:
        """save() raises if user_id is None."""
        bike = Bike(name="Test", bike_type="road")

        with pytest.raises(ValueError, match="user_id"):
            await repo.save(bike)

    @pytest.mark.asyncio
    async def test_get_by_id_returns_bike(self, repo: FakeBikeRepo) -> None:
        """get_by_id() returns the bike if found."""
        bike = await repo.save(Bike(user_id=1, name="Test", bike_type="road"))

        fetched = await repo.get_by_id(bike.id, user_id=1)

        assert fetched is not None
        assert fetched.name == "Test"

    @pytest.mark.asyncio
    async def test_get_by_id_wrong_user_returns_none(self, repo: FakeBikeRepo) -> None:
        """get_by_id() returns None if user doesn't own the bike."""
        bike = await repo.save(Bike(user_id=1, name="Test", bike_type="road"))

        fetched = await repo.get_by_id(bike.id, user_id=999)

        assert fetched is None

    @pytest.mark.asyncio
    async def test_get_by_user_returns_sorted(self, repo: FakeBikeRepo) -> None:
        """get_by_user() returns bikes sorted by name."""
        await repo.save(Bike(user_id=1, name="Zebra", bike_type="road"))
        await repo.save(Bike(user_id=1, name="Alpha", bike_type="road"))
        await repo.save(Bike(user_id=1, name="Beta", bike_type="road"))

        bikes = await repo.get_by_user(user_id=1)

        assert [b.name for b in bikes] == ["Alpha", "Beta", "Zebra"]

    @pytest.mark.asyncio
    async def test_get_by_user_excludes_retired(self, repo: FakeBikeRepo) -> None:
        """get_by_user() excludes retired bikes by default."""
        await repo.save(Bike(user_id=1, name="Active", bike_type="road"))
        await repo.save(Bike(user_id=1, name="Retired", bike_type="road", retired_at=datetime.now()))

        bikes = await repo.get_by_user(user_id=1)

        assert len(bikes) == 1
        assert bikes[0].name == "Active"

    @pytest.mark.asyncio
    async def test_get_by_user_includes_retired_when_requested(self, repo: FakeBikeRepo) -> None:
        """get_by_user() includes retired bikes when include_retired=True."""
        await repo.save(Bike(user_id=1, name="Active", bike_type="road"))
        await repo.save(Bike(user_id=1, name="Retired", bike_type="road", retired_at=datetime.now()))

        bikes = await repo.get_by_user(user_id=1, include_retired=True)

        assert len(bikes) == 2

    @pytest.mark.asyncio
    async def test_get_default_for_user(self, repo: FakeBikeRepo) -> None:
        """get_default_for_user() returns the default bike."""
        await repo.save(Bike(user_id=1, name="Regular", bike_type="road"))
        await repo.save(Bike(user_id=1, name="Default", bike_type="road", is_default=True))

        default = await repo.get_default_for_user(user_id=1)

        assert default is not None
        assert default.name == "Default"

    @pytest.mark.asyncio
    async def test_get_default_for_user_excludes_retired(self, repo: FakeBikeRepo) -> None:
        """get_default_for_user() returns None if default is retired."""
        await repo.save(
            Bike(
                user_id=1,
                name="Default",
                bike_type="road",
                is_default=True,
                retired_at=datetime.now(),
            )
        )

        default = await repo.get_default_for_user(user_id=1)

        assert default is None

    @pytest.mark.asyncio
    async def test_update_distance(self, repo: FakeBikeRepo) -> None:
        """update_distance() adds to total_distance_m."""
        bike = await repo.save(Bike(user_id=1, name="Test", bike_type="road"))

        await repo.update_distance(bike.id, user_id=1, delta_m=50000.0)

        updated = await repo.get_by_id(bike.id, user_id=1)
        assert updated.total_distance_m == 50000.0

    @pytest.mark.asyncio
    async def test_update_distance_wrong_user_no_effect(self, repo: FakeBikeRepo) -> None:
        """update_distance() does nothing if user doesn't own the bike."""
        bike = await repo.save(Bike(user_id=1, name="Test", bike_type="road", total_distance_m=0))

        await repo.update_distance(bike.id, user_id=999, delta_m=50000.0)

        updated = await repo.get_by_id(bike.id, user_id=1)
        assert updated.total_distance_m == 0

    @pytest.mark.asyncio
    async def test_set_default(self, repo: FakeBikeRepo) -> None:
        """set_default() sets a bike as default."""
        bike = await repo.save(Bike(user_id=1, name="Test", bike_type="road", is_default=False))
        assert bike.is_default is False

        await repo.set_default(user_id=1, bike_id=bike.id)

        updated = await repo.get_by_id(bike.id, user_id=1)
        assert updated.is_default is True

    @pytest.mark.asyncio
    async def test_set_default_clears_previous(self, repo: FakeBikeRepo) -> None:
        """set_default() clears the previous default."""
        bike1 = await repo.save(Bike(user_id=1, name="Bike 1", bike_type="road", is_default=True))
        bike2 = await repo.save(Bike(user_id=1, name="Bike 2", bike_type="road"))

        await repo.set_default(user_id=1, bike_id=bike2.id)

        updated1 = await repo.get_by_id(bike1.id, user_id=1)
        updated2 = await repo.get_by_id(bike2.id, user_id=1)
        assert updated1.is_default is False
        assert updated2.is_default is True

    @pytest.mark.asyncio
    async def test_clear_default(self, repo: FakeBikeRepo) -> None:
        """clear_default() removes the default flag."""
        bike = await repo.save(Bike(user_id=1, name="Test", bike_type="road", is_default=True))

        await repo.clear_default(user_id=1)

        updated = await repo.get_by_id(bike.id, user_id=1)
        assert updated.is_default is False

    @pytest.mark.asyncio
    async def test_retire(self, repo: FakeBikeRepo) -> None:
        """retire() sets retired_at timestamp."""
        bike = await repo.save(Bike(user_id=1, name="Test", bike_type="road"))

        result = await repo.retire(bike.id, user_id=1)

        assert result is True
        updated = await repo.get_by_id(bike.id, user_id=1)
        assert updated.retired_at is not None

    @pytest.mark.asyncio
    async def test_retire_clears_default(self, repo: FakeBikeRepo) -> None:
        """retire() clears is_default if bike was default."""
        bike = await repo.save(Bike(user_id=1, name="Test", bike_type="road", is_default=True))

        await repo.retire(bike.id, user_id=1)

        updated = await repo.get_by_id(bike.id, user_id=1)
        assert updated.is_default is False

    @pytest.mark.asyncio
    async def test_retire_not_found(self, repo: FakeBikeRepo) -> None:
        """retire() returns False if bike not found."""
        result = await repo.retire(bike_id=999, user_id=1)

        assert result is False

    @pytest.mark.asyncio
    async def test_retire_idempotent(self, repo: FakeBikeRepo) -> None:
        """retire() returns True if already retired."""
        bike = await repo.save(
            Bike(
                user_id=1,
                name="Test",
                bike_type="road",
                retired_at=datetime.now(),
            )
        )

        result = await repo.retire(bike.id, user_id=1)

        assert result is True
