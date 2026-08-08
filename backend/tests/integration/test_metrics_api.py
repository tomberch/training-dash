"""Integration tests for /me/metrics endpoints."""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from trainingdash.models import Activity, MetricEntry, MetricType


class TestListMetrics:
    """Tests for GET /me/metrics."""

    @pytest.mark.asyncio
    async def test_list_metrics_empty(self, auth_client):
        """Returns empty list when no metrics exist."""
        response = await auth_client.get("/api/me/metrics")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_metrics_returns_entries(self, auth_client, db_session, seed_user):
        """Returns metric entries for the user."""
        # Get FTP metric type
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        # Create metric entry
        entry = MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        )
        db_session.add(entry)
        await db_session.commit()

        response = await auth_client.get("/api/me/metrics")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["metric_type"] == "ftp"
        assert data[0]["value"] == 280.0
        assert data[0]["effective_date"] == "2025-06-01"

    @pytest.mark.asyncio
    async def test_list_metrics_filter_by_type(self, auth_client, db_session, seed_user):
        """Filters by metric_type parameter."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key.in_(["ftp", "lthr"]))
        )
        types = {mt.key: mt for mt in result.scalars().all()}

        # Create entries for both types
        db_session.add(MetricEntry(
            user_id=seed_user.id,
            metric_type_id=types["ftp"].id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        ))
        db_session.add(MetricEntry(
            user_id=seed_user.id,
            metric_type_id=types["lthr"].id,
            effective_date=date(2025, 6, 1),
            value=Decimal("165"),
            source="manual",
        ))
        await db_session.commit()

        response = await auth_client.get("/api/me/metrics?metric_type=ftp")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["metric_type"] == "ftp"

    @pytest.mark.asyncio
    async def test_list_metrics_filter_by_category(self, auth_client, db_session, seed_user):
        """Filters by category parameter."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key.in_(["ftp", "weight_kg"]))
        )
        types = {mt.key: mt for mt in result.scalars().all()}

        # Create entries (ftp=threshold, weight_kg=body)
        db_session.add(MetricEntry(
            user_id=seed_user.id,
            metric_type_id=types["ftp"].id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        ))
        db_session.add(MetricEntry(
            user_id=seed_user.id,
            metric_type_id=types["weight_kg"].id,
            effective_date=date(2025, 6, 1),
            value=Decimal("75.5"),
            source="manual",
        ))
        await db_session.commit()

        response = await auth_client.get("/api/me/metrics?category=body")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["metric_type"] == "weight_kg"

    @pytest.mark.asyncio
    async def test_list_metrics_filter_by_date_range(self, auth_client, db_session, seed_user):
        """Filters by from_date and to_date parameters."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        # Create entries for different dates
        for d in [date(2025, 1, 1), date(2025, 6, 1), date(2025, 12, 1)]:
            db_session.add(MetricEntry(
                user_id=seed_user.id,
                metric_type_id=ftp_type.id,
                effective_date=d,
                value=Decimal("280"),
                source="manual",
            ))
        await db_session.commit()

        response = await auth_client.get("/api/me/metrics?from_date=2025-03-01&to_date=2025-09-01")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["effective_date"] == "2025-06-01"

    @pytest.mark.asyncio
    async def test_list_metrics_pagination(self, auth_client, db_session, seed_user):
        """Pagination with limit and offset."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        # Create 5 entries
        for i in range(5):
            db_session.add(MetricEntry(
                user_id=seed_user.id,
                metric_type_id=ftp_type.id,
                effective_date=date(2025, 6, 1) + timedelta(days=i),
                value=Decimal("280"),
                source="manual",
            ))
        await db_session.commit()

        response = await auth_client.get("/api/me/metrics?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_list_metrics_requires_auth(self, app_client):
        """Requires authentication."""
        response = await app_client.get("/api/me/metrics")
        assert response.status_code == 401


class TestCreateMetric:
    """Tests for POST /me/metrics."""

    @pytest.mark.asyncio
    async def test_create_metric(self, auth_client):
        """Creates a new metric entry."""
        response = await auth_client.post(
            "/api/me/metrics",
            json={
                "metric_type": "ftp",
                "effective_date": "2025-06-01",
                "value": 280,
                "source": "manual",
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["metric_type"] == "ftp"
        assert data["value"] == 280.0
        assert data["effective_date"] == "2025-06-01"
        assert data["source"] == "manual"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_metric_with_notes(self, auth_client):
        """Creates metric with notes and source_detail."""
        response = await auth_client.post(
            "/api/me/metrics",
            json={
                "metric_type": "ftp",
                "effective_date": "2025-06-01",
                "value": 280,
                "source": "device",
                "source_detail": "Garmin Edge 540",
                "notes": "Test from structured workout",
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["source_detail"] == "Garmin Edge 540"
        assert data["notes"] == "Test from structured workout"

    @pytest.mark.asyncio
    async def test_create_metric_upserts_on_same_date(self, auth_client):
        """Upserts when entry exists for same user+type+date."""
        # Create initial entry
        response = await auth_client.post(
            "/api/me/metrics",
            json={
                "metric_type": "ftp",
                "effective_date": "2025-06-01",
                "value": 280,
            }
        )
        assert response.status_code == 201
        first_id = response.json()["id"]

        # Create again for same date - should update
        response = await auth_client.post(
            "/api/me/metrics",
            json={
                "metric_type": "ftp",
                "effective_date": "2025-06-01",
                "value": 290,
            }
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == first_id  # Same entry updated
        assert data["value"] == 290.0

    @pytest.mark.asyncio
    async def test_create_metric_invalid_type(self, auth_client):
        """Rejects unknown metric type."""
        response = await auth_client.post(
            "/api/me/metrics",
            json={
                "metric_type": "not_a_real_metric",
                "effective_date": "2025-06-01",
                "value": 100,
            }
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_metric_value_below_min(self, auth_client):
        """Rejects value below min_value constraint."""
        response = await auth_client.post(
            "/api/me/metrics",
            json={
                "metric_type": "ftp",  # min_value: 50
                "effective_date": "2025-06-01",
                "value": 30,
            }
        )
        assert response.status_code == 400
        assert "at least" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_metric_value_above_max(self, auth_client):
        """Rejects value above max_value constraint."""
        response = await auth_client.post(
            "/api/me/metrics",
            json={
                "metric_type": "ftp",  # max_value: 500
                "effective_date": "2025-06-01",
                "value": 600,
            }
        )
        assert response.status_code == 400
        assert "at most" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_metric_invalid_source(self, auth_client):
        """Rejects source not in allowed_sources."""
        # resting_hr only allows manual and device
        response = await auth_client.post(
            "/api/me/metrics",
            json={
                "metric_type": "resting_hr",
                "effective_date": "2025-06-01",
                "value": 55,
                "source": "calculated",
            }
        )
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_metric_requires_auth(self, app_client):
        """Requires authentication."""
        response = await app_client.post(
            "/api/me/metrics",
            json={
                "metric_type": "ftp",
                "effective_date": "2025-06-01",
                "value": 280,
            }
        )
        assert response.status_code == 401


class TestUpdateMetric:
    """Tests for PATCH /me/metrics/{id}."""

    @pytest.mark.asyncio
    async def test_update_metric_value(self, auth_client, db_session, seed_user):
        """Updates metric value."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        entry = MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)

        response = await auth_client.patch(
            f"/api/me/metrics/{entry.id}",
            json={"value": 290}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["value"] == 290.0

    @pytest.mark.asyncio
    async def test_update_metric_notes(self, auth_client, db_session, seed_user):
        """Updates metric notes."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        entry = MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)

        response = await auth_client.patch(
            f"/api/me/metrics/{entry.id}",
            json={"notes": "Updated note"}
        )
        assert response.status_code == 200
        assert response.json()["notes"] == "Updated note"

    @pytest.mark.asyncio
    async def test_update_metric_date(self, auth_client, db_session, seed_user):
        """Updates effective date."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        entry = MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)

        response = await auth_client.patch(
            f"/api/me/metrics/{entry.id}",
            json={"effective_date": "2025-07-01"}
        )
        assert response.status_code == 200
        assert response.json()["effective_date"] == "2025-07-01"

    @pytest.mark.asyncio
    async def test_update_metric_date_conflict(self, auth_client, db_session, seed_user):
        """Rejects date change if entry exists for new date."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        # Create two entries
        entry1 = MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        )
        entry2 = MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 7, 1),
            value=Decimal("290"),
            source="manual",
        )
        db_session.add_all([entry1, entry2])
        await db_session.commit()
        await db_session.refresh(entry1)

        # Try to move entry1 to entry2's date
        response = await auth_client.patch(
            f"/api/me/metrics/{entry1.id}",
            json={"effective_date": "2025-07-01"}
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_metric_blocks_device_source(self, auth_client, db_session, seed_user):
        """Cannot modify device-sourced entries."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        entry = MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="device",
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)

        response = await auth_client.patch(
            f"/api/me/metrics/{entry.id}",
            json={"value": 290}
        )
        assert response.status_code == 403
        assert "device" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_metric_not_found(self, auth_client):
        """Returns 404 for non-existent entry."""
        response = await auth_client.patch(
            "/api/me/metrics/99999",
            json={"value": 290}
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_update_metric_validates_value(self, auth_client, db_session, seed_user):
        """Validates value against metric_type constraints."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        entry = MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)

        response = await auth_client.patch(
            f"/api/me/metrics/{entry.id}",
            json={"value": 600}  # Above max_value 500
        )
        assert response.status_code == 400
        assert "at most" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_metric_requires_auth(self, app_client):
        """Requires authentication."""
        response = await app_client.patch(
            "/api/me/metrics/1",
            json={"value": 290}
        )
        assert response.status_code == 401


class TestDeleteMetric:
    """Tests for DELETE /me/metrics/{id}."""

    @pytest.mark.asyncio
    async def test_delete_metric(self, auth_client, db_session, seed_user):
        """Deletes a metric entry."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        entry = MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        )
        db_session.add(entry)
        await db_session.commit()
        await db_session.refresh(entry)

        response = await auth_client.delete(f"/api/me/metrics/{entry.id}")
        assert response.status_code == 204

        # Verify deleted
        result = await db_session.execute(
            select(MetricEntry).where(MetricEntry.id == entry.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_metric_not_found(self, auth_client):
        """Returns 404 for non-existent entry."""
        response = await auth_client.delete("/api/me/metrics/99999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_metric_requires_auth(self, app_client):
        """Requires authentication."""
        response = await app_client.delete("/api/me/metrics/1")
        assert response.status_code == 401


class TestCurrentMetrics:
    """Tests for GET /me/metrics/current."""

    @pytest.mark.asyncio
    async def test_current_metrics_empty(self, auth_client):
        """Returns all types with null values when no entries."""
        response = await auth_client.get("/api/me/metrics/current")
        assert response.status_code == 200
        data = response.json()
        # Should have all metric type keys
        assert "ftp" in data
        assert "lthr" in data
        assert "weight_kg" in data
        # All should be null
        assert data["ftp"] is None

    @pytest.mark.asyncio
    async def test_current_metrics_returns_most_recent(self, auth_client, db_session, seed_user):
        """Returns most recent entry for each type."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        # Create entries for different dates
        db_session.add(MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 1, 1),
            value=Decimal("250"),
            source="manual",
        ))
        db_session.add(MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        ))
        await db_session.commit()

        response = await auth_client.get("/api/me/metrics/current")
        assert response.status_code == 200
        data = response.json()
        assert data["ftp"]["value"] == 280.0
        assert data["ftp"]["effective_date"] == "2025-06-01"

    @pytest.mark.asyncio
    async def test_current_metrics_requires_auth(self, app_client):
        """Requires authentication."""
        response = await app_client.get("/api/me/metrics/current")
        assert response.status_code == 401


class TestEffectiveMetrics:
    """Tests for GET /me/metrics/effective."""

    @pytest.mark.asyncio
    async def test_effective_metrics_at_date(self, auth_client, db_session, seed_user):
        """Returns effective values at specific date."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        # Create entries for different dates
        db_session.add(MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 1, 1),
            value=Decimal("250"),
            source="manual",
        ))
        db_session.add(MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        ))
        await db_session.commit()

        # Query for date between the two entries
        response = await auth_client.get("/api/me/metrics/effective?date=2025-03-15")
        assert response.status_code == 200
        data = response.json()
        # Should return Jan entry (most recent <= 2025-03-15)
        assert data["ftp"]["value"] == 250.0

        # Query for date after both entries
        response = await auth_client.get("/api/me/metrics/effective?date=2025-08-01")
        assert response.status_code == 200
        data = response.json()
        # Should return June entry
        assert data["ftp"]["value"] == 280.0

    @pytest.mark.asyncio
    async def test_effective_metrics_filter_types(self, auth_client, db_session, seed_user):
        """Filters to specific metric types."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key.in_(["ftp", "lthr"]))
        )
        types = {mt.key: mt for mt in result.scalars().all()}

        db_session.add(MetricEntry(
            user_id=seed_user.id,
            metric_type_id=types["ftp"].id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        ))
        db_session.add(MetricEntry(
            user_id=seed_user.id,
            metric_type_id=types["lthr"].id,
            effective_date=date(2025, 6, 1),
            value=Decimal("165"),
            source="manual",
        ))
        await db_session.commit()

        response = await auth_client.get("/api/me/metrics/effective?date=2025-08-01&metric_types=ftp")
        assert response.status_code == 200
        data = response.json()
        assert "ftp" in data
        assert "lthr" not in data

    @pytest.mark.asyncio
    async def test_effective_metrics_null_before_first_entry(self, auth_client, db_session, seed_user):
        """Returns null for dates before first entry."""
        result = await db_session.execute(
            select(MetricType).where(MetricType.key == "ftp")
        )
        ftp_type = result.scalar_one()

        db_session.add(MetricEntry(
            user_id=seed_user.id,
            metric_type_id=ftp_type.id,
            effective_date=date(2025, 6, 1),
            value=Decimal("280"),
            source="manual",
        ))
        await db_session.commit()

        response = await auth_client.get("/api/me/metrics/effective?date=2025-01-01")
        assert response.status_code == 200
        data = response.json()
        assert data["ftp"] is None

    @pytest.mark.asyncio
    async def test_effective_metrics_requires_date(self, auth_client):
        """Requires date parameter."""
        response = await auth_client.get("/api/me/metrics/effective")
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_effective_metrics_requires_auth(self, app_client):
        """Requires authentication."""
        response = await app_client.get("/api/me/metrics/effective?date=2025-06-01")
        assert response.status_code == 401


class TestRecalcPreview:
    """Tests for GET /me/metrics/recalc-preview."""

    @pytest.mark.asyncio
    async def test_recalc_preview(self, auth_client, db_session, seed_user):
        """Returns affected activities and recalc targets."""
        # Create an activity after the effective date
        activity = Activity(
            user_id=seed_user.id,
            source="test",
            source_ref="test:activity-1",
            started_at=datetime(2025, 7, 1, 10, 0, 0),
            total_distance_m=10000,
            moving_time_s=3600,
            elapsed_time_s=3600,
        )
        db_session.add(activity)
        await db_session.commit()

        response = await auth_client.get(
            "/api/me/metrics/recalc-preview?metric_type=ftp&effective_date=2025-06-01"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["affected_activities"] == 1
        assert "power_zones" in data["recalc_targets"]
        assert "tss" in data["recalc_targets"]

    @pytest.mark.asyncio
    async def test_recalc_preview_no_affected_activities(self, auth_client, db_session, seed_user):
        """Returns 0 when no activities after effective date."""
        # Create activity before effective date
        activity = Activity(
            user_id=seed_user.id,
            source="test",
            source_ref="test:activity-1",
            started_at=datetime(2025, 1, 1, 10, 0, 0),
            total_distance_m=10000,
            moving_time_s=3600,
            elapsed_time_s=3600,
        )
        db_session.add(activity)
        await db_session.commit()

        response = await auth_client.get(
            "/api/me/metrics/recalc-preview?metric_type=ftp&effective_date=2025-06-01"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["affected_activities"] == 0

    @pytest.mark.asyncio
    async def test_recalc_preview_invalid_metric_type(self, auth_client):
        """Returns 404 for invalid metric type."""
        response = await auth_client.get(
            "/api/me/metrics/recalc-preview?metric_type=invalid&effective_date=2025-06-01"
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_recalc_preview_requires_params(self, auth_client):
        """Requires both metric_type and effective_date."""
        response = await auth_client.get("/api/me/metrics/recalc-preview")
        assert response.status_code == 422

        response = await auth_client.get("/api/me/metrics/recalc-preview?metric_type=ftp")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_recalc_preview_requires_auth(self, app_client):
        """Requires authentication."""
        response = await app_client.get(
            "/api/me/metrics/recalc-preview?metric_type=ftp&effective_date=2025-06-01"
        )
        assert response.status_code == 401
