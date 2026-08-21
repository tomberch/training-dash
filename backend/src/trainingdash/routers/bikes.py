"""Bikes endpoints: CRUD for user bikes/equipment."""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from trainingdash.auth import CurrentUser
from trainingdash.dependencies import ActivityRepoD, BikeRepoD, RecordRepoD
from trainingdash.domain.bike import BIKE_TYPES, is_calibration_eligible_type, validate_bike_type
from trainingdash.repositories.postgres.models import Bike
from trainingdash.routers.serializers import bike_response
from trainingdash.use_cases.calibrate_bike import (
    BikeNotEligibleError,
    BikeNotFoundError,
    CalibrateFromActivities,
    CalibrationError,
    InsufficientDataError,
    NoActivitiesError,
)

router = APIRouter(prefix="/api/bikes", tags=["bikes"])


# =============================================================================
# Request Models
# =============================================================================


class BikeCreate(BaseModel):
    """Request body for creating a bike."""

    name: str = Field(..., min_length=1, max_length=100)
    bike_type: str = Field(..., description="Bike type: road, tt, gravel, mtb, ebike")
    model_year: int | None = Field(None, ge=1900, le=2100)
    weight_kg: float | None = Field(None, gt=0, le=50)
    cda: float | None = Field(None, gt=0, le=1.0, description="CdA in m²")
    crr: float | None = Field(None, gt=0, le=0.1, description="Rolling resistance coefficient")
    is_default: bool = False


class BikeUpdate(BaseModel):
    """Request body for updating a bike."""

    name: str | None = Field(None, min_length=1, max_length=100)
    bike_type: str | None = Field(None, description="Bike type: road, tt, gravel, mtb, ebike")
    model_year: int | None = Field(None, ge=1900, le=2100)
    weight_kg: float | None = Field(None, gt=0, le=50)
    cda: float | None = Field(None, gt=0, le=1.0, description="CdA in m²")
    crr: float | None = Field(None, gt=0, le=0.1, description="Rolling resistance coefficient")


# =============================================================================
# Endpoints
# =============================================================================


@router.get("")
async def list_bikes(
    user: CurrentUser,
    bike_repo: BikeRepoD,
    include_retired: bool = Query(False, description="Include retired bikes"),
) -> dict[str, Any]:
    """List bikes for the current user."""
    bikes = await bike_repo.get_by_user(user.id, include_retired=include_retired)
    return {"bikes": [bike_response(b) for b in bikes]}


@router.get("/{bike_id}")
async def get_bike(
    bike_id: int,
    user: CurrentUser,
    bike_repo: BikeRepoD,
) -> dict[str, Any]:
    """Get a single bike by ID."""
    bike = await bike_repo.get_by_id(bike_id, user.id)
    if bike is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")
    return bike_response(bike)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_bike(
    user: CurrentUser,
    bike_repo: BikeRepoD,
    request: BikeCreate,
) -> dict[str, Any]:
    """Create a new bike."""
    # Validate bike type
    if not validate_bike_type(request.bike_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bike_type. Must be one of: {', '.join(sorted(BIKE_TYPES))}",
        )

    bike = Bike(
        user_id=user.id,
        name=request.name,
        bike_type=request.bike_type,
        model_year=request.model_year,
        weight_kg=request.weight_kg,
        cda=request.cda,
        crr=request.crr,
        cda_source="manual" if request.cda else None,
        crr_source="manual" if request.crr else None,
    )

    saved = await bike_repo.save(bike)

    # Set as default if requested (after save to get the ID)
    if request.is_default:
        await bike_repo.set_default(user.id, saved.id)
        # Refresh to get updated is_default
        saved = await bike_repo.get_by_id(saved.id, user.id)

    return bike_response(saved)


@router.patch("/{bike_id}")
async def update_bike(
    bike_id: int,
    user: CurrentUser,
    bike_repo: BikeRepoD,
    request: BikeUpdate,
) -> dict[str, Any]:
    """Update a bike's fields."""
    bike = await bike_repo.get_by_id(bike_id, user.id)
    if bike is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")

    # Cannot update retired bikes
    if bike.retired_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update a retired bike",
        )

    if request.name is not None:
        bike.name = request.name

    if request.bike_type is not None:
        if not validate_bike_type(request.bike_type):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid bike_type. Must be one of: {', '.join(sorted(BIKE_TYPES))}",
            )
        bike.bike_type = request.bike_type

    if request.model_year is not None:
        bike.model_year = request.model_year

    if request.weight_kg is not None:
        bike.weight_kg = request.weight_kg

    if request.cda is not None:
        bike.cda = request.cda
        bike.cda_source = "manual"

    if request.crr is not None:
        bike.crr = request.crr
        bike.crr_source = "manual"

    saved = await bike_repo.save(bike)
    return bike_response(saved)


@router.post("/{bike_id}/default", status_code=status.HTTP_200_OK)
async def set_default_bike(
    bike_id: int,
    user: CurrentUser,
    bike_repo: BikeRepoD,
) -> dict[str, Any]:
    """Set a bike as the user's default."""
    bike = await bike_repo.get_by_id(bike_id, user.id)
    if bike is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")

    if bike.retired_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot set a retired bike as default",
        )

    await bike_repo.set_default(user.id, bike_id)

    # Refresh to get updated state
    bike = await bike_repo.get_by_id(bike_id, user.id)
    return bike_response(bike)


