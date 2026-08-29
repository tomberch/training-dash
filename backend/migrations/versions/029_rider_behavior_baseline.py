"""Rider-behavior baseline storage (ADR 0005 #635).

Adds the learned stop/coast baseline per terrain type to the existing
pacing_coefficients rows: a JSONB column keyed by terrain with
non_pedaling/coasting/stopped percentages and the activity count that
informed each bucket. NULL (or missing terrains) = not learned —
quality-gated, never guessed.

Revision ID: 029
Revises: 028
Create Date: 2026-08-29

"""

import sqlalchemy as sa
from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pacing_coefficients",
        sa.Column(
            "terrain_behavior",
            sa.dialects.postgresql.JSONB(),
            nullable=True,
            comment=(
                "Learned stop/coast baseline per terrain type (ADR 0005 #635). "
                "Shape: {terrain: {non_pedaling_pct, coasting_pct, stopped_pct, "
                "activity_count}}. NULL = not learned / thinned by the quality gate."
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("pacing_coefficients", "terrain_behavior")
