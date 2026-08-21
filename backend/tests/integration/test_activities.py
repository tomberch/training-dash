import sys
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit

from trainingdash.repositories.postgres.models import Record


class TestActivityEndpoints:
    @pytest.mark.asyncio
    async def test_list_activities_returns_newest_first(self, auth_client):
        for i in range(3):
            fit_data = make_test_fit(num_records=5)
            await auth_client.post(
                "/api/upload",
                files={"file": (f"test_{i}.fit", fit_data, "application/octet-stream")},
            )
        response = await auth_client.get("/api/activities")
        assert response.status_code == 200
        data = response.json()
        activities = data["activities"]
        assert len(activities) == 3
        dates = [a["started_at"] for a in activities]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.asyncio
    async def test_get_activity_returns_summary_fields(self, auth_client):
        fit_data = make_test_fit(num_records=10)
        upload_resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]
        response = await auth_client.get(f"/api/activities/{activity_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == activity_id
        assert data["total_distance_m"] == 90.0
        assert "started_at" in data
        assert "elevation_gain_m" in data
        assert "avg_speed_mps" in data

    @pytest.mark.asyncio
    async def test_get_activity_records_returns_geojson_for_map(self, auth_client):
        fit_data = make_test_fit(num_records=5)
        upload_resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]
        response = await auth_client.get(f"/api/activities/{activity_id}/records")
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "FeatureCollection"
        assert data["activity_id"] == activity_id
        assert len(data["features"]) == 5
        f0 = data["features"][0]
        assert f0["type"] == "Feature"
        assert f0["geometry"]["type"] == "Point"
        assert f0["geometry"]["coordinates"] is not None
        assert len(f0["geometry"]["coordinates"]) == 2
        assert "distance_m" in f0["properties"]
        assert "hr_bpm" in f0["properties"]
        assert "speed_mps" in f0["properties"]

    @pytest.mark.asyncio
    async def test_get_activity_not_found(self, auth_client):
        # Use a valid UUID format that doesn't exist
        response = await auth_client.get("/api/activities/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_no_gps_still_succeeds_and_records_have_null_geom(self, auth_client, db_session):
        from uuid import UUID as UUIDType

        fit_data = make_test_fit(num_records=5, include_gps=False)
        response = await auth_client.post(
            "/api/upload",
            files={"file": ("no_gps.fit", fit_data, "application/octet-stream")},
        )
        assert response.status_code == 200
        activity_id = UUIDType(response.json()["id"])
        result = await db_session.execute(select(Record).where(Record.activity_id == activity_id))
        records = result.scalars().all()
        assert len(records) == 5
        assert all(r.lat is None for r in records)
        assert all(r.lon is None for r in records)
        assert all(r.geom is None for r in records)

    @pytest.mark.asyncio
    async def test_no_gps_activity_summary_still_computed(self, auth_client):
        fit_data = make_test_fit(num_records=5, include_gps=False)
        upload_resp = await auth_client.post(
            "/api/upload",
            files={"file": ("no_gps.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]
        response = await auth_client.get(f"/api/activities/{activity_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total_distance_m"] == 40.0
        assert data["avg_hr_bpm"] == 140

    @pytest.mark.asyncio
    async def test_empty_activity_list(self, auth_client):
        response = await auth_client.get("/api/activities")
        assert response.status_code == 200
        data = response.json()
        assert data["activities"] == []
        assert data["pagination"]["total"] == 0

    @pytest.mark.asyncio
    async def test_records_have_distance_m_for_resampling(self, auth_client):
        fit_data = make_test_fit(num_records=10)
        upload_resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        activity_id = upload_resp.json()["id"]
        response = await auth_client.get(f"/api/activities/{activity_id}/records")
        data = response.json()
        features = data["features"]
        distances = [f["properties"]["distance_m"] for f in features]
        assert distances[0] == 0
        assert distances[-1] == 90.0
        assert distances == sorted(distances)
        # Verify resampling fields are present and non-null
        r0 = features[0]["properties"]
        assert r0["hr_bpm"] is not None
        assert r0["power_w"] is not None
        assert r0["speed_mps"] is not None
        assert r0["altitude_m"] is not None


class TestDeleteActivity:
    """Tests for DELETE /api/activities/{activity_id}."""

    async def _upload(self, auth_client) -> str:
        """Upload a minimal test activity and return its id."""
        fit_data = make_test_fit(num_records=5)
        resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert resp.status_code in (200, 202)
        return resp.json()["id"]

    @pytest.mark.asyncio
    async def test_delete_returns_204(self, auth_client):
        """Owner can delete their own activity."""
        activity_id = await self._upload(auth_client)
        response = await auth_client.delete(f"/api/activities/{activity_id}")
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_removes_activity_from_db(self, auth_client):
        """Activity is gone from the database after deletion."""
        activity_id = await self._upload(auth_client)
        await auth_client.delete(f"/api/activities/{activity_id}")
        get_resp = await auth_client.get(f"/api/activities/{activity_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_cascades_records(self, auth_client, db_session):
        """Records belonging to the deleted activity are removed via CASCADE."""
        activity_id = await self._upload(auth_client)
        from uuid import UUID

        from trainingdash.repositories.postgres.models import Record

        records_before = (
            (await db_session.execute(select(Record).where(Record.activity_id == UUID(activity_id)))).scalars().all()
        )
        assert len(records_before) > 0

        await auth_client.delete(f"/api/activities/{activity_id}")
        records_after = (
            (await db_session.execute(select(Record).where(Record.activity_id == UUID(activity_id)))).scalars().all()
        )
        assert len(records_after) == 0

    @pytest.mark.asyncio
    async def test_delete_not_found_returns_404(self, auth_client):
        """Deleting a non-existent activity returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await auth_client.delete(f"/api/activities/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_other_users_activity_returns_404(self, app_client, db_session):
        """A user cannot delete another user's activity (404, not 403)."""
        import datetime

        from tests.integration.fixtures import CACHED_HASH_TESTPASS
        from trainingdash.repositories.postgres.models import Activity as ActivityModel
        from trainingdash.repositories.postgres.models import User

        # Create a second user and one of their activities
        other_user = User(
            email="other@example.com",
            password_hash=CACHED_HASH_TESTPASS,
        )
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        other_activity = ActivityModel(
            user_id=other_user.id,
            source="upload",
            source_ref="other.fit",
            started_at=datetime.datetime(2024, 1, 1, 8, 0, 0),
            total_distance_m=1000,
            moving_time_s=600,
            elapsed_time_s=600,
        )
        db_session.add(other_activity)
        await db_session.commit()
        await db_session.refresh(other_activity)

        # Log in as the seed user (not the owner)
        login = await app_client.post(
            "/api/login",
            json={"email": "testuser@example.com", "password": "testpass"},
        )
        assert login.status_code == 200

        response = await app_client.delete(f"/api/activities/{other_activity.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_decrements_route_ride_count(self, auth_client, db_session):
        """Route.ride_count is decremented when one of its activities is deleted."""
        from uuid import UUID

        from trainingdash.repositories.postgres.models import Activity as ActivityModel
        from trainingdash.repositories.postgres.models import Route

        # Upload two activities so they can share a route
        id1 = await self._upload(auth_client)
        id2 = await self._upload(auth_client)

        # Manually assign both to the same route
        act1 = (await db_session.execute(select(ActivityModel).where(ActivityModel.id == UUID(id1)))).scalar_one()
        act2 = (await db_session.execute(select(ActivityModel).where(ActivityModel.id == UUID(id2)))).scalar_one()

        route = Route(
            user_id=act1.user_id,
            simplified_polyline="SRID=4326;LINESTRING(0 0, 1 1)",
            first_seen_activity_id=act1.id,
            ride_count=2,
        )
        db_session.add(route)
        await db_session.flush()
        act1.route_id = route.id
        act2.route_id = route.id
        await db_session.commit()

        # Delete the second activity (not first_seen)
        resp = await auth_client.delete(f"/api/activities/{id2}")
        assert resp.status_code == 204

        await db_session.refresh(route)
        assert route.ride_count == 1
        assert route.first_seen_activity_id == act1.id

    @pytest.mark.asyncio
    async def test_delete_first_seen_repairs_route(self, auth_client, db_session):
        """first_seen_activity_id is nulled (ON DELETE SET NULL) when the first-seen activity is deleted."""
        from uuid import UUID

        from trainingdash.repositories.postgres.models import Activity as ActivityModel
        from trainingdash.repositories.postgres.models import Route

        id1 = await self._upload(auth_client)
        id2 = await self._upload(auth_client)

        act1 = (await db_session.execute(select(ActivityModel).where(ActivityModel.id == UUID(id1)))).scalar_one()
        act2 = (await db_session.execute(select(ActivityModel).where(ActivityModel.id == UUID(id2)))).scalar_one()

        route = Route(
            user_id=act1.user_id,
            simplified_polyline="SRID=4326;LINESTRING(0 0, 1 1)",
            first_seen_activity_id=act1.id,
            ride_count=2,
        )
        db_session.add(route)
        await db_session.flush()
        act1.route_id = route.id
        act2.route_id = route.id
        await db_session.commit()

        # Delete the first-seen activity
        resp = await auth_client.delete(f"/api/activities/{id1}")
        assert resp.status_code == 204

        await db_session.refresh(route)
        # ON DELETE SET NULL means first_seen_activity_id becomes NULL
        assert route.first_seen_activity_id is None
        assert route.ride_count == 1

    @pytest.mark.asyncio
    async def test_delete_sole_activity_removes_route(self, auth_client, db_session):
        """Route is deleted when the last activity on it is removed."""
        from uuid import UUID

        from trainingdash.repositories.postgres.models import Activity as ActivityModel
        from trainingdash.repositories.postgres.models import Route

        activity_id = await self._upload(auth_client)
        act = (
            await db_session.execute(select(ActivityModel).where(ActivityModel.id == UUID(activity_id)))
        ).scalar_one()

        route = Route(
            user_id=act.user_id,
            simplified_polyline="SRID=4326;LINESTRING(0 0, 1 1)",
            first_seen_activity_id=act.id,
            ride_count=1,
        )
        db_session.add(route)
        await db_session.flush()
        act.route_id = route.id
        route_id = route.id
        await db_session.commit()

        resp = await auth_client.delete(f"/api/activities/{activity_id}")
        assert resp.status_code == 204

        deleted_route = (await db_session.execute(select(Route).where(Route.id == route_id))).scalar_one_or_none()
        assert deleted_route is None


class TestActivityType:
    """Tests for activity_type field and filtering."""

    async def _upload(self, auth_client) -> str:
        """Upload a minimal test activity and return its id."""
        fit_data = make_test_fit(num_records=5)
        resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert resp.status_code in (200, 202)
        return resp.json()["id"]

    @pytest.mark.asyncio
    async def test_activity_type_in_list_response(self, auth_client):
        """Activity list includes activity_type field."""
        await self._upload(auth_client)
        response = await auth_client.get("/api/activities")
        assert response.status_code == 200
        data = response.json()
        assert len(data["activities"]) == 1
        # activity_type should be present (may be null for test FIT files)
        assert "activity_type" in data["activities"][0]

    @pytest.mark.asyncio
    async def test_activity_type_in_detail_response(self, auth_client):
        """Activity detail includes activity_type field."""
        activity_id = await self._upload(auth_client)
        response = await auth_client.get(f"/api/activities/{activity_id}")
        assert response.status_code == 200
        data = response.json()
        assert "activity_type" in data

    @pytest.mark.asyncio
    async def test_update_activity_type(self, auth_client):
        """PATCH can update activity_type."""
        activity_id = await self._upload(auth_client)

        response = await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"activity_type": "gravel"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["activity_type"] == "gravel"

        # Verify it persisted
        get_resp = await auth_client.get(f"/api/activities/{activity_id}")
        assert get_resp.json()["activity_type"] == "gravel"

    @pytest.mark.asyncio
    async def test_update_activity_type_to_null(self, auth_client):
        """PATCH with empty string sets activity_type to null."""
        activity_id = await self._upload(auth_client)

        # First set it to something
        await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"activity_type": "road"},
        )

        # Then clear it
        response = await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"activity_type": ""},
        )
        assert response.status_code == 200
        assert response.json()["activity_type"] is None

    @pytest.mark.asyncio
    async def test_update_activity_type_invalid(self, auth_client):
        """PATCH with invalid activity_type returns 400."""
        activity_id = await self._upload(auth_client)

        response = await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"activity_type": "invalid_type"},
        )
        assert response.status_code == 400
        assert "Invalid activity_type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_filter_activities_by_type(self, auth_client, db_session):
        """GET /activities?activity_type= filters by type."""
        from uuid import UUID

        from trainingdash.repositories.postgres.models import Activity as ActivityModel

        # Upload 3 activities
        id1 = await self._upload(auth_client)
        id2 = await self._upload(auth_client)
        id3 = await self._upload(auth_client)

        # Set different types directly in DB
        act1 = (await db_session.execute(select(ActivityModel).where(ActivityModel.id == UUID(id1)))).scalar_one()
        act2 = (await db_session.execute(select(ActivityModel).where(ActivityModel.id == UUID(id2)))).scalar_one()
        act3 = (await db_session.execute(select(ActivityModel).where(ActivityModel.id == UUID(id3)))).scalar_one()

        act1.activity_type = "road"
        act2.activity_type = "gravel"
        act3.activity_type = "road"
        await db_session.commit()

        # Filter by road
        response = await auth_client.get("/api/activities?activity_type=road")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 2
        assert all(a["activity_type"] == "road" for a in data["activities"])

        # Filter by gravel
        response = await auth_client.get("/api/activities?activity_type=gravel")
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert data["activities"][0]["activity_type"] == "gravel"

    @pytest.mark.asyncio
    async def test_filter_activities_by_unclassified(self, auth_client, db_session):
        """GET /activities?activity_type= with empty string filters for NULL."""
        from uuid import UUID

        from trainingdash.repositories.postgres.models import Activity as ActivityModel

        id1 = await self._upload(auth_client)
        id2 = await self._upload(auth_client)

        # Set one to road, set one to null (unclassified)
        act1 = (await db_session.execute(select(ActivityModel).where(ActivityModel.id == UUID(id1)))).scalar_one()
        act2 = (await db_session.execute(select(ActivityModel).where(ActivityModel.id == UUID(id2)))).scalar_one()
        act1.activity_type = "road"
        act2.activity_type = None  # Explicitly set to unclassified
        await db_session.commit()

        # Filter for unclassified (null)
        response = await auth_client.get("/api/activities?activity_type=")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 1
        assert data["activities"][0]["activity_type"] is None

    @pytest.mark.asyncio
    async def test_no_filter_returns_all(self, auth_client, db_session):
        """GET /activities without filter returns all types."""
        from uuid import UUID

        from trainingdash.repositories.postgres.models import Activity as ActivityModel

        id1 = await self._upload(auth_client)
        id2 = await self._upload(auth_client)

        act1 = (await db_session.execute(select(ActivityModel).where(ActivityModel.id == UUID(id1)))).scalar_one()
        act1.activity_type = "road"
        await db_session.commit()

        response = await auth_client.get("/api/activities")
        assert response.status_code == 200
        data = response.json()
        assert data["pagination"]["total"] == 2


