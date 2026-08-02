"""add_activity_title_columns

Revision ID: e66c3133a85f
Revises: 52c2e3ca28ab
Create Date: 2026-08-02 23:42:08.082133

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e66c3133a85f'
down_revision: Union[str, Sequence[str], None] = '52c2e3ca28ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add title and title_source columns to activities table."""
    op.add_column('activities', sa.Column('title', sa.String(255), nullable=True))
    op.add_column('activities', sa.Column('title_source', sa.String(20), server_default='auto', nullable=False))


def downgrade() -> None:
    """Remove title columns from activities table."""
    op.drop_column('activities', 'title_source')
    op.drop_column('activities', 'title')
