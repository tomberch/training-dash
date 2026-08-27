from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import sqlalchemy as sa
from geoalchemy2 import Geography, Geometry
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class Bike(Base):
    """User bike/equipment for CdA/Crr calibration and race planning."""

    __tablename__ = "bikes"
    __table_args__ = (
        sa.CheckConstraint(
            "bike_type IN ('road', 'gravel', 'mtb', 'tt', 'track', 'cx', 'commuter', 'ebike', 'other')",
            name="valid_bike_type",
        ),
        sa.CheckConstraint(
            "cda_source IN ('default', 'manual', 'calibrated') OR cda_source IS NULL",
            name="valid_cda_source",
        ),
        sa.CheckConstraint(
            "crr_source IN ('default', 'manual', 'calibrated') OR crr_source IS NULL",
            name="valid_crr_source",
        ),
        sa.Index(
            "idx_bikes_default",
            "user_id",
            unique=True,
            postgresql_where=sa.text("is_default = TRUE AND retired_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    bike_type: Mapped[str] = mapped_column(String(20), nullable=False)  # road, tt, gravel, mtb, ebike
    model_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    total_distance_m: Mapped[float] = mapped_column(Float, nullable=False, server_default=text("0"))
    cda: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)  # CdA in m²
    crr: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)  # Rolling resistance coefficient
    cda_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # default, manual, calibrated
    crr_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # default, manual, calibrated
    calibrated_at: Mapped[datetime | None] = mapped_column(nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    retired_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Aggregate CdA/Crr statistics from activities (confidence-weighted)
    estimated_cda_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_crr_avg: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_cda_stddev: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_crr_stddev: Mapped[float | None] = mapped_column(Float, nullable=True)
    aero_sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))


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
    # Time metrics: moving < timer < elapsed
    moving_time_s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timer_time_s: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Time with timer running
    elapsed_time_s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Elevation metrics
    elevation_gain_m: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    elevation_loss_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_altitude_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_altitude_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_grade_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Speed metrics
    avg_speed_mps: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    avg_speed_moving_mps: Mapped[float | None] = mapped_column(Float, nullable=True)  # distance / moving_time
    max_speed_mps: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    # Heart rate metrics
    avg_hr_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_hr_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Power metrics
    avg_power_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_power_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    np_power_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    power_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "measured" or "hr_derived"
    power_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0 for hr_derived
    # Cadence metrics
    avg_cadence_rpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_cadence_pedaling_rpm: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Only when cadence > 0
    max_cadence_rpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Temperature metrics
    avg_temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_temperature_c: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_temperature_c: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    # Activity type: road, gravel, mtb, virtual, indoor, commute, other (null = unclassified legacy)
    activity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Bike used for this activity (for CdA/Crr calibration and tracking)
    bike_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("bikes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    bike: Mapped["Bike | None"] = relationship("Bike", lazy="joined")
    # CdA/Crr estimation (from wind-corrected regression)
    estimated_cda: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_crr: Mapped[float | None] = mapped_column(Float, nullable=True)
    aero_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Weather fetch status: pending, fetched, failed, not_applicable
    weather_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
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
    vi_value: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=1.25)  # NP/avg ratio
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
    temperature_c: Mapped[int | None] = mapped_column(Integer, nullable=True)
    geom: Mapped[object | None] = mapped_column(Geography("POINT", srid=4326, spatial_index=True), nullable=True)


class ActivityWeather(Base):
    """Hourly weather snapshots during an activity.

    Stores weather conditions at hourly intervals for wind-corrected
    CdA/Crr estimation. Data fetched from Open-Meteo historical API.
    """

    __tablename__ = "activity_weather"
    __table_args__ = (UniqueConstraint("activity_id", "hour_offset", name="uq_activity_weather_hour"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hour_offset: Mapped[int] = mapped_column(Integer, nullable=False)  # Hours from activity start
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)  # Sample point latitude
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)  # Sample point longitude
    temperature_c: Mapped[float] = mapped_column(Float, nullable=False)
    wind_speed_mps: Mapped[float] = mapped_column(Float, nullable=False)
    wind_direction_deg: Mapped[float] = mapped_column(Float, nullable=False)  # Meteorological (FROM)
    pressure_hpa: Mapped[float] = mapped_column(Float, nullable=False)
    humidity_pct: Mapped[float] = mapped_column(Float, nullable=False)
    air_density: Mapped[float] = mapped_column(Float, nullable=False)  # Pre-calculated kg/m³


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
    __table_args__ = (UniqueConstraint("ride_event_id", "entry_date", name="uq_journal_entry_event_date"),)

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
    __table_args__ = (UniqueConstraint("journal_entry_id", "activity_id", name="uq_journal_entry_activity"),)

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


# =============================================================================
# Race Planner Models
# =============================================================================


