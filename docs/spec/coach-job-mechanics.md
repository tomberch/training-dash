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
| Plan generation | `coach_plan_job` | on-demand (API) | per request | yes |

## 2. Plan generation job (MVP)

`coach_plan_job` — **on-demand, API-triggered** (initial generation *and*
regenerate-with-feedback). Crons don't apply.

- **API shape: async 202** — plan-creation returns immediately with a draft placeholder;
  the UI polls draft status (week-chunks completed so far). Rationale: ~8 LLM calls for an
  8-week plan (≤24 with retries, #712) means 2–10 minutes; synchronous HTTP would time out.
- **EnqueueError class: API** (ADR-0006) — enqueue failure → 503, the only coach job in
  this class (it is the only API-triggered one).
- **Content:** header call → week-by-week chunks; heartbeat after every chunk; each chunk
  ≤2 Zod retries (error-embedded), `jsonrepair` salvage, `finish_reason` gate (#712);
  `attribution: generated`.
- **Failure posture:** `retries: 1`; final failure → dead-letter (`coach_plan` in
  `_RETRY_REGISTRY`, admin-retryable) and the draft remains in a failed state with a visible
  "generation failed, retry" affordance in the UI. A week-chunk that exhausts retries may
  escalate to kimi-k3 **for that chunk only** (#712 escalation rule) before the version
  write; exhaustion after escalation dead-letters the job.
- **Timeout:** 1800s (same as adaptation). Version written as one atomic INSERT at the end
  (crash mid-run = nothing persisted; user re-generates).

## 3. Nightly targets job

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

## 4. Weekly adaptation job

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

## 5. Strand handling: none needed

A hung coach job leaves no app-level status row to strand: targets are recomputed wholesale
next night (idempotent), and PlanVersions are single atomic INSERTs at job end (a crash
mid-run writes nothing). The strand-recovery cron is **unchanged**. Sweep-recovery via SAQ
(Swept Job semantics) applies as for any job.

## 6. Config surface

- `coach.vision_model` / `coach.plan_model` / `coach.adapt_model` (AppSettings, #717) read
  at job start; pinned ids logged with every PlanVersion/attribution for auditability.
- Cron definitions live in `worker.py` with the existing five; flags: no new tables, no new
  settings table.

## 7. MVP vs v2

- **MVP:** `coach_nightly_job` (targets + swap-detection stub), **`coach_plan_job`
  (async generation)**, `_RETRY_REGISTRY` additions (`coach_plan`, `coach_adaptation`),
  crons.
- **V2 (same plumbing):** adaptation call content switches on; daily swap becomes active;
  weekly narrative produced. No structural change — v2 is behavior behind the same job
  skeletons, which is why the map's destination can call the spec build-ready.