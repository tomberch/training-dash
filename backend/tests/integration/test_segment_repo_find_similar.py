"""Integration tests for PostgresSegmentRepo.find_similar_suggested.

The unit fakes full-scan suggested segments and derive endpoints from the
polyline; these tests lock in that the Postgres implementation's spatial
prefilter (ST_DWithin on start_point) + same-road containment check
(describes_same_road) finds the duplicates the fake does — no false
negatives, no false positives.
"""

from uuid import uuid4

import pytest
from geoalchemy2 import WKTElement

from trainingdash.domain.polyline import encode_polyline
from trainingdash.repositories.postgres.models import Segment
from trainingdash.repositories.postgres.segment_repo import PostgresSegmentRepo


def make_segment_row(
    *,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    status: str = "suggested",
) -> Segment:
    """A straight-line segment row with matching polyline + geometry."""
    points = [(start_lat, start_lon), (end_lat, end_lon)]
    segment = Segment(
        id=uuid4(),
        name="Detected Climb",
        type="climb",
        status=status,
        polyline=encode_polyline(points),
        start_point=WKTElement(f"POINT({start_lon} {start_lat})", srid=4326),
        end_point=WKTElement(f"POINT({end_lon} {end_lat})", srid=4326),
        bounds=WKTElement(
            f"POLYGON(("
            f"{min(start_lon, end_lon)} {min(start_lat, end_lat)}, "
            f"{max(start_lon, end_lon)} {min(start_lat, end_lat)}, "
            f"{max(start_lon, end_lon)} {max(start_lat, end_lat)}, "
            f"{min(start_lon, end_lon)} {max(start_lat, end_lat)}, "
            f"{min(start_lon, end_lon)} {min(start_lat, end_lat)}))",
            srid=4326,
        ),
        direction_bearing=0.0,
        distance_m=1000.0,
        elevation_gain_m=100.0,
        avg_grade_pct=10.0,
        max_grade_pct=15.0,
        elevation_profile=[],
    )
    return segment


def candidate_from(segment: Segment) -> dict:
    """Candidate args matching an existing segment (the 'same ride' shape)."""
    from geoalchemy2.shape import to_shape

    s = to_shape(segment.start_point)
    e = to_shape(segment.end_point)
    return {
        "start_lat": s.y,
        "start_lon": s.x,
        "end_lat": e.y,
        "end_lon": e.x,
        "polyline": segment.polyline,
    }


class TestFindSimilarSuggested:
    @pytest.fixture
    def repo(self, db_session):
        return PostgresSegmentRepo(db_session)

    @pytest.mark.asyncio
    async def test_finds_exact_duplicate(self, db_session, repo, seed_user):
        existing = make_segment_row(start_lat=46.9, start_lon=7.4, end_lat=46.91, end_lon=7.4)
        db_session.add(existing)
        await db_session.commit()

        found = await repo.find_similar_suggested(**candidate_from(existing))

        assert found is not None
        assert found.id == existing.id

    @pytest.mark.asyncio
    async def test_finds_duplicate_within_endpoint_tolerance(self, db_session, repo, seed_user):
        """A re-detection with ~15m GPS jitter still matches (25m tolerance)."""
        existing = make_segment_row(start_lat=46.9, start_lon=7.4, end_lat=46.91, end_lon=7.4)
        db_session.add(existing)
        await db_session.commit()

        # 0.0001 degrees latitude ≈ 11m; 0.0001 degrees longitude ≈ 7.5m at 47°N
        found = await repo.find_similar_suggested(
            start_lat=46.9001,
            start_lon=7.4001,
            end_lat=46.9101,
            end_lon=7.4001,
            polyline=encode_polyline([(46.9001, 7.4001), (46.9101, 7.4001)]),
        )

        assert found is not None
        assert found.id == existing.id

    @pytest.mark.asyncio
    async def test_rejects_different_location(self, db_session, repo, seed_user):
        existing = make_segment_row(start_lat=46.9, start_lon=7.4, end_lat=46.91, end_lon=7.4)
        db_session.add(existing)
        await db_session.commit()

        found = await repo.find_similar_suggested(
            start_lat=47.0,
            start_lon=7.4,
            end_lat=47.01,
            end_lon=7.4,
            polyline=encode_polyline([(47.0, 7.4), (47.01, 7.4)]),
        )

        assert found is None

    @pytest.mark.asyncio
    async def test_ignores_approved_segments(self, db_session, repo, seed_user):
        approved = make_segment_row(start_lat=46.9, start_lon=7.4, end_lat=46.91, end_lon=7.4, status="approved")
        db_session.add(approved)
        await db_session.commit()

        found = await repo.find_similar_suggested(**candidate_from(approved))

        assert found is None

    @pytest.mark.asyncio
    async def test_candidate_far_from_start_prefilter_still_finds_via_precise_check(self, db_session, repo, seed_user):
        """A climb detected from a later point on the same road — the
        candidate start differs slightly but stays within the ~100m
        prefilter radius. Guards against prefilter false negatives."""
        existing = make_segment_row(start_lat=46.9, start_lon=7.4, end_lat=46.91, end_lon=7.4)
        db_session.add(existing)
        await db_session.commit()

        # ~80m north of the existing start (0.00072 deg ≈ 80m lat) — inside
        # the 0.001-degree prefilter. The same-road containment check sees a
        # fully-overlapping path and still merges it (boundary wobble).
        found = await repo.find_similar_suggested(
            start_lat=46.90072,
            start_lon=7.4,
            end_lat=46.91072,
            end_lon=7.4,
            polyline=encode_polyline([(46.90072, 7.4), (46.91072, 7.4)]),
        )
        assert found is not None  # Containment criteria accept the shifted climb
        assert found.id == existing.id

    @pytest.mark.asyncio
    async def test_prefilter_rejects_far_away_candidate(self, db_session, repo, seed_user):
        """A candidate whose start is outside the prefilter radius is not found,
        regardless of path similarity (spatial gate is authoritative)."""
        existing = make_segment_row(start_lat=46.9, start_lon=7.4, end_lat=46.91, end_lon=7.4)
        db_session.add(existing)
        await db_session.commit()

        # ~200m north — outside the 0.001-degree prefilter
        found = await repo.find_similar_suggested(
            start_lat=46.9018,
            start_lon=7.4,
            end_lat=46.9118,
            end_lon=7.4,
            polyline=encode_polyline([(46.9018, 7.4), (46.9118, 7.4)]),
        )
        assert found is None
