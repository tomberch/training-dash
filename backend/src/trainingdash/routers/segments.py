"""Segment endpoints: CRUD operations and effort listing."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from geoalchemy2.shape import to_shape
from pydantic import BaseModel, Field

from trainingdash.auth import CurrentUser
from trainingdash.dependencies import (
    CreateSegmentD,
    SegmentEffortRepoD,
    SegmentRepoD,
)
from trainingdash.repositories.postgres.models import Segment, SegmentEffort
from trainingdash.routers.datetime_utils import utc_str

router = APIRouter(prefix="/api/segments", tags=["segments"])

# Pagination defaults
DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


# --- Request/Response Models ---


class CreateSegmentRequest(BaseModel):
    """Request body for creating a segment from an activity."""

    name: str = Field(min_length=3, max_length=100)
    activity_id: UUID
    start_index: int = Field(ge=0)
    end_index: int = Field(ge=0)


class UpdateSegmentRequest(BaseModel):
    """Request body for updating a segment."""

    name: str = Field(min_length=3, max_length=100)


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    total: int
    page: int
    per_page: int
    total_pages: int


# --- Serializers ---


def segment_summary(segment: Segment) -> dict:
    """Serialize a segment for list responses."""
    return {
        "id": str(segment.id),
        "name": segment.name,
        "type": segment.type,
        "climb_category": segment.climb_category,
        "distance_m": segment.distance_m,
        "elevation_gain_m": segment.elevation_gain_m,
        "avg_grade_pct": segment.avg_grade_pct,
        "effort_count": segment.effort_count,
        "athlete_count": segment.athlete_count,
    }


def segment_detail(segment: Segment, my_stats: dict | None = None) -> dict:
    """Serialize a segment with full details."""
    # Extract start/end points from PostGIS geometry
    start_point = to_shape(segment.start_point)
    end_point = to_shape(segment.end_point)

    return {
        "id": str(segment.id),
        "name": segment.name,
        "type": segment.type,
        "status": segment.status,
        "climb_category": segment.climb_category,
        "polyline": segment.polyline,
        "start_point": {"lat": start_point.y, "lng": start_point.x},
        "end_point": {"lat": end_point.y, "lng": end_point.x},
        "distance_m": segment.distance_m,
        "elevation_gain_m": segment.elevation_gain_m,
        "avg_grade_pct": segment.avg_grade_pct,
        "max_grade_pct": segment.max_grade_pct,
        "gradient_segments": segment.gradient_segments,
        "effort_count": segment.effort_count,
        "athlete_count": segment.athlete_count,
        "created_by": segment.created_by,
        "created_at": utc_str(segment.created_at),
        "my_stats": my_stats,
    }


def effort_summary(effort: SegmentEffort) -> dict:
    """Serialize a segment effort."""
    return {
        "id": str(effort.id),
        "segment_id": str(effort.segment_id),
        "activity_id": str(effort.activity_id),
        "started_at": utc_str(effort.started_at),
        "elapsed_time_seconds": effort.elapsed_time_seconds,
        "moving_time_seconds": effort.moving_time_seconds,
        "avg_power_watts": effort.avg_power_watts,
        "avg_hr_bpm": effort.avg_hr_bpm,
        "is_pr": effort.is_pr,
    }


# --- Endpoints ---


@router.get("")
async def list_segments(
    user: CurrentUser,
    segment_repo: SegmentRepoD,
    type: str | None = Query(None, description="Filter by type: climb, sprint, custom"),
    category: str | None = Query(None, description="Comma-separated climb categories: hc,1,2,3,4,nc"),
    bounds: str | None = Query(None, description="Bounding box: sw_lat,sw_lng,ne_lat,ne_lng"),
    q: str | None = Query(None, description="Search by name"),
    sort: str = Query("popularity", description="Sort by: popularity, name, distance, elevation"),
    order: str = Query("desc", description="Sort order: asc, desc"),
    page: int = Query(DEFAULT_PAGE, ge=1, description="Page number"),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE, description="Items per page"),
):
    """List approved segments with optional filters."""
    # Parse category filter
    category_list = category.split(",") if category else None

    # Parse bounds filter
    bounds_tuple = None
    if bounds:
        try:
            parts = [float(x) for x in bounds.split(",")]
            if len(parts) != 4:
                raise ValueError("Invalid bounds format")
            bounds_tuple = (parts[0], parts[1], parts[2], parts[3])
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid bounds format. Expected: sw_lat,sw_lng,ne_lat,ne_lng",
            )

    # Get total count for pagination
    total = await segment_repo.count_approved(
        type=type,
        category=category_list,
        bounds=bounds_tuple,
        search=q,
    )

    # Calculate pagination
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    offset = (page - 1) * per_page

    # Fetch segments
    segments = await segment_repo.list_approved(
        type=type,
        category=category_list,
        bounds=bounds_tuple,
        search=q,
        sort=sort,
        order=order,
        limit=per_page,
        offset=offset,
    )

    return {
        "segments": [segment_summary(s) for s in segments],
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
    }


@router.get("/{segment_id}")
async def get_segment(
    segment_id: UUID,
    user: CurrentUser,
    segment_repo: SegmentRepoD,
    effort_repo: SegmentEffortRepoD,
):
    """Get segment details with current user's stats."""
    segment = await segment_repo.get_by_id(segment_id)
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    # Get user's PR and effort count
    pr_effort = await effort_repo.get_user_pr(segment_id, user.id)
    total_efforts = await effort_repo.count_for_segment(segment_id, user.id)

    my_stats = None
    if total_efforts > 0:
        my_stats = {
            "effort_count": total_efforts,
            "pr_time_seconds": pr_effort.elapsed_time_seconds if pr_effort else None,
            "pr_date": utc_str(pr_effort.started_at) if pr_effort else None,
        }

    return segment_detail(segment, my_stats)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_segment(
    user: CurrentUser,
    create_use_case: CreateSegmentD,
    request: CreateSegmentRequest,
):
    """Create a segment from an activity's GPS data."""
    result = await create_use_case.execute(
        user_id=user.id,
        activity_id=request.activity_id,
        start_index=request.start_index,
        end_index=request.end_index,
        name=request.name,
    )

    if not result.success:
        if result.duplicate_segment_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": result.error,
                    "duplicate_segment_id": str(result.duplicate_segment_id),
                },
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error,
        )

    return segment_detail(result.segment)


