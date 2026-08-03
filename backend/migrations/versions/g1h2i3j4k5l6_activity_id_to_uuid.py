"""Convert activity ID from BigInteger to UUID

Revision ID: g1h2i3j4k5l6
Revises: f1a2b3c4d5e6
Create Date: 2026-08-03 12:00:00.000000

This is a DESTRUCTIVE migration that drops all activity-related data.
It changes the Activity.id column from BigInteger to UUID, along with
all foreign key references (Record, Lap, ActivityPeakPower, Route.first_seen_activity_id).

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop FK from activities to routes first to break circular dependency
    op.drop_constraint('activities_route_id_fkey', 'activities', type_='foreignkey')
    
    # Drop dependent tables first (FK constraints)
    op.drop_table('records')
    op.drop_table('laps')
    op.drop_table('activity_peak_powers')
    op.drop_table('routes')
    op.drop_table('activities')
    
    # Recreate activities with UUID primary key
    op.create_table(
        'activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_ref', sa.Text(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('total_distance_m', sa.Float(), nullable=False, server_default='0'),
        sa.Column('moving_time_s', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('elapsed_time_s', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('elevation_gain_m', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_speed_mps', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_hr_bpm', sa.Integer(), nullable=True),
        sa.Column('avg_power_w', sa.Integer(), nullable=True),
        sa.Column('np_power_w', sa.Integer(), nullable=True),
        sa.Column('power_source', sa.String(20), nullable=True),
        sa.Column('power_confidence', sa.Float(), nullable=True),
        sa.Column('max_speed_mps', sa.Float(), nullable=False, server_default='0'),
        sa.Column('max_hr_bpm', sa.Integer(), nullable=True),
        sa.Column('intensity_factor', sa.Float(), nullable=True),
        sa.Column('tss', sa.Float(), nullable=True),
        sa.Column('training_load', sa.Float(), nullable=True),
        sa.Column('power_zone_times', sa.Text(), nullable=True),
        sa.Column('hr_zone_times', sa.Text(), nullable=True),
        sa.Column('wbal_min_joules', sa.Integer(), nullable=True),
        sa.Column('wbal_min_pct', sa.Float(), nullable=True),
        sa.Column('is_breakthrough', sa.Boolean(), server_default='false'),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('title_source', sa.String(20), server_default='auto', nullable=False),
        sa.Column('map_polyline', sa.Text(), nullable=True),
        sa.Column('route_id', sa.BigInteger(), nullable=True),
        sa.Column('raw_fit', sa.LargeBinary(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    
    # Recreate routes table (with UUID FK to activities)
    op.create_table(
        'routes',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('simplified_polyline', sa.Text(), nullable=False),  # Will be updated to Geography after creation
        sa.Column('first_seen_activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id'), nullable=False),
        sa.Column('ride_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    
    # Add route_id FK to activities now that routes table exists
    op.create_foreign_key('activities_route_id_fkey', 'activities', 'routes', ['route_id'], ['id'])
    
    # Update routes.simplified_polyline to Geography type
    # First drop the text column and recreate as Geography
    op.execute("SELECT AddGeometryColumn('routes', 'simplified_polyline_geo', 4326, 'LINESTRING', 2)")
    op.drop_column('routes', 'simplified_polyline')
    op.execute("ALTER TABLE routes RENAME COLUMN simplified_polyline_geo TO simplified_polyline")
    op.execute("ALTER TABLE routes ALTER COLUMN simplified_polyline SET NOT NULL")
    op.execute("CREATE INDEX idx_routes_simplified_polyline ON routes USING GIST (simplified_polyline)")
    
    # Recreate records with UUID FK
    op.create_table(
        'records',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lon', sa.Float(), nullable=True),
        sa.Column('distance_m', sa.Float(), nullable=False, server_default='0'),
        sa.Column('hr_bpm', sa.Integer(), nullable=True),
        sa.Column('power_w', sa.Integer(), nullable=True),
        sa.Column('speed_mps', sa.Float(), nullable=True),
        sa.Column('altitude_m', sa.Float(), nullable=True),
        sa.Column('cadence_rpm', sa.Integer(), nullable=True),
    )
    
    # Add geom column with Geography type
    op.execute("SELECT AddGeometryColumn('records', 'geom', 4326, 'POINT', 2)")
    op.execute("CREATE INDEX idx_records_geom ON records USING GIST (geom)")
    op.execute("CREATE INDEX idx_records_activity_id ON records (activity_id)")
    
    # Recreate laps with UUID FK
    op.create_table(
        'laps',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lap_index', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('total_distance_m', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_hr_bpm', sa.Integer(), nullable=True),
        sa.Column('avg_power_w', sa.Integer(), nullable=True),
        sa.Column('max_hr_bpm', sa.Integer(), nullable=True),
    )
    op.execute("CREATE INDEX idx_laps_activity_id ON laps (activity_id)")
    
    # Recreate activity_peak_powers with UUID FK
    op.create_table(
        'activity_peak_powers',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('watts', sa.Integer(), nullable=False),
    )
    op.execute("CREATE INDEX idx_activity_peak_powers_activity_id ON activity_peak_powers (activity_id)")


def downgrade() -> None:
    # Drop new tables
    op.drop_table('records')
    op.drop_table('laps')
    op.drop_table('activity_peak_powers')
    op.drop_table('routes')
    op.drop_table('activities')
    
    # Recreate original tables with BigInteger IDs
    # This is a destructive downgrade - data will be lost
    op.create_table(
        'activities',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_ref', sa.Text(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('total_distance_m', sa.Float(), nullable=False, server_default='0'),
        sa.Column('moving_time_s', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('elapsed_time_s', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('elevation_gain_m', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_speed_mps', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_hr_bpm', sa.Integer(), nullable=True),
        sa.Column('avg_power_w', sa.Integer(), nullable=True),
        sa.Column('np_power_w', sa.Integer(), nullable=True),
        sa.Column('power_source', sa.String(20), nullable=True),
        sa.Column('power_confidence', sa.Float(), nullable=True),
        sa.Column('max_speed_mps', sa.Float(), nullable=False, server_default='0'),
        sa.Column('max_hr_bpm', sa.Integer(), nullable=True),
        sa.Column('intensity_factor', sa.Float(), nullable=True),
        sa.Column('tss', sa.Float(), nullable=True),
        sa.Column('training_load', sa.Float(), nullable=True),
        sa.Column('power_zone_times', sa.Text(), nullable=True),
        sa.Column('hr_zone_times', sa.Text(), nullable=True),
        sa.Column('wbal_min_joules', sa.Integer(), nullable=True),
        sa.Column('wbal_min_pct', sa.Float(), nullable=True),
        sa.Column('is_breakthrough', sa.Boolean(), server_default='false'),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('title_source', sa.String(20), server_default='auto', nullable=False),
        sa.Column('map_polyline', sa.Text(), nullable=True),
        sa.Column('route_id', sa.BigInteger(), nullable=True),
        sa.Column('raw_fit', sa.LargeBinary(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    
    op.create_table(
        'routes',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('first_seen_activity_id', sa.BigInteger(), sa.ForeignKey('activities.id'), nullable=False),
        sa.Column('ride_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.execute("SELECT AddGeometryColumn('routes', 'simplified_polyline', 4326, 'LINESTRING', 2)")
    op.execute("ALTER TABLE routes ALTER COLUMN simplified_polyline SET NOT NULL")
    op.execute("CREATE INDEX idx_routes_simplified_polyline ON routes USING GIST (simplified_polyline)")
    
    op.create_foreign_key('activities_route_id_fkey', 'activities', 'routes', ['route_id'], ['id'])
    
    op.create_table(
        'records',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('activity_id', sa.BigInteger(), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lon', sa.Float(), nullable=True),
        sa.Column('distance_m', sa.Float(), nullable=False, server_default='0'),
        sa.Column('hr_bpm', sa.Integer(), nullable=True),
        sa.Column('power_w', sa.Integer(), nullable=True),
        sa.Column('speed_mps', sa.Float(), nullable=True),
        sa.Column('altitude_m', sa.Float(), nullable=True),
        sa.Column('cadence_rpm', sa.Integer(), nullable=True),
    )
    op.execute("SELECT AddGeometryColumn('records', 'geom', 4326, 'POINT', 2)")
    op.execute("CREATE INDEX idx_records_geom ON records USING GIST (geom)")
    op.execute("CREATE INDEX idx_records_activity_id ON records (activity_id)")
    
    op.create_table(
        'laps',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('activity_id', sa.BigInteger(), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lap_index', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('total_distance_m', sa.Float(), nullable=False, server_default='0'),
        sa.Column('avg_hr_bpm', sa.Integer(), nullable=True),
        sa.Column('avg_power_w', sa.Integer(), nullable=True),
        sa.Column('max_hr_bpm', sa.Integer(), nullable=True),
    )
    op.execute("CREATE INDEX idx_laps_activity_id ON laps (activity_id)")
    
    op.create_table(
        'activity_peak_powers',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('activity_id', sa.BigInteger(), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('watts', sa.Integer(), nullable=False),
    )
    op.execute("CREATE INDEX idx_activity_peak_powers_activity_id ON activity_peak_powers (activity_id)")
