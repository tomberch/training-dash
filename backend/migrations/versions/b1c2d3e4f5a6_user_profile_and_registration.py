"""Add user profile fields and app settings for registration

Revision ID: b1c2d3e4f5a6
Revises: e66c3133a85f
Create Date: 2026-08-03

Changes:
- Rename users.username to users.email
- Add users.display_name (optional)
- Add users.avatar_path (optional)
- Add users.is_approved (default True for existing users)
- Add users.sync_hour (default 3)
- Create app_settings table for registration settings
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename username column to email
    op.alter_column('users', 'username', new_column_name='email')
    
    # Add new columns to users table
    op.add_column('users', sa.Column('display_name', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('avatar_path', sa.String(500), nullable=True))
    op.add_column('users', sa.Column('is_approved', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column('sync_hour', sa.Integer(), nullable=False, server_default='3'))
    
    # Create app_settings table
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    
    # Insert default setting: require approval for new registrations
    op.execute("INSERT INTO app_settings (key, value) VALUES ('require_approval', 'true')")


def downgrade() -> None:
    # Drop app_settings table
    op.drop_table('app_settings')
    
    # Remove new columns from users
    op.drop_column('users', 'sync_hour')
    op.drop_column('users', 'is_approved')
    op.drop_column('users', 'avatar_path')
    op.drop_column('users', 'display_name')
    
    # Rename email back to username
    op.alter_column('users', 'email', new_column_name='username')
