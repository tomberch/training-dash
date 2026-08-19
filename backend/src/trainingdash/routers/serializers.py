"""Response serializers for API endpoints."""

import json
from typing import Any

from trainingdash.repositories.postgres.models import (
    Activity,
    RecalculationJob,
    Record,
    User,
)
from trainingdash.routers.datetime_utils import utc_str


def user_response(user: User) -> dict:
    """Return a dict of user info for API responses."""
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_path": user.avatar_path,
        "is_admin": user.is_admin,
        "is_approved": user.is_approved,
        "unit_system": user.unit_system,
        "sync_hour": user.sync_hour,
        "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
        "weight_kg": float(user.weight_kg) if user.weight_kg else None,
        "height_cm": user.height_cm,
        "gender": user.gender,
        "power_zone_percentages": user.power_zone_percentages,
        "hr_zone_percentages": user.hr_zone_percentages,
        "hr_derived_power_enabled": user.hr_derived_power_enabled,
        "map_tile_style": user.map_tile_style,
    }


def user_summary(user: User) -> dict:
    """Return a dict summary of a user for admin responses."""
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "is_admin": user.is_admin,
        "is_approved": user.is_approved,
        "created_at": utc_str(user.created_at),
    }


def activity_summary(a: Activity) -> dict[str, Any]:
    """Return basic activity info for list views."""
    return {
        "id": str(a.id),
        "title": a.title,
        "title_source": a.title_source,
        "started_at": utc_str(a.started_at),
        "utc_offset_minutes": a.utc_offset_minutes,
        "total_distance_m": a.total_distance_m,
        "moving_time_s": a.moving_time_s,
        "elapsed_time_s": a.elapsed_time_s,
        "elevation_gain_m": a.elevation_gain_m,
        "avg_speed_mps": a.avg_speed_mps,
        "avg_hr_bpm": a.avg_hr_bpm,
        "avg_power_w": a.avg_power_w,
        "power_source": a.power_source,
        "max_speed_mps": a.max_speed_mps,
        "max_hr_bpm": a.max_hr_bpm,
        "tss": a.tss,
        "is_breakthrough": a.is_breakthrough,
        "map_polyline": a.map_polyline,
    }


def activity_detail(a: Activity) -> dict[str, Any]:
    """Return full activity details including training metrics."""
    result = activity_summary(a)
    result.update(
        {
            # Training metrics
            "np_power_w": a.np_power_w,
            "intensity_factor": a.intensity_factor,
            "tss": a.tss,
            "training_load": a.training_load,
            # Power source
            "power_source": a.power_source,
            "power_confidence": a.power_confidence,
            # Zone times (parse JSON if present)
            "power_zone_times": json.loads(a.power_zone_times) if a.power_zone_times else None,
            "hr_zone_times": json.loads(a.hr_zone_times) if a.hr_zone_times else None,
            # W'bal
            "wbal_min_joules": a.wbal_min_joules,
            "wbal_min_pct": a.wbal_min_pct,
            # Breakthrough
            "is_breakthrough": a.is_breakthrough,
        }
    )
    return result


def records_to_geojson(records: list[Record], props_keys: list[str]) -> dict:
    """Convert record list to GeoJSON FeatureCollection."""
    features = []
    for r in records:
        props = {key: getattr(r, key) for key in props_keys}
        if "timestamp" in props and props["timestamp"] is not None:
            props["timestamp"] = utc_str(props["timestamp"])
        if r.lat is not None and r.lon is not None:
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
                    "properties": props,
                }
            )
        else:
            features.append(
                {
                    "type": "Feature",
                    "geometry": None,
                    "properties": props,
                }
            )
    return {"type": "FeatureCollection", "features": features}


def recalculation_job_response(job: RecalculationJob) -> dict[str, Any]:
    """Return a dict of recalculation job status for API responses."""
    return {
        "id": job.id,
        "user_id": job.user_id,
        "status": job.status,
        "started_at": utc_str(job.started_at),
        "completed_at": utc_str(job.completed_at) if job.completed_at else None,
        "activities_updated": job.activities_updated,
        "error_message": job.error_message,
    }
