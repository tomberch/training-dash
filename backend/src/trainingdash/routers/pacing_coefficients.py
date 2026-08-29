"""Pacing coefficients endpoints: view and manage personalized pacing model parameters."""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from trainingdash.auth import CurrentUser, DbSession
from trainingdash.dependencies import BikeRepoD, PacingCoefficientsRepoD
from trainingdash.domain.pacing_calibration import (
    DEFAULT_CURVATURE_SPEED_COEFFICIENT,
    DEFAULT_DESCENT_POWER_MULTIPLIER,
    DEFAULT_GRADE_POWER_INTERCEPT,
    DEFAULT_GRADE_POWER_SLOPE,
    DEFAULT_MAX_DESCENT_SPEED_MPS,
    MIN_ACTIVITIES,
    MIN_CLIMB_SAMPLES,
    MIN_DESCENT_SAMPLES,
)
from trainingdash.use_cases.calibrate_pacing import CalibratePacing

router = APIRouter(prefix="/api/pacing-coefficients", tags=["pacing-coefficients"])


# =============================================================================
# Response Models
# =============================================================================


class CoefficientsResponse(BaseModel):
    """Pacing coefficients with metadata."""

    # Source info
    source: str = Field(description="Where coefficients come from: 'bike', 'user_default', or 'global_default'")
    bike_id: int | None = Field(description="Bike ID if bike-specific, None for user/global default")
    bike_name: str | None = Field(description="Bike name if bike-specific")

    # Climb coefficients
    grade_power_intercept: float = Field(description="Base power multiplier at 0% grade")
    grade_power_slope: float = Field(description="Power multiplier increase per 1% grade")

    # Descent coefficients
    max_descent_speed_mps: float = Field(description="Maximum descent speed in m/s")
    max_descent_speed_kmh: float = Field(description="Maximum descent speed in km/h")
    descent_power_multiplier: float = Field(description="Power multiplier on descents")
    curvature_speed_coefficient: float = Field(description="Lateral acceleration comfort in corners (a_lat, m/s²)")

    # Confidence metrics
    climb_sample_count: int = Field(description="Number of climb data points used")
    descent_sample_count: int = Field(description="Number of descent data points used")
    activity_count: int = Field(description="Number of activities contributing")
    last_calibrated_at: datetime | None = Field(description="When last calibrated")

    # Confidence level
    confidence_level: str = Field(description="Confidence: 'high', 'medium', 'low', or 'default'")
    confidence_note: str = Field(description="Explanation of confidence level")


class AllCoefficientsResponse(BaseModel):
    """All coefficients for a user (default + per-bike)."""

    user_default: CoefficientsResponse | None = Field(description="User's default coefficients")
    bikes: list[CoefficientsResponse] = Field(description="Per-bike coefficients")


class CalibrationResponse(BaseModel):
    """Result of calibration."""

    success: bool
    activities_processed: int
    climb_samples: int
    descent_samples: int
    coefficients_updated: bool
    message: str


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_model=AllCoefficientsResponse)
async def get_all_coefficients(
    current_user: CurrentUser,
    pacing_repo: PacingCoefficientsRepoD,
    bike_repo: BikeRepoD,
):
    """
    Get all pacing coefficients for the current user.

    Returns user default (if calibrated) and all bike-specific coefficients.
    """
    all_coefs = await pacing_repo.list_for_user(current_user.id)

    # Get bike names
    bikes = await bike_repo.list_for_user(current_user.id)
    bike_names = {b.id: b.name for b in bikes}

    user_default = None
    bike_coefficients = []

    for coef in all_coefs:
        response = _build_coefficients_response(coef, bike_names)
        if coef.bike_id is None:
            user_default = response
        else:
            bike_coefficients.append(response)

    return AllCoefficientsResponse(
        user_default=user_default,
        bikes=bike_coefficients,
    )


@router.get("/effective", response_model=CoefficientsResponse)
async def get_effective_coefficients(
    current_user: CurrentUser,
    pacing_repo: PacingCoefficientsRepoD,
    bike_repo: BikeRepoD,
    bike_id: int | None = None,
):
    """
    Get the effective coefficients for a bike (with fallback chain).

    Fallback: bike-specific → user default → global defaults.
    """
    coef = await pacing_repo.get_for_user_bike(current_user.id, bike_id)

    if coef is None:
        # Return global defaults
        return CoefficientsResponse(
            source="global_default",
            bike_id=None,
            bike_name=None,
            grade_power_intercept=DEFAULT_GRADE_POWER_INTERCEPT,
            grade_power_slope=DEFAULT_GRADE_POWER_SLOPE,
            max_descent_speed_mps=DEFAULT_MAX_DESCENT_SPEED_MPS,
            max_descent_speed_kmh=DEFAULT_MAX_DESCENT_SPEED_MPS * 3.6,
            descent_power_multiplier=DEFAULT_DESCENT_POWER_MULTIPLIER,
            curvature_speed_coefficient=DEFAULT_CURVATURE_SPEED_COEFFICIENT,
            climb_sample_count=0,
            descent_sample_count=0,
            activity_count=0,
            last_calibrated_at=None,
            confidence_level="default",
            confidence_note="Using global defaults. Upload activities with power data to calibrate.",
        )

    # Get bike names for display
    bikes = await bike_repo.list_for_user(current_user.id)
    bike_names = {b.id: b.name for b in bikes}

    return _build_coefficients_response(coef, bike_names)


