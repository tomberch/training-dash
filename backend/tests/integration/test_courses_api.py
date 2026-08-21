"""Integration tests for the Courses API router."""

from pathlib import Path

import pytest


# Path to test fixtures
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "courses"


@pytest.fixture
def gpx_with_elevation() -> bytes:
    """GPX file with elevation data."""
    return (FIXTURES_DIR / "simple_with_elevation.gpx").read_bytes()


@pytest.fixture
def gpx_no_elevation() -> bytes:
    """GPX file without elevation data."""
    return (FIXTURES_DIR / "simple_no_elevation.gpx").read_bytes()


@pytest.fixture
def fit_course() -> bytes:
    """FIT course file."""
    return (FIXTURES_DIR / "activity_as_course.fit").read_bytes()


@pytest.fixture
def gpx_malformed() -> bytes:
    """Malformed GPX file."""
    return (FIXTURES_DIR / "malformed.gpx").read_bytes()


class TestCoursesAPI:
    """Tests for /api/courses endpoints."""

    @pytest.mark.asyncio
    async def test_list_courses_empty(self, auth_client):
        """List courses returns empty when user has no courses."""
        response = await auth_client.get("/api/courses")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_upload_gpx_course(self, auth_client, gpx_with_elevation):
        """Upload GPX file creates a course."""
        response = await auth_client.post(
            "/api/courses",
            files={"file": ("test_course.gpx", gpx_with_elevation, "application/gpx+xml")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["source_type"] == "gpx"
        assert data["source_filename"] == "test_course.gpx"
        assert data["distance_m"] > 0
        assert data["elevation_gain_m"] >= 0
        assert data["elevation_loss_m"] >= 0
        assert data["warnings"] == []

    @pytest.mark.asyncio
    async def test_upload_gpx_with_custom_name(self, auth_client, gpx_with_elevation):
        """Upload GPX with custom name uses provided name."""
        response = await auth_client.post(
            "/api/courses",
            files={"file": ("course.gpx", gpx_with_elevation, "application/gpx+xml")},
            data={"name": "My Custom Course"},
        )
        assert response.status_code == 201
        assert response.json()["name"] == "My Custom Course"

    @pytest.mark.asyncio
    async def test_upload_gpx_without_elevation_returns_warning(
        self, auth_client, gpx_no_elevation
    ):
        """Upload GPX without elevation data returns warning."""
        response = await auth_client.post(
            "/api/courses",
            files={"file": ("flat.gpx", gpx_no_elevation, "application/gpx+xml")},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["warnings"]) == 1
        assert "elevation" in data["warnings"][0].lower()

    @pytest.mark.asyncio
    async def test_upload_fit_course(self, auth_client, fit_course):
        """Upload FIT file creates a course."""
        response = await auth_client.post(
            "/api/courses",
            files={"file": ("race.fit", fit_course, "application/octet-stream")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_type"] == "fit"
        assert data["source_filename"] == "race.fit"
        assert data["distance_m"] > 0

    @pytest.mark.asyncio
    async def test_upload_invalid_file_returns_400(self, auth_client):
        """Upload invalid file returns 400."""
        response = await auth_client.post(
            "/api/courses",
            files={"file": ("bad.xyz", b"not a valid file", "application/octet-stream")},
        )
        assert response.status_code == 400
        assert "cannot determine file type" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_malformed_gpx_returns_400(self, auth_client, gpx_malformed):
        """Upload malformed GPX returns 400."""
        response = await auth_client.post(
            "/api/courses",
            files={"file": ("bad.gpx", gpx_malformed, "application/gpx+xml")},
        )
        assert response.status_code == 400
        assert "parse" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_empty_file_returns_400(self, auth_client):
        """Upload empty file returns 400."""
        response = await auth_client.post(
            "/api/courses",
            files={"file": ("empty.gpx", b"", "application/gpx+xml")},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_courses_returns_created(self, auth_client, gpx_with_elevation):
        """List courses returns courses created by the user."""
        # Create two courses
        await auth_client.post(
            "/api/courses",
            files={"file": ("course1.gpx", gpx_with_elevation, "application/gpx+xml")},
            data={"name": "Course A"},
        )
        await auth_client.post(
            "/api/courses",
            files={"file": ("course2.gpx", gpx_with_elevation, "application/gpx+xml")},
            data={"name": "Course B"},
        )

        response = await auth_client.get("/api/courses")
        assert response.status_code == 200
        courses = response.json()
        assert len(courses) == 2
        names = [c["name"] for c in courses]
        assert "Course A" in names
        assert "Course B" in names

    @pytest.mark.asyncio
    async def test_get_course_by_id(self, auth_client, gpx_with_elevation):
        """Get a single course by ID."""
        create_response = await auth_client.post(
            "/api/courses",
            files={"file": ("test.gpx", gpx_with_elevation, "application/gpx+xml")},
            data={"name": "Test Course"},
        )
        course_id = create_response.json()["id"]

        response = await auth_client.get(f"/api/courses/{course_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test Course"
        assert data["id"] == course_id
        assert "segments" in data
        assert "climbs" in data
        assert "elevation_profile" in data
        assert isinstance(data["segments"], list)
        assert isinstance(data["climbs"], list)
        assert isinstance(data["elevation_profile"], list)

    @pytest.mark.asyncio
    async def test_get_course_returns_elevation_profile(
        self, auth_client, gpx_with_elevation
    ):
        """Get course returns elevation profile with correct structure."""
        create_response = await auth_client.post(
            "/api/courses",
            files={"file": ("test.gpx", gpx_with_elevation, "application/gpx+xml")},
        )
        course_id = create_response.json()["id"]

        response = await auth_client.get(f"/api/courses/{course_id}")
        assert response.status_code == 200
        profile = response.json()["elevation_profile"]
        assert len(profile) > 0

        # Check structure
        point = profile[0]
        assert "distance_m" in point
        assert "elevation_m" in point
        assert "grade_pct" in point

    @pytest.mark.asyncio
    async def test_get_course_not_found(self, auth_client):
        """Get non-existent course returns 404."""
        response = await auth_client.get("/api/courses/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_course(self, auth_client, gpx_with_elevation):
        """Delete a course."""
        create_response = await auth_client.post(
            "/api/courses",
            files={"file": ("test.gpx", gpx_with_elevation, "application/gpx+xml")},
        )
        course_id = create_response.json()["id"]

        # Delete it
        response = await auth_client.delete(f"/api/courses/{course_id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = await auth_client.get(f"/api/courses/{course_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_course_not_found(self, auth_client):
        """Delete non-existent course returns 404."""
        response = await auth_client.delete("/api/courses/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_access(self, app_client):
        """Unauthenticated user cannot access courses endpoints."""
        response = await app_client.get("/api/courses")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_upload(self, app_client, gpx_with_elevation):
        """Unauthenticated user cannot upload courses."""
        response = await app_client.post(
            "/api/courses",
            files={"file": ("test.gpx", gpx_with_elevation, "application/gpx+xml")},
        )
        assert response.status_code == 401


class TestCourseIsolation:
    """Tests for multi-user course isolation."""

    @pytest.mark.asyncio
    async def test_courses_scoped_to_user(
        self, auth_client, app_client, gpx_with_elevation, db_session
    ):
        """User cannot see another user's courses."""
        # Create course as test user (auth_client)
        create_response = await auth_client.post(
            "/api/courses",
            files={"file": ("private.gpx", gpx_with_elevation, "application/gpx+xml")},
            data={"name": "Private Course"},
        )
        course_id = create_response.json()["id"]

        # Create another user and login
        from tests.integration.fixtures import CACHED_HASH_TESTPASS
        from trainingdash.repositories.postgres.models import User

        other_user = User(
            email="other@example.com",
            password_hash=CACHED_HASH_TESTPASS,
        )
        db_session.add(other_user)
        await db_session.commit()

        # Login as other user
        login_response = await app_client.post(
            "/api/login",
            json={"email": "other@example.com", "password": "testpass"},
        )
        assert login_response.status_code == 200

        # Other user's list should be empty
        list_response = await app_client.get("/api/courses")
        assert list_response.status_code == 200
        assert list_response.json() == []

        # Other user cannot access first user's course
        get_response = await app_client.get(f"/api/courses/{course_id}")
        assert get_response.status_code == 404

        # Other user cannot delete first user's course
        delete_response = await app_client.delete(f"/api/courses/{course_id}")
        assert delete_response.status_code == 404
