"""Add OAuth support: user_oauth_links table and nullable password_hash

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-08-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'h2i3j4k5l6m7'
down_revision: Union[str, None] = 'g1h2i3j4k5l6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create user_oauth_links table
    op.create_table(
        'user_oauth_links',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('provider_user_id', sa.String(255), nullable=False),
        sa.Column('provider_email', sa.String(255), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    
    # Create indexes
    op.create_index('idx_oauth_user_id', 'user_oauth_links', ['user_id'])
    op.create_unique_constraint('uq_oauth_provider_user', 'user_oauth_links', ['provider', 'provider_user_id'])
    
    # Make password_hash nullable for OAuth-only users
    op.alter_column('users', 'password_hash', existing_type=sa.String(255), nullable=True)


def downgrade() -> None:
    # Make password_hash non-nullable again (will fail if any NULL values exist)
    op.alter_column('users', 'password_hash', existing_type=sa.String(255), nullable=False)
    
    # Drop indexes and table
    op.drop_constraint('uq_oauth_provider_user', 'user_oauth_links', type_='unique')
    op.drop_index('idx_oauth_user_id', 'user_oauth_links')
    op.drop_table('user_oauth_links')
