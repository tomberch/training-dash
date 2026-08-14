"""Integration tests for saved filters CRUD API."""

import pytest


class TestSavedFiltersAPI:
    """Test saved filters CRUD endpoints."""

    # --- List ---

    @pytest.mark.asyncio
    async def test_list_empty(self, auth_client):
        """List returns empty when no filters exist."""
        resp = await auth_client.get("/api/saved-filters")
        assert resp.status_code == 200
        data = resp.json()
        assert data["filters"] == []

    @pytest.mark.asyncio
    async def test_list_returns_user_filters(self, auth_client):
        """List returns only filters for the authenticated user."""
        # Create a filter
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "High TSS", "query_text": "tss > 100"},
        )
        assert resp.status_code == 201

        # List should return it
        resp = await auth_client.get("/api/saved-filters")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["filters"]) == 1
        assert data["filters"][0]["name"] == "High TSS"

    # --- Create ---

    @pytest.mark.asyncio
    async def test_create_filter(self, auth_client):
        """Create a saved filter with valid query."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={
                "name": "Long Rides",
                "query_text": "distance > 50km",
                "description": "Rides over 50km",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Long Rides"
        assert data["query_text"] == "distance > 50km"
        assert data["description"] == "Rides over 50km"
        assert data["is_default"] is False
        assert "id" in data


    @pytest.mark.asyncio
    async def test_create_filter_with_default(self, auth_client):
        """Create a filter as default."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "My Default", "query_text": "tss > 50", "is_default": True},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["is_default"] is True

    @pytest.mark.asyncio
    async def test_create_filter_invalid_query(self, auth_client):
        """Create fails with invalid query syntax."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Bad Query", "query_text": "invalid syntax !!!"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data["detail"]
        assert data["detail"]["error"]["stage"] == "parse"

    @pytest.mark.asyncio
    async def test_create_filter_invalid_field(self, auth_client):
        """Create fails with unknown field."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Bad Field", "query_text": "unknown_field > 100"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data["detail"]
        assert data["detail"]["error"]["stage"] == "validation"

    @pytest.mark.asyncio
    async def test_create_filter_duplicate_name(self, auth_client):
        """Create fails if name already exists for user."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Unique Name", "query_text": "tss > 100"},
        )
        assert resp.status_code == 201
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Unique Name", "query_text": "tss > 200"},
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_filter_sets_new_default(self, auth_client):
        """Creating a default filter clears existing default."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "First Default", "query_text": "tss > 100", "is_default": True},
        )
        first_id = resp.json()["id"]
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Second Default", "query_text": "tss > 200", "is_default": True},
        )
        assert resp.json()["is_default"] is True
        resp = await auth_client.get(f"/api/saved-filters/{first_id}")
        assert resp.json()["is_default"] is False


    # --- Get by ID ---

    @pytest.mark.asyncio
    async def test_get_filter(self, auth_client):
        """Get a filter by ID."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Test Filter", "query_text": "tss > 100"},
        )
        filter_id = resp.json()["id"]
        resp = await auth_client.get(f"/api/saved-filters/{filter_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Test Filter"

    @pytest.mark.asyncio
    async def test_get_filter_not_found(self, auth_client):
        """Get returns 404 for non-existent filter."""
        resp = await auth_client.get("/api/saved-filters/99999")
        assert resp.status_code == 404

    # --- Get Default ---

    @pytest.mark.asyncio
    async def test_get_default_none(self, auth_client):
        """Get default returns null when no default set."""
        resp = await auth_client.get("/api/saved-filters/default")
        assert resp.status_code == 200
        assert resp.json() is None

    @pytest.mark.asyncio
    async def test_get_default(self, auth_client):
        """Get default returns the default filter."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "My Default", "query_text": "tss > 50", "is_default": True},
        )
        assert resp.status_code == 201
        resp = await auth_client.get("/api/saved-filters/default")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "My Default"
        assert data["is_default"] is True

    # --- Update ---

    @pytest.mark.asyncio
    async def test_update_filter_name(self, auth_client):
        """Update filter name."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Original", "query_text": "tss > 100"},
        )
        filter_id = resp.json()["id"]
        resp = await auth_client.patch(
            f"/api/saved-filters/{filter_id}",
            json={"name": "Renamed"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"


    @pytest.mark.asyncio
    async def test_update_filter_query(self, auth_client):
        """Update filter query (re-validated)."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Test", "query_text": "tss > 100"},
        )
        filter_id = resp.json()["id"]
        resp = await auth_client.patch(
            f"/api/saved-filters/{filter_id}",
            json={"query_text": "tss > 200 AND distance > 50km"},
        )
        assert resp.status_code == 200
        assert resp.json()["query_text"] == "tss > 200 AND distance > 50km"

    @pytest.mark.asyncio
    async def test_update_filter_invalid_query(self, auth_client):
        """Update fails with invalid query."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Test", "query_text": "tss > 100"},
        )
        filter_id = resp.json()["id"]
        resp = await auth_client.patch(
            f"/api/saved-filters/{filter_id}",
            json={"query_text": "bad syntax !!!"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_update_filter_not_found(self, auth_client):
        """Update returns 404 for non-existent filter."""
        resp = await auth_client.patch(
            "/api/saved-filters/99999",
            json={"name": "Renamed"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_filter_duplicate_name(self, auth_client):
        """Update fails if name conflicts with another filter."""
        await auth_client.post(
            "/api/saved-filters",
            json={"name": "Filter A", "query_text": "tss > 100"},
        )
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Filter B", "query_text": "tss > 200"},
        )
        filter_b_id = resp.json()["id"]
        resp = await auth_client.patch(
            f"/api/saved-filters/{filter_b_id}",
            json={"name": "Filter A"},
        )
        assert resp.status_code == 409


    # --- Delete ---

    @pytest.mark.asyncio
    async def test_delete_filter(self, auth_client):
        """Delete a filter."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "To Delete", "query_text": "tss > 100"},
        )
        filter_id = resp.json()["id"]
        resp = await auth_client.delete(f"/api/saved-filters/{filter_id}")
        assert resp.status_code == 204
        resp = await auth_client.get(f"/api/saved-filters/{filter_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_filter_not_found(self, auth_client):
        """Delete returns 404 for non-existent filter."""
        resp = await auth_client.delete("/api/saved-filters/99999")
        assert resp.status_code == 404

    # --- Set/Clear Default ---

    @pytest.mark.asyncio
    async def test_set_default(self, auth_client):
        """Set a filter as default."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Test", "query_text": "tss > 100"},
        )
        filter_id = resp.json()["id"]
        assert resp.json()["is_default"] is False
        resp = await auth_client.post(f"/api/saved-filters/{filter_id}/set-default")
        assert resp.status_code == 200
        assert resp.json()["is_default"] is True

    @pytest.mark.asyncio
    async def test_set_default_clears_previous(self, auth_client):
        """Setting a new default clears the previous one."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "First", "query_text": "tss > 100", "is_default": True},
        )
        first_id = resp.json()["id"]
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Second", "query_text": "tss > 200"},
        )
        second_id = resp.json()["id"]
        await auth_client.post(f"/api/saved-filters/{second_id}/set-default")
        resp = await auth_client.get(f"/api/saved-filters/{first_id}")
        assert resp.json()["is_default"] is False
        resp = await auth_client.get(f"/api/saved-filters/{second_id}")
        assert resp.json()["is_default"] is True


    @pytest.mark.asyncio
    async def test_set_default_not_found(self, auth_client):
        """Set default returns 404 for non-existent filter."""
        resp = await auth_client.post("/api/saved-filters/99999/set-default")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_clear_default(self, auth_client):
        """Clear default removes the default status."""
        resp = await auth_client.post(
            "/api/saved-filters",
            json={"name": "Test", "query_text": "tss > 100", "is_default": True},
        )
        filter_id = resp.json()["id"]
        resp = await auth_client.post("/api/saved-filters/clear-default")
        assert resp.status_code == 204
        resp = await auth_client.get(f"/api/saved-filters/{filter_id}")
        assert resp.json()["is_default"] is False
        resp = await auth_client.get("/api/saved-filters/default")
        assert resp.json() is None

    # --- Authentication ---

    @pytest.mark.asyncio
    async def test_unauthenticated_access(self, app_client):
        """Endpoints require authentication."""
        resp = await app_client.get("/api/saved-filters")
        assert resp.status_code == 401
        resp = await app_client.post(
            "/api/saved-filters",
            json={"name": "Test", "query_text": "tss > 100"},
        )
        assert resp.status_code == 401
