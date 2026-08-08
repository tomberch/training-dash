"""Metrics endpoints: /me/metrics/* for managing historical metric entries."""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.dialects.postgresql import insert as pg_insert

from trainingdash.auth import CurrentUser, DbSession
from trainingdash.jobs import enqueue_recalculate_metrics_job
from trainingdash.models import Activity, MetricEntry, MetricType, RecalculationJob
from trainingdash.routers.datetime_utils import utc_str

router = APIRouter(prefix="/api", tags=["metrics"])


# --- Pydantic Schemas ---


class MetricEntryCreate(BaseModel):
    """Schema for creating a metric entry."""
    metric_type: str = Field(..., description="Metric type key (ftp, lthr, weight_kg, etc.)")
    effective_date: date
    value: float
    source: Literal["manual", "calculated", "device"] = "manual"
    source_detail: str | None = None
    notes: str | None = None


class MetricEntryUpdate(BaseModel):
    """Schema for updating a metric entry."""
    value: float | None = None
    effective_date: date | None = None
    notes: str | None = None


class MetricEntryRead(BaseModel):
    """Schema for reading a metric entry."""
    id: int
    metric_type: str
    metric_type_display: str
    unit: str | None
    category: str
    effective_date: date
    value: float
    source: str
    source_detail: str | None
    notes: str | None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


class RecalcPreview(BaseModel):
    """Preview of recalculation impact."""
    affected_activities: int
    recalc_targets: list[str]


# --- Helper Functions ---


async def _get_metric_type(db: DbSession, key: str) -> MetricType:
    """Get metric type by key or raise 404."""
    result = await db.execute(
        select(MetricType).where(MetricType.key == key)
    )
    metric_type = result.scalar_one_or_none()
    if metric_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Metric type '{key}' not found"
        )
    return metric_type


