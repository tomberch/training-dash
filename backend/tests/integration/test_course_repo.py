"""Integration tests for PostgresCourseRepo."""

import pytest

from trainingdash.repositories.postgres.course_repo import PostgresCourseRepo
from trainingdash.repositories.postgres.models import RaceCourse, User


class TestCourseRepoGetById:
    """Tests for CourseRepo.get_by_id."""

    @pytest.mark.asyncio
    async def test_get_existing_course(self, db_session, seed_user):
        """Can retrieve a course by ID."""
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)"
        course = RaceCourse(
            user_id=seed_user.id,
            name="Test Course",
            source_type="gpx",
            distance_m=5000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=0.0,
            geometry=wkt,
        )
        db_session.add(course)
        await db_session.commit()
        await db_session.refresh(course)

        repo = PostgresCourseRepo(db_session)
        result = await repo.get_by_id(course.id, seed_user.id)

        assert result is not None
        assert result.id == course.id
        assert result.name == "Test Course"

    @pytest.mark.asyncio
    async def test_get_nonexistent_course(self, db_session, seed_user):
        """Returns None for nonexistent course."""
        repo = PostgresCourseRepo(db_session)
        result = await repo.get_by_id(99999, seed_user.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_other_users_course(self, db_session, seed_user):
        """Cannot access another user's course."""
        # Create another user
        other_user = User(email="other-course-test@example.com", password_hash="x")
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        # Create course for other user
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)"
        course = RaceCourse(
            user_id=other_user.id,
            name="Other's Course",
            source_type="gpx",
            distance_m=5000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=0.0,
            geometry=wkt,
        )
        db_session.add(course)
        await db_session.commit()

        repo = PostgresCourseRepo(db_session)
        result = await repo.get_by_id(course.id, seed_user.id)
        assert result is None


class TestCourseRepoGetByUser:
    """Tests for CourseRepo.get_by_user."""

    @pytest.mark.asyncio
    async def test_get_user_courses(self, db_session, seed_user):
        """Can list courses for a user."""
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)"
        for i in range(3):
            course = RaceCourse(
                user_id=seed_user.id,
                name=f"Course {i}",
                source_type="gpx",
                distance_m=1000.0 * (i + 1),
                elevation_gain_m=100.0,
                elevation_loss_m=0.0,
                geometry=wkt,
            )
            db_session.add(course)
        await db_session.commit()

        repo = PostgresCourseRepo(db_session)
        courses = await repo.get_by_user(seed_user.id)

        assert len(courses) >= 3
        # Verify all three courses are present
        names = {c.name for c in courses if c.name.startswith("Course")}
        assert names == {"Course 0", "Course 1", "Course 2"}

    @pytest.mark.asyncio
    async def test_get_user_courses_empty(self, db_session):
        """Returns empty list for user with no courses."""
        user = User(email="no-courses@example.com", password_hash="x")
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        repo = PostgresCourseRepo(db_session)
        courses = await repo.get_by_user(user.id)
        assert courses == []


class TestCourseRepoSave:
    """Tests for CourseRepo.save."""

    @pytest.mark.asyncio
    async def test_save_new_course(self, db_session, seed_user):
        """Can save a new course."""
        wkt = "SRID=4326;LINESTRINGZ(-122.4 37.8 10, -122.3 37.9 500)"
        course = RaceCourse(
            user_id=seed_user.id,
            name="New Course",
            source_type="fit",
            source_filename="course.fit",
            distance_m=15000.0,
            elevation_gain_m=490.0,
            elevation_loss_m=0.0,
            geometry=wkt,
        )

        repo = PostgresCourseRepo(db_session)
        saved = await repo.save(course)

        assert saved.id is not None
        assert saved.name == "New Course"
        assert saved.source_filename == "course.fit"
        assert saved.created_at is not None

    @pytest.mark.asyncio
    async def test_save_course_with_jsonb(self, db_session, seed_user):
        """Can save a course with JSONB data."""
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)"
        course = RaceCourse(
            user_id=seed_user.id,
            name="Course with Data",
            source_type="gpx",
            distance_m=5000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=0.0,
            geometry=wkt,
            elevation_profile=[{"distance_m": 0, "elevation_m": 100, "grade_pct": 0}],
            segments=[{"start_m": 0, "end_m": 5000, "avg_grade_pct": 2.0}],
            climbs=[{"name": "Hill", "category": "4"}],
        )

        repo = PostgresCourseRepo(db_session)
        saved = await repo.save(course)

        assert saved.elevation_profile is not None
        assert saved.segments is not None
        assert saved.climbs is not None


