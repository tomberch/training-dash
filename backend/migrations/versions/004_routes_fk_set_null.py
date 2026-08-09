"""Change routes.first_seen_activity_id FK to ON DELETE SET NULL.

This allows deleting an Activity that is the first_seen of a Route without
requiring manual FK repair — the database nulls the field automatically.
The column is also changed from NOT NULL to nullable to permit this.

Revision ID: 004_routes_first_seen_on_delete_set_null
Revises: 003_add_utc_offset_to_activities
Create Date: 2026-08-06

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004_routes_fk_set_null"
down_revision: str | None = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("routes_first_seen_activity_id_fkey", "routes", type_="foreignkey")
    op.alter_column(
        "routes",
        "first_seen_activity_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=True,
    )
    op.create_foreign_key(
        "routes_first_seen_activity_id_fkey",
        "routes",
        "activities",
        ["first_seen_activity_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("routes_first_seen_activity_id_fkey", "routes", type_="foreignkey")
    op.alter_column(
        "routes",
        "first_seen_activity_id",
        existing_type=postgresql.UUID(as_uuid=True),
        nullable=False,
    )
    op.create_foreign_key(
        "routes_first_seen_activity_id_fkey",
        "routes",
        "activities",
        ["first_seen_activity_id"],
        ["id"],
    )
