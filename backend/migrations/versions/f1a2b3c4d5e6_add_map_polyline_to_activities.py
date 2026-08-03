"""Add map_polyline to activities

Revision ID: f1a2b3c4d5e6
Revises: e66c3133a85f
Create Date: 2026-08-03 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('activities', sa.Column('map_polyline', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('activities', 'map_polyline')