@router.post("/calibrate", response_model=CalibrationResponse)
async def calibrate_coefficients(
    current_user: CurrentUser,
    db: DbSession,
    pacing_repo: PacingCoefficientsRepoD,
    bike_id: int | None = None,
):
    """
    Trigger calibration of pacing coefficients.

    If bike_id is provided, calibrates for that specific bike.
    Otherwise, calibrates user default (all activities).

    Requires at least 3 activities with measured power and climbing.
    """
    use_case = CalibratePacing(db, pacing_repo)

    stats = await use_case.execute(current_user.id, bike_id)

    if stats.coefficients_updated:
        # Partial updates (#634: climb gate rejected, descent learned) carry
        # their own message; only full calibrations get the default text.
        message = stats.message or (
            f"Calibrated from {stats.activities_processed} activities with {stats.climb_samples} climb samples."
        )
        return CalibrationResponse(
            success=True,
            activities_processed=stats.activities_processed,
            climb_samples=stats.climb_samples,
            descent_samples=stats.descent_samples,
            coefficients_updated=True,
            message=message,
        )
    else:
        return CalibrationResponse(
            success=False,
            activities_processed=stats.activities_processed,
            climb_samples=stats.climb_samples,
            descent_samples=stats.descent_samples,
            coefficients_updated=False,
            message=_get_calibration_failure_message(stats),
        )


@router.post("/calibrate-all", response_model=dict[str, CalibrationResponse])
async def calibrate_all_bikes(
    current_user: CurrentUser,
    db: DbSession,
    pacing_repo: PacingCoefficientsRepoD,
):
    """
    Calibrate coefficients for all bikes plus user default.

    Runs calibration for:
    - User default (all activities combined)
    - Each bike with qualifying activities
    """
    use_case = CalibratePacing(db, pacing_repo)

    results = await use_case.execute_for_all_bikes(current_user.id)

    response = {}
    for bike_id, stats in results.items():
        key = "user_default" if bike_id is None else f"bike_{bike_id}"
        if stats.coefficients_updated:
            response[key] = CalibrationResponse(
                success=True,
                activities_processed=stats.activities_processed,
                climb_samples=stats.climb_samples,
                descent_samples=stats.descent_samples,
                coefficients_updated=True,
                message=f"Calibrated from {stats.activities_processed} activities.",
            )
        else:
            response[key] = CalibrationResponse(
                success=False,
                activities_processed=stats.activities_processed,
                climb_samples=stats.climb_samples,
                descent_samples=stats.descent_samples,
                coefficients_updated=False,
                message=_get_calibration_failure_message(stats),
            )

    return response


# =============================================================================
# Helpers
# =============================================================================


def _build_coefficients_response(coef, bike_names: dict[int, str]) -> CoefficientsResponse:
    """Build CoefficientsResponse from DB model."""
    if coef.bike_id is not None:
        source = "bike"
        bike_name = bike_names.get(coef.bike_id, f"Bike {coef.bike_id}")
    else:
        source = "user_default"
        bike_name = None

    confidence_level, confidence_note = _calculate_confidence(coef)

    return CoefficientsResponse(
        source=source,
        bike_id=coef.bike_id,
        bike_name=bike_name,
        grade_power_intercept=float(coef.grade_power_intercept),
        grade_power_slope=float(coef.grade_power_slope),
        max_descent_speed_mps=float(coef.max_descent_speed_mps),
        max_descent_speed_kmh=float(coef.max_descent_speed_mps) * 3.6,
        descent_power_multiplier=float(coef.descent_power_multiplier),
        curvature_speed_coefficient=float(coef.curvature_speed_coefficient),
        climb_sample_count=coef.climb_sample_count,
        descent_sample_count=coef.descent_sample_count,
        activity_count=coef.activity_count,
        last_calibrated_at=coef.last_calibrated_at,
        confidence_level=confidence_level,
        confidence_note=confidence_note,
    )


def _calculate_confidence(coef) -> tuple[str, str]:
    """Calculate confidence level and note based on sample counts."""
    climb_samples = coef.climb_sample_count
    descent_samples = coef.descent_sample_count
    activities = coef.activity_count

    # High: lots of data
    if climb_samples >= 10000 and descent_samples >= 5000 and activities >= 10:
        return "high", f"Based on {activities} activities with {climb_samples:,} climb samples."

    # Medium: sufficient data
    if climb_samples >= MIN_CLIMB_SAMPLES and descent_samples >= MIN_DESCENT_SAMPLES and activities >= MIN_ACTIVITIES:
        return "medium", f"Based on {activities} activities. More data will improve accuracy."

    # Low: minimal data
    if activities >= 1:
        return "low", f"Limited data ({activities} activities). Upload more rides to improve."

    return "default", "No calibration data available."


def _get_calibration_failure_message(stats) -> str:
    """Get appropriate failure message based on stats."""
    if stats.activities_processed < MIN_ACTIVITIES:
        return f"Need at least {MIN_ACTIVITIES} activities with measured power and climbing. Found {stats.activities_processed}."

    if stats.climb_samples < MIN_CLIMB_SAMPLES:
        return f"Need at least {MIN_CLIMB_SAMPLES} climb data points. Found {stats.climb_samples}."

    if stats.descent_samples < MIN_DESCENT_SAMPLES:
        return f"Need at least {MIN_DESCENT_SAMPLES} descent data points. Found {stats.descent_samples}."

    return "Insufficient data for calibration."
