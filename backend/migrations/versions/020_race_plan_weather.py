"""Add weather forecast fields to race_plans table.

Adds columns to support race day weather conditions:
- target_date: When the event is scheduled
- target_conditions: JSONB with forecast data (temp, pressure, humidity, wind, air_density)
- conditions_fetched_at: When forecast was last fetched
- wind_override_speed_mps/direction_deg: Manual wind overrides

Revision ID: 020
Revises: 019
Create Date: 2026-08-22

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("race_plans", sa.Column("target_date", sa.Date(), nullable=True))
    op.add_column("race_plans", sa.Column("target_conditions", JSONB(), nullable=True))
    op.add_column("race_plans", sa.Column("conditions_fetched_at", sa.DateTime(), nullable=True))
    op.add_column("race_plans", sa.Column("wind_override_speed_mps", sa.Float(), nullable=True))
    op.add_column("race_plans", sa.Column("wind_override_direction_deg", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("race_plans", "wind_override_direction_deg")
    op.drop_column("race_plans", "wind_override_speed_mps")
    op.drop_column("race_plans", "conditions_fetched_at")
    op.drop_column("race_plans", "target_conditions")
    op.drop_column("race_plans", "target_date")
