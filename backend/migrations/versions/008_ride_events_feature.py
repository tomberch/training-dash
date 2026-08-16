"""RideEvents feature: events, journal entries, media, and links.

Revision ID: 008_ride_events
Revises: 007_sync_enabled_column
Create Date: 2026-08-16

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "008_ride_events"
down_revision: str | None = "007_sync_enabled"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create ride_events table
    op.create_table(
        "ride_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("cover_image_id", UUID(as_uuid=True), nullable=True),  # FK added later to avoid circular ref
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_ride_events_user_id", "ride_events", ["user_id"])
    op.create_index("idx_ride_events_user_start_date", "ride_events", ["user_id", "start_date"])

    # Create journal_entries table
    op.create_table(
        "journal_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "ride_event_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ride_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("ride_event_id", "entry_date", name="uq_journal_entry_event_date"),
    )
    op.create_index("idx_journal_entries_ride_event_id", "journal_entries", ["ride_event_id"])

    # Create ride_event_media table
    op.create_table(
        "ride_event_media",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "ride_event_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ride_events.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "journal_entry_id",
            UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("media_type", sa.String(20), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=True),
        sa.Column("thumbnail_path", sa.String(500), nullable=True),
        sa.Column("external_url", sa.String(500), nullable=True),
        sa.Column("caption", sa.String(500), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # CHECK constraint: exactly one of ride_event_id or journal_entry_id must be set
        sa.CheckConstraint(
            "(ride_event_id IS NOT NULL)::int + (journal_entry_id IS NOT NULL)::int = 1",
            name="ck_ride_event_media_one_parent",
        ),
    )
    op.create_index("idx_ride_event_media_ride_event_id", "ride_event_media", ["ride_event_id"])
    op.create_index("idx_ride_event_media_journal_entry_id", "ride_event_media", ["journal_entry_id"])

    # Now add the cover_image_id FK (deferred to avoid circular reference during table creation)
    op.create_foreign_key(
        "fk_ride_events_cover_image",
        "ride_events",
        "ride_event_media",
        ["cover_image_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Create ride_event_links table
    op.create_table(
        "ride_event_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "ride_event_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ride_events.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "journal_entry_id",
            UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("link_type", sa.String(20), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        # CHECK constraint: exactly one of ride_event_id or journal_entry_id must be set
        sa.CheckConstraint(
            "(ride_event_id IS NOT NULL)::int + (journal_entry_id IS NOT NULL)::int = 1",
            name="ck_ride_event_links_one_parent",
        ),
    )
    op.create_index("idx_ride_event_links_ride_event_id", "ride_event_links", ["ride_event_id"])
    op.create_index("idx_ride_event_links_journal_entry_id", "ride_event_links", ["journal_entry_id"])

    # Create journal_entry_activities join table
    op.create_table(
        "journal_entry_activities",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "journal_entry_id",
            UUID(as_uuid=True),
            sa.ForeignKey("journal_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "activity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("journal_entry_id", "activity_id", name="uq_journal_entry_activity"),
    )
    op.create_index("idx_journal_entry_activities_journal_entry_id", "journal_entry_activities", ["journal_entry_id"])
    op.create_index("idx_journal_entry_activities_activity_id", "journal_entry_activities", ["activity_id"])

    # Add ride_event_id column to activities table
    op.add_column(
        "activities",
        sa.Column(
            "ride_event_id",
            UUID(as_uuid=True),
            sa.ForeignKey("ride_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_activities_ride_event_id", "activities", ["ride_event_id"])


def downgrade() -> None:
    # Remove ride_event_id from activities
    op.drop_index("idx_activities_ride_event_id", table_name="activities")
    op.drop_column("activities", "ride_event_id")

    # Drop journal_entry_activities
    op.drop_index("idx_journal_entry_activities_activity_id", table_name="journal_entry_activities")
    op.drop_index("idx_journal_entry_activities_journal_entry_id", table_name="journal_entry_activities")
    op.drop_table("journal_entry_activities")

    # Drop ride_event_links
    op.drop_index("idx_ride_event_links_journal_entry_id", table_name="ride_event_links")
    op.drop_index("idx_ride_event_links_ride_event_id", table_name="ride_event_links")
    op.drop_table("ride_event_links")

    # Drop cover_image FK before dropping media table
    op.drop_constraint("fk_ride_events_cover_image", "ride_events", type_="foreignkey")

    # Drop ride_event_media
    op.drop_index("idx_ride_event_media_journal_entry_id", table_name="ride_event_media")
    op.drop_index("idx_ride_event_media_ride_event_id", table_name="ride_event_media")
    op.drop_table("ride_event_media")

    # Drop journal_entries
    op.drop_index("idx_journal_entries_ride_event_id", table_name="journal_entries")
    op.drop_table("journal_entries")

    # Drop ride_events
    op.drop_index("idx_ride_events_user_start_date", table_name="ride_events")
    op.drop_index("idx_ride_events_user_id", table_name="ride_events")
    op.drop_table("ride_events")
