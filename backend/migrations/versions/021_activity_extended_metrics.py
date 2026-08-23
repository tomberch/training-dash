"""Add extended metrics fields to activities table.

Adds columns for comprehensive activity metrics:
- timer_time_s: Time with timer running (between moving and elapsed)
- elevation_loss_m: Total descent
- min_altitude_m, max_altitude_m: Elevation range
- max_grade_pct: Steepest gradient
- avg_temperature_c, min_temperature_c, max_temperature_c: Temperature stats
- avg_cadence_rpm: Average cadence (all samples)
- avg_cadence_pedaling_rpm: Average cadence while pedaling (cadence > 0)
- max_power_w: Maximum instantaneous power
- avg_speed_moving_mps: Average speed while moving (distance / moving_time)

Revision ID: 021
Revises: 020
Create Date: 2026-08-23

"""

from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Time
    op.add_column("activities", sa.Column("timer_time_s", sa.Integer(), nullable=True))
    
    # Elevation
    op.add_column("activities", sa.Column("elevation_loss_m", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("min_altitude_m", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("max_altitude_m", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("max_grade_pct", sa.Float(), nullable=True))
    
    # Temperature
    op.add_column("activities", sa.Column("avg_temperature_c", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("min_temperature_c", sa.Integer(), nullable=True))
    op.add_column("activities", sa.Column("max_temperature_c", sa.Integer(), nullable=True))
    
    # Cadence
    op.add_column("activities", sa.Column("avg_cadence_rpm", sa.Integer(), nullable=True))
    op.add_column("activities", sa.Column("avg_cadence_pedaling_rpm", sa.Integer(), nullable=True))
    
    # Power
    op.add_column("activities", sa.Column("max_power_w", sa.Integer(), nullable=True))
    
    # Speed
    op.add_column("activities", sa.Column("avg_speed_moving_mps", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("activities", "avg_speed_moving_mps")
    op.drop_column("activities", "max_power_w")
    op.drop_column("activities", "avg_cadence_pedaling_rpm")
    op.drop_column("activities", "avg_cadence_rpm")
    op.drop_column("activities", "max_temperature_c")
    op.drop_column("activities", "min_temperature_c")
    op.drop_column("activities", "avg_temperature_c")
    op.drop_column("activities", "max_grade_pct")
    op.drop_column("activities", "max_altitude_m")
    op.drop_column("activities", "min_altitude_m")
    op.drop_column("activities", "elevation_loss_m")
    op.drop_column("activities", "timer_time_s")
