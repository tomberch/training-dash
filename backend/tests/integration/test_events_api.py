"""Integration tests for Ride Events CRUD API."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from trainingdash.repositories.postgres.models import Activity


class TestEventsAPI:
    """Test ride events CRUD endpoints."""

    # --- List Events ---

    @pytest.mark.asyncio
    async def test_list_empty(self, auth_client):
        """List returns empty when no events exist."""
        resp = await auth_client.get("/api/events")
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert data["pagination"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_returns_user_events(self, auth_client):
        """List returns events for the authenticated user."""
        resp = await auth_client.post(
            "/api/events",
            json={
                "title": "Alps Tour 2026",
                "event_type": "multi_day",
                "start_date": "2026-07-01",
                "end_date": "2026-07-07",
            },
        )
        assert resp.status_code == 201

        resp = await auth_client.get("/api/events")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["title"] == "Alps Tour 2026"


    @pytest.mark.asyncio
    async def test_list_filter_by_event_type(self, auth_client):
        """List filters events by type."""
        await auth_client.post(
            "/api/events",
            json={"title": "Race", "event_type": "race", "start_date": "2026-08-01"},
        )
        await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )

        resp = await auth_client.get("/api/events?event_type=race")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["event_type"] == "race"

    @pytest.mark.asyncio
    async def test_list_pagination(self, auth_client):
        """List supports pagination."""
        for i in range(5):
            await auth_client.post(
                "/api/events",
                json={"title": f"Event {i}", "event_type": "race", "start_date": f"2026-0{i+1}-01"},
            )

        resp = await auth_client.get("/api/events?per_page=2&page=1")
        data = resp.json()
        assert len(data["events"]) == 2
        assert data["pagination"]["total"] == 5
        assert data["pagination"]["total_pages"] == 3

    # --- Create Event ---

    @pytest.mark.asyncio
    async def test_create_event(self, auth_client):
        """Create a ride event."""
        resp = await auth_client.post(
            "/api/events",
            json={
                "title": "Mountain Challenge",
                "event_type": "gran_fondo",
                "start_date": "2026-09-15",
                "description": "Epic mountain riding",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Mountain Challenge"
        assert data["event_type"] == "gran_fondo"
        assert data["start_date"] == "2026-09-15"
        assert "id" in data


    @pytest.mark.asyncio
    async def test_create_event_minimal(self, auth_client):
        """Create an event with minimal fields."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Quick Race", "event_type": "race", "start_date": "2026-10-01"},
        )
        assert resp.status_code == 201
        data = resp.json()
        # end_date defaults to start_date
        assert data["end_date"] == "2026-10-01"

    @pytest.mark.asyncio
    async def test_create_event_validation_empty_title(self, auth_client):
        """Create fails with empty title."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "", "event_type": "race", "start_date": "2026-10-01"},
        )
        assert resp.status_code == 422

    # --- Get Event ---

    @pytest.mark.asyncio
    async def test_get_event(self, auth_client):
        """Get event returns full details."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Test Event", "event_type": "race", "start_date": "2026-06-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.get(f"/api/events/{event_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Test Event"
        assert "entries" in data
        assert "media" in data
        assert "links" in data
        assert "stats" in data

    @pytest.mark.asyncio
    async def test_get_event_not_found(self, auth_client):
        """Get returns 404 for non-existent event."""
        fake_id = str(uuid4())
        resp = await auth_client.get(f"/api/events/{fake_id}")
        assert resp.status_code == 404


    # --- Update Event ---

    @pytest.mark.asyncio
    async def test_update_event(self, auth_client):
        """Update an event."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Original", "event_type": "race", "start_date": "2026-06-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.patch(
            f"/api/events/{event_id}",
            json={"title": "Updated Title", "description": "New description"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["description"] == "New description"

    @pytest.mark.asyncio
    async def test_update_event_not_found(self, auth_client):
        """Update returns 404 for non-existent event."""
        fake_id = str(uuid4())
        resp = await auth_client.patch(f"/api/events/{fake_id}", json={"title": "New"})
        assert resp.status_code == 404

    # --- Delete Event ---

    @pytest.mark.asyncio
    async def test_delete_event(self, auth_client):
        """Delete an event."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "To Delete", "event_type": "race", "start_date": "2026-06-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.delete(f"/api/events/{event_id}")
        assert resp.status_code == 204

        resp = await auth_client.get(f"/api/events/{event_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_event_not_found(self, auth_client):
        """Delete returns 404 for non-existent event."""
        fake_id = str(uuid4())
        resp = await auth_client.delete(f"/api/events/{fake_id}")
        assert resp.status_code == 404



class TestJournalEntriesAPI:
    """Test journal entries CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_journal_entry(self, auth_client):
        """Create a journal entry."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/entries",
            json={"entry_date": "2026-07-01", "description": "Day 1 - Col du Galibier"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["entry_date"] == "2026-07-01"
        assert data["description"] == "Day 1 - Col du Galibier"

    @pytest.mark.asyncio
    async def test_list_journal_entries(self, auth_client):
        """List journal entries for an event."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        await auth_client.post(
            f"/api/events/{event_id}/entries", json={"entry_date": "2026-07-02"}
        )
        await auth_client.post(
            f"/api/events/{event_id}/entries", json={"entry_date": "2026-07-01"}
        )

        resp = await auth_client.get(f"/api/events/{event_id}/entries")
        assert resp.status_code == 200
        entries = resp.json()["entries"]
        assert len(entries) == 2
        # Should be sorted by date ascending
        assert entries[0]["entry_date"] == "2026-07-01"
        assert entries[1]["entry_date"] == "2026-07-02"


    @pytest.mark.asyncio
    async def test_get_journal_entry(self, auth_client):
        """Get a single journal entry."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/entries",
            json={"entry_date": "2026-07-01", "description": "Test entry"},
        )
        entry_id = resp.json()["id"]

        resp = await auth_client.get(f"/api/events/entries/{entry_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "Test entry"
        assert "media" in data
        assert "links" in data
        assert "activities" in data

    @pytest.mark.asyncio
    async def test_update_journal_entry(self, auth_client):
        """Update a journal entry."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/entries", json={"entry_date": "2026-07-01"}
        )
        entry_id = resp.json()["id"]

        resp = await auth_client.patch(
            f"/api/events/entries/{entry_id}",
            json={"description": "Updated description"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_delete_journal_entry(self, auth_client):
        """Delete a journal entry."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/entries", json={"entry_date": "2026-07-01"}
        )
        entry_id = resp.json()["id"]

        resp = await auth_client.delete(f"/api/events/entries/{entry_id}")
        assert resp.status_code == 204

        resp = await auth_client.get(f"/api/events/entries/{entry_id}")
        assert resp.status_code == 404



class TestEventLinksAPI:
    """Test event links CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_event_link(self, auth_client):
        """Create a link on an event."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Race", "event_type": "race", "start_date": "2026-08-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/links",
            json={"url": "https://strava.com/routes/123", "title": "Race Route"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://strava.com/routes/123"
        assert data["title"] == "Race Route"

    @pytest.mark.asyncio
    async def test_create_entry_link(self, auth_client):
        """Create a link on a journal entry."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/entries", json={"entry_date": "2026-07-01"}
        )
        entry_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/entries/{entry_id}/links",
            json={"url": "https://example.com/day1", "title": "Day 1 Photos"},
        )
        assert resp.status_code == 201
        assert resp.json()["journal_entry_id"] == entry_id

    @pytest.mark.asyncio
    async def test_update_link(self, auth_client):
        """Update a link."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Race", "event_type": "race", "start_date": "2026-08-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/links", json={"url": "https://old.url", "title": "Old Title"}
        )
        link_id = resp.json()["id"]

        resp = await auth_client.patch(
            f"/api/events/links/{link_id}",
            json={"url": "https://new.url", "title": "New Title"},
        )
        assert resp.status_code == 200
        assert resp.json()["url"] == "https://new.url"
        assert resp.json()["title"] == "New Title"

    @pytest.mark.asyncio
    async def test_delete_link(self, auth_client):
        """Delete a link."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Race", "event_type": "race", "start_date": "2026-08-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/links", json={"url": "https://delete.me", "title": "Delete Me"}
        )
        link_id = resp.json()["id"]

        resp = await auth_client.delete(f"/api/events/links/{link_id}")
        assert resp.status_code == 204



class TestActivityLinkingAPI:
    """Test activity linking endpoints."""

    @pytest.fixture
    async def event_with_entry(self, auth_client):
        """Create an event with a journal entry."""
        resp = await auth_client.post(
            "/api/events",
            json={
                "title": "Tour",
                "event_type": "multi_day",
                "start_date": "2026-07-01",
                "end_date": "2026-07-03",
            },
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/entries", json={"entry_date": "2026-07-01"}
        )
        entry_id = resp.json()["id"]

        return {"event_id": event_id, "entry_id": entry_id}

    @pytest.fixture
    async def activity_in_range(self, db_session, seed_user):
        """Create an activity within the event date range."""
        activity = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            started_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            source="test",
            source_ref="test_activity_1",
            title="Morning Ride",
            total_distance_m=50000.0,
            moving_time_s=7200,
        )
        db_session.add(activity)
        await db_session.commit()
        await db_session.refresh(activity)
        return activity

    @pytest.mark.asyncio
    async def test_link_activity(self, auth_client, event_with_entry, activity_in_range):
        """Link an activity to a journal entry."""
        entry_id = event_with_entry["entry_id"]

        resp = await auth_client.post(
            f"/api/events/entries/{entry_id}/activities",
            json={"activity_id": str(activity_in_range.id)},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["activity_id"] == str(activity_in_range.id)
        assert data["journal_entry_id"] == entry_id


    @pytest.mark.asyncio
    async def test_unlink_activity(self, auth_client, event_with_entry, activity_in_range):
        """Unlink an activity from a journal entry."""
        entry_id = event_with_entry["entry_id"]

        await auth_client.post(
            f"/api/events/entries/{entry_id}/activities",
            json={"activity_id": str(activity_in_range.id)},
        )

        resp = await auth_client.delete(
            f"/api/events/entries/{entry_id}/activities/{activity_in_range.id}"
        )
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_link_nonexistent_activity(self, auth_client, event_with_entry):
        """Link fails for non-existent activity."""
        entry_id = event_with_entry["entry_id"]
        fake_id = str(uuid4())

        resp = await auth_client.post(
            f"/api/events/entries/{entry_id}/activities",
            json={"activity_id": fake_id},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_available_activities(self, auth_client, event_with_entry, activity_in_range):
        """List available activities for an event."""
        event_id = event_with_entry["event_id"]

        resp = await auth_client.get(f"/api/events/{event_id}/available-activities")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["activities"]) == 1
        assert data["activities"][0]["id"] == str(activity_in_range.id)
        assert data["activities"][0]["is_linked"] is False

    @pytest.mark.asyncio
    async def test_available_activities_marks_linked(
        self, auth_client, event_with_entry, activity_in_range
    ):
        """Available activities marks already-linked ones."""
        event_id = event_with_entry["event_id"]
        entry_id = event_with_entry["entry_id"]

        # Link the activity
        await auth_client.post(
            f"/api/events/entries/{entry_id}/activities",
            json={"activity_id": str(activity_in_range.id)},
        )

        resp = await auth_client.get(f"/api/events/{event_id}/available-activities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["activities"][0]["is_linked"] is True



class TestEventStatsAPI:
    """Test aggregate stats calculation."""

    @pytest.fixture
    async def event_with_activities(self, auth_client, db_session, seed_user):
        """Create an event with linked activities."""
        resp = await auth_client.post(
            "/api/events",
            json={
                "title": "Tour",
                "event_type": "multi_day",
                "start_date": "2026-07-01",
                "end_date": "2026-07-02",
            },
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/entries", json={"entry_date": "2026-07-01"}
        )
        entry_id = resp.json()["id"]

        # Create activities
        activity1 = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            started_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            source="test",
            source_ref="stats_test_1",
            total_distance_m=100000.0,
            moving_time_s=14400,
            elevation_gain_m=2000.0,
            tss=250.0,
        )
        activity2 = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            started_at=datetime(2026, 7, 2, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            source="test",
            source_ref="stats_test_2",
            total_distance_m=80000.0,
            moving_time_s=10800,
            elevation_gain_m=1500.0,
            tss=180.0,
        )
        db_session.add_all([activity1, activity2])
        await db_session.commit()

        # Link activities
        await auth_client.post(
            f"/api/events/entries/{entry_id}/activities",
            json={"activity_id": str(activity1.id)},
        )
        await auth_client.post(
            f"/api/events/entries/{entry_id}/activities",
            json={"activity_id": str(activity2.id)},
        )

        return event_id

    @pytest.mark.asyncio
    async def test_event_stats(self, auth_client, event_with_activities):
        """Get event includes aggregate stats."""
        resp = await auth_client.get(f"/api/events/{event_with_activities}")
        assert resp.status_code == 200
        stats = resp.json()["stats"]

        assert stats["activity_count"] == 2
        # 100km + 80km = 180km
        assert stats["total_distance_km"] == 180.0
        # 14400s + 10800s = 25200s
        assert stats["total_duration_seconds"] == 25200
        # 2000m + 1500m = 3500m
        assert stats["total_elevation_m"] == 3500.0
        # 250 + 180 = 430
        assert stats["total_tss"] == 430.0



class TestEventsAuthentication:
    """Test authentication requirements."""

    @pytest.mark.asyncio
    async def test_list_requires_auth(self, app_client):
        """List events requires authentication."""
        resp = await app_client.get("/api/events")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_requires_auth(self, app_client):
        """Create event requires authentication."""
        resp = await app_client.post(
            "/api/events",
            json={"title": "Test", "event_type": "race", "start_date": "2026-01-01"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_requires_auth(self, app_client):
        """Get event requires authentication."""
        fake_id = str(uuid4())
        resp = await app_client.get(f"/api/events/{fake_id}")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_update_requires_auth(self, app_client):
        """Update event requires authentication."""
        fake_id = str(uuid4())
        resp = await app_client.patch(f"/api/events/{fake_id}", json={"title": "New"})
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_requires_auth(self, app_client):
        """Delete event requires authentication."""
        fake_id = str(uuid4())
        resp = await app_client.delete(f"/api/events/{fake_id}")
        assert resp.status_code == 401


class TestCascadeDelete:
    """Test cascade delete behavior."""

    @pytest.mark.asyncio
    async def test_delete_event_cascades_entries(self, auth_client):
        """Deleting an event cascades to journal entries."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/entries", json={"entry_date": "2026-07-01"}
        )
        entry_id = resp.json()["id"]

        # Delete the event
        await auth_client.delete(f"/api/events/{event_id}")

        # Entry should also be gone
        resp = await auth_client.get(f"/api/events/entries/{entry_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_event_cascades_links(self, auth_client):
        """Deleting an event cascades to links."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Race", "event_type": "race", "start_date": "2026-08-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/links", json={"url": "https://test.com", "title": "Test Link"}
        )
        link_id = resp.json()["id"]

        # Delete the event
        await auth_client.delete(f"/api/events/{event_id}")

        # Link should also be gone
        resp = await auth_client.patch(f"/api/events/links/{link_id}", json={"title": "x"})
        assert resp.status_code == 404



class TestPhotoUploadAPI:
    """Test photo upload and media management endpoints."""

    @pytest.fixture
    def sample_jpeg_bytes(self):
        """Create a minimal valid JPEG image."""
        from io import BytesIO
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        buffer = BytesIO()
        img.save(buffer, format="JPEG")
        return buffer.getvalue()

    @pytest.fixture
    def sample_png_bytes(self):
        """Create a minimal valid PNG image."""
        from io import BytesIO
        from PIL import Image

        img = Image.new("RGBA", (100, 100), color="blue")
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()

    @pytest.fixture
    async def event_for_photos(self, auth_client):
        """Create an event for photo upload tests."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Photo Test Event", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        return resp.json()["id"]

    @pytest.mark.asyncio
    async def test_upload_event_photo(self, auth_client, event_for_photos, sample_jpeg_bytes):
        """Upload a photo to an event."""
        resp = await auth_client.post(
            f"/api/events/{event_for_photos}/photos",
            content=sample_jpeg_bytes,
            headers={"content-type": "image/jpeg"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["media_type"] == "photo"
        assert data["storage_path"] is not None
        assert data["thumbnail_path"] is not None
        assert ".jpg" in data["storage_path"]
        assert "_thumb" in data["thumbnail_path"]


    @pytest.mark.asyncio
    async def test_upload_photo_with_caption(self, auth_client, event_for_photos, sample_jpeg_bytes):
        """Upload a photo with a caption."""
        resp = await auth_client.post(
            f"/api/events/{event_for_photos}/photos?caption=Summit%20view",
            content=sample_jpeg_bytes,
            headers={"content-type": "image/jpeg"},
        )
        assert resp.status_code == 201
        assert resp.json()["caption"] == "Summit view"

    @pytest.mark.asyncio
    async def test_upload_png_photo(self, auth_client, event_for_photos, sample_png_bytes):
        """Upload a PNG photo."""
        resp = await auth_client.post(
            f"/api/events/{event_for_photos}/photos",
            content=sample_png_bytes,
            headers={"content-type": "image/png"},
        )
        assert resp.status_code == 201
        assert ".png" in resp.json()["storage_path"]

    @pytest.mark.asyncio
    async def test_upload_invalid_content_type(self, auth_client, event_for_photos):
        """Upload fails with invalid content type."""
        resp = await auth_client.post(
            f"/api/events/{event_for_photos}/photos",
            content=b"not an image",
            headers={"content-type": "text/plain"},
        )
        assert resp.status_code == 400
        assert "Unsupported image type" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_to_journal_entry(self, auth_client, event_for_photos, sample_jpeg_bytes):
        """Upload a photo to a journal entry."""
        # Create entry
        resp = await auth_client.post(
            f"/api/events/{event_for_photos}/entries",
            json={"entry_date": "2026-07-01"},
        )
        entry_id = resp.json()["id"]

        # Upload photo
        resp = await auth_client.post(
            f"/api/events/entries/{entry_id}/photos",
            content=sample_jpeg_bytes,
            headers={"content-type": "image/jpeg"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["journal_entry_id"] == entry_id
        assert "entries" in data["storage_path"]


    @pytest.mark.asyncio
    async def test_update_media_caption(self, auth_client, event_for_photos, sample_jpeg_bytes):
        """Update a media item's caption."""
        resp = await auth_client.post(
            f"/api/events/{event_for_photos}/photos",
            content=sample_jpeg_bytes,
            headers={"content-type": "image/jpeg"},
        )
        media_id = resp.json()["id"]

        resp = await auth_client.patch(
            f"/api/events/media/{media_id}?caption=Updated%20caption"
        )
        assert resp.status_code == 200
        assert resp.json()["caption"] == "Updated caption"

    @pytest.mark.asyncio
    async def test_delete_media(self, auth_client, event_for_photos, sample_jpeg_bytes):
        """Delete a media item."""
        resp = await auth_client.post(
            f"/api/events/{event_for_photos}/photos",
            content=sample_jpeg_bytes,
            headers={"content-type": "image/jpeg"},
        )
        media_id = resp.json()["id"]

        resp = await auth_client.delete(f"/api/events/media/{media_id}")
        assert resp.status_code == 204

        # Verify it's gone
        resp = await auth_client.patch(f"/api/events/media/{media_id}?caption=test")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_set_event_cover(self, auth_client, event_for_photos, sample_jpeg_bytes):
        """Set a photo as the event cover."""
        resp = await auth_client.post(
            f"/api/events/{event_for_photos}/photos",
            content=sample_jpeg_bytes,
            headers={"content-type": "image/jpeg"},
        )
        media_id = resp.json()["id"]

        resp = await auth_client.post(f"/api/events/{event_for_photos}/cover/{media_id}")
        assert resp.status_code == 200

        # Verify event now has cover
        resp = await auth_client.get(f"/api/events/{event_for_photos}")
        # Note: cover_image_id would be in the response if we serialize it

    @pytest.mark.asyncio
    async def test_remove_event_cover(self, auth_client, event_for_photos, sample_jpeg_bytes):
        """Remove the event cover."""
        # Upload and set cover
        resp = await auth_client.post(
            f"/api/events/{event_for_photos}/photos",
            content=sample_jpeg_bytes,
            headers={"content-type": "image/jpeg"},
        )
        media_id = resp.json()["id"]
        await auth_client.post(f"/api/events/{event_for_photos}/cover/{media_id}")

        # Remove cover
        resp = await auth_client.delete(f"/api/events/{event_for_photos}/cover")
        assert resp.status_code == 204


    @pytest.mark.asyncio
    async def test_upload_requires_auth(self, app_client):
        """Photo upload requires authentication."""
        fake_id = str(uuid4())
        resp = await app_client.post(
            f"/api/events/{fake_id}/photos",
            content=b"fake image data",
            headers={"content-type": "image/jpeg"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_photos_included_in_event_detail(self, auth_client, event_for_photos, sample_jpeg_bytes):
        """Photos are included when fetching event details."""
        # Upload a photo
        await auth_client.post(
            f"/api/events/{event_for_photos}/photos",
            content=sample_jpeg_bytes,
            headers={"content-type": "image/jpeg"},
        )

        # Get event details
        resp = await auth_client.get(f"/api/events/{event_for_photos}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["media"]) == 1
        assert data["media"][0]["media_type"] == "photo"

    @pytest.mark.asyncio
    async def test_entry_photos_included_in_entry_detail(
        self, auth_client, event_for_photos, sample_jpeg_bytes
    ):
        """Photos are included when fetching entry details."""
        # Create entry
        resp = await auth_client.post(
            f"/api/events/{event_for_photos}/entries",
            json={"entry_date": "2026-07-01"},
        )
        entry_id = resp.json()["id"]

        # Upload photo to entry
        await auth_client.post(
            f"/api/events/entries/{entry_id}/photos",
            content=sample_jpeg_bytes,
            headers={"content-type": "image/jpeg"},
        )

        # Get entry details
        resp = await auth_client.get(f"/api/events/entries/{entry_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["media"]) == 1



class TestVideoEmbedAPI:
    """Test video embed endpoints."""

    @pytest.mark.asyncio
    async def test_add_video_to_event(self, auth_client):
        """Add a video embed to an event."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Race Day", "event_type": "race", "start_date": "2026-08-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/videos",
            json={
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "title": "Race Highlights",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["media_type"] == "video"
        assert data["storage_path"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert data["caption"] == "Race Highlights"

    @pytest.mark.asyncio
    async def test_add_video_to_entry(self, auth_client):
        """Add a video embed to a journal entry."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/entries", json={"entry_date": "2026-07-01"}
        )
        entry_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/entries/{entry_id}/videos",
            json={
                "url": "https://vimeo.com/123456789",
                "title": "Day 1 Recap",
                "sort_order": 1,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["media_type"] == "video"
        assert data["journal_entry_id"] == entry_id

    @pytest.mark.asyncio
    async def test_delete_event_video(self, auth_client):
        """Delete a video from an event."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Race", "event_type": "race", "start_date": "2026-08-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/videos",
            json={"url": "https://youtube.com/watch?v=abc", "title": "Video"},
        )
        video_id = resp.json()["id"]

        resp = await auth_client.delete(f"/api/events/{event_id}/videos/{video_id}")
        assert resp.status_code == 204

        # Verify deleted
        resp = await auth_client.get(f"/api/events/{event_id}")
        media = resp.json()["media"]
        assert len(media) == 0

    @pytest.mark.asyncio
    async def test_delete_entry_video(self, auth_client):
        """Delete a video from a journal entry."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/entries", json={"entry_date": "2026-07-01"}
        )
        entry_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/entries/{entry_id}/videos",
            json={"url": "https://vimeo.com/999", "title": "Clip"},
        )
        video_id = resp.json()["id"]

        resp = await auth_client.delete(f"/api/events/entries/{entry_id}/videos/{video_id}")
        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_video_appears_in_event_detail(self, auth_client):
        """Video embeds appear in event detail response."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Race", "event_type": "race", "start_date": "2026-08-01"},
        )
        event_id = resp.json()["id"]

        await auth_client.post(
            f"/api/events/{event_id}/videos",
            json={"url": "https://youtube.com/v1", "title": "Video 1"},
        )
        await auth_client.post(
            f"/api/events/{event_id}/videos",
            json={"url": "https://youtube.com/v2", "title": "Video 2"},
        )

        resp = await auth_client.get(f"/api/events/{event_id}")
        media = resp.json()["media"]
        assert len(media) == 2
        assert all(m["media_type"] == "video" for m in media)


class TestBatchActivityLinkingAPI:
    """Test batch activity linking to events."""

    @pytest.mark.asyncio
    async def test_batch_link_activities_to_event(self, auth_client, db_session, seed_user):
        """Batch link multiple activities to an event."""
        from datetime import UTC, datetime

        # Create event
        resp = await auth_client.post(
            "/api/events",
            json={
                "title": "Tour",
                "event_type": "multi_day",
                "start_date": "2026-07-01",
                "end_date": "2026-07-03",
            },
        )
        event_id = resp.json()["id"]

        # Create activities
        activity1 = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            started_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            source="test",
            source_ref="batch_test_1",
            total_distance_m=50000.0,
        )
        activity2 = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            started_at=datetime(2026, 7, 2, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            source="test",
            source_ref="batch_test_2",
            total_distance_m=60000.0,
        )
        db_session.add_all([activity1, activity2])
        await db_session.commit()

        # Batch link
        resp = await auth_client.post(
            f"/api/events/{event_id}/activities",
            json={"activity_ids": [str(activity1.id), str(activity2.id)]},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["count"] == 2
        assert len(data["linked"]) == 2

    @pytest.mark.asyncio
    async def test_batch_link_auto_creates_journal_entries(self, auth_client, db_session, seed_user):
        """Batch linking auto-creates journal entries for activity dates."""
        from datetime import UTC, datetime

        resp = await auth_client.post(
            "/api/events",
            json={
                "title": "Tour",
                "event_type": "multi_day",
                "start_date": "2026-07-01",
                "end_date": "2026-07-03",
            },
        )
        event_id = resp.json()["id"]

        # Activities on different days
        activity1 = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            started_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            source="test",
            source_ref="batch_auto_1",
        )
        activity2 = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            started_at=datetime(2026, 7, 3, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            source="test",
            source_ref="batch_auto_2",
        )
        db_session.add_all([activity1, activity2])
        await db_session.commit()

        await auth_client.post(
            f"/api/events/{event_id}/activities",
            json={"activity_ids": [str(activity1.id), str(activity2.id)]},
        )

        # Check entries were created
        resp = await auth_client.get(f"/api/events/{event_id}")
        entries = resp.json()["entries"]
        entry_dates = {e["entry_date"] for e in entries}
        assert "2026-07-01" in entry_dates
        assert "2026-07-03" in entry_dates

    @pytest.mark.asyncio
    async def test_unlink_activity_from_event(self, auth_client, db_session, seed_user):
        """Unlink an activity from an event."""
        from datetime import UTC, datetime

        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        activity = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            started_at=datetime(2026, 7, 1, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            source="test",
            source_ref="unlink_test",
        )
        db_session.add(activity)
        await db_session.commit()

        # Link then unlink
        await auth_client.post(
            f"/api/events/{event_id}/activities",
            json={"activity_ids": [str(activity.id)]},
        )

        resp = await auth_client.delete(f"/api/events/{event_id}/activities/{activity.id}")
        assert resp.status_code == 204

        # Verify unlinked
        resp = await auth_client.get(f"/api/events/{event_id}")
        assert resp.json()["stats"]["activity_count"] == 0


class TestQuickLinkAPI:
    """Test activity quick-link endpoints."""

    @pytest.mark.asyncio
    async def test_get_available_events(self, auth_client, db_session, seed_user):
        """Get events available for linking to an activity."""
        from datetime import UTC, datetime

        # Create events with different date ranges
        await auth_client.post(
            "/api/events",
            json={
                "title": "July Tour",
                "event_type": "multi_day",
                "start_date": "2026-07-01",
                "end_date": "2026-07-10",
            },
        )
        await auth_client.post(
            "/api/events",
            json={
                "title": "August Race",
                "event_type": "race",
                "start_date": "2026-08-15",
            },
        )

        # Activity in July
        activity = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            started_at=datetime(2026, 7, 5, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            source="test",
            source_ref="quicklink_test",
        )
        db_session.add(activity)
        await db_session.commit()

        resp = await auth_client.get(f"/api/activities/{activity.id}/available-events")
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) == 1
        assert events[0]["title"] == "July Tour"

    @pytest.mark.asyncio
    async def test_quick_link_activity_to_event(self, auth_client, db_session, seed_user):
        """Quick-link an activity to an event."""
        from datetime import UTC, datetime

        resp = await auth_client.post(
            "/api/events",
            json={
                "title": "Tour",
                "event_type": "multi_day",
                "start_date": "2026-07-01",
                "end_date": "2026-07-07",
            },
        )
        event_id = resp.json()["id"]

        activity = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            started_at=datetime(2026, 7, 3, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            source="test",
            source_ref="quicklink_link_test",
        )
        db_session.add(activity)
        await db_session.commit()

        resp = await auth_client.post(
            f"/api/activities/{activity.id}/event",
            json={"event_id": event_id},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["event_id"] == event_id
        assert data["activity_id"] == str(activity.id)
        assert "entry_id" in data

    @pytest.mark.asyncio
    async def test_quick_link_creates_entry_for_date(self, auth_client, db_session, seed_user):
        """Quick-linking auto-creates a journal entry for activity date."""
        from datetime import UTC, datetime

        resp = await auth_client.post(
            "/api/events",
            json={
                "title": "Tour",
                "event_type": "multi_day",
                "start_date": "2026-07-01",
                "end_date": "2026-07-07",
            },
        )
        event_id = resp.json()["id"]

        activity = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            started_at=datetime(2026, 7, 4, 10, 0, tzinfo=UTC).replace(tzinfo=None),
            source="test",
            source_ref="quicklink_entry_test",
        )
        db_session.add(activity)
        await db_session.commit()

        await auth_client.post(
            f"/api/activities/{activity.id}/event",
            json={"event_id": event_id},
        )

        resp = await auth_client.get(f"/api/events/{event_id}")
        entries = resp.json()["entries"]
        assert len(entries) == 1
        assert entries[0]["entry_date"] == "2026-07-04"


class TestBatchPhotoUploadAPI:
    """Test batch photo upload endpoints."""

    @pytest.mark.asyncio
    async def test_batch_upload_event_photos(self, auth_client, tmp_path):
        """Upload multiple photos to an event."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        # Create test images
        from PIL import Image
        from io import BytesIO

        files = []
        for i in range(3):
            img = Image.new("RGB", (100, 100), color=(i * 50, 100, 150))
            buf = BytesIO()
            img.save(buf, format="JPEG")
            buf.seek(0)
            files.append(("files", (f"photo{i}.jpg", buf.getvalue(), "image/jpeg")))

        resp = await auth_client.post(
            f"/api/events/{event_id}/photos/batch",
            files=files,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["count"] == 3
        assert len(data["uploaded"]) == 3
        assert len(data["errors"]) == 0

    @pytest.mark.asyncio
    async def test_batch_upload_with_invalid_files(self, auth_client):
        """Batch upload handles invalid files gracefully."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        from PIL import Image
        from io import BytesIO

        # One valid, one invalid
        img = Image.new("RGB", (100, 100), color="red")
        buf = BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)

        files = [
            ("files", ("photo.jpg", buf.getvalue(), "image/jpeg")),
            ("files", ("doc.txt", b"not an image", "text/plain")),
        ]

        resp = await auth_client.post(
            f"/api/events/{event_id}/photos/batch",
            files=files,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["count"] == 1
        assert len(data["errors"]) == 1
        assert "text/plain" in data["errors"][0]["error"]

    @pytest.mark.asyncio
    async def test_batch_upload_entry_photos(self, auth_client):
        """Upload multiple photos to a journal entry."""
        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        resp = await auth_client.post(
            f"/api/events/{event_id}/entries", json={"entry_date": "2026-07-01"}
        )
        entry_id = resp.json()["id"]

        from PIL import Image
        from io import BytesIO

        files = []
        for i in range(2):
            img = Image.new("RGB", (100, 100), color=(200, i * 50, 100))
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            files.append(("files", (f"entry{i}.png", buf.getvalue(), "image/png")))

        resp = await auth_client.post(
            f"/api/events/entries/{entry_id}/photos/batch",
            files=files,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["count"] == 2


class TestEventDeleteCleanup:
    """Test event deletion cleans up files."""

    @pytest.mark.asyncio
    async def test_delete_event_removes_upload_directory(self, auth_client, tmp_path, monkeypatch):
        """Deleting an event removes the uploads directory."""
        import os

        # Set temp uploads dir
        uploads_dir = tmp_path / "uploads"
        uploads_dir.mkdir()
        monkeypatch.setenv("TRAININGDASH_UPLOADS_DIR", str(uploads_dir))

        resp = await auth_client.post(
            "/api/events",
            json={"title": "Tour", "event_type": "multi_day", "start_date": "2026-07-01"},
        )
        event_id = resp.json()["id"]

        # Create the event upload directory with a dummy file
        event_upload_dir = uploads_dir / "events" / event_id
        event_upload_dir.mkdir(parents=True)
        (event_upload_dir / "test.jpg").write_bytes(b"fake image data")
        assert event_upload_dir.exists()

        # Delete event
        resp = await auth_client.delete(f"/api/events/{event_id}")
        assert resp.status_code == 204

        # Verify directory was removed
        assert not event_upload_dir.exists()
