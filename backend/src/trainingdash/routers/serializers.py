"""Response serializers for API endpoints."""

import json
from typing import Any

from trainingdash.models import (
    Activity,
    HrZone,
    PowerZone,
    Record,
    ThresholdHistory,
    User,
)


def user_response(user: User) -> dict:
    """Return a dict of user info for API responses."""
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "unit_system": user.unit_system,
        "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
        "weight_kg": float(user.weight_kg) if user.weight_kg else None,
        "hr_derived_power_enabled": user.hr_derived_power_enabled,
    }


def user_summary(user: User) -> dict:
    """Return a dict summary of a user for admin responses."""
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat(),
    }


def threshold_response(t: ThresholdHistory) -> dict:
    """Return a dict of threshold info for API responses."""
    return {
        "id": t.id,
        "effective_date": t.effective_date.isoformat(),
        "ftp_watts": t.ftp_watts,
        "lthr_bpm": t.lthr_bpm,
        "hrmax_bpm": t.hrmax_bpm,
    }


def power_zone_response(z: PowerZone) -> dict:
    """Return a dict of power zone info for API responses."""
    return {
        "zone_number": z.zone_number,
        "name": z.name,
        "min_watts": z.min_watts,
        "max_watts": z.max_watts,
        "is_custom": z.is_custom,
    }


def hr_zone_response(z: HrZone) -> dict:
    """Return a dict of HR zone info for API responses."""
    return {
        "zone_number": z.zone_number,
        "name": z.name,
        "min_bpm": z.min_bpm,
        "max_bpm": z.max_bpm,
        "is_custom": z.is_custom,
    }


def activity_summary(a: Activity) -> dict[str, Any]:
    """Return basic activity info for list views."""
    return {
        "id": a.id,
        "title": a.title,
        "title_source": a.title_source,
        "started_at": a.started_at.isoformat(),
        "total_distance_m": a.total_distance_m,
        "moving_time_s": a.moving_time_s,
        "elapsed_time_s": a.elapsed_time_s,
        "elevation_gain_m": a.elevation_gain_m,
        "avg_speed_mps": a.avg_speed_mps,
        "avg_hr_bpm": a.avg_hr_bpm,
        "avg_power_w": a.avg_power_w,
        "max_speed_mps": a.max_speed_mps,
        "max_hr_bpm": a.max_hr_bpm,
        "is_breakthrough": a.is_breakthrough,
    }


def activity_detail(a: Activity) -> dict[str, Any]:
    """Return full activity details including training metrics."""
    result = activity_summary(a)
    result.update({
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
    })
    return result


def records_to_geojson(records: list[Record], props_keys: list[str]) -> dict:
    """Convert record list to GeoJSON FeatureCollection."""
    features = []
    for r in records:
        props = {key: getattr(r, key) for key in props_keys}
        if "timestamp" in props and props["timestamp"] is not None:
            props["timestamp"] = props["timestamp"].isoformat()
        if r.lat is not None and r.lon is not None:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
                "properties": props,
            })
        else:
            features.append({
                "type": "Feature",
                "geometry": None,
                "properties": props,
            })
    return {"type": "FeatureCollection", "features": features}
