"""Replace gradient_segments with elevation_profile in segments table.

Changes from bar-chart gradient segments to elevation profile points
for rendering as an area chart. Each point stores distance, elevation,
and preceding window grade.

Part of Segment v2 (#665).

Revision ID: 033
Revises: 032
Create Date: 2026-09-18
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new elevation_profile column
    # [{distance_m, elevation_m, grade_pct}, ...]
    op.add_column(
        "segments",
        sa.Column("elevation_profile", JSONB, nullable=False, server_default="[]"),
    )

    # Drop old gradient_segments column
    op.drop_column("segments", "gradient_segments")

    # Remove the server default now that the column exists
    op.alter_column("segments", "elevation_profile", server_default=None)


def downgrade() -> None:
    # Add back gradient_segments column
    # [{distance_m, grade_pct}, ...]
    op.add_column(
        "segments",
        sa.Column("gradient_segments", JSONB, nullable=False, server_default="[]"),
    )

    # Drop elevation_profile column
    op.drop_column("segments", "elevation_profile")

    # Remove the server default
    op.alter_column("segments", "gradient_segments", server_default=None)
