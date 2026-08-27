"""Race plans endpoints: generate and manage race pacing plans."""

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from trainingdash.auth import CurrentUser
from trainingdash.dependencies import (
    ActivityRepoD,
    BikeRepoD,
    CourseRepoD,
    PacingCoefficientsRepoD,
    RacePlanRepoD,
    RecordRepoD,
    UserRepoD,
)
from trainingdash.integrations.weather import (
    fetch_race_day_forecast,
    get_calm_conditions,
)
from trainingdash.domain.pacing import RideTypeParams, RideTypePreset
from trainingdash.use_cases.compare_execution import CompareExecution
from trainingdash.use_cases.generate_race_plan import (
    GeneratePlanRequest,
    GenerateRacePlan,
)
from trainingdash.use_cases.get_matching_activities import GetMatchingActivities

router = APIRouter(prefix="/api/race-plans", tags=["race-plans"])


# =============================================================================
# Request/Response Models
# =============================================================================


class RideTypeParamsSchema(BaseModel):
    """Custom ride type parameters for race plan generation.
    
    descent_aggressiveness: 0=very cautious, 100=race pace. Affects curvature-based speed reduction on descents.
    stop_pct: Expected percentage of extra time for stops (traffic, feeds, breaks). 0-50%.
    """
    
    descent_aggressiveness: int = Field(..., ge=0, le=100, description="0=cautious descents, 100=aggressive racing")
    stop_pct: float = Field(..., ge=0, le=50, description="Expected stop time as % of riding time (0-50)")
    
    def to_domain(self) -> RideTypeParams:
        """Convert to domain object."""
        return RideTypeParams(
            descent_aggressiveness=self.descent_aggressiveness,
            stop_pct=self.stop_pct,
        )


