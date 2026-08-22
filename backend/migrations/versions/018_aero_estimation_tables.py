"""Add CdA/Crr estimation columns and weather storage.

Implements storage decisions from #575 (weather) and #576 (CdA/Crr).

Activity columns:
- estimated_cda: Per-activity CdA estimate (m²)
- estimated_crr: Per-activity Crr estimate
- aero_confidence: Confidence score 0.0-1.0
- weather_status: Status of weather data fetch

Bike columns:
- estimated_cda_avg: Confidence-weighted average CdA
- estimated_crr_avg: Confidence-weighted average Crr
- estimated_cda_stddev: Standard deviation for CdA
- estimated_crr_stddev: Standard deviation for Crr
- aero_sample_count: Number of activities contributing to aggregates

Activity weather table:
- Hourly weather snapshots during the activity
- Includes wind, pressure, humidity, temperature, pre-calculated air density

Revision ID: 018
Revises: 017
Create Date: 2026-08-21

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Activity CdA/Crr columns
    op.add_column("activities", sa.Column("estimated_cda", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("estimated_crr", sa.Float(), nullable=True))
    op.add_column("activities", sa.Column("aero_confidence", sa.Float(), nullable=True))
    op.add_column(
        "activities",
        sa.Column(
            "weather_status",
            sa.String(20),
            nullable=True,
            comment="Weather fetch status: pending, fetched, failed, not_applicable",
        ),
    )

    # Bike aggregate columns
    op.add_column("bikes", sa.Column("estimated_cda_avg", sa.Float(), nullable=True))
    op.add_column("bikes", sa.Column("estimated_crr_avg", sa.Float(), nullable=True))
    op.add_column("bikes", sa.Column("estimated_cda_stddev", sa.Float(), nullable=True))
    op.add_column("bikes", sa.Column("estimated_crr_stddev", sa.Float(), nullable=True))
    op.add_column("bikes", sa.Column("aero_sample_count", sa.Integer(), nullable=True, server_default="0"))

    # Activity weather table - hourly snapshots during activity
    op.create_table(
        "activity_weather",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "activity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hour_offset", sa.Integer(), nullable=False, comment="Hours from activity start"),
        sa.Column("lat", sa.Float(), nullable=True, comment="Sample point latitude"),
        sa.Column("lon", sa.Float(), nullable=True, comment="Sample point longitude"),
        sa.Column("temperature_c", sa.Float(), nullable=False),
        sa.Column("wind_speed_mps", sa.Float(), nullable=False),
        sa.Column("wind_direction_deg", sa.Float(), nullable=False, comment="Meteorological direction (FROM)"),
        sa.Column("pressure_hpa", sa.Float(), nullable=False),
        sa.Column("humidity_pct", sa.Float(), nullable=False),
        sa.Column("air_density", sa.Float(), nullable=False, comment="Pre-calculated kg/m³"),
        sa.UniqueConstraint("activity_id", "hour_offset", name="uq_activity_weather_hour"),
    )

    op.create_index("ix_activity_weather_activity_id", "activity_weather", ["activity_id"])


def downgrade() -> None:
    op.drop_index("ix_activity_weather_activity_id")
    op.drop_table("activity_weather")

    op.drop_column("bikes", "aero_sample_count")
    op.drop_column("bikes", "estimated_crr_stddev")
    op.drop_column("bikes", "estimated_cda_stddev")
    op.drop_column("bikes", "estimated_crr_avg")
    op.drop_column("bikes", "estimated_cda_avg")

    op.drop_column("activities", "weather_status")
    op.drop_column("activities", "aero_confidence")
    op.drop_column("activities", "estimated_crr")
    op.drop_column("activities", "estimated_cda")