@router.patch("/{segment_id}")
async def update_segment(
    segment_id: UUID,
    user: CurrentUser,
    segment_repo: SegmentRepoD,
    request: UpdateSegmentRequest,
):
    """Update a segment's name. Only the owner can update."""
    segment = await segment_repo.get_by_id(segment_id)
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    # Check ownership
    if segment.created_by != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the segment owner can update it",
        )

    # Update name
    segment.name = request.name
    saved = await segment_repo.save(segment)
    return segment_detail(saved)


@router.delete("/{segment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_segment(
    segment_id: UUID,
    user: CurrentUser,
    segment_repo: SegmentRepoD,
):
    """Soft-delete a segment. Only the owner can delete."""
    segment = await segment_repo.get_by_id(segment_id)
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    # Check ownership
    if segment.created_by != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the segment owner can delete it",
        )

    await segment_repo.soft_delete(segment_id)


@router.get("/{segment_id}/efforts")
async def list_segment_efforts(
    segment_id: UUID,
    user: CurrentUser,
    segment_repo: SegmentRepoD,
    effort_repo: SegmentEffortRepoD,
    sort: str = Query("time", description="Sort by: time, date, power"),
    order: str = Query("asc", description="Sort order: asc, desc"),
    page: int = Query(DEFAULT_PAGE, ge=1, description="Page number"),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE, description="Items per page"),
):
    """List current user's efforts on a segment."""
    # Verify segment exists
    segment = await segment_repo.get_by_id(segment_id)
    if segment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")

    # Get total count
    total = await effort_repo.count_for_segment(segment_id, user.id)

    # Calculate pagination
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    offset = (page - 1) * per_page

    # Fetch efforts
    efforts = await effort_repo.list_for_segment(
        segment_id=segment_id,
        user_id=user.id,
        sort=sort,
        order=order,
        limit=per_page,
        offset=offset,
    )

    return {
        "efforts": [effort_summary(e) for e in efforts],
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
    }
