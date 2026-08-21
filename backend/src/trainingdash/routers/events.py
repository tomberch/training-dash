"""Ride Events endpoints: CRUD for events, journal entries, links, media, activity linking."""

from datetime import date
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from trainingdash.auth import CurrentUser, DbSession
from trainingdash.dependencies import (
    ActivityRepoD,
    BatchLinkActivitiesD,
    MediaServiceD,
)
from trainingdash.repositories.postgres.models import (
    Activity,
    JournalEntry,
    JournalEntryActivity,
    RideEvent,
    RideEventLink,
    RideEventMedia,
)
from trainingdash.repositories.postgres.ride_event_repo import (
    PostgresJournalEntryActivityRepo,
    PostgresJournalEntryRepo,
    PostgresRideEventLinkRepo,
    PostgresRideEventMediaRepo,
    PostgresRideEventRepo,
)
from trainingdash.services.media import MediaValidationError

router = APIRouter(prefix="/api/events", tags=["events"])

# Pagination defaults
DEFAULT_PAGE = 1
DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateEventRequest(BaseModel):
    """Request body for creating a ride event."""

    title: str = Field(..., min_length=1, max_length=200)
    event_type: str = Field(..., description="Event type: race, gran_fondo, multi_day, single_day, other")
    start_date: date
    end_date: date | None = None  # Defaults to start_date if not provided
    description: str | None = None


class UpdateEventRequest(BaseModel):
    """Request body for updating a ride event."""

    title: str | None = Field(None, min_length=1, max_length=200)
    event_type: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class CreateJournalEntryRequest(BaseModel):
    """Request body for creating a journal entry."""

    entry_date: date
    description: str | None = None


class UpdateJournalEntryRequest(BaseModel):
    """Request body for updating a journal entry."""

    entry_date: date | None = None
    description: str | None = None


class CreateLinkRequest(BaseModel):
    """Request body for creating a link."""

    url: str = Field(..., min_length=1, max_length=500)
    title: str = Field(..., min_length=1, max_length=255)
    link_type: str = Field(default="other", description="Link type: route, place, article, video, gear, other")
    sort_order: int = 0


class UpdateLinkRequest(BaseModel):
    """Request body for updating a link."""

    url: str | None = Field(None, min_length=1, max_length=500)
    title: str | None = Field(None, min_length=1, max_length=255)
    link_type: str | None = None
    sort_order: int | None = None


class LinkActivityRequest(BaseModel):
    """Request body for linking an activity to a journal entry."""

    activity_id: UUID
    sort_order: int = 0


class ReorderActivitiesRequest(BaseModel):
    """Request body for reordering activities in a journal entry."""

    activity_ids: list[UUID]


class BatchLinkActivitiesRequest(BaseModel):
    """Request body for batch linking activities to an event."""

    activity_ids: list[UUID]


class CreateVideoEmbedRequest(BaseModel):
    """Request body for creating a video embed."""

    url: str = Field(..., min_length=1, max_length=500)
    title: str = Field(..., min_length=1, max_length=255)
    sort_order: int = 0


# =============================================================================
# Serializers
# =============================================================================


def serialize_event(event: RideEvent) -> dict:
    """Serialize a RideEvent to API response format."""
    return {
        "id": str(event.id),
        "title": event.title,
        "event_type": event.event_type,
        "start_date": event.start_date.isoformat(),
        "end_date": event.end_date.isoformat() if event.end_date else None,
        "description": event.description,
        "cover_image_id": str(event.cover_image_id) if event.cover_image_id else None,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None,
    }


def serialize_event_summary(
    event: RideEvent,
    cover_image_url: str | None = None,
    total_distance_km: float | None = None,
    total_elevation_m: float | None = None,
    total_activities: int = 0,
    total_photos: int = 0,
) -> dict:
    """Serialize a RideEvent for list view with summary stats."""
    return {
        "id": str(event.id),
        "title": event.title,
        "event_type": event.event_type,
        "start_date": event.start_date.isoformat(),
        "end_date": event.end_date.isoformat() if event.end_date else None,
        "cover_image_url": cover_image_url,
        "total_distance_km": total_distance_km,
        "total_elevation_m": total_elevation_m,
        "total_activities": total_activities,
        "total_photos": total_photos,
    }


