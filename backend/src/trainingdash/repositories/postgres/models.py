from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from trainingdash.repositories.postgres.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_approved: Mapped[bool] = mapped_column(default=True)
    unit_system: Mapped[str] = mapped_column(String(10), default="metric", nullable=False)
    sync_hour: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)  # male | female | null
    power_zone_percentages = mapped_column(JSONB, nullable=True)  # custom zone % overrides
    hr_zone_percentages = mapped_column(JSONB, nullable=True)  # custom zone % overrides
    hr_derived_power_enabled: Mapped[bool] = mapped_column(default=False)
    map_tile_style: Mapped[str] = mapped_column(String(20), default="osm", nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class UserOAuthLink(Base):
    """Links users to OAuth provider accounts (GitHub, Google, etc.)."""

    __tablename__ = "user_oauth_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # 'github', 'google'
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    __table_args__ = (
        # One link per provider account globally (prevents same OAuth account linking to multiple users)
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    )


class AppSettings(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))

    def as_bool(self, default: bool = False) -> bool:
        """Parse the setting value as a boolean."""
        if self.value is None:
            return default
        return self.value.lower() in ("true", "1", "yes", "on")

    @staticmethod
    def bool_to_str(value: bool) -> str:
        """Convert a boolean to the canonical string representation."""
        return "true" if value else "false"


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    simplified_polyline: Mapped[object] = mapped_column(
        Geography("LINESTRING", srid=4326, spatial_index=True), nullable=False
    )
    first_seen_activity_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
    )
    ride_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    total_distance_m: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    moving_time_s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    elapsed_time_s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    elevation_gain_m: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    avg_speed_mps: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    avg_hr_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_power_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    np_power_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    power_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "measured" or "hr_derived"
    power_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0 for hr_derived
    max_speed_mps: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    max_hr_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Training metrics
    intensity_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    tss: Mapped[float | None] = mapped_column(Float, nullable=True)
    training_load: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Zone time distribution (JSON: {zone_number: seconds})
    power_zone_times: Mapped[str | None] = mapped_column(Text, nullable=True)
    hr_zone_times: Mapped[str | None] = mapped_column(Text, nullable=True)
    # W'bal metrics
    wbal_min_joules: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wbal_min_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Breakthrough detection
    is_breakthrough: Mapped[bool] = mapped_column(default=False)
    # Activity title
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Title source: 'auto' (geocoded), 'manual' (user edited), 'pending' (bulk import, awaiting geocoding)
    title_source: Mapped[str] = mapped_column(String(20), server_default="auto", nullable=False)
    # Simplified GPS polyline for list view thumbnails (Google polyline encoding)
    map_polyline: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Routing
    route_id: Mapped[int | None] = mapped_column(ForeignKey("routes.id"), nullable=True)
    # Event association (one event per activity)
    ride_event_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("ride_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Direction bearing for same-route comparison (0-359 degrees, from start to 25% point)
    direction_bearing: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    # Direction bearing at 75% for detecting opposite-direction loops
    direction_bearing_75: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    raw_fit: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    utc_offset_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Lap(Base):
    __tablename__ = "laps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    lap_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[datetime] = mapped_column(nullable=False)
    total_distance_m: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    avg_hr_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_power_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_hr_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ActivityPeakPower(Base):
    """Peak power values at standard durations for an activity."""

    __tablename__ = "activity_peak_powers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    watts: Mapped[int] = mapped_column(Integer, nullable=False)


class FitnessHistory(Base):
    """User fitness model snapshots over time (3-parameter CP model)."""

    __tablename__ = "fitness_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(nullable=False)
    # Peak Power (neuromuscular, ~5s)
    pp_watts: Mapped[int] = mapped_column(Integer, nullable=False)
    # Anaerobic Work Capacity (W')
    w_prime_joules: Mapped[int] = mapped_column(Integer, nullable=False)
    # Critical Power (sustainable threshold)
    cp_watts: Mapped[int] = mapped_column(Integer, nullable=False)


class Notification(Base):
    """User notifications (FTP suggestions, etc.)."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "ftp_suggestion"
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON payload
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending/accepted/dismissed
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class AuditLog(Base):
    """Record of destructive admin actions (nuke operations)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # nuke_activities, nuke_integrations, nuke_account
    target_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Not FK, user may be deleted
    target_user_email: Mapped[str] = mapped_column(String(255), nullable=False)  # Preserved even if user deleted
    summary: Mapped[str] = mapped_column(Text, nullable=False)  # e.g., "347 activities, 52847 records"
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class EFModel(Base):
    """Efficiency Factor model for HR-derived power estimation."""

    __tablename__ = "ef_models"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    ef_value: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)  # NP/HR ratio
    computed_at: Mapped[datetime] = mapped_column(nullable=False)
    ride_count: Mapped[int] = mapped_column(Integer, nullable=False)  # Number of rides used
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)  # 0.0-1.0


class XertCredentials(Base):
    __tablename__ = "xert_credentials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    xert_email: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sync_since: Mapped[datetime | None] = mapped_column(nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), onupdate=text("now()"))


class GarminCredentials(Base):
    __tablename__ = "garmin_credentials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    garmin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sync_since: Mapped[datetime | None] = mapped_column(nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), onupdate=text("now()"))


