# Fitter — Self-Hosted Fitness Analysis App

**Status:** ready-for-agent

## Problem Statement

I want to see my ride history the way Garmin Connect, TrainingPeaks, Golden Cheetah, and Strava show it — a plethora of stats and charts, a map when GPS data is available, and especially the ability to compare rides along the same route and see, segment by segment, where I was faster or slower. I also want records (longest ride, fastest time on a given route). The commercial options are closed, cloud-only, and don't give me control over my own data or the comparison features I actually care about. I want a self-hosted app, running on my home server, that my family (~5 trusted members) and I can use to sync FIT files from Xert, see rich analysis, and compare rides — with my data staying at home.

## Solution

A self-hosted web application, deployed via Docker Compose on a home server, that ingests FIT activity files (auto-synced from Xert per user, or manually uploaded through an authenticated form), parses them into structured rows in Postgres+PostGIS, and presents each user's activities through a React single-page app: a map with metric-colored polyline, charts toggleable between time and distance axes, route matching via Hausdorff distance to group same-route rides, a continuous time-gap-vs-distance curve for comparing two rides on the same route, and lifetime plus per-route records. Authentication is admin-provisioned per-user; sync credentials are encrypted at rest and decrypted only inside background jobs.

## User Stories

1. As a family member, I want to log in with credentials my admin created for me, so that I see only my own activities.
2. As the admin, I want to create accounts for my family members from a private admin screen, so that they can log in without self-serve signup.
3. As the admin, I want to reset a family member's password from the admin screen, so that I can help them when they forget it.
4. As a logged-in user, I want to upload a `.fit` file through a form in the app, so that the activity is parsed and attributed to me.
5. As a logged-in user, I want to see a list of my activities newest-first with totals (distance, moving time, elevation gain), so that I can browse my history.
6. As a logged-in user, I want to open an activity and see a map with the route polyline, so that I can see where I rode.
7. As a logged-in user, I want the map polyline colored by a chosen metric (speed, HR, power, or time-gap in comparison mode), so that I can see where I was faster or slower at a glance.
8. As a logged-in user, I want charts of HR, power, speed/pace, and elevation over time, so that I can relive a single ride on the time axis.
9. As a logged-in user, I want to toggle any chart between time and distance axes, so that I can analyze the same data in either frame without leaving the activity.
10. As a logged-in user, I want the activity detail to show summary stats (total distance, moving time, elevation gain, average speed, average HR, average power, NP/XP if available), so that I get the headline numbers at a glance.
11. As a logged-in user, I want two rides matched as "the same route" when their simplified polylines are within a tunable Hausdorff distance, so that I can find other rides on a route I care about without manual labeling.
12. As a logged-in user, I want to select a second ride to compare against the current one and see a continuous time-gap-vs-distance curve, so that I can see exactly where I gained or lost time across the route.
13. As a logged-in user, when comparison mode is active I want the map polyline to color by time-gap (green where faster, red where slower), so that the geography and the curve tell the same story.
14. As a logged-in user, I want my lifetime PRs (longest ride by distance, longest ride by time, fastest 5/10/40km point-to-point, max speed, max HR, biggest elevation gain, highest sustained power if available) computed from my activity summaries, so that I can see my personal bests.
15. As a logged-in user, I want per-route PRs (fastest time on Route X) computed once route matching has grouped my rides, so that I can chase a specific route record.
16. As a logged-in user, I want to see only my own records and activities, so that family members' data stays isolated from mine.
17. As the admin, I want to store my Xert credentials (username and password) encrypted at rest, so that a nightly job can sync my activities automatically.
18. As a family member, I want to store my Xert credentials encrypted at rest on my user row, so that a nightly job syncs my activities automatically too.
19. As any user, I want the nightly Xert sync to log in as me, pull new activities, parse them, and attribute them to my account, so that I never have to manually upload.
20. As any user, I want the Xert sync to skip activities already imported, so that I don't get duplicates after re-syncs.
21. As any user, I want the raw FIT bytes kept after parsing, so that a parser fix or a new derived metric can be backfilled from the original file without losing fidelity.
22. As any user, I want activities without GPS to still parse and show summary stats and charts, so that indoor/trainer rides are not rejected.
23. As the admin, I want the app to run as `docker compose up` on the home server, so that it survives reboots and updates with a single command.
24. As the admin, I want the compose file to contain the app, Postgres+PostGIS, and Redis — with no reverse proxy — so that I control exposure myself.
25. As any user, I want manual uploads and auto-synced activities to flow through the same ingest pipeline, so that there is one code path for parsing and storage.

