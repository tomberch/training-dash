from datetime import datetime, date
from decimal import Decimal

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
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from trainingdash.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False)
    unit_system: Mapped[str] = mapped_column(String(10), default="metric", nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    simplified_polyline: Mapped[object] = mapped_column(
        Geography("LINESTRING", srid=4326, spatial_index=True), nullable=False
    )
    first_seen_activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id"), nullable=False
    )
    ride_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
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
    # Routing
    route_id: Mapped[int | None] = mapped_column(
        ForeignKey("routes.id"), nullable=True
    )
    raw_fit: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class Lap(Base):
    __tablename__ = "laps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    lap_index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[datetime] = mapped_column(nullable=False)
    total_distance_m: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    avg_hr_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_power_w: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_hr_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)


class XertCredentials(Base):
    __tablename__ = "xert_credentials"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    xert_email: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_password: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sync_since: Mapped[datetime | None] = mapped_column(nullable=True)
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
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()")
    )


class ThresholdHistory(Base):
    """Tracks FTP, LTHR, and HRmax over time with effective dates."""
    __tablename__ = "threshold_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    ftp_watts: Mapped[int] = mapped_column(Integer, nullable=False)
    lthr_bpm: Mapped[int] = mapped_column(Integer, nullable=False)
    hrmax_bpm: Mapped[int] = mapped_column(Integer, nullable=False)
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
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
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