async def _get_owned_entry(db: DbSession, user_id: int, entry_id: int) -> MetricEntry:
    """Get metric entry by ID, ensuring it belongs to the user."""
    result = await db.execute(
        select(MetricEntry).where(
            MetricEntry.id == entry_id,
            MetricEntry.user_id == user_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Metric entry not found"
        )
    return entry


def _entry_to_read(entry: MetricEntry, metric_type: MetricType) -> dict:
    """Convert MetricEntry to response dict."""
    return {
        "id": entry.id,
        "metric_type": metric_type.key,
        "metric_type_display": metric_type.display_name,
        "unit": metric_type.unit,
        "category": metric_type.category,
        "effective_date": entry.effective_date.isoformat(),
        "value": float(entry.value),
        "source": entry.source,
        "source_detail": entry.source_detail,
        "notes": entry.notes,
        "created_at": utc_str(entry.created_at),
        "updated_at": utc_str(entry.updated_at),
    }


async def _trigger_recalculation(db: DbSession, user_id: int) -> None:
    """Trigger metric recalculation job for the user."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.execute(
        pg_insert(RecalculationJob)
        .values(user_id=user_id, status="pending", started_at=now)
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={"status": "pending", "started_at": now, "completed_at": None, "error_message": None},
        )
    )
    await db.commit()
    
    try:
        await enqueue_recalculate_metrics_job(user_id)
    except Exception:
        pass  # Job enqueueing failure is non-blocking


# --- Endpoints ---


@router.get("/me/metrics")
async def list_metrics(
    db: DbSession,
    user: CurrentUser,
    metric_type: str | None = Query(None, description="Filter by metric type key"),
    category: str | None = Query(None, description="Filter by category (threshold, body, fitness, recovery)"),
    from_date: date | None = Query(None, description="Filter entries on or after this date"),
    to_date: date | None = Query(None, description="Filter entries on or before this date"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List metric entries with optional filters."""
    # Build query
    query = (
        select(MetricEntry, MetricType)
        .join(MetricType, MetricEntry.metric_type_id == MetricType.id)
        .where(MetricEntry.user_id == user.id)
    )
    
    if metric_type:
        query = query.where(MetricType.key == metric_type)
    
    if category:
        query = query.where(MetricType.category == category)
    
    if from_date:
        query = query.where(MetricEntry.effective_date >= from_date)
    
    if to_date:
        query = query.where(MetricEntry.effective_date <= to_date)
    
    query = (
        query
        .order_by(MetricEntry.effective_date.desc(), MetricType.sort_order)
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(query)
    rows = result.all()
    
    return [_entry_to_read(entry, mt) for entry, mt in rows]


@router.post("/me/metrics", status_code=status.HTTP_201_CREATED)
async def create_metric(
    db: DbSession,
    user: CurrentUser,
    body: MetricEntryCreate,
):
    """Create or upsert a metric entry.
    
    If an entry already exists for the same user, metric_type, and effective_date,
    it will be updated (upsert behavior).
    """
    # Get and validate metric type
    metric_type = await _get_metric_type(db, body.metric_type)
    
    # Validate value against constraints
    if metric_type.min_value is not None and body.value < float(metric_type.min_value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Value must be at least {metric_type.min_value}"
        )
    if metric_type.max_value is not None and body.value > float(metric_type.max_value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Value must be at most {metric_type.max_value}"
        )
    
    # Validate source against allowed_sources
    if metric_type.allowed_sources and body.source not in metric_type.allowed_sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Source '{body.source}' not allowed for {metric_type.key}. Allowed: {metric_type.allowed_sources}"
        )
    
    # Check if entry exists for this date
    result = await db.execute(
        select(MetricEntry).where(
            MetricEntry.user_id == user.id,
            MetricEntry.metric_type_id == metric_type.id,
            MetricEntry.effective_date == body.effective_date,
        )
    )
    existing = result.scalar_one_or_none()
    
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    if existing:
        # Update existing entry
        existing.value = Decimal(str(body.value))
        existing.source = body.source
        existing.source_detail = body.source_detail
        existing.notes = body.notes
        existing.updated_at = now
        entry = existing
    else:
        # Create new entry
        entry = MetricEntry(
            user_id=user.id,
            metric_type_id=metric_type.id,
            effective_date=body.effective_date,
            value=Decimal(str(body.value)),
            source=body.source,
            source_detail=body.source_detail,
            notes=body.notes,
        )
        db.add(entry)
    
    await db.commit()
    await db.refresh(entry)
    
    # Trigger recalculation if this metric affects computed values
    if metric_type.recalc_targets:
        await _trigger_recalculation(db, user.id)
    
    return _entry_to_read(entry, metric_type)


@router.patch("/me/metrics/{entry_id}")
async def update_metric(
    db: DbSession,
    user: CurrentUser,
    entry_id: int,
    body: MetricEntryUpdate,
):
    """Update an existing metric entry.
    
    Device-sourced entries cannot be modified.
    """
    entry = await _get_owned_entry(db, user.id, entry_id)
    
    # Block modification of device entries
    if entry.source == "device":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify device-sourced entries"
        )
    
    # Get metric type for response
    result = await db.execute(
        select(MetricType).where(MetricType.id == entry.metric_type_id)
    )
    metric_type = result.scalar_one()
    
    needs_recalc = False
    
    if body.value is not None:
        # Validate value against constraints
        if metric_type.min_value is not None and body.value < float(metric_type.min_value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Value must be at least {metric_type.min_value}"
            )
        if metric_type.max_value is not None and body.value > float(metric_type.max_value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Value must be at most {metric_type.max_value}"
            )
        entry.value = Decimal(str(body.value))
        needs_recalc = True
    
    if body.effective_date is not None:
        # Check for duplicate on new date
        result = await db.execute(
            select(MetricEntry).where(
                MetricEntry.user_id == user.id,
                MetricEntry.metric_type_id == entry.metric_type_id,
                MetricEntry.effective_date == body.effective_date,
                MetricEntry.id != entry.id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Entry already exists for {body.effective_date}"
            )
        entry.effective_date = body.effective_date
        needs_recalc = True
    
    if body.notes is not None:
        entry.notes = body.notes
    
    entry.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    
    await db.commit()
    await db.refresh(entry)
    
    # Trigger recalculation if value or date changed
    if needs_recalc and metric_type.recalc_targets:
        await _trigger_recalculation(db, user.id)
    
    return _entry_to_read(entry, metric_type)


@router.delete("/me/metrics/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_metric(
    db: DbSession,
    user: CurrentUser,
    entry_id: int,
):
    """Delete a metric entry."""
    entry = await _get_owned_entry(db, user.id, entry_id)
    
    # Get metric type to check recalc_targets
    result = await db.execute(
        select(MetricType).where(MetricType.id == entry.metric_type_id)
    )
    metric_type = result.scalar_one()
    
    await db.delete(entry)
    await db.commit()
    
    # Trigger recalculation
    if metric_type.recalc_targets:
        await _trigger_recalculation(db, user.id)
    
    return None


@router.get("/me/metrics/current")
async def get_current_metrics(
    db: DbSession,
    user: CurrentUser,
):
    """Get most recent entry for each metric type.
    
    Returns a dict keyed by metric type, with null for types with no entries.
    """
    # Get all metric types
    result = await db.execute(
        select(MetricType).order_by(MetricType.sort_order)
    )
    all_types = result.scalars().all()
    
    # For each type, get most recent entry
    response = {}
    for mt in all_types:
        result = await db.execute(
            select(MetricEntry)
            .where(
                MetricEntry.user_id == user.id,
                MetricEntry.metric_type_id == mt.id,
            )
            .order_by(MetricEntry.effective_date.desc())
            .limit(1)
        )
        entry = result.scalar_one_or_none()
        
        if entry:
            response[mt.key] = _entry_to_read(entry, mt)
        else:
            response[mt.key] = None
    
    return response


@router.get("/me/metrics/effective")
async def get_effective_metrics(
    db: DbSession,
    user: CurrentUser,
    target_date: date = Query(..., alias="date", description="Date to get effective values for"),
    metric_types: str | None = Query(None, description="Comma-separated list of metric type keys"),
):
    """Get effective metric values at a specific date.
    
    Returns the most recent entry for each metric type where effective_date <= target_date.
    """
    # Get metric types to query
    if metric_types:
        type_keys = [k.strip() for k in metric_types.split(",")]
        result = await db.execute(
            select(MetricType)
            .where(MetricType.key.in_(type_keys))
            .order_by(MetricType.sort_order)
        )
    else:
        result = await db.execute(
            select(MetricType).order_by(MetricType.sort_order)
        )
    
    types_to_query = result.scalars().all()
    
    # For each type, get most recent entry <= target_date
    response = {}
    for mt in types_to_query:
        result = await db.execute(
            select(MetricEntry)
            .where(
                MetricEntry.user_id == user.id,
                MetricEntry.metric_type_id == mt.id,
                MetricEntry.effective_date <= target_date,
            )
            .order_by(MetricEntry.effective_date.desc())
            .limit(1)
        )
        entry = result.scalar_one_or_none()
        
        if entry:
            response[mt.key] = _entry_to_read(entry, mt)
        else:
            response[mt.key] = None
    
    return response


@router.get("/me/metrics/recalc-preview")
async def recalc_preview(
    db: DbSession,
    user: CurrentUser,
    metric_type: str = Query(..., description="Metric type key"),
    effective_date: date = Query(..., description="Effective date of the change"),
):
    """Preview what would be recalculated if a metric is changed.
    
    Returns the number of affected activities and the recalculation targets.
    """
    # Get metric type
    mt = await _get_metric_type(db, metric_type)
    
    # Count activities that would be affected (activities on or after effective_date)
    result = await db.execute(
        select(func.count())
        .select_from(Activity)
        .where(
            Activity.user_id == user.id,
            func.date(Activity.started_at) >= effective_date,
        )
    )
    affected_count = result.scalar() or 0
    
    return {
        "affected_activities": affected_count,
        "recalc_targets": mt.recalc_targets or [],
    }
