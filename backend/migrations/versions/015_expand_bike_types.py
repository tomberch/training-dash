"""Expand bike_type constraint to include more bike types.

Adds: track, cx, commuter, other

Revision ID: 015_expand_bike_types
Revises: 014_ef_models_vi_value
Create Date: 2026-08-21

"""

from collections.abc import Sequence

from alembic import op

revision: str = "015_expand_bike_types"
down_revision: str | None = "014_ef_models_vi_value"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the old constraint
    op.drop_constraint("valid_bike_type", "bikes", type_="check")
    
    # Add the expanded constraint
    op.create_check_constraint(
        "valid_bike_type",
        "bikes",
        "bike_type IN ('road', 'gravel', 'mtb', 'tt', 'track', 'cx', 'commuter', 'ebike', 'other')",
    )


def downgrade() -> None:
    # Drop the expanded constraint
    op.drop_constraint("valid_bike_type", "bikes", type_="check")
    
    # Restore the original constraint
    op.create_check_constraint(
        "valid_bike_type",
        "bikes",
        "bike_type IN ('road', 'tt', 'gravel', 'mtb', 'ebike')",
    )
