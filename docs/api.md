# API Reference

TrainDash exposes a REST API at `/api/*`. All endpoints except `/api/login` and `/api/register` require authentication via session cookie.

## Authentication

### POST /api/login

Authenticate and receive a session cookie.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secret"
}
```

**Response:** `200 OK` with `Set-Cookie: session=...`
```json
{
  "id": 1,
  "email": "user@example.com",
  "is_admin": false,
  "unit_system": "metric"
}
```

### POST /api/logout

Clear the session cookie.

**Response:** `200 OK`
```json
{ "success": true }
```

### POST /api/register

Register a new account. The first registered user becomes admin automatically. Subsequent users may require admin approval depending on app settings.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "secret"
}
```

**Response:** `200 OK` (auto-logged in)

---

## User Profile

### GET /api/me

Get current user info.

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "display_name": "John",
  "is_admin": false,
  "unit_system": "metric",
  "date_of_birth": "1990-01-15",
  "weight_kg": 75.0,
  "sync_hour": 3,
  "hr_power_model": { "status": "ready", "r2": 0.85 }
}
```

### PATCH /api/me

Update user preferences.

**Request:**
```json
{
  "display_name": "John",
  "unit_system": "imperial",
  "date_of_birth": "1990-01-15",
  "weight_kg": 75.0,
  "sync_hour": 3,
  "hr_derived_power_enabled": true
}
```

---

## Activities

### GET /api/activities

List activities with pagination.

**Query params:**
- `page` (default: 1) — Page number
- `per_page` (default: 20, max: 100) — Items per page

**Response:**
```json
{
  "activities": [
    {
      "id": 123,
      "title": "Morning Ride",
      "started_at": "2024-01-15T08:30:00Z",
      "total_distance_m": 45000,
      "moving_time_s": 5400,
      "elevation_gain_m": 450,
      "avg_speed_mps": 8.3,
      "avg_hr_bpm": 145,
      "tss": 85,
      "map_polyline": "encoded_polyline_string"
    }
  ],
  "pagination": {
    "total": 150,
    "page": 1,
    "per_page": 20,
    "total_pages": 8
  }
}
```

### GET /api/activities/:id

Get full activity details including peak powers.

**Response:**
```json
{
  "id": 123,
  "title": "Morning Ride",
  "started_at": "2024-01-15T08:30:00Z",
  "total_distance_m": 45000,
  "moving_time_s": 5400,
  "elapsed_time_s": 5800,
  "elevation_gain_m": 450,
  "avg_speed_mps": 8.3,
  "max_speed_mps": 15.2,
  "avg_hr_bpm": 145,
  "max_hr_bpm": 178,
  "avg_power_w": 185,
  "np_power_w": 195,
  "tss": 85,
  "if_factor": 0.85,
  "route_id": 5,
  "is_breakthrough": false,
  "peaks": [
    {
      "duration_seconds": 5,
      "watts": 850,
      "all_time_pr": 900,
      "pct_of_pr": 94.4,
      "is_pr": false
    }
  ]
}
```

### PATCH /api/activities/:id

Update activity (currently only title).

**Request:**
```json
{ "title": "Epic Mountain Ride" }
```

### DELETE /api/activities/:id

Permanently delete an activity owned by the current user.

Cascades to all child rows (Records, Laps, ActivityPeakPower). Route
`ride_count` is decremented; if the deleted activity was the only one on its
route the route is also removed. If the deleted activity was the
`first_seen_activity_id` of a route, that field is set to `NULL` automatically
(ON DELETE SET NULL). A background job then recomputes the fitness model and
breakthrough flags asynchronously so the response is immediate.

**Response:** `204 No Content`

**Errors:**
- `404 Not Found` — activity does not exist or is not owned by the current user

### POST /api/activities/:id/generate-title

Auto-generate title using geocoding.

### GET /api/activities/:id/records

Get GPS and sensor data as GeoJSON.

**Response:**
```json
{
  "type": "FeatureCollection",
  "activity_id": 123,
  "features": [
    {
      "type": "Feature",
      "geometry": { "type": "Point", "coordinates": [7.45, 46.95] },
      "properties": {
        "timestamp": "2024-01-15T08:30:00Z",
        "distance_m": 0,
        "hr_bpm": 120,
        "power_w": 150,
        "speed_mps": 5.5,
        "altitude_m": 450
      }
    }
  ]
}
```

### GET /api/activities/:id/wbal

Get W'bal (anaerobic capacity) time series.

**Response:**
```json
{
  "wbal_series": [
    { "elapsed_s": 0, "distance_m": 0, "wbal_joules": 15000, "wbal_pct": 100 },
    { "elapsed_s": 60, "distance_m": 500, "wbal_joules": 12000, "wbal_pct": 80 }
  ],
  "w_prime_joules": 15000,
  "ftp_watts": 250,
  "wbal_min_joules": 3000,
  "wbal_min_pct": 20
}
```

### GET /api/activities/:id/same-route

Get other activities on the same route.

**Response:**
```json
{
  "route_id": 5,
  "activities": [
    { "id": 100, "title": "Previous Ride", "started_at": "2024-01-10T09:00:00Z" }
  ]
}
```

### GET /api/activities/:id/compare?other=:other_id

Compare two activities on the same route.

**Response:**
```json
{
  "comparable": true,
  "gap_series": [
    { "distance_m": 0, "gap_seconds": 0 },
    { "distance_m": 1000, "gap_seconds": -5 }
  ],
  "other_geojson": { "type": "FeatureCollection", "features": [...] }
}
```

### POST /api/upload

Upload a FIT file.

**Request:** `multipart/form-data` with `file` field

**Response:** `202 Accepted` (async processing)
```json
{ "job_id": "abc123", "source_ref": "morning_ride.fit" }
```

Or `200 OK` (sync processing if Redis unavailable)
```json
{ "id": 123, "started_at": "2024-01-15T08:30:00Z" }
```

### GET /api/jobs/:job_id

Check upload job status.

**Response:**
```json
{
  "status": "complete",
  "result": { "activity_id": 123 }
}
```

---

## Analytics

### GET /api/pmc

Get Performance Management Chart data.

**Query params:**
- `start` — Start date (YYYY-MM-DD, default: 12 weeks ago)
- `end` — End date (YYYY-MM-DD, default: today)

**Response:**
```json
[
  {
    "date": "2024-01-15",
    "tss": 85,
    "ctl": 45.2,
    "atl": 62.1,
    "tsb": -16.9
  }
]
```

### GET /api/power-curve

Get best power at each duration.

**Query params:**
- `start` — Filter start date (optional)
- `end` — Filter end date (optional)

**Response:**
```json
[
  {
    "duration_seconds": 5,
    "watts": 900,
    "achieved_date": "2024-01-10",
    "days_ago": 5
  },
  {
    "duration_seconds": 60,
    "watts": 400,
    "achieved_date": "2024-01-12",
    "days_ago": 3
  }
]
```

### GET /api/records

Get lifetime and per-route PRs.

**Response:**
```json
{
  "lifetime_prs": {
    "longest_distance_m": { "value": 150000 },
    "longest_moving_time_s": { "value": 18000 },
    "max_speed_mps": { "value": 18.5 },
    "biggest_elevation_gain_m": { "value": 2500 },
    "highest_sustained_power_w": { "value": 280 },
    "fastest_5000_m": { "value": 540, "activity_id": 45 },
    "fastest_10000_m": { "value": 1150, "activity_id": 67 }
  },
  "route_prs": [
    {
      "route_id": 5,
      "route_label": "2024-01-01",
      "fastest_time_s": 3200,
      "activity_id": 123
    }
  ]
}
```

### GET /api/fitness

Get current fitness model (PP, W', CP).

**Response:**
```json
{
  "current": {
    "computed_at": "2024-01-15T10:00:00Z",
    "pp_watts": 900,
    "w_prime_joules": 15000,
    "cp_watts": 250
  },
  "history": [...]
}
```

---

## User Settings

### GET /api/me/thresholds

Get threshold history (FTP, LTHR, HRmax).

**Response:**
```json
[
  {
    "id": 5,
    "effective_date": "2024-01-01",
    "ftp_watts": 250,
    "lthr_bpm": 165,
    "hrmax_bpm": 185,
    "is_auto_calculated": false
  }
]
```

### POST /api/me/thresholds

Create a new threshold entry.

**Request:**
```json
{
  "effective_date": "2024-01-15",
  "ftp_watts": 260,
  "lthr_bpm": 168,
  "hrmax_bpm": 185
}
```

### GET /api/me/zones

Get power and HR zones.

### PUT /api/me/zones

Update zones or reset to defaults.

**Request:**
```json
{
  "reset_to_defaults": true
}
```

Or update specific zones:
```json
{
  "power_zones": [
    { "zone_number": 4, "name": "Threshold", "min_value": 240, "max_value": 280 }
  ]
}
```

---

## Integrations

### GET /api/me/xert-credentials

Check Xert integration status.

**Response:**
```json
{
  "configured": true,
  "xert_email": "user@example.com",
  "sync_since": "2024-01-01"
}
```

### PUT /api/me/xert-credentials

Configure Xert integration. Validates credentials via login attempt.

**Request:**
```json
{
  "xert_email": "user@example.com",
  "xert_password": "secret",
  "sync_since": "2024-01-01"
}
```

### DELETE /api/me/xert-credentials

Disconnect Xert integration.

### GET /api/me/garmin-credentials

Check Garmin integration status.

### PUT /api/me/garmin-credentials

Configure Garmin integration. May return `{ "mfa_required": true }`.

**Request:**
```json
{
  "garmin_email": "user@example.com",
  "garmin_password": "secret",
  "sync_since": "2024-01-01"
}
```

### POST /api/me/garmin-credentials/mfa

Complete Garmin MFA.

**Request:**
```json
{ "mfa_code": "123456" }
```

### DELETE /api/me/garmin-credentials

Disconnect Garmin integration.

### POST /api/me/import/garmin

Trigger manual Garmin import.

### POST /api/me/import/xert

Trigger manual Xert import.

---

## Admin Endpoints

All admin endpoints require `is_admin: true`.

### GET /api/admin/users

List all users.

### POST /api/admin/users

Create a new user.

**Request:**
```json
{
  "email": "newuser@example.com",
  "password": "secret"
}
```

### POST /api/admin/users/:id/reset-password

Reset a user's password.

### POST /api/admin/users/:id/import

Trigger import for a user (both Garmin and Xert if configured).

### GET /api/admin/users/:id/nuke-preview

Preview what would be deleted for each nuke action.

### POST /api/admin/users/:id/nuke/activities

Delete all activities for a user. Requires email confirmation.

**Request:**
```json
{ "confirm_email": "user@example.com" }
```

### POST /api/admin/users/:id/nuke/integrations

Delete all integration credentials for a user.

### POST /api/admin/users/:id/nuke/account

Delete a user account entirely.

### GET /api/admin/settings

Get app settings.

### PUT /api/admin/settings/:key

Update an app setting (e.g., `require_approval`).

---

## Map Tiles

Tile proxy endpoints that cache map tiles to disk for 30 days, reducing load on
upstream providers and improving repeat-load performance.

### GET /tiles/{z}/{x}/{y}.png

Proxy and cache an OpenStreetMap raster tile.

**Path params:** `z` (zoom 0–19), `x`, `y` (valid tile coordinates for the zoom level)

**Response:** `200 OK` — PNG image with headers:
- `Cache-Control: public, max-age=2592000`
- `X-Cache: HIT` (served from disk) or `MISS` (fetched from upstream)

**Errors:** `400` invalid zoom or coordinates · `502` upstream unreachable

---

### GET /tiles/carto/{style}/{z}/{x}/{y}.png

Proxy and cache a CartoDB raster tile. Used by the frontend for theme-aware map
backgrounds (Positron for light theme, Dark Matter for dark theme).

**Path params:**
- `style` — `light` (CartoDB Positron) or `dark` (CartoDB Dark Matter)
- `z`, `x`, `y` — zoom level and tile coordinates (same constraints as OSM endpoint)

**Response:** `200 OK` — PNG image with the same `Cache-Control` and `X-Cache` headers.

**Errors:** `400` unknown style, invalid zoom, or invalid coordinates · `502` upstream unreachable

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common status codes:
- `400 Bad Request` — Invalid input
- `401 Unauthorized` — Not authenticated
- `403 Forbidden` — Not authorized (e.g., non-admin accessing admin endpoints)
- `404 Not Found` — Resource doesn't exist or not owned by user
- `500 Internal Server Error` — Server error