class RaceCourse(Base):
    """A race course with elevation profile and segments for pacing optimization.

    Courses can be imported from GPX files, FIT files, or created manually.
    The geometry stores the full 3D linestring (lat, lon, elevation).
    Processed data (elevation_profile, segments, climbs) is stored as JSONB
    for flexible querying and efficient retrieval.
    """

    __tablename__ = "race_courses"
    __table_args__ = (
        sa.CheckConstraint(
            "source_type IN ('gpx', 'fit', 'manual', 'activity')",
            name="valid_source_type",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # gpx, fit, manual, activity
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Course metrics
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_gain_m: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_loss_m: Mapped[float] = mapped_column(Float, nullable=False)
    min_elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_elevation_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Geometry (PostGIS) - LineStringZ includes elevation
    geometry: Mapped[object] = mapped_column(Geometry("LINESTRINGZ", srid=4326, spatial_index=True), nullable=False)

    # Processed data (JSONB)
    # elevation_profile: [{distance_m, elevation_m, grade_pct}, ...]
    elevation_profile: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # segments: [{start_m, end_m, avg_grade_pct, distance_m, min_elevation_m, max_elevation_m}, ...]
    segments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # climbs: [{name, start_m, end_m, distance_m, avg_grade_pct, elevation_gain_m, category}, ...]
    climbs: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="select")


class RacePlan(Base):
    """A generated race plan with power targets for each course segment.

    Plans store the rider and bike parameters used at generation time,
    along with optimization settings and results. Segment targets are
    stored as JSONB for flexible retrieval.
    """

    __tablename__ = "race_plans"
    __table_args__ = (
        sa.CheckConstraint(
            "optimization_method IN ('heuristic', 'optimized', 'time_targeted') OR optimization_method IS NULL",
            name="valid_optimization_method",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("race_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bike_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("bikes.id", ondelete="SET NULL"), nullable=True)

    # Plan metadata
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    # Rider parameters used
    rider_weight_kg: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    ftp_watts: Mapped[int] = mapped_column(Integer, nullable=False)
    cp_watts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    w_prime_joules: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Bike parameters used
    bike_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    cda: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    crr: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)

    # Plan configuration
    target_intensity: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)  # e.g., 0.85 for 85% IF
    optimization_method: Mapped[str | None] = mapped_column(String(20), nullable=True)  # heuristic, optimized
    max_descent_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)  # Cap descent speed
    
    # Ride type configuration
    ride_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # race, gran_fondo, training, touring, custom
    descent_aggressiveness: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100
    stop_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-50

    # Results
    total_time_s: Mapped[float] = mapped_column(Float, nullable=False)
    total_distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    avg_power_w: Mapped[float] = mapped_column(Float, nullable=False)
    normalized_power_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    intensity_factor: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)

    # Segment targets (JSONB)
    # [{segment_idx, power_w, time_s, speed_mps}, ...]
    segment_targets: Mapped[list] = mapped_column(JSONB, nullable=False)

    # W'bal prediction
    wbal_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    wbal_min_distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Weather/conditions for race day
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # Event date
    target_conditions: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # {temp_c, pressure_hpa, humidity_pct, wind_speed_mps, wind_direction_deg, air_density}
    conditions_fetched_at: Mapped[datetime | None] = mapped_column(nullable=True)  # When forecast was last fetched
    wind_override_speed_mps: Mapped[float | None] = mapped_column(Float, nullable=True)  # Manual wind override
    wind_override_direction_deg: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", lazy="select")
    course: Mapped["RaceCourse"] = relationship("RaceCourse", lazy="select")
    bike: Mapped["Bike | None"] = relationship("Bike", lazy="select")


# =============================================================================
# Backup Models
# =============================================================================


