"""add_is_auto_calculated_to_threshold_history

Revision ID: a1b2c3d4e5f6
Revises: e66c3133a85f
Create Date: 2026-08-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e66c3133a85f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_auto_calculated column to threshold_history table."""
    op.add_column(
        'threshold_history',
        sa.Column('is_auto_calculated', sa.Boolean(), server_default='false', nullable=False)
    )


def downgrade() -> None:
    """Remove is_auto_calculated column from threshold_history table."""
    op.drop_column('threshold_history', 'is_auto_calculated')