class MetricType(Base):
    """Defines available metric types (FTP, LTHR, weight, etc.)."""

    __tablename__ = "metric_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # threshold | body | fitness | recovery
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)  # integer | decimal
    min_value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    max_value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    allowed_sources = mapped_column(ARRAY(Text), nullable=True)  # e.g. ["manual", "calculated", "device"]
    recalc_targets = mapped_column(ARRAY(Text), nullable=True)  # e.g. ["power_zones", "tss"]
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")


class MetricEntry(Base):
    """Historical metric values for a user (FTP on date X, weight on date Y, etc.)."""

    __tablename__ = "metric_entries"
    __table_args__ = (UniqueConstraint("user_id", "metric_type_id", "effective_date", name="uq_metric_user_type_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    metric_type_id: Mapped[int] = mapped_column(ForeignKey("metric_types.id"), nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # manual | calculated | device
    source_detail: Mapped[str | None] = mapped_column(String(50), nullable=True)  # ramp_test, garmin_sync, etc.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Record(Base):
    __tablename__ = "records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(nullable=False)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_m: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    hr_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    power_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)
    altitude_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    cadence_rpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geom: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326, spatial_index=True), nullable=True)


class RecalculationJob(Base):
    """Tracks the status of an async metric recalculation job.

    One row per user — upserted on each run. Status transitions:
    pending → running → completed | failed.
    """

    __tablename__ = "recalculation_jobs"
    __table_args__ = (UniqueConstraint("user_id", name="uq_recalculation_job_user"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    started_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    activities_updated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class Event(Base):
    """System event log entry for the Admin System Dashboard.

    Events capture activity lifecycle, sync operations, job outcomes, etc.
    for observability and debugging.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    outcome: Mapped[str] = mapped_column(String(10), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)


class CacheStats(Base):
    """Hourly cache hit/miss statistics for the Admin System Dashboard.

    Aggregates cache performance metrics in hourly buckets per cache type
    (tiles_osm, tiles_carto, geocoding).
    """

    __tablename__ = "cache_stats"
    __table_args__ = (UniqueConstraint("bucket_start", "cache_type", name="uq_cache_stats_bucket_type"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    bucket_start: Mapped[datetime] = mapped_column(nullable=False)
    cache_type: Mapped[str] = mapped_column(String(20), nullable=False)
    hits: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    misses: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class SavedFilter(Base):
    """User-saved query filters for reuse across sessions.

    Stores the raw DSL query text. Query is validated on save and on load
    (since field availability may change). Return type is inferred from
    query structure (list vs aggregation).
    """

    __tablename__ = "saved_filters"
    __table_args__ = (
        # Each user can have unique filter names
        UniqueConstraint("user_id", "name", name="uq_saved_filter_user_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), onupdate=text("now()"))


# =============================================================================
# Events Feature Models
# =============================================================================


class RideEvent(Base):
    """A user-curated event grouping related activities (races, tours, trips).

    Events can span single or multiple days and contain journal entries,
    media (photos/videos), and links. Activities can be linked at the event
    level or to specific journal entries.
    """

    __tablename__ = "ride_events"

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # Markdown
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # race, tour, bikepacking, event, other
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)  # Same as start for single-day
    cover_image_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("ride_event_media.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), onupdate=text("now()"))

    __table_args__ = (
        # Index for listing events by date
        {"schema": None},  # default schema
    )


class JournalEntry(Base):
    """Day-by-day journal entry for a multi-day event.

    Each entry has a date (unique within event), optional description,
    and can have activities, media, and links attached.
    """

    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("ride_event_id", "entry_date", name="uq_journal_entry_event_date"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    ride_event_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("ride_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # Markdown
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), onupdate=text("now()"))


class JournalEntryActivity(Base):
    """Join table linking activities to journal entries.

    An activity can be linked to at most one journal entry. Linking to
    a journal entry implicitly links to the parent event.
    """

    __tablename__ = "journal_entry_activities"
    __table_args__ = (
        UniqueConstraint("journal_entry_id", "activity_id", name="uq_journal_entry_activity"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    journal_entry_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    activity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RideEventMedia(Base):
    """Photos and video embeds attached to events or journal entries.

    Media can be attached to either an event (event-level) or a journal
    entry (entry-level), but not both. This is enforced by a CHECK constraint.
    """

    __tablename__ = "ride_event_media"
    __table_args__ = (
        # Exactly one of ride_event_id or journal_entry_id must be set
        {"schema": None},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    ride_event_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("ride_events.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    journal_entry_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    media_type: Mapped[str] = mapped_column(String(20), nullable=False)  # photo, youtube, vimeo
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # For photos
    thumbnail_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # For photo thumbnails
    external_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # For youtube/vimeo
    caption: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class RideEventLink(Base):
    """External links attached to events or journal entries.

    Links can be attached to either an event (event-level) or a journal
    entry (entry-level), but not both. This is enforced by a CHECK constraint.
    """

    __tablename__ = "ride_event_links"
    __table_args__ = (
        # Exactly one of ride_event_id or journal_entry_id must be set
        {"schema": None},
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    ride_event_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("ride_events.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    journal_entry_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("journal_entries.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_type: Mapped[str] = mapped_column(String(20), nullable=False)  # route, place, article, video, gear, other
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