class GeneratePlanRequestSchema(BaseModel):
    """Request to generate a new race pacing plan.

    Two targeting modes:
    1. Intensity mode (default): Set target_intensity as % of FTP
    2. Time mode: Set target_time_s to specify desired finish time

    If target_time_s is provided, optimizer calculates power to hit that time.

    CdA/Crr selection:
    - If override_cda AND override_crr are both provided, use those values
    - Otherwise, smart selection: estimated from activities > manual bike config > defaults

    Weather conditions:
    - Set target_date to get forecast (within 16 days)
    - Wind overrides require both speed AND direction
    """

    course_id: int
    bike_id: int | None = None
    rider_weight_kg: float | None = None
    gear_weight_kg: float | None = Field(
        None, ge=0, le=15, description="Gear weight in kg (clothing, shoes, bottles, etc.). Default 3.0 kg"
    )
    ftp_watts: int = Field(..., ge=100, le=600)
    cp_watts: int | None = Field(None, ge=100, le=600)
    w_prime_joules: int | None = Field(None, ge=5000, le=50000)
    target_intensity: float = Field(0.85, ge=0.5, le=1.2)
    target_time_s: float | None = Field(None, ge=60, le=86400)  # 1 min to 24 hours
    use_optimizer: bool = False
    name: str | None = Field(None, max_length=200)
    # CdA/Crr overrides - if both set, use these instead of smart selection
    override_cda: float | None = Field(None, ge=0.15, le=0.6, description="Override CdA in m²")
    override_crr: float | None = Field(None, ge=0.002, le=0.015, description="Override Crr coefficient")
    # Weather/conditions for race day
    target_date: date | None = Field(None, description="Event date for weather forecast")
    target_hour: int = Field(10, ge=0, le=23, description="Hour of day for forecast (0-23)")
    wind_override_speed_mps: float | None = Field(None, ge=0, le=30, description="Manual wind speed override (m/s)")
    wind_override_direction_deg: float | None = Field(
        None, ge=0, le=360, description="Manual wind direction override (degrees)"
    )
    max_descent_speed_mps: float | None = Field(
        None, ge=5, le=30, description="Max descent speed cap (m/s). Default ~18 m/s = 65 km/h"
    )
    # Ride type configuration
    ride_type: RideTypePreset = Field(
        "gran_fondo",
        description="Ride type preset: race, gran_fondo, training, touring, custom. Controls descent aggressiveness and stop time.",
    )
    ride_type_params: "RideTypeParamsSchema | None" = Field(
        None,
        description="Custom ride type params (required when ride_type='custom'). descent_aggressiveness: 0-100, stop_pct: 0-50.",
    )

    def to_domain(self) -> GeneratePlanRequest:
        """Convert to domain request object."""
        return GeneratePlanRequest(
            course_id=self.course_id,
            bike_id=self.bike_id,
            rider_weight_kg=self.rider_weight_kg,
            gear_weight_kg=self.gear_weight_kg,
            ftp_watts=self.ftp_watts,
            cp_watts=self.cp_watts,
            w_prime_joules=self.w_prime_joules,
            target_intensity=self.target_intensity,
            target_time_s=self.target_time_s,
            use_optimizer=self.use_optimizer,
            name=self.name,
            override_cda=self.override_cda,
            override_crr=self.override_crr,
            target_date=self.target_date,
            target_hour=self.target_hour,
            wind_override_speed_mps=self.wind_override_speed_mps,
            wind_override_direction_deg=self.wind_override_direction_deg,
            max_descent_speed_mps=self.max_descent_speed_mps,
            ride_type=self.ride_type,
            ride_type_params=self.ride_type_params.to_domain() if self.ride_type_params else None,
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


class AeroSelectionSchema(BaseModel):
    """CdA/Crr selection metadata."""

    cda: float
    crr: float
    source: str  # "user_override", "estimated", "manual", "default"
    confidence_note: str | None = None
    cda_stddev: float | None = None
    crr_stddev: float | None = None
    sample_count: int | None = None


class WeatherConditionsSchema(BaseModel):
    """Weather conditions used for race planning."""

    temperature_c: float
    wind_speed_mps: float
    wind_direction_deg: float
    pressure_hpa: float
    humidity_pct: float
    air_density: float


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
    # Ride type configuration
    ride_type: str | None = None
    descent_aggressiveness: int | None = None
    stop_pct: float | None = None
    # Comparison and metadata
    comparison: ComparisonSchema
    warnings: list[str]
    aero_selection: AeroSelectionSchema | None = None
    weather_conditions: WeatherConditionsSchema | None = None
    forecast_stale: bool = False  # True if calm conditions used (no real forecast)


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
    # Weather metadata
    target_date: date | None = None
    conditions_fetched_at: datetime | None = None
    forecast_stale: bool = False  # True if fetched > 24h ago or target_date changed
    wind_override_speed_mps: float | None = None
    wind_override_direction_deg: float | None = None
    max_descent_speed_mps: float | None = None


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
    # Ride type configuration
    ride_type: RideTypePreset | None = Field(None, description="Ride type preset")
    ride_type_params: RideTypeParamsSchema | None = Field(None, description="Custom ride type params")


class CompareRequestSchema(BaseModel):
    """Request to compare activity against a plan."""

    activity_id: UUID


class RefreshWeatherResponse(BaseModel):
    """Response after refreshing weather forecast."""

    plan_id: int
    target_date: date | None
    weather_conditions: WeatherConditionsSchema | None
    conditions_fetched_at: datetime | None
    message: str


class SegmentComparisonSchema(BaseModel):
    """Comparison data for a single segment."""

    segment_idx: int
    distance_m: float
    grade_pct: float
    planned_power_w: float
    actual_power_w: float | None
    power_delta_pct: float | None
    planned_time_s: float
    actual_time_s: float | None
    time_delta_s: float | None


class ComparisonResponse(BaseModel):
    """Response from comparing activity execution against race plan."""

    plan_id: int
    activity_id: UUID

    total_planned_time_s: float
    total_planned_time_formatted: str
    total_actual_time_s: float
    total_actual_time_formatted: str
    time_delta_s: float
    time_delta_formatted: str  # "+2:30" or "-1:15"
    time_delta_pct: float

    pacing_consistency: float
    segments_over_target: int
    segments_under_target: int

    segment_comparisons: list[SegmentComparisonSchema]
    insights: list[str]


class ActivityListItem(BaseModel):
    """Summary item for activity list."""

    id: UUID
    name: str | None
    started_at: datetime
    total_distance_m: float
    moving_time_s: int
    avg_power_w: float | None


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


def format_time_delta(seconds: float) -> str:
    """Format time delta as +M:SS or -M:SS."""
    sign = "+" if seconds >= 0 else "-"
    abs_seconds = abs(int(seconds))
    minutes, secs = divmod(abs_seconds, 60)
    return f"{sign}{minutes}:{secs:02d}"


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
    pacing_coefficients_repo: PacingCoefficientsRepoD,
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
    use_case = GenerateRacePlan(course_repo, bike_repo, user_repo, plan_repo, pacing_coefficients_repo)

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
        ride_type=plan.ride_type,
        descent_aggressiveness=plan.descent_aggressiveness,
        stop_pct=plan.stop_pct,
        comparison=ComparisonSchema(**result.comparison),
        warnings=result.warnings,
        aero_selection=AeroSelectionSchema(**result.aero_selection) if result.aero_selection else None,
        weather_conditions=WeatherConditionsSchema(**result.weather_conditions) if result.weather_conditions else None,
        forecast_stale=result.forecast_stale,
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
    segment_targets = [SegmentTargetSchema(**st) for st in (plan.segment_targets or [])]

    # Parse weather conditions if present
    weather_conditions = None
    if plan.target_conditions:
        weather_conditions = WeatherConditionsSchema(**plan.target_conditions)

    # Check if forecast is stale (> 24 hours old)
    forecast_stale = False
    if plan.target_date and plan.conditions_fetched_at:
        age = datetime.now(UTC) - plan.conditions_fetched_at
        forecast_stale = age.total_seconds() > 86400  # 24 hours

    return RacePlanDetailResponse(
        id=plan.id,
        course_id=plan.course_id,
        name=plan.name,
        total_time_s=plan.total_time_s,
        total_time_formatted=format_time(plan.total_time_s),
        avg_power_w=plan.avg_power_w,
        normalized_power_w=plan.normalized_power_w,
        intensity_factor=float(plan.intensity_factor) if plan.intensity_factor else None,
        ride_type=plan.ride_type,
        descent_aggressiveness=plan.descent_aggressiveness,
        stop_pct=plan.stop_pct,
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
        # Weather metadata
        weather_conditions=weather_conditions,
        target_date=plan.target_date,
        conditions_fetched_at=plan.conditions_fetched_at,
        forecast_stale=forecast_stale,
        wind_override_speed_mps=plan.wind_override_speed_mps,
        wind_override_direction_deg=plan.wind_override_direction_deg,
        max_descent_speed_mps=plan.max_descent_speed_mps,
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
    pacing_coefficients_repo: PacingCoefficientsRepoD,
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
    weight = updates.rider_weight_kg if updates.rider_weight_kg is not None else float(existing_plan.rider_weight_kg)
    ftp = updates.ftp_watts if updates.ftp_watts is not None else existing_plan.ftp_watts
    cp = updates.cp_watts if updates.cp_watts is not None else existing_plan.cp_watts
    w_prime = updates.w_prime_joules if updates.w_prime_joules is not None else existing_plan.w_prime_joules
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
        # Preserve or update ride_type
        ride_type=updates.ride_type if updates.ride_type is not None else (existing_plan.ride_type or "gran_fondo"),
        ride_type_params=updates.ride_type_params.to_domain() if updates.ride_type_params else None,
    )

    # Generate new plan
    use_case = GenerateRacePlan(course_repo, bike_repo, user_repo, plan_repo, pacing_coefficients_repo)

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
        ride_type=plan.ride_type,
        descent_aggressiveness=plan.descent_aggressiveness,
        stop_pct=plan.stop_pct,
        comparison=ComparisonSchema(**result.comparison),
        warnings=result.warnings,
        aero_selection=AeroSelectionSchema(**result.aero_selection) if result.aero_selection else None,
        weather_conditions=WeatherConditionsSchema(**result.weather_conditions) if result.weather_conditions else None,
        forecast_stale=result.forecast_stale,
    )


