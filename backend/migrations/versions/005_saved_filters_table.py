"""Saved filters table for storing user query filters.

Revision ID: 005_saved_filters
Revises: 004_geocoding_cache
Create Date: 2026-08-14

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005_saved_filters"
down_revision: str | None = "004_geocoding_cache_update"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "saved_filters",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "name", name="uq_saved_filter_user_name"),
    )

    # Index for user lookups (list filters, get default)
    op.create_index(
        "idx_saved_filters_user_id",
        "saved_filters",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_saved_filters_user_id", table_name="saved_filters")
    op.drop_table("saved_filters")
