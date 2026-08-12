"""Cache stats table for tracking cache hit/miss statistics.

Revision ID: 003_cache_stats
Revises: 002_events
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003_cache_stats"
down_revision: str | None = "002_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cache_stats",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cache_type", sa.String(20), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("misses", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("bucket_start", "cache_type", name="uq_cache_stats_bucket_type"),
    )

    # Primary query: recent stats ordered by time
    op.create_index(
        "idx_cache_stats_bucket",
        "cache_stats",
        [sa.text("bucket_start DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_cache_stats_bucket", table_name="cache_stats")
    op.drop_table("cache_stats")
