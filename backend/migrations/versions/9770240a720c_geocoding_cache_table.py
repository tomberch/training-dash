"""geocoding_cache table

Revision ID: 9770240a720c
Revises: 012_drop_threshold_history
Create Date: 2026-08-09 16:43:20.600516

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9770240a720c'
down_revision: Union[str, Sequence[str], None] = '012_drop_threshold_history'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the geocoding_cache table (previously created on first use by
    PostgresGeocodingCacheRepo._ensure_table, which committed on the caller's
    session — a transaction-safety bug. Move schema management to Alembic.)
    """
    op.execute("""
        CREATE TABLE IF NOT EXISTS geocoding_cache (
            cache_key VARCHAR(100) PRIMARY KEY,
            result_json TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)


def downgrade() -> None:
    """Drop the geocoding_cache table."""
    op.execute("DROP TABLE IF EXISTS geocoding_cache")
