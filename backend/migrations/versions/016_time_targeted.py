"""Add time_targeted to valid optimization methods.

Supports the target time optimization mode where users specify a desired
finish time and the optimizer calculates the power needed.

Revision ID: 016_time_targeted
Revises: 015_expand_bike_types
Create Date: 2026-08-21

"""

from collections.abc import Sequence

from alembic import op

revision: str = "016_time_targeted"
down_revision: str | None = "015_expand_bike_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop the old constraint
    op.drop_constraint("valid_optimization_method", "race_plans", type_="check")

    # Add the expanded constraint with time_targeted
    op.create_check_constraint(
        "valid_optimization_method",
        "race_plans",
        "optimization_method IN ('heuristic', 'optimized', 'time_targeted') OR optimization_method IS NULL",
    )


def downgrade() -> None:
    # Drop the expanded constraint
    op.drop_constraint("valid_optimization_method", "race_plans", type_="check")

    # Restore the original constraint
    op.create_check_constraint(
        "valid_optimization_method",
        "race_plans",
        "optimization_method IN ('heuristic', 'optimized') OR optimization_method IS NULL",
    )
