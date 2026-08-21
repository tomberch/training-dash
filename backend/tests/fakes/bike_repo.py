"""In-memory fake implementation of BikeRepo for testing."""

from datetime import datetime

from trainingdash.repositories.postgres.models import Bike


class FakeBikeRepo:
    """
    In-memory fake implementation of BikeRepo protocol.

    Stores bikes in a dict keyed by (user_id, bike_id).
    Provides inspection methods for test assertions.
    """

    def __init__(self) -> None:
        self._bikes: dict[tuple[int, int], Bike] = {}
        self._next_id: int = 1

    # --- Protocol methods ---

    async def get_by_id(self, bike_id: int, user_id: int) -> Bike | None:
        return self._bikes.get((user_id, bike_id))

    async def get_by_user(self, user_id: int, include_retired: bool = False) -> list[Bike]:
        user_bikes = [
            b for (uid, _), b in self._bikes.items() if uid == user_id and (include_retired or b.retired_at is None)
        ]
        # Sort by name
        user_bikes.sort(key=lambda b: b.name or "")
        return user_bikes

    async def get_default_for_user(self, user_id: int) -> Bike | None:
        for (uid, _), bike in self._bikes.items():
            if uid == user_id and bike.is_default and bike.retired_at is None:
                return bike
        return None

    async def save(self, bike: Bike) -> Bike:
        if bike.user_id is None:
            raise ValueError("Bike must have a user_id")
        # Assign ID if not set
        if bike.id is None:
            bike.id = self._next_id
            self._next_id += 1
        self._bikes[(bike.user_id, bike.id)] = bike
        return bike

    async def update_distance(self, bike_id: int, user_id: int, delta_m: float) -> None:
        for (uid, bid), bike in self._bikes.items():
            if bid == bike_id and uid == user_id:
                bike.total_distance_m = (bike.total_distance_m or 0) + delta_m
                return

    async def set_default(self, user_id: int, bike_id: int) -> None:
        # Clear existing default
        for (uid, _), bike in self._bikes.items():
            if uid == user_id and bike.is_default:
                bike.is_default = False

        # Set new default
        bike = self._bikes.get((user_id, bike_id))
        if bike and bike.retired_at is None:
            bike.is_default = True

    async def clear_default(self, user_id: int) -> None:
        for (uid, _), bike in self._bikes.items():
            if uid == user_id and bike.is_default:
                bike.is_default = False

    async def retire(self, bike_id: int, user_id: int) -> bool:
        bike = self._bikes.get((user_id, bike_id))
        if bike is None:
            return False

        if bike.retired_at is not None:
            return True  # Already retired

        if bike.is_default:
            bike.is_default = False

        bike.retired_at = datetime.now()
        return True

    async def update_calibration(
        self,
        bike_id: int,
        user_id: int,
        cda: float,
    ) -> bool:
        """Update bike's CdA from calibration."""
        bike = self._bikes.get((user_id, bike_id))
        if bike is None:
            return False
        bike.cda = cda
        bike.cda_source = "calibrated"
        bike.calibrated_at = datetime.now()
        return True

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored bikes."""
        self._bikes.clear()
        self._next_id = 1

    def all(self) -> list[Bike]:
        """Return all stored bikes (for test assertions)."""
        return list(self._bikes.values())

    def add(self, bike: Bike) -> Bike:
        """Synchronous helper to add a bike for test setup."""
        if bike.user_id is None:
            raise ValueError("Bike must have a user_id")
        if bike.id is None:
            bike.id = self._next_id
            self._next_id += 1
        self._bikes[(bike.user_id, bike.id)] = bike
        return bike
