# Admin Job Operations Surface

Status: Accepted

Decides the admin frontend surface for job/worker operations. Extends ADR 0006 (job &
worker resilience) — the backend decisions there determine what this surface can show and do.
Decided in map tomberch/training-dash#685 (ticket #691).

## Context

`SystemDashboard.tsx` (`/admin/system`) already shows active/queued SAQ jobs (view-only),
a filterable system event log, and cache stats. The `/api/admin/system/jobs` endpoint filters
`status IN ('active','queued')` — failed, aborted, and stuck jobs are invisible. ADR 0006
introduced dead-letter `job.failed` events (with job args, since SAQ TTL-deletes terminal rows),
`job.enqueue_failed` and `sync.lost_tick` events, worker liveness via `queue.info()`, and
cross-process `queue.abort()`. Admin usage of this surface is episodic — investigating a failed
sync, freeing a wedged job — not a daily queue console.

## Decision

**Extend SystemDashboard; no new page.** The dashboard already holds the ingredients (live
jobs, event log, cache stats); a dedicated Jobs page would duplicate the event log and add
navigation for rarely-used functionality. If it outgrows the dashboard, a dedicated page can be
spun out later.

**Actions — three, no more:**

1. **Retry** — re-enqueue a failed job from its dead-letter event payload (job name + args);
   the retried run gets a fresh SAQ key so it always fires.
2. **Abort** — `queue.abort(key)` on a stuck/`active` job; SAQ delivers the abort cross-process
   within ~1 s (two-phase: `aborting` → `aborted`).
3. **Resync** — re-run the existing admin trigger-import endpoint for a user.

No **Edit&Replay**: editing job kwargs before re-enqueueing is an attack surface and a footgun
(edited args run unvalidated). If a job needs different arguments, use Resync or fix code.

**Safety model:**

- All three actions are admin-only (existing `AdminUser` dependency) and **all three write
  Audit Log entries** (`action` ∈ `job.retry` / `job.abort` / `user.resync`, `details` carrying
  the job key / target user). This resolves how job operations interact with the Audit Log:
  job ops are audited like nukes, just with lighter guards.
- Exactly **one confirmation dialog**: aborting a job that is currently `active` — "this will
  cancel a running job; data may be partially written." Retry and Resync merely enqueue work.
- Aborting a mid-run `backup_job` **is allowed** (an admin watching a wedged backup needs an
  escape hatch); it is audited, and the strand-recovery cron (ADR 0006) marks its
  `BackupHistory` row failed. No type-the-email guard — job operations are scoped and
  effectively reversible, unlike Nukes.

**Read surface — five additions, no trend charts:**

1. **Worker liveness** row — from `queue.info()`: number of live workers and last heartbeat age.
2. **Failed/stuck jobs** — the `/jobs` endpoint grows `failed` + `aborted` statuses (SAQ retains
   terminal rows ~600 s, so this shows the recent tail), each with an **attempts** count.
3. **Dead-letter feed** — the existing event log, with the new event types (`job.enqueue_failed`,
   `sync.lost_tick`) filterable and dead-letter `job.failed` events carrying the args Retry needs.
4. **Per-user last-sync** — a column in the AdminView user table showing `last_synced_at`
   from the integration credentials rows.
5. Stranded `recalculation_jobs`/`BackupHistory` rows need no extra UI — the strand-recovery
   cron (ADR 0006) turns them into failed rows visible in existing status surfaces.

Failure-trend charts are explicitly not built now (YAGNI for episodic admin use; the filterable
event log covers investigation).

## Consequences

- Backend additions for #694: `POST /api/admin/system/jobs/{key}/retry`,
  `POST /api/admin/system/jobs/{key}/abort`, worker-liveness field on the jobs response,
  status filter + attempts on `/jobs`, `last_synced_at` in the admin user response, and the
  three Audit Log actions.
- Frontend additions for #695: jobs-card status filter + attempts + action buttons (with the
  one confirm), event-log filter options for the new event types, worker-liveness row,
  last-sync column in AdminView.
- Deliberately rejected: dedicated jobs page, Edit&Replay, confirm dialogs on every action,
  trend charts.