"""Courses endpoints: CRUD for race courses."""

from datetime import datetime

from fastapi import APIRouter, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from trainingdash.auth import CurrentUser
from trainingdash.dependencies import CourseRepoD
from trainingdash.use_cases.create_course import (
    CourseCreationError,
    CreateCourse,
)

router = APIRouter(prefix="/api/courses", tags=["courses"])


# =============================================================================
# Response Models
# =============================================================================


class CourseResponse(BaseModel):
    """Response for course creation with warnings."""

    id: int
    name: str
    source_type: str
    source_filename: str | None
    distance_m: float
    elevation_gain_m: float
    elevation_loss_m: float
    min_elevation_m: float | None
    max_elevation_m: float | None
    created_at: datetime
    warnings: list[str] = Field(default_factory=list)


class CourseListItem(BaseModel):
    """Summary item for course list view."""

    id: int
    name: str
    source_type: str
    distance_m: float
    elevation_gain_m: float
    created_at: datetime


class SegmentDetail(BaseModel):
    """A segment in the course."""

    start_m: float
    end_m: float
    distance_m: float
    avg_grade_pct: float
    elevation_gain_m: float
    elevation_loss_m: float
    terrain_type: str


class ClimbDetail(BaseModel):
    """A climb in the course."""

    name: str | None
    start_m: float
    end_m: float
    distance_m: float
    avg_grade_pct: float
    elevation_gain_m: float
    max_grade_pct: float
    category: str | None


class ElevationPoint(BaseModel):
    """A point in the elevation profile."""

    distance_m: float
    elevation_m: float
    grade_pct: float


class CourseDetailResponse(BaseModel):
    """Full course details with segments, climbs, and elevation profile."""

    id: int
    name: str
    description: str | None
    source_type: str
    source_filename: str | None
    distance_m: float
    elevation_gain_m: float
    elevation_loss_m: float
    min_elevation_m: float | None
    max_elevation_m: float | None
    created_at: datetime
    updated_at: datetime
    segments: list[SegmentDetail]
    climbs: list[ClimbDetail]
    elevation_profile: list[ElevationPoint]


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def upload_course(
    file: UploadFile,
    current_user: CurrentUser,
    course_repo: CourseRepoD,
    name: str | None = Form(None),
):
    """
    Upload GPX or FIT file to create a course.

    The file is parsed and processed to extract:
    - Elevation profile (smoothed)
    - Grade calculations
    - Course segments
    - Climb detection and categorization

    Args:
        file: GPX or FIT file upload
        name: Optional course name (defaults to filename or parsed name)

    Returns:
        Created course with any processing warnings
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must have a filename",
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty",
        )

    use_case = CreateCourse(course_repo)
    try:
        result = await use_case.execute(
            user_id=current_user.id,
            file_content=content,
            filename=file.filename,
            name=name,
        )
    except CourseCreationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return CourseResponse(
        id=result.course.id,
        name=result.course.name,
        source_type=result.course.source_type,
        source_filename=result.course.source_filename,
        distance_m=result.course.distance_m,
        elevation_gain_m=result.course.elevation_gain_m,
        elevation_loss_m=result.course.elevation_loss_m,
        min_elevation_m=result.course.min_elevation_m,
        max_elevation_m=result.course.max_elevation_m,
        created_at=result.course.created_at,
        warnings=result.warnings,
    )


@router.get("", response_model=list[CourseListItem])
async def list_courses(
    current_user: CurrentUser,
    course_repo: CourseRepoD,
):
    """
    List user's courses.

    Returns courses ordered by created_at descending (newest first).
    """
    courses = await course_repo.get_by_user(current_user.id)
    return [
        CourseListItem(
            id=c.id,
            name=c.name,
            source_type=c.source_type,
            distance_m=c.distance_m,
            elevation_gain_m=c.elevation_gain_m,
            created_at=c.created_at,
        )
        for c in courses
    ]


@router.get("/{course_id}", response_model=CourseDetailResponse)
async def get_course(
    course_id: int,
    current_user: CurrentUser,
    course_repo: CourseRepoD,
):
    """
    Get course details including segments, climbs, and elevation profile.
    """
    course = await course_repo.get_by_id(course_id, current_user.id)
    if course is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    # Parse JSONB data into response models
    segments = [
        SegmentDetail(**s) for s in (course.segments or [])
    ]
    climbs = [
        ClimbDetail(**c) for c in (course.climbs or [])
    ]
    elevation_profile = [
        ElevationPoint(**p) for p in (course.elevation_profile or [])
    ]

    return CourseDetailResponse(
        id=course.id,
        name=course.name,
        description=course.description,
        source_type=course.source_type,
        source_filename=course.source_filename,
        distance_m=course.distance_m,
        elevation_gain_m=course.elevation_gain_m,
        elevation_loss_m=course.elevation_loss_m,
        min_elevation_m=course.min_elevation_m,
        max_elevation_m=course.max_elevation_m,
        created_at=course.created_at,
        updated_at=course.updated_at,
        segments=segments,
        climbs=climbs,
        elevation_profile=elevation_profile,
    )


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: int,
    current_user: CurrentUser,
    course_repo: CourseRepoD,
):
    """
    Delete a course.
    """
    deleted = await course_repo.delete(course_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )
    return None
