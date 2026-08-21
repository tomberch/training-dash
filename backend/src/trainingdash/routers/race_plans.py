"""Race plans endpoints: generate and manage race pacing plans."""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from trainingdash.auth import CurrentUser
from trainingdash.dependencies import BikeRepoD, CourseRepoD, RacePlanRepoD, UserRepoD
from trainingdash.use_cases.generate_race_plan import (
    GeneratePlanRequest,
    GenerateRacePlan,
)

router = APIRouter(prefix="/api/race-plans", tags=["race-plans"])


# =============================================================================
# Request/Response Models
# =============================================================================


class GeneratePlanRequestSchema(BaseModel):
    """Request to generate a new race pacing plan."""

    course_id: int
    bike_id: int | None = None
    rider_weight_kg: float | None = None
    ftp_watts: int = Field(..., ge=100, le=600)
    cp_watts: int | None = Field(None, ge=100, le=600)
    w_prime_joules: int | None = Field(None, ge=5000, le=50000)
    target_intensity: float = Field(0.85, ge=0.5, le=1.2)
    use_optimizer: bool = False
    name: str | None = Field(None, max_length=200)

    def to_domain(self) -> GeneratePlanRequest:
        """Convert to domain request object."""
        return GeneratePlanRequest(
            course_id=self.course_id,
            bike_id=self.bike_id,
            rider_weight_kg=self.rider_weight_kg,
            ftp_watts=self.ftp_watts,
            cp_watts=self.cp_watts,
            w_prime_joules=self.w_prime_joules,
            target_intensity=self.target_intensity,
            use_optimizer=self.use_optimizer,
            name=self.name,
        )


class SegmentTargetSchema(BaseModel):
    """Power target for a course segment."""

    segment_idx: int
    power_w: float
    time_s: float
    speed_mps: float


class RiderParamsSchema(BaseModel):
    """Rider parameters used for plan generation."""

    weight_kg: float
    ftp_watts: int
    cp_watts: int | None
    w_prime_joules: int | None


class BikeParamsSchema(BaseModel):
    """Bike parameters used for plan generation."""

    weight_kg: float | None
    cda: float
    crr: float


class WbalPredictionSchema(BaseModel):
    """W'bal depletion prediction."""

    min_wbal: float | None
    min_wbal_distance_m: float | None


class ComparisonSchema(BaseModel):
    """Time comparison between pacing strategies."""

    constant_time_s: float | None = None
    heuristic_time_s: float | None = None
    optimized_time_s: float | None = None
    improvement_vs_constant_pct: float | None = None
    improvement_vs_heuristic_pct: float | None = None


class RacePlanResponse(BaseModel):
    """Response after generating a race plan."""

    id: int
    course_id: int
    name: str | None
    total_time_s: float
    total_time_formatted: str  # "1:23:45"
    avg_power_w: float
    normalized_power_w: float | None
    intensity_factor: float | None
    comparison: ComparisonSchema
    warnings: list[str]


class RacePlanListItem(BaseModel):
    """Summary item for race plan list view."""

    id: int
    course_id: int
    name: str | None
    total_time_s: float
    total_time_formatted: str
    avg_power_w: float
    optimization_method: str | None
    created_at: datetime


class RacePlanDetailResponse(RacePlanResponse):
    """Full race plan details with segment targets."""

    segment_targets: list[SegmentTargetSchema]
    wbal_prediction: WbalPredictionSchema | None
    rider_params: RiderParamsSchema
    bike_params: BikeParamsSchema
    optimization_method: str | None
    created_at: datetime


class PlanUpdateSchema(BaseModel):
    """Updates for plan regeneration."""

    ftp_watts: int | None = Field(None, ge=100, le=600)
    cp_watts: int | None = Field(None, ge=100, le=600)
    w_prime_joules: int | None = Field(None, ge=5000, le=50000)
    target_intensity: float | None = Field(None, ge=0.5, le=1.2)
    use_optimizer: bool | None = None
    bike_id: int | None = None
    rider_weight_kg: float | None = None
    name: str | None = Field(None, max_length=200)


# =============================================================================
# Helper Functions
# =============================================================================


def format_time(seconds: float) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


# =============================================================================
# Endpoints
# =============================================================================


@router.post("", response_model=RacePlanResponse, status_code=status.HTTP_201_CREATED)
async def generate_plan(
    request: GeneratePlanRequestSchema,
    current_user: CurrentUser,
    course_repo: CourseRepoD,
    bike_repo: BikeRepoD,
    user_repo: UserRepoD,
    plan_repo: RacePlanRepoD,
):
    """
    Generate a new race pacing plan.

    Requires course_id and ftp_watts at minimum.
    Other parameters have sensible defaults:
    - CP estimated as 95% of FTP
    - W' defaults to 20kJ
    - Target intensity defaults to 0.85 (85% of FTP)
    - Uses heuristic pacing by default (use_optimizer=false)
    """
    use_case = GenerateRacePlan(course_repo, bike_repo, user_repo, plan_repo)

    try:
        result = await use_case.execute(current_user.id, request.to_domain())
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    plan = result.plan
    return RacePlanResponse(
        id=plan.id,
        course_id=plan.course_id,
        name=plan.name,
        total_time_s=plan.total_time_s,
        total_time_formatted=format_time(plan.total_time_s),
        avg_power_w=plan.avg_power_w,
        normalized_power_w=plan.normalized_power_w,
        intensity_factor=float(plan.intensity_factor) if plan.intensity_factor else None,
        comparison=ComparisonSchema(**result.comparison),
        warnings=result.warnings,
    )


