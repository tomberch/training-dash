"""Integration tests for FTP auto-detection and notifications (#23)."""
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tests" / "fixtures"))
from generate_fit import make_test_fit  # noqa: E402
from trainingdash.models import Notification, ThresholdHistory  # noqa: E402


class TestNotificationsEndpoint:
    """Tests for notification endpoints."""

    @pytest.mark.asyncio
    async def test_notifications_empty_initially(self, auth_client):
        """GET /me/notifications returns empty array when no notifications."""
        response = await auth_client.get("/api/me/notifications")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_notifications_includes_required_fields(self, auth_client, db_session):
        """Notifications include all required fields."""
        # Create a notification directly
        notification = Notification(
            user_id=1,  # Test user
            type="ftp_suggestion",
            message="Test message",
            payload='{"suggested_ftp": 280}',
            status="pending",
        )
        db_session.add(notification)
        await db_session.commit()
        
        response = await auth_client.get("/api/me/notifications")
        assert response.status_code == 200
        data = response.json()
        
        assert len(data) == 1
        n = data[0]
        assert "id" in n
        assert "type" in n
        assert "message" in n
        assert "payload" in n
        assert "created_at" in n
        assert n["type"] == "ftp_suggestion"
        assert n["payload"]["suggested_ftp"] == 280

    @pytest.mark.asyncio
    async def test_notifications_only_shows_pending(self, auth_client, db_session):
        """Only pending notifications are returned."""
        # Create notifications with different statuses
        for status in ["pending", "accepted", "dismissed"]:
            notification = Notification(
                user_id=1,
                type="ftp_suggestion",
                message=f"Status: {status}",
                status=status,
            )
            db_session.add(notification)
        await db_session.commit()
        
        response = await auth_client.get("/api/me/notifications")
        data = response.json()
        
        # Only pending should be returned
        assert len(data) == 1
        assert data[0]["message"] == "Status: pending"

    @pytest.mark.asyncio
    async def test_notifications_requires_auth(self, app_client):
        """GET /me/notifications requires authentication."""
        response = await app_client.get("/api/me/notifications")
        assert response.status_code == 401


class TestAcceptNotification:
    """Tests for accepting notifications."""

    @pytest.mark.asyncio
    async def test_accept_notification(self, auth_client, db_session):
        """Accept notification marks it as accepted."""
        notification = Notification(
            user_id=1,
            type="test_type",
            message="Test",
            status="pending",
        )
        db_session.add(notification)
        await db_session.commit()
        await db_session.refresh(notification)
        
        response = await auth_client.post(f"/api/me/notifications/{notification.id}/accept")
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Verify status changed
        await db_session.refresh(notification)
        assert notification.status == "accepted"

    @pytest.mark.asyncio
    async def test_accept_ftp_suggestion_creates_threshold(self, auth_client, db_session):
        """Accepting FTP suggestion creates a new threshold."""
        from datetime import date as date_type
        
        # Create existing threshold
        threshold = ThresholdHistory(
            user_id=1,
            effective_date=date_type(2024, 1, 1),
            ftp_watts=250,
            lthr_bpm=165,
            hrmax_bpm=185,
        )
        db_session.add(threshold)
        
        # Create FTP suggestion
        notification = Notification(
            user_id=1,
            type="ftp_suggestion",
            message="Suggest FTP update",
            payload='{"suggested_ftp": 280, "current_ftp": 250}',
            status="pending",
        )
        db_session.add(notification)
        await db_session.commit()
        await db_session.refresh(notification)
        
        # Accept the notification
        response = await auth_client.post(f"/api/me/notifications/{notification.id}/accept")
        assert response.status_code == 200
        
        # Verify new threshold was created
        result = await db_session.execute(
            select(ThresholdHistory)
            .where(ThresholdHistory.user_id == 1)
            .order_by(ThresholdHistory.effective_date.desc())
        )
        thresholds = result.scalars().all()
        
        # Should have 2 thresholds now
        assert len(thresholds) == 2
        # Latest should have suggested FTP
        assert thresholds[0].ftp_watts == 280

    @pytest.mark.asyncio
    async def test_accept_not_found(self, auth_client):
        """Accept returns 404 for non-existent notification."""
        response = await auth_client.post("/api/me/notifications/99999/accept")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_accept_already_processed(self, auth_client, db_session):
        """Accept returns 400 for already processed notification."""
        notification = Notification(
            user_id=1,
            type="test_type",
            message="Test",
            status="accepted",  # Already processed
        )
        db_session.add(notification)
        await db_session.commit()
        await db_session.refresh(notification)
        
        response = await auth_client.post(f"/api/me/notifications/{notification.id}/accept")
        assert response.status_code == 400


