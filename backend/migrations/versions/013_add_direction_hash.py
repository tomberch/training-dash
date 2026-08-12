"""Add direction_hash column to activities for fast same-route direction comparison.

Revision ID: 013_direction_hash
Revises: 9770240a720c
Create Date: 2026-08-11

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013_direction_hash"
down_revision: str = "9770240a720c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("direction_hash", sa.String(32), nullable=True),
    )
    # Index for fast lookups when comparing activities on the same route
    op.create_index(
        "ix_activities_route_direction",
        "activities",
        ["route_id", "direction_hash"],
        postgresql_where=sa.text("route_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_activities_route_direction", table_name="activities")
    op.drop_column("activities", "direction_hash")
