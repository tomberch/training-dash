# 08 — arq + Redis: move ingest and route-matching off the request path

**What to build:** Add a Redis container to the Docker Compose file. Introduce a separate arq worker process that runs background jobs. Move `ingest_fit` (parse + store) and `match_route` (Hausdorff matching) off the request path and into the worker. The upload endpoint enqueues an `ingest_fit` job and returns immediately with a job id; `match_route` is enqueued automatically when `ingest_fit` completes. The activity detail page polls job status or shows a "processing" state until ingest is done. Jobs persist in Redis, survive restart, and retry on failure.

**Blocked by:** 04 (route matching — the ingest→match job chain is defined here; moving it off-thread only makes sense once it exists)

**Status:** ready-for-agent

- [ ] Redis container added to `docker compose`; app and worker both connect to it
- [ ] arq worker process runs alongside the FastAPI app (separate compose service)
- [ ] `POST /upload` enqueues an `ingest_fit` job and returns a job id immediately (202 Accepted)
- [ ] `ingest_fit` job parses and stores; on success enqueues `match_route` for the new activity
- [ ] `match_route` job runs Hausdorff matching and sets `route_id`
- [ ] `GET /activities/:id` indicates when ingest is still processing (job status pending); activity detail shows a "processing" state
- [ ] Jobs persist in Redis and survive a worker restart; retried on failure
- [ ] Integration test: upload enqueues a job, worker processes it, activity appears with records and `route_id` once both jobs complete
- [ ] Integration test: killing the worker mid-job and restarting does not lose the job (it re-runs)