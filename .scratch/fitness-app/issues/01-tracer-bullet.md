# 01 — Tracer-bullet: upload → parse → store → activity detail with map + auth

**What to build:** A logged-in user uploads a `.fit` file through a form in the app; the file parses with `fit-tool`, writes `activities` + `laps` + `records` (with a nullable PostGIS `geom` column on records) to Postgres/PostGIS, and the activity detail page renders a map with the route polyline plus summary stat tiles (total distance, moving time, elevation gain, avg speed). Admin-provisioned auth stands up here: session login, one seed user (created via CLI or migration — no admin screen yet). One time-axis speed chart renders to prove the chart path end-to-end. This ticket stands up the whole architectural spine: Postgres+PostGIS, FastAPI, React+Vite, Docker Compose (app + db, no Redis yet).

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [ ] `docker compose up` starts the app and a Postgres+PostGIS container; the app connects to the DB
- [ ] A seed user exists (created via migration or CLI), and `POST /login` with that user's credentials returns a session cookie
- [ ] `GET /activities` and `GET /activities/:id` require auth; unauthenticated requests are rejected
- [ ] `POST /upload` accepts a `.fit` file from an authenticated user and returns the new activity's id
- [ ] The uploaded FIT is parsed with `fit-tool`: semicircles→degrees, FIT epoch (1990-12-31)→UTC, units confirmed (watts unscaled, m/s not km/h)
- [ ] `activities` (summary row), `laps`, and `records` (one per FIT record, with nullable `geom geography(POINT, 4326)`) are written, attributed to the authenticated user
- [ ] Raw FIT bytes are stored on the `activities` row
- [ ] A `.fit` file without GPS data still parses and stores (records with null `geom`); activity detail shows summary stats
- [ ] The activity detail page renders a map with the route polyline (from records with non-null geom)
- [ ] The activity detail page renders summary stat tiles (distance, moving time, elevation gain, avg speed)
- [ ] The activity detail page renders one time-axis speed chart
- [ ] Integration test: upload a real `.fit` fixture, assert activity + records rows exist with correct lat/lon/hr/power/alt, assert `GET /activities/:id` returns the summary and GeoJSON for the map
- [ ] Unit tests: FIT parser unit conversions (semicircles→degrees, FIT epoch, watts, m/s), missing optional fields yield null not crash
- [ ] Component test: activity detail renders map polyline from GeoJSON and the speed chart on time axis