"""Add audit_log table for tracking destructive admin actions

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-08-03
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('admin_id', sa.BigInteger(), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('target_user_id', sa.Integer(), nullable=True),
        sa.Column('target_user_email', sa.String(255), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_audit_log_admin_id', 'audit_log', ['admin_id'])
    op.create_index('ix_audit_log_target_user_id', 'audit_log', ['target_user_id'])
    op.create_index('ix_audit_log_created_at', 'audit_log', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_audit_log_created_at', table_name='audit_log')
    op.drop_index('ix_audit_log_target_user_id', table_name='audit_log')
    op.drop_index('ix_audit_log_admin_id', table_name='audit_log')
    op.drop_table('audit_log')
