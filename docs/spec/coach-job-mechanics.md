# Coach Spec: Adaptation Job Mechanics (SAQ Wiring)

> Wayfinder ticket #718 (map #706). Appendix to [coach-adaptation-loop.md](coach-adaptation-loop.md):
> how the Coach's jobs ride the existing SAQ machinery. House patterns: `jobs.py` helpers
> (`_enqueue`, `EnqueueError`, `None` = dev/no-queue), ADR-0006 three-class policy, ADR-0007
> retry registry, heartbeat for long jobs, thin-dispatch hourly crons in `worker.py`,
> strand recovery unchanged.

## 1. Job inventory

| Job | Function name | Cadence | Scope | LLM? |
|-----|--------------|---------|-------|------|
| Nightly targets + swap | `coach_nightly_job` | daily, after wellness sync | per user | no |
| Weekly adaptation | `coach_adaptation_job` | weekly, off-peak | per user w/ active plan | yes |

## 2. Nightly targets job

- **Trigger:** thin-dispatch hourly cron `coach_targets_scheduler` (same pattern as
  `hourly_import_scheduler`): matches users whose `sync_hour` was scheduled **the previous
  hour**, enqueues `coach_nightly_job` per user.
- **Ordering guarantee:** runs at `sync_hour + 1` so the nightly Garmin wellness import has
  landed (watermark self-heal) before targets/swap compute — the wellness states the swap
  reads are this night's, not stale.
- **Key (hour-bucketed):** `coach:{user_id}:{YYYY-MM-DDTHH}` — a retried scheduler tick
  dedupes at enqueue time; manual/admin re-trigger omits the key ("run now", like imports).
- **Content (per #716):** ① compute Daily Targets (#714 engine), floor-checked; ② daily swap
  check (wellness states → swap swappable HI → new PlanVersion `adapted_deterministic`);
  single heartbeat between steps. Timeout 300s; no LLM calls inside.
- **EnqueueError class:** internal chains (ADR-0006) → event + notification on failure; API
  never 503s off this job.

## 3. Weekly adaptation job

- **Trigger:** cron `coach_adaptation_scheduler`, hourly thin-dispatch, pinned inside the
  off-peak window per #707 pricing (weekend + weekday nights UTC); user's adaptation_hour
  defaults inside the window. Enqueues `coach_adaptation_job` only for users with an
  `active` plan (pre-filter in dispatch SQL, not in the job).
- **Key:** `coach:adapt:{user_id}:{YYYY-WW}` (ISO week bucket).
- **Content (per #716 two-pass):** deterministic proposer → LLM call(s) deepseek-v4.1-flash
  → deterministic checker. Plan-generation calls (draft/regenerate) reuse the same worker
  function shape with `attribution: generated`; week-by-week chunking per #712 with
  heartbeat after **every** week-chunk (bounded ~25 calls worst case, timeout 1800s).
- **Failure posture:** no retry storm — `retries: 1`; on final failure the job dead-letters
  (`coach_adaptation` entry added to `_RETRY_REGISTRY` for admin retry) and the user sees a
  visible "adaptation didn't run" notification; last targets stay in force (never a broken
  mid-state because PlanVersions are written atomically at the end).
- **EnqueueError class:** internal chains → event + notification.

## 4. Strand handling: none needed

A hung coach job leaves no app-level status row to strand: targets are recomputed wholesale
next night (idempotent), and PlanVersions are single atomic INSERTs at job end (a crash
mid-run writes nothing). The strand-recovery cron is **unchanged**. Sweep-recovery via SAQ
(Swept Job semantics) applies as for any job.

## 5. Config surface

- `coach.vision_model` / `coach.plan_model` / `coach.adapt_model` (AppSettings, #717) read
  at job start; pinned ids logged with every PlanVersion/attribution for auditability.
- Cron definitions live in `worker.py` with the existing five; flags: no new tables, no new
  settings table.

## 6. MVP vs v2

- **MVP:** `coach_nightly_job` (targets + swap-detection stub), plan generation jobs,
  `_RETRY_REGISTRY` additions, crons.
- **V2 (same plumbing):** adaptation call content switches on; daily swap becomes active;
  weekly narrative produced. No structural change — v2 is behavior behind the same job
  skeletons, which is why the map's destination can call the spec build-ready.