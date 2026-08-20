"""Integration tests for the Bikes API router."""

import pytest

from trainingdash.repositories.postgres.models import Bike


class TestBikesAPI:
    """Tests for /api/bikes endpoints."""

    @pytest.mark.asyncio
    async def test_list_bikes_empty(self, auth_client):
        """List bikes returns empty when user has no bikes."""
        response = await auth_client.get("/api/bikes")
        assert response.status_code == 200
        data = response.json()
        assert data["bikes"] == []

    @pytest.mark.asyncio
    async def test_create_bike(self, auth_client):
        """Create a bike with minimal fields."""
        response = await auth_client.post(
            "/api/bikes",
            json={"name": "Canyon Aeroad", "bike_type": "road"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Canyon Aeroad"
        assert data["bike_type"] == "road"
        assert data["id"] is not None
        assert data["is_default"] is False
        assert data["retired_at"] is None

    @pytest.mark.asyncio
    async def test_create_bike_with_all_fields(self, auth_client):
        """Create a bike with all optional fields."""
        response = await auth_client.post(
            "/api/bikes",
            json={
                "name": "Specialized Shiv",
                "bike_type": "tt",
                "model_year": 2023,
                "weight_kg": 8.5,
                "cda": 0.22,
                "crr": 0.003,
                "is_default": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Specialized Shiv"
        assert data["bike_type"] == "tt"
        assert data["model_year"] == 2023
        assert data["weight_kg"] == 8.5
        assert data["cda"] == 0.22
        assert data["crr"] == 0.003
        assert data["is_default"] is True
        assert data["cda_source"] == "manual"
        assert data["crr_source"] == "manual"

    @pytest.mark.asyncio
    async def test_create_bike_invalid_type(self, auth_client):
        """Create bike with invalid type returns 400."""
        response = await auth_client.post(
            "/api/bikes",
            json={"name": "Test", "bike_type": "invalid"},
        )
        assert response.status_code == 400
        assert "Invalid bike_type" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_bikes_returns_created(self, auth_client):
        """List bikes returns bikes created by the user."""
        # Create two bikes
        await auth_client.post("/api/bikes", json={"name": "Bike A", "bike_type": "road"})
        await auth_client.post("/api/bikes", json={"name": "Bike B", "bike_type": "gravel"})

        response = await auth_client.get("/api/bikes")
        assert response.status_code == 200
        bikes = response.json()["bikes"]
        assert len(bikes) == 2
        names = [b["name"] for b in bikes]
        assert "Bike A" in names
        assert "Bike B" in names

    @pytest.mark.asyncio
    async def test_get_bike_by_id(self, auth_client):
        """Get a single bike by ID."""
        create_response = await auth_client.post(
            "/api/bikes",
            json={"name": "Test Bike", "bike_type": "mtb"},
        )
        bike_id = create_response.json()["id"]

        response = await auth_client.get(f"/api/bikes/{bike_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Test Bike"
        assert response.json()["bike_type"] == "mtb"

    @pytest.mark.asyncio
    async def test_get_bike_not_found(self, auth_client):
        """Get non-existent bike returns 404."""
        response = await auth_client.get("/api/bikes/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_bike(self, auth_client):
        """Update bike fields."""
        create_response = await auth_client.post(
            "/api/bikes",
            json={"name": "Old Name", "bike_type": "road"},
        )
        bike_id = create_response.json()["id"]

        response = await auth_client.patch(
            f"/api/bikes/{bike_id}",
            json={"name": "New Name", "weight_kg": 7.5},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["weight_kg"] == 7.5

    @pytest.mark.asyncio
    async def test_update_bike_cda_sets_source(self, auth_client):
        """Updating CdA sets cda_source to manual."""
        create_response = await auth_client.post(
            "/api/bikes",
            json={"name": "Test", "bike_type": "road"},
        )
        bike_id = create_response.json()["id"]
        assert create_response.json()["cda_source"] is None

        response = await auth_client.patch(
            f"/api/bikes/{bike_id}",
            json={"cda": 0.28},
        )
        assert response.status_code == 200
        assert response.json()["cda"] == 0.28
        assert response.json()["cda_source"] == "manual"

    @pytest.mark.asyncio
    async def test_update_bike_not_found(self, auth_client):
        """Update non-existent bike returns 404."""
        response = await auth_client.patch(
            "/api/bikes/99999",
            json={"name": "Test"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_set_default_bike(self, auth_client):
        """Set a bike as default."""
        create_response = await auth_client.post(
            "/api/bikes",
            json={"name": "Default Bike", "bike_type": "road"},
        )
        bike_id = create_response.json()["id"]
        assert create_response.json()["is_default"] is False

        response = await auth_client.post(f"/api/bikes/{bike_id}/default")
        assert response.status_code == 200
        assert response.json()["is_default"] is True

    @pytest.mark.asyncio
    async def test_set_default_clears_previous(self, auth_client):
        """Setting default clears previous default."""
        # Create first bike as default
        create1 = await auth_client.post(
            "/api/bikes",
            json={"name": "Bike 1", "bike_type": "road", "is_default": True},
        )
        bike1_id = create1.json()["id"]

        # Create second bike
        create2 = await auth_client.post(
            "/api/bikes",
            json={"name": "Bike 2", "bike_type": "gravel"},
        )
        bike2_id = create2.json()["id"]

        # Set bike 2 as default
        await auth_client.post(f"/api/bikes/{bike2_id}/default")

        # Check bike 1 is no longer default
        get1 = await auth_client.get(f"/api/bikes/{bike1_id}")
        assert get1.json()["is_default"] is False

        # Check bike 2 is now default
        get2 = await auth_client.get(f"/api/bikes/{bike2_id}")
        assert get2.json()["is_default"] is True

    @pytest.mark.asyncio
    async def test_set_default_not_found(self, auth_client):
        """Set default on non-existent bike returns 404."""
        response = await auth_client.post("/api/bikes/99999/default")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_retire_bike(self, auth_client):
        """Retire a bike."""
        create_response = await auth_client.post(
            "/api/bikes",
            json={"name": "To Retire", "bike_type": "road"},
        )
        bike_id = create_response.json()["id"]

        response = await auth_client.post(f"/api/bikes/{bike_id}/retire")
        assert response.status_code == 200
        assert response.json()["retired_at"] is not None

    @pytest.mark.asyncio
    async def test_retire_clears_default(self, auth_client):
        """Retiring a default bike clears default status."""
        create_response = await auth_client.post(
            "/api/bikes",
            json={"name": "Default", "bike_type": "road", "is_default": True},
        )
        bike_id = create_response.json()["id"]
        assert create_response.json()["is_default"] is True

        response = await auth_client.post(f"/api/bikes/{bike_id}/retire")
        assert response.status_code == 200
        assert response.json()["is_default"] is False
        assert response.json()["retired_at"] is not None

    @pytest.mark.asyncio
    async def test_retire_not_found(self, auth_client):
        """Retire non-existent bike returns 404."""
        response = await auth_client.post("/api/bikes/99999/retire")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_excludes_retired_by_default(self, auth_client):
        """List bikes excludes retired bikes by default."""
        # Create active and retired bikes
        await auth_client.post("/api/bikes", json={"name": "Active", "bike_type": "road"})
        create2 = await auth_client.post("/api/bikes", json={"name": "Retired", "bike_type": "gravel"})
        await auth_client.post(f"/api/bikes/{create2.json()['id']}/retire")

        response = await auth_client.get("/api/bikes")
        bikes = response.json()["bikes"]
        assert len(bikes) == 1
        assert bikes[0]["name"] == "Active"

    @pytest.mark.asyncio
    async def test_list_includes_retired_when_requested(self, auth_client):
        """List bikes includes retired when include_retired=true."""
        # Create active and retired bikes
        await auth_client.post("/api/bikes", json={"name": "Active", "bike_type": "road"})
        create2 = await auth_client.post("/api/bikes", json={"name": "Retired", "bike_type": "gravel"})
        await auth_client.post(f"/api/bikes/{create2.json()['id']}/retire")

        response = await auth_client.get("/api/bikes?include_retired=true")
        bikes = response.json()["bikes"]
        assert len(bikes) == 2

    @pytest.mark.asyncio
    async def test_cannot_update_retired_bike(self, auth_client):
        """Cannot update a retired bike."""
        create_response = await auth_client.post(
            "/api/bikes",
            json={"name": "Retired", "bike_type": "road"},
        )
        bike_id = create_response.json()["id"]
        await auth_client.post(f"/api/bikes/{bike_id}/retire")

        response = await auth_client.patch(
            f"/api/bikes/{bike_id}",
            json={"name": "New Name"},
        )
        assert response.status_code == 400
        assert "retired" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_cannot_set_retired_as_default(self, auth_client):
        """Cannot set a retired bike as default."""
        create_response = await auth_client.post(
            "/api/bikes",
            json={"name": "Retired", "bike_type": "road"},
        )
        bike_id = create_response.json()["id"]
        await auth_client.post(f"/api/bikes/{bike_id}/retire")

        response = await auth_client.post(f"/api/bikes/{bike_id}/default")
        assert response.status_code == 400
        assert "retired" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_unauthenticated_cannot_access(self, app_client):
        """Unauthenticated user cannot access bikes endpoints."""
        # app_client is not logged in
        response = await app_client.get("/api/bikes")
        assert response.status_code == 401