## Implementation Decisions

### Stack and runtime

- **Backend:** Python + FastAPI. One process serves the HTTP API; a separate arq worker process runs background jobs. Both share the same codebase.
- **Frontend:** React + Vite, single-page application, served as static assets by FastAPI or a CDN-bundled build step. Consumes the FastAPI JSON API.
- **Storage:** Postgres with the PostGIS extension. One container in the compose file.
- **Jobs:** arq (asyncio-native RQ-alike) backed by Redis. One Redis container in the compose file. Jobs persist in Redis, survive restart, and retry on failure.
- **FIT parsing:** `fit-tool` (pure Python, maintained). Reads FIT message types as objects; the ingest loop iterates records and laps directly.
- **Deployment:** Docker Compose on a home server. Three services: `app` (FastAPI), `worker` (arq), `db` (Postgres+PostGIS). Plus `redis`. No reverse proxy — the app exposes itself directly; the admin handles TLS/exposure.

### Database schema

- `users` — `id`, `username`, `password_hash`, `is_admin`, `created_at`. Admin-provisioned; no self-serve signup column.
- `xert_credentials` — `user_id` (FK), `username`, `encrypted_password`, `updated_at`. The encryption key lives in an env var / docker secret, never in the DB.
- `activities` — `id`, `user_id` (FK), `source` (`upload`/`xert`), `source_ref` (Xert activity ID or upload filename), `started_at`, `total_distance_m`, `moving_time_s`, `elapsed_time_s`, `elevation_gain_m`, `avg_speed_mps`, `avg_hr_bpm`, `avg_power_w`, `np_power_w` (nullable), `max_speed_mps`, `max_hr_bpm`, `route_id` (nullable, set after matching), `raw_fit` (bytea — the original file bytes), `created_at`.
- `laps` — `id`, `activity_id` (FK), `lap_index`, `start_time`, `end_time`, `total_distance_m`, `avg_hr_bpm`, `avg_power_w`, `max_hr_bpm`.
- `records` — `id`, `activity_id` (FK), `timestamp`, `lat`, `lon`, `distance_m` (cumulative), `hr_bpm`, `power_w`, `speed_mps`, `altitude_m`, `cadence_rpm`, `geom` (`geography(POINT, 4326)` — nullable for no-GPS activities). Indexed with a GiST index for route-matching queries.
- `routes` — `id`, `user_id` (FK), `simplified_polyline` (`geography(LINESTRING, 4326)` — the `ST_Simplify`'d representative path), `first_seen_activity_id`, `ride_count`, `created_at`. One row per discovered route cluster.
- `records_table` for PRs is not a separate table — lifetime PRs are computed by SQL aggregations over `activities`; per-route PRs by `min(elapsed_time_s) ... GROUP BY route_id, user_id`.

### Ingest pipeline

One code path, invoked by both the upload endpoint and the Xert sync job:
1. Read FIT bytes (from upload body or Xert download).
2. Parse with `fit-tool`; iterate records and laps.
3. Write `activities` summary row (computed from session message + lap rollups), `laps` rows, and `records` rows (one per FIT record message). Convert semicircles→degrees, FIT epoch (1990-12-31)→UTC, and confirm units (watts unscaled, m/s not km/h).
4. Keep raw FIT bytes in `activities.raw_fit`.
5. Enqueue a follow-up `match_route` job (arq) that computes `ST_Simplify` on the new activity's polyline and runs `ST_HausdorffDistance` against existing `routes` for this user. If below threshold (default ~100m, tunable per user later), set `activities.route_id`; otherwise insert a new `routes` row and point the activity at it.

### Route matching

- On ingest (post-parse), build the activity's polyline from `records` ordered by timestamp.
- `ST_Simplify` to ~50m tolerance to kill GPS noise.
- Compare against candidate `routes` for the same user via `ST_HausdorffDistance(simplified_activity_polyline, route.simplified_polyline)`. Candidates can be pre-filtered by bounding box and start/end cluster for index efficiency.
- If the minimum Hausdorff distance is below the threshold, assign the activity to that route. Otherwise, create a new route row with this activity's simplified polyline as the representative path.
- Threshold is a single tunable; revisit with real data. If Hausdorff alone underperforms, layer a start/end/bbox pre-filter (cheap, indexed) before the Hausdorff score.

### Comparison

- When a user selects a second activity to compare against the current one (both must share a `route_id`):
  - Resample both rides' `records` to a common distance axis (every 50m of route distance traveled) using cumulative `distance_m`.
  - At each bucket, compute the difference in cumulative elapsed time between the two rides.
  - Return the time-gap series as JSON: `[{ distance_m: 0, gap_s: 0 }, ...]`.
  - The frontend renders a single line: positive = current ride is slower (behind), negative = faster (ahead), plotted against distance.
- The map polyline in comparison mode colors by the per-bucket gap value (green/red).

### Auth

- Session-based auth. Admin-provisioned accounts only; no signup endpoint.
- `POST /login` (username + password) → session cookie.
- Admin-only endpoints: `POST /admin/users` (create account), `POST /admin/users/:id/reset-password`.
- All activity endpoints require auth and scope reads/writes to the authenticated user's `user_id`.
- Data isolation enforced at the query layer: every `activities`/`records`/`routes` query filters by `user_id = current_user.id`.

### Background jobs (arq + Redis)

- `ingest_fit(user_id, fit_bytes, source, source_ref)` — parse and store. Enqueued by the upload endpoint and the sync job.
- `match_route(activity_id)` — run Hausdorff matching for one activity, set `route_id`. Enqueued after `ingest_fit` completes.
- `sync_xert(user_id)` — decrypt the user's stored Xert credentials, log in to Xert, pull activities not yet imported, enqueue `ingest_fit` for each. Scheduled nightly per user with stored credentials; also manually triggerable from the UI.

### Frontend (React + Vite)

- **Activity list** — table of the user's activities newest-first with totals.
- **Activity detail** — map (MapLibre or Leaflet) with the route polyline colored by a chosen metric; charts (HR, power, speed/pace, elevation) with a per-chart toggle between time and distance axes; summary stat tiles.
- **Route comparison** — when a second same-route activity is selected, the map polyline recolors by time-gap and the time-gap-vs-distance curve renders alongside.
- **Records** — lifetime PRs always visible; per-route PRs visible once matching has run.
- **Admin screen** — create/reset user accounts; trigger a user's Xert sync manually.

### Sync credentials

- Per-user Xert credentials stored in `xert_credentials` as `encrypted_password` (AES via a key in the `FITTER_ENCRYPTION_KEY` env var / docker secret).
- Decryption happens only inside the `sync_xert` job, never in any HTTP response path.
- The Xert export API shape is a **research ticket** — confirm how Xert exposes FIT downloads before building the sync job. Until then, manual upload is the only input path.

### Out-of-process assumptions

- Xert's actual export endpoint shape is unknown and deferred to a research ticket. The `sync_xert` job interface is specified; its internals depend on what the research finds.

## Testing Decisions

### What makes a good test

Only test external behavior, not implementation details. A test should survive a refactor that preserves the API contract and DB shape. Tests assert on HTTP responses, DB rows, and rendered component output — never on internal function call counts or private method names.

### Seams

**Seam 1 — FastAPI HTTP integration (primary):** `pytest` + `testcontainers` spins a real Postgres/PostGIS image per session. Tests hit real endpoints (`POST /upload`, `GET /activities`, `GET /activities/:id`, `GET /activities/:id/compare?other=:id2`, `GET /records`) and assert on DB rows + API response shape. Covers ingest → parse → store → PostGIS query → API in one seam. Fixture: real `.fit` files committed under `tests/fixtures/`.

Example tests: `test_upload_fit_returns_201_and_activity_id`, `test_uploaded_fit_writes_records_with_lat_lon_alt_hr_power`, `test_two_rides_same_route_matched_with_low_hausdorff_distance`, `test_time_gap_curve_two_same_route_rides_aligned_by_distance`, `test_longest_ride_record_computed_from_activity_summary`, `test_user_a_cannot_see_user_b_activities`, `test_login_with_admin_provisioned_credentials_returns_session`.

**Seam 2 — Pure-function unit (`pytest`, no DB):** Isolated tests for the FIT parser mapper, the distance resampler, the Hausdorff threshold logic, and the encryption helpers. Fast, no I/O. These catch silent unit/encoding bugs (semicircles not converted, FIT epoch wrong, power scaled wrong) that would corrupt data without crashing.

Example tests: `test_parse_record_message_maps_lat_lon_semicircles_to_degrees`, `test_parse_timestamp_uses_fit_epoch_1990_offset`, `test_resample_by_distance_50m_buckets_uniform_points`, `test_time_gap_curve_handles_different_total_distances_truncates_to_min`, `test_identical_polylines_distance_zero`, `test_encrypt_then_decrypt_round_trip`.

**Seam 3 — React component (`vitest`, mocked API):** Component tests with API responses mocked to a known shape. Catches rendering bugs (axis toggle swaps wrong, polyline colors inverted, chart series misaligned) without wiring real HTTP.

Example tests: `renders_map_with_polyline_from_geojson`, `toggles_to_distance_axis_on_button_click`, `renders_time_gap_curve_green_where_faster_red_where_slower`, `renders_lifetime_prs_from_user_summary`.

### Prior art

Greenfield repo — no existing tests to match. The integration tests establish the project's test conventions; later tickets follow their shape.

## Out of Scope

- **Strava-style social feed** — no cross-user activity feed, likes, kudos, or comments.
- **Cross-user leaderboards** — records are per-user; a family ranked board is not built.
- **Strava segments** — auto-detected named segments (climb, sprint, descent) and their PRs. Deferred to a later ticket once the time-gap curve and route matching have shipped and the user knows which stretches to name.
- **Workout planning** — no structured training plan authoring (the TrainingPeaks feature). This app is read-mostly analysis.
- **Auto-sync from Garmin Connect** — Garmin has no official public pull API; scraping is deferred. Manual FIT upload covers Garmin-only activities for now.
- **Route fingerprinting / DTW** — custom route-matching algorithms beyond Hausdorff. Reach for only if Hausdorff underperforms on real data.
- **Climb/descent auto-detection and hill shading** — the map colors by metric only; auto-detected sustained-grade regions are a later enhancement.
- **Mobile-native apps** — the SPA is responsive but there is no iOS/Android build.
- **Multi-tenant public signup** — accounts are admin-provisioned only; no self-serve registration or email verification flow.
- **Reverse proxy in compose** — no Caddy/Traefik; the admin handles TLS and exposure.

## Further Notes

### Deferred research ticket

**Xert export API shape** — before the `sync_xert` job can be implemented, research how Xert exposes a user's activity FIT files for download (endpoint, auth flow, pagination, rate limits). The job's interface is specified in this spec; its internals depend on the research findings. Until then, manual upload is the only input path and the sync job is a stub.

### Suggested build order

1. Tracer-bullet slice (Q20): FIT upload form → parse with `fit-tool` → write `activities`+`records` → FastAPI endpoint → React activity detail with map polyline + admin-provisioned auth + one time-axis chart. Proves every architectural seam in one thin vertical slice.
2. Remaining chart series (power, HR, speed/pace, elevation) + the time/distance axis toggle per chart.
3. Route matching via Hausdorff + `routes` table + `route_id` assignment on ingest.
4. Comparison mode: second-ride selection, time-gap-vs-distance curve, map recolor by gap.
5. Lifetime PRs from summary columns.
6. Per-route PRs once matching exists.
7. arq + Redis wired; `ingest_fit` and `match_route` moved off the request path into the worker.
8. Xert sync job (after the research ticket resolves).
9. Admin screen (user provisioning, password reset, manual sync trigger) — may land earlier if needed for testing.

### Open tunables

- Hausdorff threshold (default ~100m on simplified polylines) — revisit with real ride data.
- Distance resample bucket size (default 50m) — revisit based on chart smoothness.
- Map polyline color scale — TBD with real HR/power/time-gap distributions.