@router.get("", response_model=list[RacePlanListItem])
async def list_plans(
    current_user: CurrentUser,
    plan_repo: RacePlanRepoD,
    course_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """
    List user's race plans.

    Optionally filter by course_id.
    Returns plans ordered by created_at descending (newest first).
    """
    if course_id is not None:
        plans = await plan_repo.get_by_course(course_id, current_user.id)
        plans = plans[:limit]  # Apply limit in-memory
    else:
        plans = await plan_repo.get_by_user(current_user.id, limit=limit)

    return [
        RacePlanListItem(
            id=p.id,
            course_id=p.course_id,
            name=p.name,
            total_time_s=p.total_time_s,
            total_time_formatted=format_time(p.total_time_s),
            avg_power_w=p.avg_power_w,
            optimization_method=p.optimization_method,
            created_at=p.created_at,
        )
        for p in plans
    ]


@router.get("/{plan_id}", response_model=RacePlanDetailResponse)
async def get_plan(
    plan_id: int,
    current_user: CurrentUser,
    plan_repo: RacePlanRepoD,
):
    """Get full plan details including segment targets."""
    plan = await plan_repo.get_by_id(plan_id, current_user.id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Race plan not found",
        )

    # Parse segment targets from JSONB
    segment_targets = [
        SegmentTargetSchema(**st) for st in (plan.segment_targets or [])
    ]

    return RacePlanDetailResponse(
        id=plan.id,
        course_id=plan.course_id,
        name=plan.name,
        total_time_s=plan.total_time_s,
        total_time_formatted=format_time(plan.total_time_s),
        avg_power_w=plan.avg_power_w,
        normalized_power_w=plan.normalized_power_w,
        intensity_factor=float(plan.intensity_factor) if plan.intensity_factor else None,
        comparison=ComparisonSchema(),  # Empty for detail view (comparison computed at generation time)
        warnings=[],  # No warnings stored
        segment_targets=segment_targets,
        wbal_prediction=WbalPredictionSchema(
            min_wbal=plan.wbal_min,
            min_wbal_distance_m=plan.wbal_min_distance_m,
        ),
        rider_params=RiderParamsSchema(
            weight_kg=float(plan.rider_weight_kg),
            ftp_watts=plan.ftp_watts,
            cp_watts=plan.cp_watts,
            w_prime_joules=plan.w_prime_joules,
        ),
        bike_params=BikeParamsSchema(
            weight_kg=float(plan.bike_weight_kg) if plan.bike_weight_kg else None,
            cda=float(plan.cda),
            crr=float(plan.crr),
        ),
        optimization_method=plan.optimization_method,
        created_at=plan.created_at,
    )


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: int,
    current_user: CurrentUser,
    plan_repo: RacePlanRepoD,
):
    """Delete a race plan."""
    deleted = await plan_repo.delete(plan_id, current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Race plan not found",
        )
    return None


@router.post("/{plan_id}/regenerate", response_model=RacePlanResponse, status_code=status.HTTP_201_CREATED)
async def regenerate_plan(
    plan_id: int,
    current_user: CurrentUser,
    course_repo: CourseRepoD,
    bike_repo: BikeRepoD,
    user_repo: UserRepoD,
    plan_repo: RacePlanRepoD,
    updates: PlanUpdateSchema | None = None,
):
    """
    Regenerate plan with updated parameters.

    Creates a new plan based on an existing one with modifications.
    The original plan is preserved.
    """
    # Get existing plan
    existing_plan = await plan_repo.get_by_id(plan_id, current_user.id)
    if existing_plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Race plan not found",
        )

    # Build new request from existing plan + updates
    updates = updates or PlanUpdateSchema()

    # Merge existing values with updates (updates take precedence if not None)
    bike_id = updates.bike_id if updates.bike_id is not None else existing_plan.bike_id
    weight = (
        updates.rider_weight_kg
        if updates.rider_weight_kg is not None
        else float(existing_plan.rider_weight_kg)
    )
    ftp = updates.ftp_watts if updates.ftp_watts is not None else existing_plan.ftp_watts
    cp = updates.cp_watts if updates.cp_watts is not None else existing_plan.cp_watts
    w_prime = (
        updates.w_prime_joules
        if updates.w_prime_joules is not None
        else existing_plan.w_prime_joules
    )
    intensity = (
        updates.target_intensity
        if updates.target_intensity is not None
        else (float(existing_plan.target_intensity) if existing_plan.target_intensity else 0.85)
    )
    use_opt = (
        updates.use_optimizer
        if updates.use_optimizer is not None
        else (existing_plan.optimization_method == "optimized")
    )
    name = updates.name if updates.name is not None else existing_plan.name

    new_request = GeneratePlanRequest(
        course_id=existing_plan.course_id,
        bike_id=bike_id,
        rider_weight_kg=weight,
        ftp_watts=ftp,
        cp_watts=cp,
        w_prime_joules=w_prime,
        target_intensity=intensity,
        use_optimizer=use_opt,
        name=name,
    )

    # Generate new plan
    use_case = GenerateRacePlan(course_repo, bike_repo, user_repo, plan_repo)

    try:
        result = await use_case.execute(current_user.id, new_request)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    plan = result.plan
    return RacePlanResponse(
        id=plan.id,
        course_id=plan.course_id,
        name=plan.name,
        total_time_s=plan.total_time_s,
        total_time_formatted=format_time(plan.total_time_s),
        avg_power_w=plan.avg_power_w,
        normalized_power_w=plan.normalized_power_w,
        intensity_factor=float(plan.intensity_factor) if plan.intensity_factor else None,
        comparison=ComparisonSchema(**result.comparison),
        warnings=result.warnings,
    )
