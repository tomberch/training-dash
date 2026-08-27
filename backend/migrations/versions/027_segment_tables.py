"""Add segment system tables.

Creates tables for:
- segments: global segment definitions (climbs, sprints, custom)
- segment_efforts: user efforts on segments (times, power, PR tracking)
- segment_suggestions: per-user suggestions with repetition tracking

Revision ID: 027
Revises: 026
Create Date: 2026-08-27

"""

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Segments table
    op.create_table(
        "segments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),  # climb, sprint, custom
        sa.Column("status", sa.String(20), nullable=False, server_default="suggested"),  # suggested, approved
        sa.Column("climb_category", sa.String(10), nullable=True),  # hc, 1, 2, 3, 4, nc
        # Geometry
        sa.Column("polyline", sa.Text, nullable=False),  # Encoded polyline
        sa.Column("start_point", Geometry("POINT", srid=4326), nullable=False),
        sa.Column("end_point", Geometry("POINT", srid=4326), nullable=False),
        sa.Column("bounds", Geometry("POLYGON", srid=4326), nullable=False),  # Bounding box for spatial queries
        sa.Column("direction_bearing", sa.Float, nullable=True),  # 0-360 degrees
        # Metrics
        sa.Column("distance_m", sa.Float, nullable=False),
        sa.Column("elevation_gain_m", sa.Float, nullable=False),
        sa.Column("avg_grade_pct", sa.Float, nullable=False),
        sa.Column("max_grade_pct", sa.Float, nullable=False),
        sa.Column("gradient_segments", JSONB, nullable=False),  # [{distance_m, grade_pct}, ...]
        # Counts (denormalized for fast queries)
        sa.Column("effort_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("athlete_count", sa.Integer, nullable=False, server_default="0"),
        # Ownership & tracking
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "source_activity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime, nullable=True),  # Soft delete
        sa.Column("matching_job_id", sa.String(100), nullable=True),  # For progress tracking
        # Constraints
        sa.CheckConstraint("type IN ('climb', 'sprint', 'custom')", name="segments_valid_type"),
        sa.CheckConstraint("status IN ('suggested', 'approved')", name="segments_valid_status"),
    )

    # Note: Spatial indices for start_point, end_point, bounds are created
    # automatically by GeoAlchemy2 for Geometry columns

    # Query indices
    op.create_index(
        "idx_segments_type",
        "segments",
        ["type"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "idx_segments_status",
        "segments",
        ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("idx_segments_created_by", "segments", ["created_by"])

    # Segment efforts table
    op.create_table(
        "segment_efforts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "segment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("segments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "activity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("elapsed_time_seconds", sa.Integer, nullable=False),
        sa.Column("moving_time_seconds", sa.Integer, nullable=True),
        sa.Column("avg_power_watts", sa.Integer, nullable=True),
        sa.Column("avg_hr_bpm", sa.Integer, nullable=True),
        sa.Column("start_index", sa.Integer, nullable=False),
        sa.Column("end_index", sa.Integer, nullable=False),
        sa.Column("is_pr", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        # Unique constraint to prevent duplicate efforts
        sa.UniqueConstraint("segment_id", "activity_id", "start_index", name="uq_segment_effort_unique"),
    )

    op.create_index("idx_segment_efforts_segment", "segment_efforts", ["segment_id"])
    op.create_index("idx_segment_efforts_activity", "segment_efforts", ["activity_id"])
    op.create_index("idx_segment_efforts_user", "segment_efforts", ["user_id"])
    op.create_index(
        "idx_segment_efforts_pr",
        "segment_efforts",
        ["segment_id", "user_id"],
        postgresql_where=sa.text("is_pr = TRUE"),
    )

    # Segment suggestions table
    op.create_table(
        "segment_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "segment_id",
            UUID(as_uuid=True),
            sa.ForeignKey("segments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("repetition_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("first_ridden_at", sa.DateTime, nullable=False),
        sa.Column("last_ridden_at", sa.DateTime, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("dismissed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        # Unique constraint: one suggestion per segment per user
        sa.UniqueConstraint("segment_id", "user_id", name="uq_segment_suggestion_user"),
    )

    op.create_index(
        "idx_segment_suggestions_user",
        "segment_suggestions",
        ["user_id"],
        postgresql_where=sa.text("dismissed_at IS NULL"),
    )


def downgrade() -> None:
    # Drop segment_suggestions
    op.drop_index("idx_segment_suggestions_user")
    op.drop_table("segment_suggestions")

    # Drop segment_efforts
    op.drop_index("idx_segment_efforts_pr")
    op.drop_index("idx_segment_efforts_user")
    op.drop_index("idx_segment_efforts_activity")
    op.drop_index("idx_segment_efforts_segment")
    op.drop_table("segment_efforts")

    # Drop segments
    op.drop_index("idx_segments_created_by")
    op.drop_index("idx_segments_status")
    op.drop_index("idx_segments_type")
    # Note: Spatial indices are auto-dropped with the table by GeoAlchemy2
    op.drop_table("segments")
