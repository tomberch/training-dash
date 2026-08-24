"""Add 'activity' to race_courses source_type check constraint.

Revision ID: 023
Revises: 022
Create Date: 2026-08-23
"""

from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old constraint and add new one with 'activity' included
    op.drop_constraint("valid_source_type", "race_courses", type_="check")
    op.create_check_constraint(
        "valid_source_type",
        "race_courses",
        "source_type IN ('gpx', 'fit', 'manual', 'activity')",
    )


def downgrade() -> None:
    op.drop_constraint("valid_source_type", "race_courses", type_="check")
    op.create_check_constraint(
        "valid_source_type",
        "race_courses",
        "source_type IN ('gpx', 'fit', 'manual')",
    )
