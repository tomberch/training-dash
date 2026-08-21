"""In-memory fake implementation of CourseRepo for testing."""

from datetime import datetime

from trainingdash.repositories.postgres.models import RaceCourse


class FakeCourseRepo:
    """
    In-memory fake implementation of CourseRepo protocol.

    Stores courses in a dict keyed by (user_id, course_id).
    Provides inspection methods for test assertions.
    """

    def __init__(self) -> None:
        self._courses: dict[tuple[int, int], RaceCourse] = {}
        self._next_id: int = 1

    # --- Protocol methods ---

    async def get_by_id(self, course_id: int, user_id: int) -> RaceCourse | None:
        return self._courses.get((user_id, course_id))

    async def get_by_user(self, user_id: int) -> list[RaceCourse]:
        user_courses = [
            c for (uid, _), c in self._courses.items()
            if uid == user_id
        ]
        # Sort by created_at descending
        user_courses.sort(key=lambda c: c.created_at or datetime.min, reverse=True)
        return user_courses

    async def save(self, course: RaceCourse) -> RaceCourse:
        if course.user_id is None:
            raise ValueError("Course must have a user_id")
        # Assign ID if not set
        if course.id is None:
            course.id = self._next_id
            self._next_id += 1
        # Set timestamps if not set
        if course.created_at is None:
            course.created_at = datetime.now()
        if course.updated_at is None:
            course.updated_at = datetime.now()
        self._courses[(course.user_id, course.id)] = course
        return course

    async def delete(self, course_id: int, user_id: int) -> bool:
        key = (user_id, course_id)
        if key in self._courses:
            del self._courses[key]
            return True
        return False

    async def update_processed_data(
        self,
        course_id: int,
        user_id: int,
        elevation_profile: list[dict],
        segments: list[dict],
        climbs: list[dict],
    ) -> None:
        course = self._courses.get((user_id, course_id))
        if course:
            course.elevation_profile = elevation_profile
            course.segments = segments
            course.climbs = climbs
            course.updated_at = datetime.now()

    # --- Test helper methods ---

    def clear(self) -> None:
        """Clear all stored courses."""
        self._courses.clear()
        self._next_id = 1

    def all(self) -> list[RaceCourse]:
        """Return all stored courses (for test assertions)."""
        return list(self._courses.values())

    def add(self, course: RaceCourse) -> RaceCourse:
        """Synchronous helper to add a course for test setup."""
        if course.user_id is None:
            raise ValueError("Course must have a user_id")
        if course.id is None:
            course.id = self._next_id
            self._next_id += 1
        if course.created_at is None:
            course.created_at = datetime.now()
        if course.updated_at is None:
            course.updated_at = datetime.now()
        self._courses[(course.user_id, course.id)] = course
        return course
