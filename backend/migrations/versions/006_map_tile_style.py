"""Add map_tile_style column to users table.

Revision ID: 006_map_tile_style
Revises: 005_saved_filters
Create Date: 2026-08-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006_map_tile_style"
down_revision: str | None = "005_saved_filters"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "map_tile_style",
            sa.String(20),
            nullable=False,
            server_default="osm",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "map_tile_style")
