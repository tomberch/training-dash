"""Add direction_bearing column for robust same-route direction comparison.

The direction_bearing is a single integer (0-359) representing the bearing from
the start point to the 25% distance point. This is more robust than the
direction_hash approach which was sensitive to GPS noise at cardinal direction
boundaries.

Two activities are considered same-direction if their bearings are within 90°.

Revision ID: 014_direction_bearing
Revises: 013_direction_hash
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014_direction_bearing"
down_revision: str = "013_direction_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("direction_bearing", sa.SmallInteger(), nullable=True),
    )
    # Index for fast lookups when comparing activities on the same route
    op.create_index(
        "ix_activities_route_bearing",
        "activities",
        ["route_id", "direction_bearing"],
        postgresql_where=sa.text("route_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_activities_route_bearing", table_name="activities")
    op.drop_column("activities", "direction_bearing")
