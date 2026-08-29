"""Sustainability traffic light on race plans (ADR 0005 #638).

green = sustainable, yellow = very hard near-limit, red = beyond
capability. Red plans are still generated and saved, flagged; only
physically impossible requests are hard errors (the scale-to-time
solver draws that line). Existing rows stay NULL until regenerated
(honest: their effort data predates the assessment).

Revision ID: 031
Revises: 030
Create Date: 2026-08-29

"""

import sqlalchemy as sa
from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "race_plans",
        sa.Column(
            "sustainability",
            sa.String(10),
            nullable=True,
            comment="green/yellow/red effort flag (ADR 0005 #638); NULL = legacy plan",
        ),
    )
    op.create_check_constraint(
        "valid_sustainability",
        "race_plans",
        "sustainability IN ('green', 'yellow', 'red') OR sustainability IS NULL",
    )


def downgrade() -> None:
    op.drop_constraint("valid_sustainability", "race_plans", type_="check")
    op.drop_column("race_plans", "sustainability")
