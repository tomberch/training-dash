"""In-memory fake implementation of RacePlanRepo for testing."""

from datetime import datetime

from trainingdash.repositories.postgres.models import RacePlan


class FakeRacePlanRepo:
    """
    In-memory fake implementation of RacePlanRepo protocol.

    Stores plans in a dict keyed by (user_id, plan_id).
    Provides inspection methods for test assertions.
    """

    def __init__(self) -> None:
        self._plans: dict[tuple[int, int], RacePlan] = {}
        self._next_id: int = 1

    # --- Protocol methods ---

    async def get_by_id(self, plan_id: int, user_id: int) -> RacePlan | None:
        return self._plans.get((user_id, plan_id))

    async def get_by_course(self, course_id: int, user_id: int) -> list[RacePlan]:
        course_plans = [p for (uid, _), p in self._plans.items() if uid == user_id and p.course_id == course_id]
        # Sort by created_at descending
        course_plans.sort(key=lambda p: p.created_at or datetime.min, reverse=True)
        return course_plans

    async def get_by_user(self, user_id: int, limit: int = 20) -> list[RacePlan]:
        user_plans = [p for (uid, _), p in self._plans.items() if uid == user_id]
        # Sort by created_at descending
        user_plans.sort(key=lambda p: p.created_at or datetime.min, reverse=True)
        return user_plans[:limit]

    async def save(self, plan: RacePlan) -> RacePlan:
        if plan.user_id is None:
            raise ValueError("Plan must have a user_id")
        # Assign ID if not set
        if plan.id is None:
            plan.id = self._next_id
            self._next_id += 1
        # Set timestamp if not set
        if plan.created_at is None:
            plan.created_at = datetime.now()
        self._plans[(plan.user_id, plan.id)] = plan
        return plan

    async def delete(self, plan_id: int, user_id: int) -> bool:
        key = (user_id, plan_id)
        if key in self._plans:
            del self._plans[key]
            return True
        return False

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored plans."""
        self._plans.clear()
        self._next_id = 1

    def all(self) -> list[RacePlan]:
        """Return all stored plans (for test assertions)."""
        return list(self._plans.values())

    def add(self, plan: RacePlan) -> RacePlan:
        """Synchronous helper to add a plan for test setup."""
        if plan.user_id is None:
            raise ValueError("Plan must have a user_id")
        if plan.id is None:
            plan.id = self._next_id
            self._next_id += 1
        if plan.created_at is None:
            plan.created_at = datetime.now()
        self._plans[(plan.user_id, plan.id)] = plan
        return plan
