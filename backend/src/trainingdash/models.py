from datetime import datetime, date
from decimal import Decimal
from uuid import UUID, uuid4

from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Date,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from trainingdash.db import Base


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
    hr_derived_power_enabled: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class UserOAuthLink(Base):
    """Links users to OAuth provider accounts (GitHub, Google, etc.)."""
    __tablename__ = "user_oauth_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
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
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
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

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
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
    route_id: Mapped[int | None] = mapped_column(
        ForeignKey("routes.id"), nullable=True
    )
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
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
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
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "ftp_suggestion"
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON payload
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending/accepted/dismissed
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class AuditLog(Base):
    """Record of destructive admin actions (nuke operations)."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    admin_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # nuke_activities, nuke_integrations, nuke_account
    target_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Not FK, user may be deleted
    target_user_email: Mapped[str] = mapped_column(String(255), nullable=False)  # Preserved even if user deleted
    summary: Mapped[str] = mapped_column(Text, nullable=False)  # e.g., "347 activities, 52847 records"
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class EFModel(Base):
    """Efficiency Factor model for HR-derived power estimation."""
    __tablename__ = "ef_models"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    ef_value: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)  # NP/HR ratio
    computed_at: Mapped[datetime] = mapped_column(nullable=False)
    ride_count: Mapped[int] = mapped_column(Integer, nullable=False)  # Number of rides used
    confidence: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)  # 0.0-1.0


class XertCredentials(Base):
    __tablename__ = "xert_credentials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    xert_email: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sync_since: Mapped[datetime | None] = mapped_column(nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()")
    )


class GarminCredentials(Base):
    __tablename__ = "garmin_credentials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    garmin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sync_since: Mapped[datetime | None] = mapped_column(nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()")
    )


class ThresholdHistory(Base):
    """Tracks FTP, LTHR, and HRmax over time with effective dates."""
    __tablename__ = "threshold_history"
    __table_args__ = (
        UniqueConstraint("user_id", "effective_date", name="uq_threshold_user_date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    ftp_watts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lthr_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hrmax_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_auto_calculated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class PowerZone(Base):
    """Coggan 7-zone power zones based on FTP."""
    __tablename__ = "power_zones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    zone_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-7
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    min_watts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_watts: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = unlimited
    is_custom: Mapped[bool] = mapped_column(default=False)  # True if user customized


class HrZone(Base):
    """Friel 5-zone HR zones based on LTHR."""
    __tablename__ = "hr_zones"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    zone_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    min_bpm: Mapped[int] = mapped_column(Integer, nullable=False)
    max_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = unlimited
    is_custom: Mapped[bool] = mapped_column(default=False)  # True if user customized


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
    geom: Mapped[object | None] = mapped_column(
        Geography("POINT", srid=4326, spatial_index=True), nullable=True
    )