@router.post("/{bike_id}/retire", status_code=status.HTTP_200_OK)
async def retire_bike(
    bike_id: int,
    user: CurrentUser,
    bike_repo: BikeRepoD,
) -> dict[str, Any]:
    """Retire a bike (soft delete)."""
    result = await bike_repo.retire(bike_id, user.id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")

    bike = await bike_repo.get_by_id(bike_id, user.id)
    return bike_response(bike)



# =============================================================================
# Calibration Endpoints
# =============================================================================


class CalibrationResponse(BaseModel):
    """Response body for calibration result."""

    bike_id: int
    cda: float
    confidence: Literal["low", "medium", "high"]
    n_activities_used: int
    n_segments_used: int
    total_duration_s: float
    previous_cda: float | None
    updated: bool
    warnings: list[str]
    rejection_summary: dict[str, int]


class CalibrationStatusResponse(BaseModel):
    """Response body for calibration status check."""

    eligible: bool
    n_activities: int
    estimated_confidence: Literal["low", "medium", "high"]
    last_calibrated: datetime | None
    reason: str | None = None


class CalibrateRequest(BaseModel):
    """Request body for calibration."""

    min_confidence: Literal["low", "medium", "high"] = "medium"
    rider_mass_kg: float | None = Field(None, gt=30, le=200, description="Rider mass in kg")


@router.post("/{bike_id}/calibrate", response_model=CalibrationResponse)
async def calibrate_bike(
    bike_id: int,
    user: CurrentUser,
    bike_repo: BikeRepoD,
    activity_repo: ActivityRepoD,
    record_repo: RecordRepoD,
    request: CalibrateRequest | None = None,
) -> CalibrationResponse:
    """
    Trigger CdA calibration for a bike.

    Analyzes recent activities tagged to this bike and estimates CdA
    using steady-state segments at speed (>30 km/h on flat terrain).

    The bike's CdA will be updated if the confidence level meets or exceeds
    the min_confidence threshold. If not, the result is returned but the
    bike is not modified.

    Requirements for calibration:
    - Bike must not be an e-bike (motor assistance skews data)
    - Activities must be tagged to this bike
    - Rides must have power data
    - Needs steady-state segments: speed >30 km/h, flat (<2% grade),
      consistent power (CV <15%) and speed (CV <5%), minimum 60s duration
    """
    # Verify bike exists and is owned by user
    bike = await bike_repo.get_by_id(bike_id, user.id)
    if bike is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")

    # Check eligibility
    if not is_calibration_eligible_type(bike.bike_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bike type '{bike.bike_type}' is not eligible for calibration",
        )

    # Parse request
    min_confidence = "medium"
    rider_mass_kg = None
    if request:
        min_confidence = request.min_confidence
        rider_mass_kg = request.rider_mass_kg

    # Run calibration
    use_case = CalibrateFromActivities(activity_repo, bike_repo, record_repo)
    try:
        result = await use_case.execute(
            user_id=user.id,
            bike_id=bike_id,
            min_confidence=min_confidence,
            rider_mass_kg=rider_mass_kg,
        )
    except BikeNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")
    except BikeNotEligibleError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except NoActivitiesError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except InsufficientDataError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except CalibrationError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    return CalibrationResponse(
        bike_id=result.bike_id,
        cda=result.cda,
        confidence=result.confidence,  # type: ignore
        n_activities_used=result.n_activities_used,
        n_segments_used=result.n_segments_used,
        total_duration_s=result.total_calibration_duration_s,
        previous_cda=result.previous_cda,
        updated=result.updated,
        warnings=result.warnings,
        rejection_summary=result.rejection_summary,
    )


@router.get("/{bike_id}/calibration-status", response_model=CalibrationStatusResponse)
async def get_calibration_status(
    bike_id: int,
    user: CurrentUser,
    bike_repo: BikeRepoD,
    activity_repo: ActivityRepoD,
) -> CalibrationStatusResponse:
    """
    Check if a bike has enough data for calibration.

    Returns eligibility status, number of activities available,
    estimated confidence level, and last calibration timestamp.
    """
    bike = await bike_repo.get_by_id(bike_id, user.id)
    if bike is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")

    # Check type eligibility
    if not is_calibration_eligible_type(bike.bike_type):
        return CalibrationStatusResponse(
            eligible=False,
            n_activities=0,
            estimated_confidence="low",
            last_calibrated=bike.calibrated_at,
            reason=f"Bike type '{bike.bike_type}' is not eligible for calibration",
        )

    # Count activities with power data tagged to this bike
    # Use list_by_bike and filter - simple read operation
    activities = await activity_repo.list_by_bike(bike_id, user.id, limit=100)
    n_activities = sum(
        1 for a in activities if a.avg_power_w is not None and a.avg_power_w > 0
    )

    # Determine eligibility and estimated confidence
    if n_activities == 0:
        return CalibrationStatusResponse(
            eligible=False,
            n_activities=0,
            estimated_confidence="low",
            last_calibrated=bike.calibrated_at,
            reason="No activities with power data are tagged to this bike",
        )

    # Estimate confidence based on activity count
    # (actual confidence depends on segment selection during calibration)
    if n_activities >= 10:
        estimated_confidence = "high"
    elif n_activities >= 5:
        estimated_confidence = "medium"
    else:
        estimated_confidence = "low"

    return CalibrationStatusResponse(
        eligible=True,
        n_activities=n_activities,
        estimated_confidence=estimated_confidence,  # type: ignore
        last_calibrated=bike.calibrated_at,
        reason=None,
    )
