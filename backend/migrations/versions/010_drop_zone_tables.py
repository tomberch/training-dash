"""Drop power_zones and hr_zones tables.

Zones are now computed on-the-fly from thresholds and user zone percentages.

Revision ID: 010_drop_zone_tables
Revises: 009_user_profile_zones
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa


revision = "010_drop_zone_tables"
down_revision = "009_user_profile_zones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("hr_zones")
    op.drop_table("power_zones")


def downgrade() -> None:
    # Recreate power_zones table
    op.create_table(
        "power_zones",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("zone_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("min_watts", sa.Integer(), nullable=False),
        sa.Column("max_watts", sa.Integer(), nullable=True),
        sa.Column("is_custom", sa.Boolean(), default=False),
    )

    # Recreate hr_zones table
    op.create_table(
        "hr_zones",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("zone_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("min_bpm", sa.Integer(), nullable=False),
        sa.Column("max_bpm", sa.Integer(), nullable=True),
        sa.Column("is_custom", sa.Boolean(), default=False),
    )
