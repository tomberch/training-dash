"""Add race_courses table.

Database foundation for race courses with PostGIS geometry,
elevation profiles, segments, and climb detection.

Source types: gpx, fit, manual
Segments store grade-based course sections for pacing.
Climbs store detected climbs with categories (4, 3, 2, 1, HC).

Revision ID: 012_race_courses_table
Revises: 011_bikes_table
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "012_race_courses_table"
down_revision: str | None = "011_bikes_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "race_courses",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False),  # gpx, fit, manual
        sa.Column("source_filename", sa.String(255), nullable=True),
        # Course metrics
        sa.Column("distance_m", sa.Float, nullable=False),
        sa.Column("elevation_gain_m", sa.Float, nullable=False),
        sa.Column("elevation_loss_m", sa.Float, nullable=False),
        sa.Column("min_elevation_m", sa.Float, nullable=True),
        sa.Column("max_elevation_m", sa.Float, nullable=True),
        # Geometry (PostGIS) - LineStringZ includes elevation
        sa.Column("geometry", Geometry("LINESTRINGZ", srid=4326), nullable=False),
        # Processed data (JSONB for flexibility)
        # elevation_profile: [{distance_m, elevation_m, grade_pct}, ...]
        sa.Column("elevation_profile", sa.dialects.postgresql.JSONB, nullable=True),
        # segments: [{start_m, end_m, avg_grade_pct, distance_m, min_elevation_m, max_elevation_m}, ...]
        sa.Column("segments", sa.dialects.postgresql.JSONB, nullable=True),
        # climbs: [{name, start_m, end_m, distance_m, avg_grade_pct, elevation_gain_m, category}, ...]
        sa.Column("climbs", sa.dialects.postgresql.JSONB, nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.text("now()")),
        # Constraints
        sa.CheckConstraint(
            "source_type IN ('gpx', 'fit', 'manual')",
            name="valid_source_type",
        ),
    )

    # Indices
    op.create_index("idx_race_courses_user", "race_courses", ["user_id"])
    # Spatial index is created automatically by geoalchemy2 for Geometry columns


def downgrade() -> None:
    op.drop_index("idx_race_courses_user", table_name="race_courses")
    op.drop_table("race_courses")