# =============================================================================
# Weather Endpoints
# =============================================================================


@router.post("/{plan_id}/refresh-weather", response_model=RefreshWeatherResponse)
async def refresh_weather(
    plan_id: int,
    current_user: CurrentUser,
    plan_repo: RacePlanRepoD,
    course_repo: CourseRepoD,
    target_hour: int = Query(10, ge=0, le=23, description="Hour of day for forecast"),
):
    """
    Refresh weather forecast for a race plan.

    Fetches updated forecast from Open-Meteo if:
    - Plan has a target_date set
    - Target date is within 16 days

    Returns calm conditions (no wind) if target_date is not set or beyond forecast range.
    """
    # Get plan
    plan = await plan_repo.get_by_id(plan_id)
    if not plan or plan.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Race plan not found",
        )

    # Check if plan has target_date
    if not plan.target_date:
        return RefreshWeatherResponse(
            plan_id=plan_id,
            target_date=None,
            weather_conditions=None,
            conditions_fetched_at=None,
            message="No target date set for this plan",
        )

    # Get course for location
    course = await course_repo.get_by_id(plan.course_id)
    if not course or course.start_lat is None or course.start_lon is None:
        calm = get_calm_conditions()
        return RefreshWeatherResponse(
            plan_id=plan_id,
            target_date=plan.target_date,
            weather_conditions=WeatherConditionsSchema(**calm.to_dict()),
            conditions_fetched_at=None,
            message="Course has no location data, using calm conditions",
        )

    # Fetch forecast
    result = await fetch_race_day_forecast(
        lat=course.start_lat,
        lon=course.start_lon,
        target_date=plan.target_date,
        target_hour=target_hour,
    )

    conditions = result.conditions or get_calm_conditions()
    now = datetime.now(UTC)

    # Update plan in database
    plan.target_conditions = conditions.to_dict()
    plan.conditions_fetched_at = now
    await plan_repo.save(plan)

    # Build message
    if result.error_message:
        message = result.error_message
    elif result.forecast_available:
        message = f"Forecast updated for {plan.target_date}"
    else:
        message = "Using calm conditions (no forecast available)"

    return RefreshWeatherResponse(
        plan_id=plan_id,
        target_date=plan.target_date,
        weather_conditions=WeatherConditionsSchema(**conditions.to_dict()),
        conditions_fetched_at=now,
        message=message,
    )


