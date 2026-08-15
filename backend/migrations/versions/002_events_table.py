"""Events table for system event log.

Revision ID: 002_events
Revises: 001_initial
Create Date: 2026-08-12

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002_events"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )

    # Primary query: recent events, filtered by type/outcome/user
    op.create_index(
        "idx_events_created_at",
        "events",
        [sa.text("created_at DESC")],
    )

    # Filter by type and outcome
    op.create_index(
        "idx_events_type_outcome",
        "events",
        ["event_type", "outcome"],
    )

    # Filter by user (partial index - only non-null user_ids)
    op.execute("CREATE INDEX idx_events_user_id ON events (user_id) WHERE user_id IS NOT NULL")

    # Index for pruning queries: finding old events to delete
    op.create_index(
        "idx_events_pruning",
        "events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_events_pruning", table_name="events")
    op.drop_index("idx_events_user_id", table_name="events")
    op.drop_index("idx_events_type_outcome", table_name="events")
    op.drop_index("idx_events_created_at", table_name="events")
    op.drop_table("events")
