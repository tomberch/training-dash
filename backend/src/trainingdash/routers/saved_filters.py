"""Saved filters CRUD endpoints."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from trainingdash.auth import CurrentUser
from trainingdash.dependencies import SavedFilterRepoD
from trainingdash.repositories.postgres.saved_filter_repo import QueryValidationError
from trainingdash.routers.datetime_utils import utc_str

router = APIRouter(prefix="/api/saved-filters", tags=["saved-filters"])


# --- Response/Request Models ---


class SavedFilterResponse(BaseModel):
    """Response model for a saved filter."""

    id: int
    name: str
    query_text: str
    description: str | None
    is_default: bool
    created_at: str
    updated_at: str


class SavedFilterListResponse(BaseModel):
    """Response model for list of saved filters."""

    filters: list[SavedFilterResponse]


class CreateSavedFilterRequest(BaseModel):
    """Request model for creating a saved filter."""

    name: str = Field(..., min_length=1, max_length=100)
    query_text: str = Field(..., min_length=1)
    description: str | None = Field(None, max_length=500)
    is_default: bool = False


class UpdateSavedFilterRequest(BaseModel):
    """Request model for updating a saved filter.

    Only provided fields are updated. Omitted fields are left unchanged.
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    query_text: str | None = Field(None, min_length=1)
    description: str | None = Field(None, max_length=500)
    is_default: bool | None = None


class QueryErrorDetail(BaseModel):
    """Error details for query validation failures."""

    stage: str
    message: str


class QueryErrorResponse(BaseModel):
    """Response body for query validation errors."""

    error: QueryErrorDetail


# --- Helper ---


def _filter_to_response(f) -> SavedFilterResponse:
    """Convert a SavedFilter model to response."""
    return SavedFilterResponse(
        id=f.id,
        name=f.name,
        query_text=f.query_text,
        description=f.description,
        is_default=f.is_default,
        created_at=utc_str(f.created_at),
        updated_at=utc_str(f.updated_at),
    )


# --- Endpoints ---


@router.get("", response_model=SavedFilterListResponse)
async def list_saved_filters(
    repo: SavedFilterRepoD,
    user: CurrentUser,
):
    """List all saved filters for the current user.

    Returns filters ordered by name.
    """
    filters = await repo.list_for_user(user.id)
    return SavedFilterListResponse(filters=[_filter_to_response(f) for f in filters])


@router.get("/default", response_model=SavedFilterResponse | None)
async def get_default_filter(
    repo: SavedFilterRepoD,
    user: CurrentUser,
):
    """Get the user's default filter, if any.

    Returns null if no default is set.
    """
    f = await repo.get_default(user.id)
    return _filter_to_response(f) if f else None


@router.get("/{filter_id}", response_model=SavedFilterResponse)
async def get_saved_filter(
    filter_id: int,
    repo: SavedFilterRepoD,
    user: CurrentUser,
):
    """Get a saved filter by ID."""
    f = await repo.get_by_id(filter_id, user.id)
    if f is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved filter not found",
        )
    return _filter_to_response(f)


@router.post(
    "",
    response_model=SavedFilterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": QueryErrorResponse, "description": "Query validation error"},
        409: {"description": "Filter with this name already exists"},
    },
)
async def create_saved_filter(
    request: CreateSavedFilterRequest,
    repo: SavedFilterRepoD,
    user: CurrentUser,
):
    """Create a new saved filter.

    The query is validated before saving. If is_default is true, any existing
    default filter for the user is cleared.
    """
    # Check for duplicate name
    existing = await repo.get_by_name(request.name, user.id)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Filter with name '{request.name}' already exists",
        )

    try:
        f = await repo.create(
            user_id=user.id,
            name=request.name,
            query_text=request.query_text,
            description=request.description,
            is_default=request.is_default,
        )
    except QueryValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"stage": e.stage, "message": e.message}},
        )

    return _filter_to_response(f)


@router.patch(
    "/{filter_id}",
    response_model=SavedFilterResponse,
    responses={
        400: {"model": QueryErrorResponse, "description": "Query validation error"},
        404: {"description": "Filter not found"},
        409: {"description": "Filter with this name already exists"},
    },
)
async def update_saved_filter(
    filter_id: int,
    request: UpdateSavedFilterRequest,
    repo: SavedFilterRepoD,
    user: CurrentUser,
):
    """Update a saved filter.

    Only provided fields are updated. Query is re-validated if changed.
    If is_default is set to true, any existing default is cleared.
    """
    # Check if filter exists
    existing = await repo.get_by_id(filter_id, user.id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved filter not found",
        )

    # Check for duplicate name if changing
    if request.name is not None and request.name != existing.name:
        name_conflict = await repo.get_by_name(request.name, user.id)
        if name_conflict is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Filter with name '{request.name}' already exists",
            )

    try:
        f = await repo.update(
            filter_id=filter_id,
            user_id=user.id,
            name=request.name,
            query_text=request.query_text,
            description=request.description,
            is_default=request.is_default,
        )
    except QueryValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"stage": e.stage, "message": e.message}},
        )

    return _filter_to_response(f)


@router.delete("/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_filter(
    filter_id: int,
    repo: SavedFilterRepoD,
    user: CurrentUser,
):
    """Delete a saved filter."""
    deleted = await repo.delete(filter_id, user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved filter not found",
        )


@router.post("/{filter_id}/set-default", response_model=SavedFilterResponse)
async def set_default_filter(
    filter_id: int,
    repo: SavedFilterRepoD,
    user: CurrentUser,
):
    """Set a filter as the user's default.

    Clears any existing default filter.
    """
    success = await repo.set_default(filter_id, user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Saved filter not found",
        )

    f = await repo.get_by_id(filter_id, user.id)
    return _filter_to_response(f)


@router.post("/clear-default", status_code=status.HTTP_204_NO_CONTENT)
async def clear_default_filter(
    repo: SavedFilterRepoD,
    user: CurrentUser,
):
    """Clear the user's default filter (no filter is default)."""
    await repo.clear_default(user.id)