# =============================================================================
# Comparison Endpoints
# =============================================================================


@router.post("/{plan_id}/compare", response_model=ComparisonResponse)
async def compare_execution(
    plan_id: int,
    request: CompareRequestSchema,
    current_user: CurrentUser,
    plan_repo: RacePlanRepoD,
    activity_repo: ActivityRepoD,
    record_repo: RecordRepoD,
    course_repo: CourseRepoD,
):
    """
    Compare an executed activity against a race plan.

    The activity should be a ride on the same course as the plan.
    Returns segment-by-segment comparison and summary insights.
    """
    use_case = CompareExecution(plan_repo, activity_repo, record_repo, course_repo)

    try:
        result = await use_case.execute(current_user.id, plan_id, request.activity_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return ComparisonResponse(
        plan_id=result.plan_id,
        activity_id=result.activity_id,
        total_planned_time_s=result.total_planned_time_s,
        total_planned_time_formatted=format_time(result.total_planned_time_s),
        total_actual_time_s=result.total_actual_time_s,
        total_actual_time_formatted=format_time(result.total_actual_time_s),
        time_delta_s=result.time_delta_s,
        time_delta_formatted=format_time_delta(result.time_delta_s),
        time_delta_pct=result.time_delta_pct,
        pacing_consistency=result.pacing_consistency,
        segments_over_target=result.segments_over_target,
        segments_under_target=result.segments_under_target,
        segment_comparisons=[
            SegmentComparisonSchema(
                segment_idx=c.segment_idx,
                distance_m=c.distance_m,
                grade_pct=c.grade_pct,
                planned_power_w=c.planned_power_w,
                actual_power_w=c.actual_power_w,
                power_delta_pct=c.power_delta_pct,
                planned_time_s=c.planned_time_s,
                actual_time_s=c.actual_time_s,
                time_delta_s=c.time_delta_s,
            )
            for c in result.segment_comparisons
        ],
        insights=result.insights,
    )


@router.get("/{plan_id}/matching-activities", response_model=list[ActivityListItem])
async def get_matching_activities(
    plan_id: int,
    current_user: CurrentUser,
    plan_repo: RacePlanRepoD,
    activity_repo: ActivityRepoD,
    course_repo: CourseRepoD,
):
    """
    Get activities that could be compared to this plan.

    Returns activities that:
    - Have power data
    - Match approximate distance of the course (within 20%)
    """
    use_case = GetMatchingActivities(plan_repo, activity_repo, course_repo)

    try:
        results = await use_case.execute(current_user.id, plan_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return [
        ActivityListItem(
            id=a.id,
            name=a.title,
            started_at=a.started_at,
            total_distance_m=a.total_distance_m,
            moving_time_s=a.moving_time_s,
            avg_power_w=a.avg_power_w,
        )
        for a in results
    ]
