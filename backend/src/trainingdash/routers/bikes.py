"""Bikes endpoints: CRUD for user bikes/equipment."""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from trainingdash.auth import CurrentUser
from trainingdash.dependencies import BikeRepoD
from trainingdash.domain.bike import BIKE_TYPES, validate_bike_type
from trainingdash.repositories.postgres.models import Bike
from trainingdash.routers.serializers import bike_response

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
):
    """List bikes for the current user."""
    bikes = await bike_repo.get_by_user(user.id, include_retired=include_retired)
    return {"bikes": [bike_response(b) for b in bikes]}


@router.get("/{bike_id}")
async def get_bike(
    bike_id: int,
    user: CurrentUser,
    bike_repo: BikeRepoD,
):
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
):
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
):
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
):
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
):
    """Retire a bike (soft delete)."""
    result = await bike_repo.retire(bike_id, user.id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bike not found")

    bike = await bike_repo.get_by_id(bike_id, user.id)
    return bike_response(bike)