def serialize_journal_entry(entry: JournalEntry) -> dict:
    """Serialize a JournalEntry to API response format."""
    return {
        "id": str(entry.id),
        "ride_event_id": str(entry.ride_event_id),
        "entry_date": entry.entry_date.isoformat(),
        "description": entry.description,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


def serialize_link(link: RideEventLink) -> dict:
    """Serialize a RideEventLink to API response format."""
    return {
        "id": str(link.id),
        "ride_event_id": str(link.ride_event_id) if link.ride_event_id else None,
        "journal_entry_id": str(link.journal_entry_id) if link.journal_entry_id else None,
        "url": link.url,
        "title": link.title,
        "link_type": link.link_type,
        "sort_order": link.sort_order,
    }


def serialize_media(media: RideEventMedia) -> dict:
    """Serialize a RideEventMedia to API response format."""
    return {
        "id": str(media.id),
        "ride_event_id": str(media.ride_event_id) if media.ride_event_id else None,
        "journal_entry_id": str(media.journal_entry_id) if media.journal_entry_id else None,
        "media_type": media.media_type,
        "storage_path": media.storage_path,
        "thumbnail_path": media.thumbnail_path,
        "caption": media.caption,
        "sort_order": media.sort_order,
    }


def serialize_activity_link(link: JournalEntryActivity, activity: Activity | None = None) -> dict:
    """Serialize a JournalEntryActivity to API response format, optionally with activity details."""
    result = {
        "id": link.id,
        "journal_entry_id": str(link.journal_entry_id),
        "activity_id": str(link.activity_id),
        "sort_order": link.sort_order,
    }
    if activity:
        result["activity"] = {
            "id": str(activity.id),
            "title": activity.title,
            "started_at": activity.started_at.isoformat() if activity.started_at else None,
            "distance_km": round(activity.total_distance_m / 1000, 1) if activity.total_distance_m else None,
            "elevation_m": round(activity.elevation_gain_m) if activity.elevation_gain_m else None,
            "duration_seconds": activity.moving_time_s,
            "map_polyline": activity.map_polyline,
        }
    return result


# =============================================================================
# Helper Functions
# =============================================================================


async def _get_event_repo(db: DbSession) -> PostgresRideEventRepo:
    return PostgresRideEventRepo(db)


async def _get_entry_repo(db: DbSession) -> PostgresJournalEntryRepo:
    return PostgresJournalEntryRepo(db)


async def _get_media_repo(db: DbSession) -> PostgresRideEventMediaRepo:
    return PostgresRideEventMediaRepo(db)


async def _get_link_repo(db: DbSession) -> PostgresRideEventLinkRepo:
    return PostgresRideEventLinkRepo(db)


async def _get_activity_link_repo(db: DbSession) -> PostgresJournalEntryActivityRepo:
    return PostgresJournalEntryActivityRepo(db)


async def _get_owned_event(db: DbSession, user: CurrentUser, event_id: UUID) -> RideEvent:
    """Fetch an event owned by the current user or raise 404."""
    repo = await _get_event_repo(db)
    event = await repo.get_by_id(event_id, user.id)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


async def _get_owned_entry(db: DbSession, user: CurrentUser, entry_id: UUID) -> JournalEntry:
    """Fetch a journal entry owned by the current user or raise 404."""
    repo = await _get_entry_repo(db)
    entry = await repo.get_by_id(entry_id, user.id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return entry


# =============================================================================
# Event Endpoints
# =============================================================================


@router.get("")
async def list_events(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(DEFAULT_PAGE, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE, description="Items per page"),
    event_type: str | None = Query(None, description="Filter by event type"),
):
    """List ride events for the current user with pagination and summary stats."""
    repo = await _get_event_repo(db)

    total = await repo.count_for_user(user.id, event_type=event_type)
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    offset = (page - 1) * per_page

    events = await repo.list_for_user(user.id, event_type=event_type, limit=per_page, offset=offset)

    # Collect all event IDs for batch queries
    event_ids = [e.id for e in events]

    # Batch fetch cover images
    cover_images: dict[UUID, str] = {}
    if event_ids:
        result = await db.execute(
            select(RideEventMedia.ride_event_id, RideEventMedia.storage_path).where(
                RideEventMedia.id.in_(
                    select(RideEvent.cover_image_id)
                    .where(RideEvent.id.in_(event_ids))
                    .where(RideEvent.cover_image_id.isnot(None))
                )
            )
        )
        for row in result.all():
            cover_images[row[0]] = row[1]

    # Batch fetch photo counts per event
    photo_counts: dict[UUID, int] = {}
    if event_ids:
        result = await db.execute(
            select(RideEventMedia.ride_event_id, func.count(RideEventMedia.id))
            .where(RideEventMedia.ride_event_id.in_(event_ids))
            .where(RideEventMedia.media_type == "photo")
            .group_by(RideEventMedia.ride_event_id)
        )
        for row in result.all():
            photo_counts[row[0]] = row[1]

    # Batch fetch activity stats per event via journal entries
    activity_stats: dict[UUID, dict] = {eid: {"count": 0, "distance": None, "elevation": None} for eid in event_ids}
    if event_ids:
        # Get activity links through journal entries
        result = await db.execute(
            select(
                JournalEntry.ride_event_id,
                func.count(JournalEntryActivity.id).label("activity_count"),
                func.sum(Activity.total_distance_m).label("total_distance"),
                func.sum(Activity.elevation_gain_m).label("total_elevation"),
            )
            .select_from(JournalEntry)
            .join(JournalEntryActivity, JournalEntryActivity.journal_entry_id == JournalEntry.id)
            .join(Activity, Activity.id == JournalEntryActivity.activity_id)
            .where(JournalEntry.ride_event_id.in_(event_ids))
            .group_by(JournalEntry.ride_event_id)
        )
        for row in result.all():
            activity_stats[row[0]] = {
                "count": row[1] or 0,
                "distance": round(float(row[2]) / 1000, 1) if row[2] else None,
                "elevation": round(float(row[3])) if row[3] else None,
            }

    return {
        "events": [
            serialize_event_summary(
                e,
                cover_image_url=cover_images.get(e.id),
                total_distance_km=activity_stats[e.id]["distance"],
                total_elevation_m=activity_stats[e.id]["elevation"],
                total_activities=activity_stats[e.id]["count"],
                total_photos=photo_counts.get(e.id, 0),
            )
            for e in events
        ],
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_event(
    db: DbSession,
    user: CurrentUser,
    request: CreateEventRequest,
):
    """Create a new ride event."""
    repo = await _get_event_repo(db)

    event = RideEvent(
        id=uuid4(),
        user_id=user.id,
        title=request.title,
        event_type=request.event_type,
        start_date=request.start_date,
        end_date=request.end_date or request.start_date,  # Default to start_date for single-day
        description=request.description,
    )

    saved = await repo.save(event)
    return serialize_event(saved)


@router.get("/{event_id}")
async def get_event(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
):
    """Get a ride event with all related data (entries, media, links)."""
    event = await _get_owned_event(db, user, event_id)

    # Fetch related data
    entry_repo = await _get_entry_repo(db)
    media_repo = await _get_media_repo(db)
    link_repo = await _get_link_repo(db)
    activity_link_repo = await _get_activity_link_repo(db)

    entries = await entry_repo.list_for_event(event_id)
    event_media = await media_repo.list_for_event(event_id)
    event_links = await link_repo.list_for_event(event_id)

    # Fetch all activity IDs across all entries first, then batch-fetch activities
    activity_link_repo = await _get_activity_link_repo(db)
    all_activity_links = await activity_link_repo.list_for_event(event_id)
    activity_ids = [link.activity_id for link in all_activity_links]

    # Batch fetch all activities for this event
    activities_map: dict[UUID, Activity] = {}
    if activity_ids:
        result = await db.execute(select(Activity).where(Activity.id.in_(activity_ids)))
        for activity in result.scalars().all():
            activities_map[activity.id] = activity

    # Build entries with their media, links, and activities (with details)
    entries_data = []
    for entry in entries:
        entry_media = await media_repo.list_for_entry(entry.id)
        entry_links = await link_repo.list_for_entry(entry.id)
        entry_activities = await activity_link_repo.list_for_entry(entry.id)

        entries_data.append(
            {
                **serialize_journal_entry(entry),
                "media": [serialize_media(m) for m in entry_media],
                "links": [serialize_link(link) for link in entry_links],
                "activities": [serialize_activity_link(a, activities_map.get(a.activity_id)) for a in entry_activities],
            }
        )

    # Calculate aggregate stats (activity_ids already collected above)
    stats = {
        "total_distance_km": None,
        "total_duration_seconds": None,
        "total_elevation_m": None,
        "total_tss": None,
        "activity_count": len(activity_ids),
    }

    if activity_ids:
        # Fetch aggregate stats from activities
        result = await db.execute(
            select(
                func.sum(Activity.total_distance_m),
                func.sum(Activity.moving_time_s),
                func.sum(Activity.elevation_gain_m),
                func.sum(Activity.tss),
            ).where(Activity.id.in_(activity_ids))
        )
        row = result.one()
        # Convert meters to km for display
        stats["total_distance_km"] = round(float(row[0]) / 1000, 1) if row[0] else None
        stats["total_duration_seconds"] = int(row[1]) if row[1] else None
        stats["total_elevation_m"] = float(row[2]) if row[2] else None
        stats["total_tss"] = float(row[3]) if row[3] else None

    return {
        **serialize_event(event),
        "entries": entries_data,
        "media": [serialize_media(m) for m in event_media],
        "links": [serialize_link(link) for link in event_links],
        "stats": stats,
    }


@router.patch("/{event_id}")
async def update_event(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
    request: UpdateEventRequest,
):
    """Update a ride event."""
    event = await _get_owned_event(db, user, event_id)
    repo = await _get_event_repo(db)

    if request.title is not None:
        event.title = request.title
    if request.event_type is not None:
        event.event_type = request.event_type
    if request.start_date is not None:
        event.start_date = request.start_date
    if request.end_date is not None:
        event.end_date = request.end_date
    if request.description is not None:
        event.description = request.description

    saved = await repo.save(event)
    return serialize_event(saved)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
    media_service: MediaServiceD,
):
    """Delete a ride event (cascades to entries, media, links). Cleans up uploaded files."""
    # Verify ownership first
    event = await _get_owned_event(db, user, event_id)

    # Delete uploaded files directory for this event
    media_service.delete_event_directory(event_id)

    # Delete database record (cascades handle entries, media, links)
    repo = await _get_event_repo(db)
    deleted = await repo.delete(event_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")


# =============================================================================
# Journal Entry Endpoints
# =============================================================================


@router.post("/{event_id}/entries", status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
    request: CreateJournalEntryRequest,
):
    """Create a new journal entry for an event."""
    await _get_owned_event(db, user, event_id)  # Verify ownership
    repo = await _get_entry_repo(db)

    entry = JournalEntry(
        id=uuid4(),
        ride_event_id=event_id,
        entry_date=request.entry_date,
        description=request.description,
    )

    saved = await repo.save(entry)
    return serialize_journal_entry(saved)


@router.get("/{event_id}/entries")
async def list_journal_entries(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
):
    """List all journal entries for an event."""
    await _get_owned_event(db, user, event_id)  # Verify ownership
    repo = await _get_entry_repo(db)

    entries = await repo.list_for_event(event_id)
    return {"entries": [serialize_journal_entry(e) for e in entries]}


@router.get("/entries/{entry_id}")
async def get_journal_entry(
    db: DbSession,
    user: CurrentUser,
    entry_id: UUID,
):
    """Get a journal entry with its media, links, and activities."""
    entry = await _get_owned_entry(db, user, entry_id)

    media_repo = await _get_media_repo(db)
    link_repo = await _get_link_repo(db)
    activity_link_repo = await _get_activity_link_repo(db)

    entry_media = await media_repo.list_for_entry(entry_id)
    entry_links = await link_repo.list_for_entry(entry_id)
    entry_activities = await activity_link_repo.list_for_entry(entry_id)

    return {
        **serialize_journal_entry(entry),
        "media": [serialize_media(m) for m in entry_media],
        "links": [serialize_link(link) for link in entry_links],
        "activities": [serialize_activity_link(a) for a in entry_activities],
    }


@router.patch("/entries/{entry_id}")
async def update_journal_entry(
    db: DbSession,
    user: CurrentUser,
    entry_id: UUID,
    request: UpdateJournalEntryRequest,
):
    """Update a journal entry."""
    entry = await _get_owned_entry(db, user, entry_id)
    repo = await _get_entry_repo(db)

    if request.entry_date is not None:
        entry.entry_date = request.entry_date
    if request.description is not None:
        entry.description = request.description

    saved = await repo.save(entry)
    return serialize_journal_entry(saved)


@router.delete("/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_journal_entry(
    db: DbSession,
    user: CurrentUser,
    entry_id: UUID,
):
    """Delete a journal entry."""
    repo = await _get_entry_repo(db)
    deleted = await repo.delete(entry_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")


# =============================================================================
# Event Link Endpoints
# =============================================================================


@router.post("/{event_id}/links", status_code=status.HTTP_201_CREATED)
async def create_event_link(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
    request: CreateLinkRequest,
):
    """Add a link to an event."""
    await _get_owned_event(db, user, event_id)
    repo = await _get_link_repo(db)

    link = RideEventLink(
        id=uuid4(),
        ride_event_id=event_id,
        url=request.url,
        title=request.title,
        link_type=request.link_type,
        sort_order=request.sort_order,
    )

    saved = await repo.save(link)
    return serialize_link(saved)


@router.post("/entries/{entry_id}/links", status_code=status.HTTP_201_CREATED)
async def create_entry_link(
    db: DbSession,
    user: CurrentUser,
    entry_id: UUID,
    request: CreateLinkRequest,
):
    """Add a link to a journal entry."""
    await _get_owned_entry(db, user, entry_id)
    repo = await _get_link_repo(db)

    link = RideEventLink(
        id=uuid4(),
        journal_entry_id=entry_id,
        url=request.url,
        title=request.title,
        link_type=request.link_type,
        sort_order=request.sort_order,
    )

    saved = await repo.save(link)
    return serialize_link(saved)


@router.patch("/links/{link_id}")
async def update_link(
    db: DbSession,
    user: CurrentUser,
    link_id: UUID,
    request: UpdateLinkRequest,
):
    """Update a link."""
    repo = await _get_link_repo(db)
    link = await repo.get_by_id(link_id, user.id)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")

    if request.url is not None:
        link.url = request.url
    if request.title is not None:
        link.title = request.title
    if request.link_type is not None:
        link.link_type = request.link_type
    if request.sort_order is not None:
        link.sort_order = request.sort_order

    saved = await repo.save(link)
    return serialize_link(saved)


@router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    db: DbSession,
    user: CurrentUser,
    link_id: UUID,
):
    """Delete a link."""
    repo = await _get_link_repo(db)
    deleted = await repo.delete(link_id, user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")


# =============================================================================
# Video Embed Endpoints
# =============================================================================


@router.post("/{event_id}/videos", status_code=status.HTTP_201_CREATED)
async def create_event_video(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
    request: CreateVideoEmbedRequest,
):
    """Add a video embed to an event."""
    await _get_owned_event(db, user, event_id)
    repo = await _get_media_repo(db)

    media = RideEventMedia(
        id=uuid4(),
        ride_event_id=event_id,
        media_type="video",
        storage_path=request.url,  # For videos, storage_path holds the embed URL
        caption=request.title,
        sort_order=request.sort_order,
    )

    saved = await repo.save(media)
    return serialize_media(saved)


@router.post("/entries/{entry_id}/videos", status_code=status.HTTP_201_CREATED)
async def create_entry_video(
    db: DbSession,
    user: CurrentUser,
    entry_id: UUID,
    request: CreateVideoEmbedRequest,
):
    """Add a video embed to a journal entry."""
    await _get_owned_entry(db, user, entry_id)
    repo = await _get_media_repo(db)

    media = RideEventMedia(
        id=uuid4(),
        journal_entry_id=entry_id,
        media_type="video",
        storage_path=request.url,  # For videos, storage_path holds the embed URL
        caption=request.title,
        sort_order=request.sort_order,
    )

    saved = await repo.save(media)
    return serialize_media(saved)


@router.delete("/{event_id}/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event_video(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
    video_id: UUID,
):
    """Delete a video embed from an event."""
    await _get_owned_event(db, user, event_id)
    repo = await _get_media_repo(db)

    media = await repo.get_by_id(video_id, user.id)
    if media is None or media.ride_event_id != event_id or media.media_type != "video":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    await repo.delete(video_id, user.id)


@router.delete("/entries/{entry_id}/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry_video(
    db: DbSession,
    user: CurrentUser,
    entry_id: UUID,
    video_id: UUID,
):
    """Delete a video embed from a journal entry."""
    await _get_owned_entry(db, user, entry_id)
    repo = await _get_media_repo(db)

    media = await repo.get_by_id(video_id, user.id)
    if media is None or media.journal_entry_id != entry_id or media.media_type != "video":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    await repo.delete(video_id, user.id)


# =============================================================================
# Activity Linking Endpoints
# =============================================================================


@router.post("/{event_id}/activities", status_code=status.HTTP_201_CREATED)
async def batch_link_activities(
    user: CurrentUser,
    event_id: UUID,
    request: BatchLinkActivitiesRequest,
    use_case: BatchLinkActivitiesD,
):
    """
    Batch link activities to an event.

    Activities are linked via a journal entry for the activity's date.
    If no journal entry exists for that date, one is auto-created.
    """
    try:
        result = await use_case.execute(user.id, event_id, request.activity_ids)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    return {
        "linked": [
            {
                "id": link.link_id,
                "journal_entry_id": str(link.journal_entry_id),
                "activity_id": str(link.activity_id),
                "sort_order": link.sort_order,
            }
            for link in result.linked
        ],
        "count": len(result.linked),
    }


@router.delete("/{event_id}/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_activity_from_event(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
    activity_id: UUID,
):
    """Unlink an activity from an event (removes from any journal entry)."""
    await _get_owned_event(db, user, event_id)
    activity_link_repo = await _get_activity_link_repo(db)

    # Find all links for this activity in this event
    links = await activity_link_repo.list_for_event(event_id)
    unlinked = False
    for link in links:
        if link.activity_id == activity_id:
            await activity_link_repo.unlink(link.journal_entry_id, activity_id)
            unlinked = True

    if not unlinked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not linked to this event")


@router.post("/entries/{entry_id}/activities", status_code=status.HTTP_201_CREATED)
async def link_activity(
    db: DbSession,
    user: CurrentUser,
    activity_repo: ActivityRepoD,
    entry_id: UUID,
    request: LinkActivityRequest,
):
    """Link an activity to a journal entry."""
    await _get_owned_entry(db, user, entry_id)

    # Verify user owns the activity
    activity = await activity_repo.get_by_id(request.activity_id, user.id)
    if activity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")

    repo = await _get_activity_link_repo(db)
    link = await repo.link(entry_id, request.activity_id, request.sort_order)
    return serialize_activity_link(link)


@router.delete("/entries/{entry_id}/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_activity(
    db: DbSession,
    user: CurrentUser,
    entry_id: UUID,
    activity_id: UUID,
):
    """Unlink an activity from a journal entry."""
    await _get_owned_entry(db, user, entry_id)

    repo = await _get_activity_link_repo(db)
    unlinked = await repo.unlink(entry_id, activity_id)
    if not unlinked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity link not found")


@router.put("/entries/{entry_id}/activities/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_activities(
    db: DbSession,
    user: CurrentUser,
    entry_id: UUID,
    request: ReorderActivitiesRequest,
):
    """Reorder activities in a journal entry."""
    await _get_owned_entry(db, user, entry_id)

    repo = await _get_activity_link_repo(db)
    await repo.reorder(entry_id, request.activity_ids)


# =============================================================================
# Activities Available for Linking
# =============================================================================


@router.get("/{event_id}/available-activities")
async def list_available_activities(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
    page: int = Query(DEFAULT_PAGE, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
):
    """
    List activities available to link to this event.

    Returns activities within the event's date range that aren't already
    linked to any journal entry in this event.
    """
    event = await _get_owned_event(db, user, event_id)

    # Get already-linked activity IDs
    activity_link_repo = await _get_activity_link_repo(db)
    linked = await activity_link_repo.list_for_event(event_id)
    linked_ids = {link.activity_id for link in linked}

    # Build query for activities in date range
    start = event.start_date
    end = event.end_date or event.start_date

    query = (
        select(Activity)
        .where(
            Activity.user_id == user.id,
            func.date(Activity.started_at) >= start,
            func.date(Activity.started_at) <= end,
        )
        .order_by(Activity.started_at.desc())
    )

    # Count total matching
    count_result = await db.execute(
        select(func.count(Activity.id)).where(
            Activity.user_id == user.id,
            func.date(Activity.started_at) >= start,
            func.date(Activity.started_at) <= end,
        )
    )
    total = count_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    result = await db.execute(query.offset(offset).limit(per_page))
    activities = result.scalars().all()

    # Mark which are already linked
    activities_data = []
    for a in activities:
        activities_data.append(
            {
                "id": str(a.id),
                "title": a.title,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "distance_km": round(a.total_distance_m / 1000, 1) if a.total_distance_m else None,
                "duration_seconds": a.moving_time_s,
                "is_linked": a.id in linked_ids,
            }
        )

    return {
        "activities": activities_data,
        "pagination": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 1,
        },
    }


# =============================================================================
# =============================================================================
# Photo Upload Endpoints
# =============================================================================


@router.post("/{event_id}/photos", status_code=status.HTTP_201_CREATED)
async def upload_event_photo(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
    request: Request,
    media_service: MediaServiceD,
    caption: str | None = Query(None, max_length=500),
):
    """Upload a photo to an event."""
    event = await _get_owned_event(db, user, event_id)

    content_type = request.headers.get("content-type", "")
    body = await request.body()

    try:
        result = media_service.save_photo(body, content_type, event_id)
    except MediaValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Create media record
    media = RideEventMedia(
        id=result.media_id,
        ride_event_id=event_id,
        media_type="photo",
        storage_path=result.storage_path,
        thumbnail_path=result.thumbnail_path,
        caption=caption,
        sort_order=0,
    )

    repo = await _get_media_repo(db)
    saved = await repo.save(media)

    # Auto-set as cover if event doesn't have one
    if event.cover_image_id is None:
        event.cover_image_id = saved.id
        event_repo = await _get_event_repo(db)
        await event_repo.save(event)

    return serialize_media(saved)


@router.post("/{event_id}/photos/batch", status_code=status.HTTP_201_CREATED)
async def upload_event_photos_batch(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
    media_service: MediaServiceD,
    files: list[UploadFile] = File(...),
):
    """Upload multiple photos to an event in a single request."""
    event = await _get_owned_event(db, user, event_id)

    # Read all files and prepare for batch processing
    file_data: list[tuple[bytes, str, str | None]] = []
    for file in files:
        body = await file.read()
        file_data.append((body, file.content_type or "", file.filename))

    # Save all photos
    result = media_service.save_photos_batch(file_data, event_id)

    # Create media records for successful uploads
    repo = await _get_media_repo(db)
    uploaded = []

    for idx, upload in enumerate(result.uploaded):
        media = RideEventMedia(
            id=upload.media_id,
            ride_event_id=event_id,
            media_type="photo",
            storage_path=upload.storage_path,
            thumbnail_path=upload.thumbnail_path,
            caption=None,
            sort_order=idx,
        )
        saved = await repo.save(media)
        uploaded.append(serialize_media(saved))

    # Auto-set first uploaded photo as cover if event doesn't have one
    if uploaded and event.cover_image_id is None:
        event.cover_image_id = UUID(uploaded[0]["id"])
        event_repo = await _get_event_repo(db)
        await event_repo.save(event)

    return {"uploaded": uploaded, "errors": result.errors, "count": len(uploaded)}


@router.post("/entries/{entry_id}/photos", status_code=status.HTTP_201_CREATED)
async def upload_entry_photo(
    db: DbSession,
    user: CurrentUser,
    entry_id: UUID,
    request: Request,
    media_service: MediaServiceD,
    caption: str | None = Query(None, max_length=500),
):
    """Upload a photo to a journal entry."""
    entry = await _get_owned_entry(db, user, entry_id)

    content_type = request.headers.get("content-type", "")
    body = await request.body()

    try:
        result = media_service.save_photo(body, content_type, entry.ride_event_id, is_entry=True)
    except MediaValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Create media record
    media = RideEventMedia(
        id=result.media_id,
        journal_entry_id=entry_id,
        media_type="photo",
        storage_path=result.storage_path,
        thumbnail_path=result.thumbnail_path,
        caption=caption,
        sort_order=0,
    )

    repo = await _get_media_repo(db)
    saved = await repo.save(media)
    return serialize_media(saved)


@router.post("/entries/{entry_id}/photos/batch", status_code=status.HTTP_201_CREATED)
async def upload_entry_photos_batch(
    db: DbSession,
    user: CurrentUser,
    entry_id: UUID,
    media_service: MediaServiceD,
    files: list[UploadFile] = File(...),
):
    """Upload multiple photos to a journal entry in a single request."""
    entry = await _get_owned_entry(db, user, entry_id)

    # Read all files and prepare for batch processing
    file_data: list[tuple[bytes, str, str | None]] = []
    for file in files:
        body = await file.read()
        file_data.append((body, file.content_type or "", file.filename))

    # Save all photos
    result = media_service.save_photos_batch(file_data, entry.ride_event_id, is_entry=True)

    # Create media records for successful uploads
    repo = await _get_media_repo(db)
    uploaded = []

    for idx, upload in enumerate(result.uploaded):
        media = RideEventMedia(
            id=upload.media_id,
            journal_entry_id=entry_id,
            media_type="photo",
            storage_path=upload.storage_path,
            thumbnail_path=upload.thumbnail_path,
            caption=None,
            sort_order=idx,
        )
        saved = await repo.save(media)
        uploaded.append(serialize_media(saved))

    return {"uploaded": uploaded, "errors": result.errors, "count": len(uploaded)}


@router.patch("/media/{media_id}")
async def update_media(
    db: DbSession,
    user: CurrentUser,
    media_id: UUID,
    caption: str | None = Query(None, max_length=500),
    sort_order: int | None = Query(None),
):
    """Update media metadata (caption, sort_order)."""
    repo = await _get_media_repo(db)
    media = await repo.get_by_id(media_id, user.id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    if caption is not None:
        media.caption = caption
    if sort_order is not None:
        media.sort_order = sort_order

    saved = await repo.save(media)
    return serialize_media(saved)


@router.delete("/media/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(
    db: DbSession,
    user: CurrentUser,
    media_id: UUID,
    media_service: MediaServiceD,
):
    """Delete a photo/media item."""
    repo = await _get_media_repo(db)
    media = await repo.get_by_id(media_id, user.id)
    if media is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

    # Delete files from disk
    media_service.delete_media_files(media.storage_path, media.thumbnail_path)

    # Delete record
    await repo.delete(media_id, user.id)


@router.post("/{event_id}/cover/{media_id}", status_code=status.HTTP_200_OK)
async def set_event_cover(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
    media_id: UUID,
):
    """Set a photo as the event cover image."""
    event = await _get_owned_event(db, user, event_id)

    # Verify media belongs to this event
    media_repo = await _get_media_repo(db)
    media = await media_repo.get_by_id(media_id, user.id)
    if media is None or media.ride_event_id != event_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Media not found or does not belong to this event",
        )

    event.cover_image_id = media_id
    event_repo = await _get_event_repo(db)
    saved = await event_repo.save(event)
    return serialize_event(saved)


@router.delete("/{event_id}/cover", status_code=status.HTTP_204_NO_CONTENT)
async def remove_event_cover(
    db: DbSession,
    user: CurrentUser,
    event_id: UUID,
):
    """Remove the event cover image."""
    event = await _get_owned_event(db, user, event_id)
    event.cover_image_id = None
    event_repo = await _get_event_repo(db)
    await event_repo.save(event)
