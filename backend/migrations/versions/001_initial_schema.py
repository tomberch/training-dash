"""Initial schema - all tables.

Revision ID: 001_initial
Revises: None
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geography

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable PostGIS
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_path", sa.String(500), nullable=True),
        sa.Column("is_admin", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_approved", sa.Boolean(), default=True, nullable=False),
        sa.Column("unit_system", sa.String(10), default="metric", nullable=False),
        sa.Column("sync_hour", sa.Integer(), default=3, nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("weight_kg", sa.Numeric(5, 2), nullable=True),
        sa.Column("height_cm", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("power_zone_percentages", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("hr_zone_percentages", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("hr_derived_power_enabled", sa.Boolean(), default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # user_oauth_links
    op.create_table(
        "user_oauth_links",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_user_id", sa.String(255), nullable=False),
        sa.Column("provider_email", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
    )

    # app_settings
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # activities (created before routes due to FK from routes)
    op.create_table(
        "activities",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("total_distance_m", sa.Float(), nullable=False, default=0),
        sa.Column("moving_time_s", sa.Integer(), nullable=False, default=0),
        sa.Column("elapsed_time_s", sa.Integer(), nullable=False, default=0),
        sa.Column("elevation_gain_m", sa.Float(), nullable=False, default=0),
        sa.Column("avg_speed_mps", sa.Float(), nullable=False, default=0),
        sa.Column("avg_hr_bpm", sa.Integer(), nullable=True),
        sa.Column("avg_power_w", sa.Integer(), nullable=True),
        sa.Column("np_power_w", sa.Integer(), nullable=True),
        sa.Column("power_source", sa.String(20), nullable=True),
        sa.Column("power_confidence", sa.Float(), nullable=True),
        sa.Column("max_speed_mps", sa.Float(), nullable=False, default=0),
        sa.Column("max_hr_bpm", sa.Integer(), nullable=True),
        sa.Column("intensity_factor", sa.Float(), nullable=True),
        sa.Column("tss", sa.Float(), nullable=True),
        sa.Column("training_load", sa.Float(), nullable=True),
        sa.Column("power_zone_times", sa.Text(), nullable=True),
        sa.Column("hr_zone_times", sa.Text(), nullable=True),
        sa.Column("wbal_min_joules", sa.Integer(), nullable=True),
        sa.Column("wbal_min_pct", sa.Float(), nullable=True),
        sa.Column("is_breakthrough", sa.Boolean(), default=False, nullable=False),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("title_source", sa.String(20), server_default="auto", nullable=False),
        sa.Column("map_polyline", sa.Text(), nullable=True),
        sa.Column("route_id", sa.BigInteger(), nullable=True),  # FK added after routes table
        sa.Column("direction_bearing", sa.SmallInteger(), nullable=True),
        sa.Column("raw_fit", sa.LargeBinary(), nullable=True),
        sa.Column("utc_offset_minutes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_activities_user_started", "activities", ["user_id", "started_at"])
    op.create_index(
        "ix_activities_route_bearing",
        "activities",
        ["route_id", "direction_bearing"],
        postgresql_where=sa.text("route_id IS NOT NULL"),
    )

    # routes
    op.create_table(
        "routes",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("simplified_polyline", Geography("LINESTRING", srid=4326, spatial_index=True), nullable=False),
        sa.Column(
            "first_seen_activity_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ride_count", sa.Integer(), nullable=False, default=1),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # Add FK from activities to routes
    op.create_foreign_key("fk_activities_route_id", "activities", "routes", ["route_id"], ["id"])

    # laps
    op.create_table(
        "laps",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "activity_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("lap_index", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("total_distance_m", sa.Float(), nullable=False, default=0),
        sa.Column("avg_hr_bpm", sa.Integer(), nullable=True),
        sa.Column("avg_power_w", sa.Integer(), nullable=True),
        sa.Column("max_hr_bpm", sa.Integer(), nullable=True),
    )

    # activity_peak_powers
    op.create_table(
        "activity_peak_powers",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "activity_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("watts", sa.Integer(), nullable=False),
    )

    # fitness_history
    op.create_table(
        "fitness_history",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("pp_watts", sa.Integer(), nullable=False),
        sa.Column("w_prime_joules", sa.Integer(), nullable=False),
        sa.Column("cp_watts", sa.Integer(), nullable=False),
    )

    # notifications
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("admin_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("target_user_id", sa.Integer(), nullable=True),
        sa.Column("target_user_email", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # ef_models
    op.create_table(
        "ef_models",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
        ),
        sa.Column("ef_value", sa.Numeric(6, 4), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.Column("ride_count", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
    )

    # xert_credentials
    op.create_table(
        "xert_credentials",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
        ),
        sa.Column("xert_email", sa.String(255), nullable=False),
        sa.Column("encrypted_password", sa.LargeBinary(), nullable=False),
        sa.Column("sync_since", sa.DateTime(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # garmin_credentials
    op.create_table(
        "garmin_credentials",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
        ),
        sa.Column("garmin_email", sa.String(255), nullable=False),
        sa.Column("encrypted_password", sa.LargeBinary(), nullable=False),
        sa.Column("sync_since", sa.DateTime(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    # metric_types
    op.create_table(
        "metric_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(50), unique=True, nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("data_type", sa.String(20), nullable=False),
        sa.Column("min_value", sa.Numeric(), nullable=True),
        sa.Column("max_value", sa.Numeric(), nullable=True),
        sa.Column("allowed_sources", sa.dialects.postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("recalc_targets", sa.dialects.postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )

    # Seed metric types
    op.execute("""
        INSERT INTO metric_types (id, key, display_name, unit, category, data_type, min_value, max_value, allowed_sources, recalc_targets, sort_order)
        VALUES
            (1, 'ftp', 'FTP', 'W', 'threshold', 'integer', 50, 500, ARRAY['manual', 'calculated'], ARRAY['power_zones', 'tss'], 1),
            (2, 'lthr', 'LTHR', 'bpm', 'threshold', 'integer', 100, 220, ARRAY['manual', 'calculated'], ARRAY['hr_zones'], 2),
            (3, 'hrmax', 'Max HR', 'bpm', 'threshold', 'integer', 120, 250, ARRAY['manual', 'calculated', 'device'], ARRAY['hr_zones'], 3),
            (4, 'weight', 'Weight', 'kg', 'body', 'decimal', 30, 200, ARRAY['manual', 'device'], NULL, 10),
            (5, 'restinghr', 'Resting HR', 'bpm', 'body', 'integer', 30, 100, ARRAY['manual', 'device'], NULL, 11)
    """)

    # metric_entries
    op.create_table(
        "metric_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("metric_type_id", sa.Integer(), sa.ForeignKey("metric_types.id"), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("source_detail", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "metric_type_id", "effective_date", name="uq_metric_user_type_date"),
    )

    # records
    op.create_table(
        "records",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "activity_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("distance_m", sa.Float(), nullable=False, default=0),
        sa.Column("hr_bpm", sa.Integer(), nullable=True),
        sa.Column("power_w", sa.Integer(), nullable=True),
        sa.Column("speed_mps", sa.Float(), nullable=True),
        sa.Column("altitude_m", sa.Float(), nullable=True),
        sa.Column("cadence_rpm", sa.Integer(), nullable=True),
        sa.Column("geom", Geography("POINT", srid=4326, spatial_index=True), nullable=True),
    )
    op.create_index("ix_records_activity_id", "records", ["activity_id"])

    # recalculation_jobs
    op.create_table(
        "recalculation_jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, default="pending"),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("activities_updated", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.UniqueConstraint("user_id", name="uq_recalculation_job_user"),
    )

    # geocoding_cache
    op.create_table(
        "geocoding_cache",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("city", sa.String(255), nullable=True),
        sa.Column("region", sa.String(255), nullable=True),
        sa.Column("country", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_geocoding_cache_coords", "geocoding_cache", ["lat", "lon"])


def downgrade() -> None:
    op.drop_table("geocoding_cache")
    op.drop_table("recalculation_jobs")
    op.drop_table("records")
    op.drop_table("metric_entries")
    op.drop_table("metric_types")
    op.drop_table("garmin_credentials")
    op.drop_table("xert_credentials")
    op.drop_table("ef_models")
    op.drop_table("audit_log")
    op.drop_table("notifications")
    op.drop_table("fitness_history")
    op.drop_table("activity_peak_powers")
    op.drop_table("laps")
    op.drop_foreign_key("fk_activities_route_id", "activities")
    op.drop_table("routes")
    op.drop_table("activities")
    op.drop_table("app_settings")
    op.drop_table("user_oauth_links")
    op.drop_table("users")
