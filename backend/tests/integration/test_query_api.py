"""Integration tests for the query API endpoint."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient, ASGITransport

from trainingdash.app import app
from trainingdash.repositories.postgres.models import Activity


@pytest.fixture
async def sample_activities(db_session, seed_user):
    """Create sample activities for query testing."""
    now = datetime.now()
    activities = []

    # Activity 1: High TSS, high elevation
    a1 = Activity(
        id=uuid4(),
        user_id=seed_user.id,
        source="xert",
        source_ref="xert_1",
        started_at=now - timedelta(days=1),
        total_distance_m=50000,  # 50km
        moving_time_s=7200,  # 2 hours
        elapsed_time_s=7500,
        elevation_gain_m=1000,
        avg_speed_mps=6.94,
        avg_hr_bpm=145,
        avg_power_w=220,
        np_power_w=240,
        max_speed_mps=15.0,
        max_hr_bpm=175,
        tss=150,
        intensity_factor=0.85,
        training_load=100,
        is_breakthrough=True,
        title="Epic Mountain Ride",
    )
    activities.append(a1)

    # Activity 2: Low TSS, flat
    a2 = Activity(
        id=uuid4(),
        user_id=seed_user.id,
        source="garmin",
        source_ref="garmin_1",
        started_at=now - timedelta(days=3),
        total_distance_m=30000,  # 30km
        moving_time_s=3600,  # 1 hour
        elapsed_time_s=3700,
        elevation_gain_m=100,
        avg_speed_mps=8.33,
        avg_hr_bpm=130,
        avg_power_w=180,
        np_power_w=190,
        max_speed_mps=12.0,
        max_hr_bpm=155,
        tss=60,
        intensity_factor=0.7,
        training_load=50,
        is_breakthrough=False,
        title="Recovery Spin",
    )
    activities.append(a2)

    # Activity 3: Medium TSS
    a3 = Activity(
        id=uuid4(),
        user_id=seed_user.id,
        source="xert",
        source_ref="xert_2",
        started_at=now - timedelta(days=7),
        total_distance_m=40000,  # 40km
        moving_time_s=5400,  # 1.5 hours
        elapsed_time_s=5600,
        elevation_gain_m=500,
        avg_speed_mps=7.41,
        avg_hr_bpm=140,
        avg_power_w=200,
        np_power_w=220,
        max_speed_mps=14.0,
        max_hr_bpm=170,
        tss=100,
        intensity_factor=0.78,
        training_load=80,
        is_breakthrough=False,
        title="Morning Ride",
    )
    activities.append(a3)

    for a in activities:
        db_session.add(a)
    await db_session.commit()

    return activities


class TestQueryAPIListQueries:
    """Test list query execution."""

    @pytest.mark.asyncio
    async def test_simple_comparison(self, auth_client, sample_activities):
        """Test simple TSS comparison."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "tss > 80"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "list"
        assert data["total"] == 2  # TSS 150 and 100
        assert len(data["results"]) == 2

    @pytest.mark.asyncio
    async def test_distance_with_unit(self, auth_client, sample_activities):
        """Test distance comparison with km unit."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "distance > 35km"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "list"
        assert data["total"] == 2  # 50km and 40km

    @pytest.mark.asyncio
    async def test_source_in(self, auth_client, sample_activities):
        """Test IN operator with source."""
        response = await auth_client.post(
            "/api/query",
            json={"query": 'source IN ("xert")'},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # Two xert activities

    @pytest.mark.asyncio
    async def test_breakthrough_flag(self, auth_client, sample_activities):
        """Test boolean field."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "breakthrough = true"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_text_contains(self, auth_client, sample_activities):
        """Test text matching."""
        response = await auth_client.post(
            "/api/query",
            json={"query": 'title CONTAINS "Ride"'},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # "Epic Mountain Ride" and "Morning Ride"

    @pytest.mark.asyncio
    async def test_and_operator(self, auth_client, sample_activities):
        """Test AND operator."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "tss > 80 AND distance > 40km"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1  # Only the 50km ride with TSS 150

    @pytest.mark.asyncio
    async def test_or_operator(self, auth_client, sample_activities):
        """Test OR operator."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "breakthrough = true OR tss < 70"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # Breakthrough + low TSS

    @pytest.mark.asyncio
    async def test_order_by(self, auth_client, sample_activities):
        """Test ORDER BY clause."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "tss > 0 ORDER BY tss DESC"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 3
        # Check ordering
        tss_values = [r["tss"] for r in data["results"]]
        assert tss_values == sorted(tss_values, reverse=True)

    @pytest.mark.asyncio
    async def test_limit(self, auth_client, sample_activities):
        """Test LIMIT clause."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "tss > 0 ORDER BY tss DESC LIMIT 2"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["total"] == 2  # With explicit LIMIT, total = result count

    @pytest.mark.asyncio
    async def test_pagination(self, auth_client, sample_activities):
        """Test pagination for queries without LIMIT."""
        response = await auth_client.post(
            "/api/query?page=1&per_page=2",
            json={"query": "tss > 0"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 2
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["per_page"] == 2


class TestQueryAPIAggregations:
    """Test aggregation query execution."""

    @pytest.mark.asyncio
    async def test_count_star(self, auth_client, sample_activities):
        """Test COUNT(*)."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "COUNT(*)"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "scalar"
        assert "count_all" in data["results"]
        assert data["results"]["count_all"] == 3

    @pytest.mark.asyncio
    async def test_avg(self, auth_client, sample_activities):
        """Test AVG aggregation."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "AVG(tss)"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "scalar"
        # Average of 150, 100, 60 = 103.33
        assert "avg_tss" in data["results"]
        avg_tss = data["results"]["avg_tss"]
        assert 103 <= avg_tss <= 104

    @pytest.mark.asyncio
    async def test_sum(self, auth_client, sample_activities):
        """Test SUM aggregation."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "SUM(distance)"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "scalar"
        # Sum of 50000 + 30000 + 40000 = 120000
        assert data["results"]["sum_total_distance_m"] == 120000

    @pytest.mark.asyncio
    async def test_multiple_aggregates(self, auth_client, sample_activities):
        """Test multiple aggregations."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "COUNT(*), AVG(tss), SUM(distance)"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "scalar"
        assert data["results"]["count_all"] == 3
        assert "avg_tss" in data["results"]
        assert data["results"]["sum_total_distance_m"] == 120000

    @pytest.mark.asyncio
    async def test_aggregate_with_filter(self, auth_client, sample_activities):
        """Test aggregation with WHERE clause."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "AVG(tss) WHERE tss > 80"},
        )
        assert response.status_code == 200
        data = response.json()
        # Average of 150 and 100 = 125
        assert data["results"]["avg_tss"] == 125


class TestQueryAPIGroupBy:
    """Test GROUP BY query execution."""

    @pytest.mark.asyncio
    async def test_group_by_source(self, auth_client, sample_activities):
        """Test GROUP BY field."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "COUNT(*) GROUP BY source"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "grouped"
        assert "source" in data["group_by"]
        assert len(data["results"]) == 2  # xert and garmin

        # Find counts by source
        source_counts = {r["source"]: r["count_all"] for r in data["results"]}
        assert source_counts["xert"] == 2
        assert source_counts["garmin"] == 1


class TestQueryAPIErrors:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_parse_error(self, auth_client):
        """Test parse error response."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "tss > > 100"},  # Invalid syntax
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data["detail"]
        assert data["detail"]["error"]["stage"] == "parse"

    @pytest.mark.asyncio
    async def test_validation_error_unknown_field(self, auth_client):
        """Test validation error for unknown field."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "unknown_field > 100"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data["detail"]
        assert data["detail"]["error"]["stage"] == "validation"
        assert data["detail"]["error"]["field"] == "unknown_field"

    @pytest.mark.asyncio
    async def test_validation_error_with_suggestion(self, auth_client):
        """Test validation error includes suggestions."""
        response = await auth_client.post(
            "/api/query",
            json={"query": "tsss > 100"},  # Typo
        )
        assert response.status_code == 400
        data = response.json()
        assert "error" in data["detail"]
        assert data["detail"]["error"]["suggestions"] is not None
        assert "tss" in data["detail"]["error"]["suggestions"]

    @pytest.mark.asyncio
    async def test_empty_query(self, auth_client):
        """Test empty query error."""
        response = await auth_client.post(
            "/api/query",
            json={"query": ""},
        )
        # Should be a validation error from pydantic (min_length=1)
        assert response.status_code == 422


class TestQueryAPIUserScoping:
    """Test that queries are scoped to the current user."""

    @pytest.mark.asyncio
    async def test_only_sees_own_activities(self, db_session, auth_client, seed_user):
        """Test user can only see their own activities."""
        from trainingdash.repositories.postgres.models import User

        # Create another user
        other_user = User(
            email="other@example.com",
            display_name="Other User",
            password_hash="hash",
            is_approved=True,
        )
        db_session.add(other_user)
        await db_session.flush()

        # Create activity for seed_user
        a1 = Activity(
            id=uuid4(),
            user_id=seed_user.id,
            source="xert",
            source_ref="own_1",
            started_at=datetime.now(),
            total_distance_m=10000,
            moving_time_s=1800,
            elapsed_time_s=1800,
            elevation_gain_m=100,
            avg_speed_mps=5.5,
            tss=50,
        )
        db_session.add(a1)

        # Create activity for another user
        a2 = Activity(
            id=uuid4(),
            user_id=other_user.id,
            source="xert",
            source_ref="other_1",
            started_at=datetime.now(),
            total_distance_m=10000,
            moving_time_s=1800,
            elapsed_time_s=1800,
            elevation_gain_m=100,
            avg_speed_mps=5.5,
            tss=50,
        )
        db_session.add(a2)
        await db_session.commit()

        # Query should only return seed_user's activity
        response = await auth_client.post(
            "/api/query",
            json={"query": "COUNT(*)"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["results"]["count_all"] == 1
