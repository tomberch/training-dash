# Job & Worker Resilience

Status: Accepted

Covers the backend resilience policy for SAQ (Postgres-backed) background jobs, decided in the
job-resilience investigation (map: tomberch/training-dash#685; decisions #687, #688, #689, #690;
SAQ capability research: #686, verified against SAQ 0.26.4 source). The frontend/admin operations
surface is decided separately in #691.

## Context

Jobs run on SAQ 0.26.4 (single `default` queue, single worker container, concurrency 10).
Before this decision set: no job used retries (SAQ default `retries=1` = one attempt, terminal
`failed`); a killed worker process left `saq_jobs` rows orphaned in `active` forever (heartbeat
defaulted to 0, so the sweeper's stuck-test never fired for long jobs); `enqueue_*` helpers in
`jobs.py` silently no-oped when the queue was unavailable and callers skipped jobs with no
signal; app-level status rows (`recalculation_jobs`, `BackupHistory`) stranded in `running`
forever after a worker death — the stranded backup row blocked all future scheduled backups;
and a single 2-hour `batch_weather_job` could occupy many of the 10 concurrency slots, starving
ingest and import jobs.

Key SAQ facts the decisions build on (from #686 research):

- `retries=N` = N **total attempts**; awaiting-retry rows are `queued` with a future
  `scheduled`; `timeout` is per-attempt; swept (crash-recovered) jobs retry if attempts remain.
- SAQ has a built-in stuck-job sweeper (60 s cadence, advisory-lock coordinated) that recovers
  `active` rows past `timeout` **or** `heartbeat`; with `heartbeat=0` and a long timeout,
  crash detection waits the full timeout.
- `group_key` (Postgres-only) guarantees at most one active job per group.
- Cron jobs (`unique=True` → one row keyed `cron:{function}`) never back-run missed ticks.
- Terminal job rows are TTL-deleted after 600 s — failed jobs vanish without a durable record.

## Decisions

### 1. Retry policy (#687)

- All regular jobs: `retries=3` (4 attempts), `retry_delay=30`, `retry_backoff=300`
  (SAQ's jittered exponential, capped at 5 min).
- Cron scheduler jobs (`hourly_import_scheduler`, `hourly_backup_scheduler`,
  `flush_cache_stats`, `prune_old_data`): `retries=2`, flat `retry_delay=60`, no backoff —
  all attempts finish inside the same hourly tick, so scheduler retries never overlap the
  next scheduler window.
- No exception taxonomy (no `NonRetryableError` layer): permanent failures (corrupt FIT,
  bad credentials) raise sub-second and burn attempts cheaply. This is safe because every job
  class is idempotent (ingest/imports dedupe via `source_ref` and duplicate detection
  (`started_at` ±60 s + distance 1%); recalc recomputes; retroactive match checkpoints;
  batch weather skips completed activities; restic is content-dedupe).
- Scheduler-enqueued import/backup jobs carry **hour-bucketed SAQ keys**
  (`import:xert:{user_id}:{YYYY-MM-DDTHH}`) so a retried scheduler tick dedupes at enqueue
  time instead of double-firing per-user jobs. Enqueue helpers accept an explicit `key`
  parameter; **manual user/admin triggers pass no key** (SAQ auto-generates a unique one),
  so "sync now" always enqueues.
- SAQ TTL-deletes terminal rows after 600 s; the `tracked_job` wrapper records a durable
  dead-letter `job.failed` event (job name, key, args, attempts, truncated error) when the
  final attempt fails — the events table is the failure history.

### 2. Stuck-job detection & recovery (#688)

- SAQ's sweeper is the only stuck-job detector; it checks `timeout` **or** `heartbeat`.
  **Heartbeats on long jobs** — `batch_weather_job` 120 s, `backup_job` 60 s,
  `retroactive_match_job` 120 s, import jobs 120 s — with timeouts kept as backstops; job
  bodies refresh via a small shared `job.update()` helper. Crash detection drops from hours
  to ~2 min + sweep cadence. Short jobs stay timeout-only.
- App-table strands (SAQ sweeps only `saq_jobs`): a new **hourly strand-recovery cron** marks
  `recalculation_jobs` rows stuck in `running` past ~2× timeout → `failed`
  ('stuck — recovered by sweeper'), and `BackupHistory` rows stuck in `running` → `failed`
  (a stranded `running` backup blocks all future scheduled backups via `is_backup_running`).
- Missed cron ticks are never back-run by SAQ. Catch-up relies on the existing
  **`last_synced_at` watermark**: the next healthy hourly import tick derives its date range
  from it (minus a 4 h overlap) and converges after any outage. Safeguard: when the scheduler
  sees a scheduled user whose `last_synced_at` is >25 h stale, it writes a `sync.lost_tick`
  event. No tick ledger, no outbox.
- Worker *process* death is infrastructure, not app code: `restart: unless-stopped` on the
  worker service in all compose files + a `saq --check` container healthcheck (exits nonzero
  when no live worker is registered). In-app worker-liveness display is a #691 concern.
- Swept jobs auto-retry via normal SAQ retry logic (effective because of the retry budgets
  above) — **except `backup_job`, which is never auto-retried after a sweep** (a mid-restic
  process death is unverifiable); its history row is marked failed by the strand-recovery
  cron, and the next `schedule_hour` window or a manual re-trigger covers recovery.

### 3. Enqueue-failure handling (#689)

Call-site policy in three classes:

- **User-facing API endpoints** (FIT upload, import triggers, admin trigger-import, backup
  trigger, recalculate): any enqueue failure (`None` or exception) → **503** so the UI can
  prompt a retry. Exception: FIT upload keeps its synchronous fallback (inline ingest).
- **Internal chain steps & best-effort follow-ups** (route→segment chains, retroactive match,
  recalc-after-delete, batch-weather finalize): never raise; log + write a
  **`job.enqueue_failed` event**, plus a **user Notification** when an identifiable user is
  affected (dedupe/throttling of repeat notifications is an implementation concern in #694).
- **Recalculation paths**: fix the stranded-`pending` bug — the `recalculation_jobs` row is
  upserted *before* enqueue; both `None` and exceptions must mark the row `failed`.

Helper contract: `None` on `queue_available()`-false stays, documented as dev/no-queue mode
(never fires in production, where `DATABASE_URL` is always set); real enqueue errors raise a
single typed **`EnqueueError`** from every helper, never swallowed.

Scope note: the SAQ queue lives in the same Postgres as the app DB, so a full DB outage takes
down the API too — this policy covers transient/partial queue failures (pool errors,
serialization failures, pool exhaustion), the realistic case. Lost scheduler ticks rely on the
next hourly tick (imports are idempotent), per #689.

### 4. Queue crowding, timeouts, worker scaling (#690)

- **Single queue + single worker stays.** The three long job classes get SAQ `group_key`
  caps — at most one active job per class: `batch_weather_job` → `batch_weather`,
  `backup_job` → `backup`, `retroactive_match_job` → `retroactive_match`. Worst case 3 of 10
  slots held by long jobs; ingest/import/sync keep 7+ free. A second-worker queue split was
  rejected for now (single-box self-hosting; the backup volume constraint) and can be
  revisited on observed pressure.
- **Cap UX**: a second backfill trigger while one runs → **503 "backfill already running"**
  at enqueue time (reusing the admin endpoint's existing guard pattern); same-group jobs are
  never left silently queued by SAQ's group semantics.
- **Worker scaling**: none for now.
- **Timeout table** (targeted fixes): `match_route_job` and `segment_process_job` get explicit
  `timeout=120` (previously unset → SAQ 10 s default — a latent bug for Hausdorff clustering);
  `ingest_job` 60s → 300s; imports 300s, recalc 300s, retroactive_match 600s, backup 1800s,
  batch_weather 7200s unchanged; dead `enqueue_fetch_weather_job` helper deleted.

## Consequences

- Retry pressure is bounded and scheduler-safe: flat cron budgets keep retries inside the
  hourly tick; hour-bucketed keys prevent duplicate provider imports on scheduler retries.
- The events table becomes the durable job-failure history (SAQ rows are ephemeral);
  the admin surface (#691) reads it for failed-job views and retry/abort actions.
- `EnqueueError` is the single seam callers need to handle; the `None` path remains a
  dev-only convenience and must not grow new meaning.
- The strand-recovery cron makes our own status tables truthful; guards
  (`is_backup_running`) can keep their simple semantics.
- Explicitly rejected and worth not re-proposing: a `NonRetryableError` taxonomy,
  a cron catch-up ledger, a transactional outbox, a dedicated dead-letter table, a
  queue-split/second-worker deployment, and SAQ priority tuning.