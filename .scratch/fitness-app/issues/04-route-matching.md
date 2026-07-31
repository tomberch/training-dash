# 04 — Route matching via Hausdorff + `routes` table

**What to build:** On ingest (post-parse), build the activity's polyline from its records (ordered by timestamp), `ST_Simplify` it to ~50m tolerance, and compare against existing `routes` for the same user via `ST_HausdorffDistance`. If the minimum distance is below a tunable threshold (default ~100m), assign the activity to that route. Otherwise, insert a new `routes` row with this activity's simplified polyline as the representative path and point the activity at it. `route_id` lands on `activities`. Two rides on the same route now share a `route_id`.

**Blocked by:** 01 (tracer-bullet spine — needs ingest and records with geom)

**Status:** ready-for-agent

- [ ] `routes` table exists: `id`, `user_id`, `simplified_polyline` (geography(LINESTRING, 4326)), `first_seen_activity_id`, `ride_count`, `created_at`
- [ ] `activities.route_id` is populated after ingest (run inline for now; ticket 08 moves it off the request path)
- [ ] On ingest, the activity's polyline is built from records, `ST_Simplify`'d to 50m tolerance, and compared to existing same-user routes via `ST_HausdorffDistance`
- [ ] Below threshold → assign to the matching route and increment `ride_count`; above → create a new route
- [ ] Hausdorff threshold is a single tunable constant (default ~100m) — revisit with real data
- [ ] Integration test: two rides on the same route (real `.fit` fixtures) end up with the same `route_id`; two rides on different routes do not
- [ ] Integration test: out-and-back rides match to the same route
- [ ] Unit test: identical polylines → Hausdorff distance zero; parallel-offset polylines → distance equals offset; `ST_Simplify` reduces point count without changing shape