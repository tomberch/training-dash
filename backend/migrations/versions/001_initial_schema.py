"""Initial schema - consolidated migration.

Revision ID: 001_initial
Revises: 
Create Date: 2026-08-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from geoalchemy2 import Geography

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis_topology")
    op.execute("CREATE EXTENSION IF NOT EXISTS fuzzystrmatch")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder")

    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('avatar_path', sa.String(500), nullable=True),
        sa.Column('is_admin', sa.Boolean(), default=False, nullable=False),
        sa.Column('is_approved', sa.Boolean(), default=True, nullable=False),
        sa.Column('unit_system', sa.String(10), default='metric', nullable=False),
        sa.Column('sync_hour', sa.Integer(), default=3, nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('weight_kg', sa.Numeric(5, 2), nullable=True),
        sa.Column('hr_derived_power_enabled', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )

    # User OAuth links (GitHub, Google, etc.)
    op.create_table(
        'user_oauth_links',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('provider_user_id', sa.String(255), nullable=False),
        sa.Column('provider_email', sa.String(255), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('provider', 'provider_user_id', name='uq_oauth_provider_user'),
    )

    # App settings (key-value store)
    op.create_table(
        'app_settings',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )

    # Activities table (with UUID primary key)
    op.create_table(
        'activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),
        sa.Column('source_ref', sa.Text(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('total_distance_m', sa.Float(), nullable=False, default=0),
        sa.Column('moving_time_s', sa.Integer(), nullable=False, default=0),
        sa.Column('elapsed_time_s', sa.Integer(), nullable=False, default=0),
        sa.Column('elevation_gain_m', sa.Float(), nullable=False, default=0),
        sa.Column('avg_speed_mps', sa.Float(), nullable=False, default=0),
        sa.Column('avg_hr_bpm', sa.Integer(), nullable=True),
        sa.Column('avg_power_w', sa.Integer(), nullable=True),
        sa.Column('np_power_w', sa.Integer(), nullable=True),
        sa.Column('power_source', sa.String(20), nullable=True),
        sa.Column('power_confidence', sa.Float(), nullable=True),
        sa.Column('max_speed_mps', sa.Float(), nullable=False, default=0),
        sa.Column('max_hr_bpm', sa.Integer(), nullable=True),
        sa.Column('intensity_factor', sa.Float(), nullable=True),
        sa.Column('tss', sa.Float(), nullable=True),
        sa.Column('training_load', sa.Float(), nullable=True),
        sa.Column('power_zone_times', sa.Text(), nullable=True),
        sa.Column('hr_zone_times', sa.Text(), nullable=True),
        sa.Column('wbal_min_joules', sa.Integer(), nullable=True),
        sa.Column('wbal_min_pct', sa.Float(), nullable=True),
        sa.Column('is_breakthrough', sa.Boolean(), default=False, nullable=False),
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('title_source', sa.String(20), server_default='auto', nullable=False),
        sa.Column('map_polyline', sa.Text(), nullable=True),
        sa.Column('route_id', sa.BigInteger(), nullable=True),
        sa.Column('raw_fit', sa.LargeBinary(), nullable=True),
        sa.Column('utc_offset_minutes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_activities_user_id', 'activities', ['user_id'])
    op.create_index('ix_activities_started_at', 'activities', ['started_at'])

    # Routes table
    op.create_table(
        'routes',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('simplified_polyline', Geography('LINESTRING', srid=4326, spatial_index=True), nullable=False),
        sa.Column('first_seen_activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id'), nullable=False),
        sa.Column('ride_count', sa.Integer(), nullable=False, default=1),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )

    # Add foreign key for activities.route_id now that routes table exists
    op.create_foreign_key('fk_activities_route_id', 'activities', 'routes', ['route_id'], ['id'])

    # Records table (GPS/sensor data points)
    op.create_table(
        'records',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lon', sa.Float(), nullable=True),
        sa.Column('distance_m', sa.Float(), nullable=False, default=0),
        sa.Column('hr_bpm', sa.Integer(), nullable=True),
        sa.Column('power_w', sa.Integer(), nullable=True),
        sa.Column('speed_mps', sa.Float(), nullable=True),
        sa.Column('altitude_m', sa.Float(), nullable=True),
        sa.Column('cadence_rpm', sa.Integer(), nullable=True),
        sa.Column('geom', Geography('POINT', srid=4326, spatial_index=True), nullable=True),
    )
    op.create_index('ix_records_activity_id', 'records', ['activity_id'])

    # Laps table
    op.create_table(
        'laps',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('lap_index', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('total_distance_m', sa.Float(), nullable=False, default=0),
        sa.Column('avg_hr_bpm', sa.Integer(), nullable=True),
        sa.Column('avg_power_w', sa.Integer(), nullable=True),
        sa.Column('max_hr_bpm', sa.Integer(), nullable=True),
    )

    # Activity peak powers
    op.create_table(
        'activity_peak_powers',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('activity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=False),
        sa.Column('watts', sa.Integer(), nullable=False),
    )
    op.create_index('ix_activity_peak_powers_activity_id', 'activity_peak_powers', ['activity_id'])

    # Fitness history (CP model snapshots)
    op.create_table(
        'fitness_history',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('computed_at', sa.DateTime(), nullable=False),
        sa.Column('pp_watts', sa.Integer(), nullable=False),
        sa.Column('w_prime_joules', sa.Integer(), nullable=False),
        sa.Column('cp_watts', sa.Integer(), nullable=False),
    )

    # Notifications
    op.create_table(
        'notifications',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, default='pending'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )

    # Audit log
    op.create_table(
        'audit_log',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('admin_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('target_user_id', sa.Integer(), nullable=True),
        sa.Column('target_user_email', sa.String(255), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )

    # EF models (for HR-derived power)
    op.create_table(
        'ef_models',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('ef_value', sa.Numeric(6, 4), nullable=False),
        sa.Column('computed_at', sa.DateTime(), nullable=False),
        sa.Column('ride_count', sa.Integer(), nullable=False),
        sa.Column('confidence', sa.Numeric(4, 3), nullable=False),
    )

    # Xert credentials
    op.create_table(
        'xert_credentials',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('xert_email', sa.String(255), nullable=False),
        sa.Column('encrypted_password', sa.LargeBinary(), nullable=False),
        sa.Column('sync_since', sa.DateTime(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )

    # Garmin credentials
    op.create_table(
        'garmin_credentials',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('garmin_email', sa.String(255), nullable=False),
        sa.Column('encrypted_password', sa.LargeBinary(), nullable=False),
        sa.Column('sync_since', sa.DateTime(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )

    # Threshold history (FTP, LTHR, HRmax)
    op.create_table(
        'threshold_history',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('ftp_watts', sa.Integer(), nullable=True),
        sa.Column('lthr_bpm', sa.Integer(), nullable=True),
        sa.Column('hrmax_bpm', sa.Integer(), nullable=True),
        sa.Column('is_auto_calculated', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_threshold_history_user_effective', 'threshold_history', ['user_id', 'effective_date'])

    # Power zones
    op.create_table(
        'power_zones',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('zone_number', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('min_watts', sa.Integer(), nullable=False),
        sa.Column('max_watts', sa.Integer(), nullable=True),
        sa.Column('is_custom', sa.Boolean(), default=False, nullable=False),
    )

    # HR zones
    op.create_table(
        'hr_zones',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('zone_number', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('min_bpm', sa.Integer(), nullable=False),
        sa.Column('max_bpm', sa.Integer(), nullable=True),
        sa.Column('is_custom', sa.Boolean(), default=False, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('hr_zones')
    op.drop_table('power_zones')
    op.drop_table('threshold_history')
    op.drop_table('garmin_credentials')
    op.drop_table('xert_credentials')
    op.drop_table('ef_models')
    op.drop_table('audit_log')
    op.drop_table('notifications')
    op.drop_table('fitness_history')
    op.drop_table('activity_peak_powers')
    op.drop_table('laps')
    op.drop_table('records')
    op.drop_foreign_key('fk_activities_route_id', 'activities')
    op.drop_table('routes')
    op.drop_table('activities')
    op.drop_table('app_settings')
    op.drop_table('user_oauth_links')
    op.drop_table('users')