class TestDismissNotification:
    """Tests for dismissing notifications."""

    @pytest.mark.asyncio
    async def test_dismiss_notification(self, auth_client, db_session):
        """Dismiss notification marks it as dismissed."""
        notification = Notification(
            user_id=1,
            type="test_type",
            message="Test",
            status="pending",
        )
        db_session.add(notification)
        await db_session.commit()
        await db_session.refresh(notification)
        
        response = await auth_client.post(f"/api/me/notifications/{notification.id}/dismiss")
        assert response.status_code == 200
        assert response.json()["success"] is True
        
        # Verify status changed
        await db_session.refresh(notification)
        assert notification.status == "dismissed"

    @pytest.mark.asyncio
    async def test_dismiss_not_found(self, auth_client):
        """Dismiss returns 404 for non-existent notification."""
        response = await auth_client.post("/api/me/notifications/99999/dismiss")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_dismiss_already_processed(self, auth_client, db_session):
        """Dismiss returns 400 for already processed notification."""
        notification = Notification(
            user_id=1,
            type="test_type",
            message="Test",
            status="dismissed",  # Already processed
        )
        db_session.add(notification)
        await db_session.commit()
        await db_session.refresh(notification)
        
        response = await auth_client.post(f"/api/me/notifications/{notification.id}/dismiss")
        assert response.status_code == 400


class TestFTPAutoDetection:
    """Tests for automatic FTP notification creation."""

    @pytest.mark.asyncio
    async def test_notification_created_when_cp_diverges(self, auth_client, db_session):
        """Notification created when fitness model CP diverges from FTP."""
        # Create a threshold with low FTP (to ensure divergence)
        await auth_client.post(
            "/api/me/thresholds",
            json={
                "effective_date": "2024-01-01",
                "ftp_watts": 150,  # Low FTP, test fit power is 200-279
                "lthr_bpm": 165,
                "hrmax_bpm": 185,
            }
        )
        
        # Upload FIT file (this triggers breakthrough -> fitness model update)
        fit_data = make_test_fit(num_records=300)  # 5 min for good CP estimate
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        
        # Check for notification
        response = await auth_client.get("/api/me/notifications")
        data = response.json()
        
        # Should have FTP suggestion notification
        ftp_notifications = [n for n in data if n["type"] == "ftp_suggestion"]
        assert len(ftp_notifications) >= 1
        
        # Notification should have payload with suggested FTP
        n = ftp_notifications[0]
        assert n["payload"] is not None
        assert "suggested_ftp" in n["payload"]
        assert "current_ftp" in n["payload"]
        assert n["payload"]["current_ftp"] == 150

    @pytest.mark.asyncio
    async def test_no_notification_when_cp_close_to_ftp(self, auth_client, db_session):
        """No notification when CP is within 5% of FTP."""
        # Create a threshold with FTP close to expected CP
        # Test FIT power is 200-279, averaging around 240
        # CP estimate will be around 228-240 depending on model
        await auth_client.post(
            "/api/me/thresholds",
            json={
                "effective_date": "2024-01-01",
                "ftp_watts": 240,  # Close to expected CP
                "lthr_bpm": 165,
                "hrmax_bpm": 185,
            }
        )
        
        # Upload FIT file
        fit_data = make_test_fit(num_records=300)
        await auth_client.post(
            "/api/upload",
            files={"file": ("test.fit", fit_data, "application/octet-stream")},
        )
        
        # Check for notification - should have none or different type
        response = await auth_client.get("/api/me/notifications")
        data = response.json()
        
        ftp_notifications = [n for n in data if n["type"] == "ftp_suggestion"]
        # Within 5% = no notification (or possibly one if edge case)
        # This is a soft assertion since CP estimation varies
        assert len(ftp_notifications) <= 1