class TestActivityBikeTagging:
    """Tests for activity bike tagging via PATCH /api/activities/{id}."""

    async def _upload(self, auth_client) -> str:
        """Upload a minimal test activity and return its id."""
        fit_data = make_test_fit(num_records=5)
        resp = await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        assert resp.status_code in (200, 202)
        return resp.json()["id"]

    async def _create_bike(self, auth_client, name: str = "Test Bike") -> int:
        """Create a bike and return its id."""
        resp = await auth_client.post(
            "/api/bikes",
            json={"name": name, "bike_type": "road"},
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    @pytest.mark.asyncio
    async def test_activity_includes_bike_id_in_response(self, auth_client):
        """Activity response includes bike_id field."""
        activity_id = await self._upload(auth_client)
        response = await auth_client.get(f"/api/activities/{activity_id}")
        assert response.status_code == 200
        data = response.json()
        assert "bike_id" in data
        assert data["bike_id"] is None  # No bike assigned yet

    @pytest.mark.asyncio
    async def test_activity_includes_bike_summary_in_list(self, auth_client):
        """Activity list response includes bike_id and bike summary fields."""
        await self._upload(auth_client)
        response = await auth_client.get("/api/activities")
        assert response.status_code == 200
        activity = response.json()["activities"][0]
        assert "bike_id" in activity
        assert "bike" in activity
        assert activity["bike"] is None  # No bike assigned

    @pytest.mark.asyncio
    async def test_assign_bike_to_activity(self, auth_client):
        """PATCH can assign a bike to an activity."""
        activity_id = await self._upload(auth_client)
        bike_id = await self._create_bike(auth_client)

        response = await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": bike_id},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["bike_id"] == bike_id
        assert data["bike"] is not None
        assert data["bike"]["id"] == bike_id
        assert data["bike"]["name"] == "Test Bike"

    @pytest.mark.asyncio
    async def test_assign_bike_persists(self, auth_client):
        """Assigned bike is persisted and returned on subsequent requests."""
        activity_id = await self._upload(auth_client)
        bike_id = await self._create_bike(auth_client)

        await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": bike_id},
        )

        # Verify via GET
        get_resp = await auth_client.get(f"/api/activities/{activity_id}")
        assert get_resp.json()["bike_id"] == bike_id

    @pytest.mark.asyncio
    async def test_remove_bike_from_activity(self, auth_client):
        """PATCH with bike_id=null removes the bike."""
        activity_id = await self._upload(auth_client)
        bike_id = await self._create_bike(auth_client)

        # First assign
        await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": bike_id},
        )

        # Then remove
        response = await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": None},
        )
        assert response.status_code == 200
        assert response.json()["bike_id"] is None
        assert response.json()["bike"] is None

    @pytest.mark.asyncio
    async def test_change_bike_on_activity(self, auth_client):
        """PATCH can change from one bike to another."""
        activity_id = await self._upload(auth_client)
        bike1_id = await self._create_bike(auth_client, "Bike 1")
        bike2_id = await self._create_bike(auth_client, "Bike 2")

        # Assign first bike
        await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": bike1_id},
        )

        # Change to second bike
        response = await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": bike2_id},
        )
        assert response.status_code == 200
        assert response.json()["bike_id"] == bike2_id
        assert response.json()["bike"]["name"] == "Bike 2"

    @pytest.mark.asyncio
    async def test_cannot_assign_nonexistent_bike(self, auth_client):
        """Cannot assign a bike that doesn't exist."""
        activity_id = await self._upload(auth_client)

        response = await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": 99999},
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_cannot_assign_other_users_bike(self, auth_client, app_client, db_session):
        """Cannot assign another user's bike to an activity."""
        from tests.integration.fixtures import CACHED_HASH_TESTPASS
        from trainingdash.repositories.postgres.models import Bike, User

        activity_id = await self._upload(auth_client)

        # Create another user with a bike
        other_user = User(email="other@example.com", password_hash=CACHED_HASH_TESTPASS)
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        other_bike = Bike(user_id=other_user.id, name="Other's Bike", bike_type="road")
        db_session.add(other_bike)
        await db_session.commit()
        await db_session.refresh(other_bike)

        response = await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": other_bike.id},
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_cannot_assign_retired_bike(self, auth_client):
        """Cannot assign a retired bike to an activity."""
        activity_id = await self._upload(auth_client)
        bike_id = await self._create_bike(auth_client)

        # Retire the bike
        await auth_client.post(f"/api/bikes/{bike_id}/retire")

        response = await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": bike_id},
        )
        assert response.status_code == 400
        assert "retired" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_bike_distance_updates_on_assign(self, auth_client):
        """Assigning a bike adds the activity distance to bike total."""
        activity_id = await self._upload(auth_client)
        bike_id = await self._create_bike(auth_client)

        # Get activity distance
        activity_resp = await auth_client.get(f"/api/activities/{activity_id}")
        activity_distance = activity_resp.json()["total_distance_m"]

        # Check bike distance before
        bike_before = await auth_client.get(f"/api/bikes/{bike_id}")
        assert bike_before.json()["total_distance_m"] == 0

        # Assign bike
        await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": bike_id},
        )

        # Check bike distance after
        bike_after = await auth_client.get(f"/api/bikes/{bike_id}")
        assert bike_after.json()["total_distance_m"] == activity_distance

    @pytest.mark.asyncio
    async def test_bike_distance_updates_on_remove(self, auth_client):
        """Removing a bike subtracts the activity distance from bike total."""
        activity_id = await self._upload(auth_client)
        bike_id = await self._create_bike(auth_client)

        # Assign bike
        await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": bike_id},
        )

        # Get activity distance
        activity_resp = await auth_client.get(f"/api/activities/{activity_id}")
        activity_distance = activity_resp.json()["total_distance_m"]

        # Verify bike has distance
        bike_mid = await auth_client.get(f"/api/bikes/{bike_id}")
        assert bike_mid.json()["total_distance_m"] == activity_distance

        # Remove bike
        await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": None},
        )

        # Check bike distance is back to 0
        bike_after = await auth_client.get(f"/api/bikes/{bike_id}")
        assert bike_after.json()["total_distance_m"] == 0

    @pytest.mark.asyncio
    async def test_bike_distance_updates_on_change(self, auth_client):
        """Changing bikes transfers distance from old to new bike."""
        activity_id = await self._upload(auth_client)
        bike1_id = await self._create_bike(auth_client, "Bike 1")
        bike2_id = await self._create_bike(auth_client, "Bike 2")

        # Assign to first bike
        await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": bike1_id},
        )

        # Get activity distance
        activity_resp = await auth_client.get(f"/api/activities/{activity_id}")
        activity_distance = activity_resp.json()["total_distance_m"]

        # Verify bike 1 has distance
        bike1_mid = await auth_client.get(f"/api/bikes/{bike1_id}")
        assert bike1_mid.json()["total_distance_m"] == activity_distance

        # Change to second bike
        await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": bike2_id},
        )

        # Check bike 1 lost distance, bike 2 gained it
        bike1_after = await auth_client.get(f"/api/bikes/{bike1_id}")
        bike2_after = await auth_client.get(f"/api/bikes/{bike2_id}")
        assert bike1_after.json()["total_distance_m"] == 0
        assert bike2_after.json()["total_distance_m"] == activity_distance

    @pytest.mark.asyncio
    async def test_update_title_does_not_affect_bike(self, auth_client):
        """Updating title without bike_id doesn't change bike assignment."""
        activity_id = await self._upload(auth_client)
        bike_id = await self._create_bike(auth_client)

        # Assign bike
        await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"bike_id": bike_id},
        )

        # Update title only
        response = await auth_client.patch(
            f"/api/activities/{activity_id}",
            json={"title": "New Title"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "New Title"
        assert response.json()["bike_id"] == bike_id  # Bike unchanged