class TestCourseRepoDelete:
    """Tests for CourseRepo.delete."""

    @pytest.mark.asyncio
    async def test_delete_existing_course(self, db_session, seed_user):
        """Can delete a course."""
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)"
        course = RaceCourse(
            user_id=seed_user.id,
            name="To Delete",
            source_type="gpx",
            distance_m=1000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=0.0,
            geometry=wkt,
        )
        db_session.add(course)
        await db_session.commit()
        course_id = course.id

        repo = PostgresCourseRepo(db_session)
        result = await repo.delete(course_id, seed_user.id)

        assert result is True

        # Verify deleted
        fetched = await repo.get_by_id(course_id, seed_user.id)
        assert fetched is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_course(self, db_session, seed_user):
        """Returns False for nonexistent course."""
        repo = PostgresCourseRepo(db_session)
        result = await repo.delete(99999, seed_user.id)
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_other_users_course(self, db_session, seed_user):
        """Cannot delete another user's course."""
        # Create another user
        other_user = User(email="delete-other-course@example.com", password_hash="x")
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        # Create course for other user
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)"
        course = RaceCourse(
            user_id=other_user.id,
            name="Other's Course",
            source_type="gpx",
            distance_m=1000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=0.0,
            geometry=wkt,
        )
        db_session.add(course)
        await db_session.commit()

        repo = PostgresCourseRepo(db_session)
        result = await repo.delete(course.id, seed_user.id)
        assert result is False


class TestCourseRepoUpdateProcessedData:
    """Tests for CourseRepo.update_processed_data."""

    @pytest.mark.asyncio
    async def test_update_processed_data(self, db_session, seed_user):
        """Can update processed data for a course."""
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 500, 2 2 200)"
        course = RaceCourse(
            user_id=seed_user.id,
            name="Process Test",
            source_type="gpx",
            distance_m=10000.0,
            elevation_gain_m=400.0,
            elevation_loss_m=300.0,
            geometry=wkt,
        )
        db_session.add(course)
        await db_session.commit()
        course_id = course.id

        elevation_profile = [
            {"distance_m": 0, "elevation_m": 100, "grade_pct": 0},
            {"distance_m": 5000, "elevation_m": 500, "grade_pct": 8.0},
            {"distance_m": 10000, "elevation_m": 200, "grade_pct": -6.0},
        ]
        segments = [
            {"start_m": 0, "end_m": 5000, "avg_grade_pct": 8.0, "distance_m": 5000},
            {"start_m": 5000, "end_m": 10000, "avg_grade_pct": -6.0, "distance_m": 5000},
        ]
        climbs = [
            {
                "name": "Big Climb",
                "start_m": 0,
                "end_m": 5000,
                "distance_m": 5000,
                "avg_grade_pct": 8.0,
                "elevation_gain_m": 400,
                "category": "2",
            }
        ]

        repo = PostgresCourseRepo(db_session)
        await repo.update_processed_data(
            course_id, seed_user.id, elevation_profile, segments, climbs
        )

        # Re-fetch to verify (get_by_id uses populate_existing)
        updated = await repo.get_by_id(course_id, seed_user.id)

        assert updated is not None
        assert updated.elevation_profile == elevation_profile
        assert updated.segments == segments
        assert updated.climbs == climbs

    @pytest.mark.asyncio
    async def test_update_processed_data_other_user(self, db_session, seed_user):
        """Cannot update another user's course processed data."""
        # Create another user
        other_user = User(email="update-other-course@example.com", password_hash="x")
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        # Create course for other user
        wkt = "SRID=4326;LINESTRINGZ(0 0 100, 1 1 200)"
        course = RaceCourse(
            user_id=other_user.id,
            name="Other's Course",
            source_type="gpx",
            distance_m=1000.0,
            elevation_gain_m=100.0,
            elevation_loss_m=0.0,
            geometry=wkt,
        )
        db_session.add(course)
        await db_session.commit()
        course_id = course.id

        repo = PostgresCourseRepo(db_session)
        # This should not update anything (wrong user_id)
        await repo.update_processed_data(
            course_id,
            seed_user.id,  # Wrong user
            [{"test": 1}],
            [{"test": 2}],
            [{"test": 3}],
        )

        # Re-fetch as the owner to verify not updated
        fetched = await repo.get_by_id(course_id, other_user.id)
        assert fetched.elevation_profile is None