class BackupConfig(Base):
    """Singleton configuration for restic backups.

    Only one row (id=1) is allowed, enforced by a CHECK constraint.
    Stores encrypted restic repository password and retention settings.
    """

    __tablename__ = "backup_config"
    __table_args__ = (sa.CheckConstraint("id = 1", name="backup_config_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    repository_path: Mapped[str] = mapped_column(String(500), nullable=False, server_default="/backups")
    encrypted_password: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # Schedule: hour of day (0-23) like sync_hour, null = manual only
    schedule_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Retention policy
    retention_keep_daily: Mapped[int] = mapped_column(Integer, nullable=False, server_default="7")
    retention_keep_weekly: Mapped[int] = mapped_column(Integer, nullable=False, server_default="4")
    retention_keep_monthly: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    # Options
    exclude_raw_fit: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class BackupHistory(Base):
    """Log of backup operations with metadata from restic.

    Records both successful and failed backup attempts, including
    statistics from restic's JSON output for completed backups.
    """

    __tablename__ = "backup_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Restic snapshot ID (short form, e.g. "a1b2c3d4")
    snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Trigger type: scheduled, manual
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Status: running, completed, failed
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Timing
    started_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Backup metadata (from restic JSON output)
    files_new: Mapped[int | None] = mapped_column(Integer, nullable=True)
    files_changed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    files_unmodified: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bytes_added: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bytes_total: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Database metadata
    db_migration_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Error info
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class PacingCoefficients(Base):
    """Personalized pacing model coefficients per user/bike.

    Stores coefficients learned from actual ride data to enable
    personalized power and speed predictions. Each user can have:
    - One user-default row (bike_id=NULL) that applies to all bikes
    - Additional bike-specific rows that override the default

    Fallback chain: bike-specific → user default → global defaults
    """

    __tablename__ = "pacing_coefficients"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "bike_id", name="uq_pacing_coefficients_user_bike"),
        sa.Index(
            "ix_pacing_coefficients_user_default",
            "user_id",
            unique=True,
            postgresql_where=sa.text("bike_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    bike_id: Mapped[int | None] = mapped_column(
        ForeignKey("bikes.id", ondelete="CASCADE"),
        nullable=True,
        comment="NULL = user default (applies to all bikes without specific coefficients)",
    )

    # Climb coefficients
    grade_power_intercept: Mapped[Decimal] = mapped_column(
        Numeric(4, 3),
        nullable=False,
        server_default=text("1.100"),
        comment="Base power multiplier at 0% grade",
    )
    grade_power_slope: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False,
        server_default=text("0.0350"),
        comment="Power multiplier increase per 1% grade",
    )

    # Descent coefficients
    max_descent_speed_mps: Mapped[Decimal] = mapped_column(
        Numeric(4, 1),
        nullable=False,
        server_default=text("18.0"),
        comment="Absolute speed limit on descents (m/s)",
    )
    descent_power_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        nullable=False,
        server_default=text("0.50"),
        comment="Power multiplier on descents (grade < -3%)",
    )
    curvature_speed_coefficient: Mapped[Decimal] = mapped_column(
        Numeric(6, 1),
        nullable=False,
        server_default=text("-68.0"),
        comment="Speed reduction per unit curvature (m/s per 1/m)",
    )

    # Learning metadata
    climb_sample_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Number of climb data points used for regression",
    )
    descent_sample_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Number of descent data points used for regression",
    )
    activity_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
        comment="Number of activities contributing to coefficients",
    )
    last_calibrated_at: Mapped[datetime | None] = mapped_column(
        nullable=True,
        comment="When coefficients were last updated",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))



# =============================================================================
# Segment System Models
# =============================================================================


class Segment(Base):
    """Global segment definition (climb, sprint, or custom).

    Segments are shared across all users. A segment can be:
    - 'suggested': Auto-detected, awaiting user approval
    - 'approved': Confirmed by a user, visible to all

    Soft-deleted via deleted_at timestamp.
    """

    __tablename__ = "segments"
    __table_args__ = (
        sa.CheckConstraint("type IN ('climb', 'sprint', 'custom')", name="segments_valid_type"),
        sa.CheckConstraint("status IN ('suggested', 'approved')", name="segments_valid_status"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # climb, sprint, custom
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="suggested")
    climb_category: Mapped[str | None] = mapped_column(String(10), nullable=True)  # hc, 1, 2, 3, 4, nc

    # Geometry
    polyline: Mapped[str] = mapped_column(Text, nullable=False)  # Encoded polyline
    start_point: Mapped[object] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    end_point: Mapped[object] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    bounds: Mapped[object] = mapped_column(Geometry("POLYGON", srid=4326), nullable=False)
    direction_bearing: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0-360 degrees

    # Metrics
    distance_m: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_gain_m: Mapped[float] = mapped_column(Float, nullable=False)
    avg_grade_pct: Mapped[float] = mapped_column(Float, nullable=False)
    max_grade_pct: Mapped[float] = mapped_column(Float, nullable=False)
    gradient_segments = mapped_column(JSONB, nullable=False)  # [{distance_m, grade_pct}, ...]

    # Denormalized counts (updated by triggers or application code)
    effort_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    athlete_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # Ownership & tracking
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source_activity_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("activities.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)  # Soft delete
    matching_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class SegmentEffort(Base):
    """A user's effort on a segment during an activity.

    Tracks elapsed time, power, HR, and PR status.
    start_index/end_index refer to the record indices in the activity.
    """

    __tablename__ = "segment_efforts"
    __table_args__ = (
        UniqueConstraint("segment_id", "activity_id", "start_index", name="uq_segment_effort_unique"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    segment_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("segments.id", ondelete="CASCADE"), nullable=False
    )
    activity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    started_at: Mapped[datetime] = mapped_column(nullable=False)
    elapsed_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    moving_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_power_watts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_hr_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    start_index: Mapped[int] = mapped_column(Integer, nullable=False)
    end_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_pr: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    # Relationships
    segment: Mapped["Segment"] = relationship("Segment", lazy="joined")
    activity: Mapped["Activity"] = relationship("Activity", lazy="select")


class SegmentSuggestion(Base):
    """Per-user segment suggestion with repetition tracking.

    When a user rides a suggested segment multiple times, the repetition_count
    increases and expires_at is extended (90 days from last ride).
    Users can dismiss suggestions they don't want to see.
    """

    __tablename__ = "segment_suggestions"
    __table_args__ = (
        UniqueConstraint("segment_id", "user_id", name="uq_segment_suggestion_user"),
    )

    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid4)
    segment_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("segments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    repetition_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    first_ridden_at: Mapped[datetime] = mapped_column(nullable=False)
    last_ridden_at: Mapped[datetime] = mapped_column(nullable=False)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    dismissed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=text("now()"))

    # Relationships
    segment: Mapped["Segment"] = relationship("Segment", lazy="joined")
