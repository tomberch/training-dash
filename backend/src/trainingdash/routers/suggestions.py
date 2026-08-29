"""Suggestions endpoints: list, approve, dismiss segment suggestions."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from geoalchemy2.shape import to_shape
from pydantic import BaseModel, Field

from trainingdash.auth import CurrentUser
from trainingdash.dependencies import (
    ApproveSuggestionD,
    SegmentRepoD,
    SegmentSuggestionRepoD,
)
from trainingdash.jobs import enqueue_retroactive_match_job
from trainingdash.routers.datetime_utils import utc_str

router = APIRouter(prefix="/api/suggestions", tags=["suggestions"])

# Pagination defaults
DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


# --- Request/Response Models ---


class ApproveSuggestionRequest(BaseModel):
    """Request body for approving a suggestion."""

    name: str = Field(min_length=3, max_length=100)


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    total: int
    page: int
    per_page: int
    total_pages: int


# --- Serializers ---


def suggestion_response(suggestion, segment) -> dict:
    """Serialize a suggestion with its segment details."""
    # Extract start/end points from PostGIS geometry
    start_point = to_shape(segment.start_point)
    end_point = to_shape(segment.end_point)

    return {
        "id": str(suggestion.id),
        "segment_id": str(suggestion.segment_id),
        "segment_type": segment.type,
        "climb_category": segment.climb_category,
        "distance_m": segment.distance_m,
        "elevation_gain_m": segment.elevation_gain_m,
        "avg_grade_pct": segment.avg_grade_pct,
        "max_grade_pct": segment.max_grade_pct,
        "repetition_count": suggestion.repetition_count,
        "first_ridden_at": utc_str(suggestion.first_ridden_at),
        "last_ridden_at": utc_str(suggestion.last_ridden_at),
        "expires_at": utc_str(suggestion.expires_at),
        "polyline": segment.polyline,
        "gradient_segments": segment.gradient_segments,
        "start_point": {"lat": start_point.y, "lng": start_point.x},
        "end_point": {"lat": end_point.y, "lng": end_point.x},
    }


def segment_response(segment) -> dict:
    """Serialize an approved segment."""
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
    }


# --- Endpoints ---


@router.get("")
async def list_suggestions(
    user: CurrentUser,
    suggestion_repo: SegmentSuggestionRepoD,
    segment_repo: SegmentRepoD,
    page: int = Query(DEFAULT_PAGE, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
):
    """
    List pending suggestions for the current user.

    Excludes dismissed suggestions. Returns suggestions ordered by
    repetition_count descending (most repeated first).
    """
    offset = (page - 1) * per_page

    # Get suggestions (excludes dismissed by default)
    suggestions = await suggestion_repo.list_for_user(
        user_id=user.id,
        include_dismissed=False,
        limit=per_page,
        offset=offset,
    )

    # Get total count for pagination
    total = await suggestion_repo.count_for_user(user.id, include_dismissed=False)
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1

    # Load segment details for each suggestion
    items = []
    for suggestion in suggestions:
        segment = await segment_repo.get_by_id(suggestion.segment_id)
        if segment:
            items.append(suggestion_response(suggestion, segment))

    return {
        "items": items,
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
    }


@router.post("/{suggestion_id}/approve", status_code=status.HTTP_201_CREATED)
async def approve_suggestion(
    user: CurrentUser,
    approve_use_case: ApproveSuggestionD,
    segment_repo: SegmentRepoD,
    suggestion_id: UUID,
    request: ApproveSuggestionRequest,
):
    """
    Approve a suggestion with a name.

    Converts the suggested segment to an approved segment.
    Returns 201 with the approved segment on success.
    Returns 409 with the existing segment if a duplicate is found.
    """
    result = await approve_use_case.execute(
        user_id=user.id,
        suggestion_id=suggestion_id,
        name=request.name,
    )

    if not result.success:
        if result.duplicate_segment is not None:
            # 409 Conflict with duplicate segment info
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": result.error,
                    "existing_segment": segment_response(result.duplicate_segment),
                },
            )
        elif "not found" in result.error.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.error,
            )
        elif "different user" in result.error.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=result.error,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.error,
            )

    # Enqueue retroactive matching job
    try:
        await enqueue_retroactive_match_job(str(result.segment.id))
    except Exception:
        # Log but don't fail - segment was approved successfully
        pass

    return segment_response(result.segment)


@router.post("/{suggestion_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_suggestion(
    user: CurrentUser,
    suggestion_repo: SegmentSuggestionRepoD,
    suggestion_id: UUID,
):
    """
    Dismiss a single suggestion.

    The suggestion will no longer appear in the user's list.
    """
    # Load suggestion to verify ownership
    suggestion = await suggestion_repo.get_by_id(suggestion_id)

    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suggestion not found",
        )

    if suggestion.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Suggestion belongs to a different user",
        )

    if suggestion.dismissed_at is not None:
        # Already dismissed, treat as success
        return

    await suggestion_repo.dismiss(suggestion_id)


@router.post("/dismiss-all", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_all_suggestions(
    user: CurrentUser,
    suggestion_repo: SegmentSuggestionRepoD,
):
    """
    Dismiss all pending suggestions for the current user.

    All suggestions will no longer appear in the user's list.
    """
    await suggestion_repo.dismiss_all(user.id)
