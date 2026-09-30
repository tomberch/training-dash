# TrainingDash — Domain Glossary

## Swept Job

A job that SAQ's built-in sweeper killed and recovered after its worker became unresponsive (crash or hang) — detected via stale `timeout` or `heartbeat`. Swept jobs are retried automatically if attempts remain, except backups. The retry row's error reads `swept`.
_Avoid_: orphaned job, zombie job

## Stuck Job

A job whose execution has stopped making progress: past its `timeout`, or past its `heartbeat` without a refresh. Detected by SAQ's sweeper; distinct from a *failed* job (which raised an error on its own).
_Avoid_: hung job, dead job

## Heartbeat

The freshness signal a long-running job must renew (`job.update()`) to prove it is alive. Long jobs carry one; a stale heartbeat marks the job stuck.
_Avoid_: liveness ping, healthcheck (container-level liveness uses `saq --check`)

## Dead Letter

The durable event written when a job exhausts its attempts. SAQ TTL-deletes terminal job rows, so the `job.failed` event (with name, key, args, attempts, error) is the permanent failure record.
_Avoid_: dead-letter queue (we keep no separate queue)

## Strand

An app-level status row left in a non-terminal state (`running`/`pending`) because its worker died — e.g. a `RecalculationJob` or `BackupHistory` row. Fixed by the strand-recovery cron, not by SAQ.
_Avoid_: orphan, stuck row

## EnqueueError

The single typed error raised by every `enqueue_*` helper when enqueueing actually fails (queue unreachable, serialization). Callers handle it per the three-class policy: 503 (API), event + notification (internal chains), or `mark_failed` (recalculation paths). `None` from a helper is not an error — it is the dev/no-queue signal.
_Avoid_: queue error, job error

## Hour-Bucketed Key

The SAQ idempotency key given to scheduler-enqueued import/backup jobs (`import:xert:{user_id}:{YYYY-MM-DDTHH}`), making a retried scheduler tick dedupe at enqueue time. Manual triggers deliberately omit the key so "sync now" always fires.
_Avoid_: dedupe key (SAQ-level uniqueness, but the hour bucket is our convention)

## Watermark

The `last_synced_at` timestamp on integration credentials from which each import derives its date range. It makes missed cron ticks self-healing: the next healthy tick imports the missed window automatically.
_Avoid_: checkpoint (that word is reserved for retroactive segment matching)

## Nuke

An admin-only destructive action that permanently deletes a user's data. Three variants exist:

- **Reset Activities** — deletes activities, records, laps, peaks, routes, fitness history, and notifications. Preserves the user account, credentials, and threshold/zone settings.
- **Disconnect Integrations** — deletes Garmin and Xert credentials only. Preserves all other data.
- **Delete User** — deletes the user account and all associated data.

All nuke actions are hard deletes (no soft delete or trash can). A safety mechanism requires the admin to type the target user's email after seeing a count preview. Each nuke is recorded in the Audit Log.

## Audit Log

A record of destructive admin actions. Stores who performed the action, what action was taken, which user was affected, a summary of what was deleted, and when. Does not store the actual deleted data — only metadata about the operation.

## User

A person with an account in the system. Users are provisioned by an Admin; there is no self-serve signup. Each User owns their own Activities, Records, and Routes — data is isolated per user.

## Admin

A User with `is_admin = true`. Admins can create accounts, reset passwords, and trigger syncs for other users. Admins cannot access other users' preferences or credentials.

## Preferences

Per-user display settings stored on the User record. Currently includes:

- **Unit System** — either *Metric* (km, m, km/h) or *Imperial* (mi, ft, mph). Affects all distance, elevation, and speed displays throughout the app. Default: Metric.
- **Theme** — Light (Latte), Dark (Mocha), or Midnight. Can also follow system preference.
- **Map Tile Style** — OpenStreetMap (colorful), Positron (light minimal), Dark Matter (dark), or Voyager (light with colors). Affects all maps in the app. Default: OpenStreetMap.

## Integration

A connection to an external service that syncs data into TrainingDash. Each integration has its own credentials stored per user. Users can configure multiple integrations; if the same activity appears in both, the first one synced wins (duplicates detected by `started_at` within 60s and `total_distance_m` within 1%).

- **Xert Integration** — stores encrypted Xert email and password. When configured, a nightly job (2 AM) syncs the user's activities from Xert by downloading raw FIT files via a web session and ingesting them through the standard FIT pipeline. This gives full field coverage: power, HR, cadence, GPS, temperature, grade, and left/right power balance. XSS (Xert Strain Score) is fetched separately via the OAuth API and stored as the activity's training load. Credentials are validated on save by attempting a Xert login.

- **Garmin Integration** — stores encrypted Garmin email and password. When configured, a nightly job (3 AM) syncs the user's activities from Garmin Connect by downloading FIT files. Credentials are validated on save; if MFA is enabled, validation is a two-step flow (credentials first, then MFA code).

## Activity

A single workout session (ride, run, etc.) parsed from a FIT file. Belongs to one User. Contains summary stats and links to Records.

**Deletion** — An Activity can be permanently deleted by its owner. The delete is a hard delete (no trash / soft delete). On deletion:

- Child rows (Records, Laps, ActivityPeakPower) are removed via database CASCADE.
- The owning Route's `ride_count` is decremented. If the activity was the last one on the Route, the Route is also deleted.
- If the deleted Activity was the Route's `first_seen_activity_id`, that FK is set to NULL automatically (ON DELETE SET NULL).
- A background job (`recalculate_after_delete_job`) recomputes the fitness model (CP model / FitnessHistory) and re-evaluates `is_breakthrough` flags on all remaining activities for that user. The DELETE endpoint returns 204 immediately; recalculation is asynchronous.

## Record

A single data point within an Activity — one row per timestamp with lat/lon, HR, power, speed, altitude, etc.

## RecalculationJob

A background job that recomputes training metrics (NP, IF, TSS, W'bal, zone times) for all of a user's activities that have power data. One row per user — upserted on each run. Triggered automatically when a user saves a new Threshold, and manually via Settings → Thresholds → Recalculate.

Statuses: **pending** (enqueued, not yet started) → **running** (in progress) → **completed** (finished, `activities_updated` count recorded) | **failed** (`error_message` recorded). A row stuck in `running` or `pending` is a **Strand**; the strand-recovery cron marks it failed. Enqueue failure is marked failed immediately (per ADR 0006).

## Route

A cluster of Activities that follow the same geographic path, identified via Hausdorff distance on simplified polylines. Used for per-route PRs and ride comparison.

## Daily Targets

The per-day kcal + macro goals the deterministic nutrition engine derives nightly (formula set per ADR-worthy research: Mifflin-St Jeor / Katch-McArdle TDEE, EA floor, macro ordering). Yesterday's finalized set is what the UI shows; there are no intraday recalibrations. The LLM never sets Daily Targets directly — it may propose deficit/split adjustments weekly, within bounds, floors never move.
_Avoid_: calorie budget, macro prescription

## Meal Entry

A confirmed, itemized food record for one calendar day (user-local date, no cross-midnight split), with optional photo (retained) and per-item provenance distinguishing VLM estimate, user correction, and later edit. kcal/macros are computed deterministically from the food DB; VLM calorie numbers are never stored.
_Avoid_: food log entry, diary row

## Draft Meal

An unconfirmed photo-derived meal. Visible as a pending kcal preview but excluded from all compliance math until confirmed.
_Avoid_: pending entry, unlogged meal

## Compliance Digest

The 7-day averages of confirmed intake (kcal, protein, etc.) that feed the Athlete Snapshot's nutrition-compliance block and the weekly adaptation. Single bad days cannot whipsaw targets because the engine only consumes the Digest.
_Avoid_: weekly summary, streak

## Adaptation Loop

The feedback-control system through which the Coach adapts targets and plans from observed outcomes: a weekly bounded LLM pass (two-pass: deterministic proposer emits the Allowed Adjustment Range, LLM picks within it and narrates, deterministic checker re-validates), a nightly deterministic pass (nutrition trend-safety shrink, wellness-driven Daily Swap), and the 4-week Re-Detection rhythm. Custom ML fitting is deliberately deferred; structured logging keeps it possible.
_Avoid_: dynamic training (too vague), self-learning coach

## Re-Detection

The deterministic 4-week pass recomputing wellness baselines, prompting FTP re-tests via the existing threshold machinery, and re-checking goal velocity. No LLM participates; the loop's LLM pass first sees re-detected values at the next weekly call.
_Avoid_: recalibration (reserved for nutrition target math), baseline reset

## Allowed Adjustment Range

The pre-computed bounds the deterministic proposer hands to the adaptation LLM (deficit/split range per #711; plan-change envelope per plan validation). The LLM picks within the Range and never operates outside it; violations are clamped and visibly flagged.
_Avoid_: suggestion budget, free rein

## Goal Focus

The primary emphasis of a Plan: threshold, endurance, climbing, sprint_anaerobic, or event_prep (MVP enum). One primary per Plan; weight goals ride as subordinate compliance goals. Maps deterministically to an Emphasis Vector. FTP is one focus among five, not the singular goal.
_Avoid_: goal type, rider type

## Emphasis Vector

The deterministic per-zone emphasis over the seven power zones derived from a Goal Focus (e.g. threshold focuses Threshold + Sweet Spot). Generated plans are validated against it: a plan whose zone mix contradicts it is invalid. Approximated for MVP from time-in-zone trends and power-duration bests.
_Avoid_: progression level (TrainerRoad's per-zone progression system — approximated, not built), zone bias

## Plan

A dated multi-week schedule of Workout Days addressing one primary Goal Focus. At most one active Plan per user. States: draft, active, archived. Generated week-by-week from the Athlete Snapshot.
_Avoid_: training program, block (a Plan may contain sequencing of blocks per goal-compatibility rules)

## Plan Version

An immutable full copy of a Plan created on any change (regeneration, adaptation, user move, daily swap). Chained to the version it supersedes (chain, not tree) and carrying Attribution. Never mutated in place.
_Avoid_: plan edit, revision

## Workout Day

One day of a Plan Version: workout type (closed enum incl. rest and strength), duration, target zone, estimated TSS (authoritative TSS recomputed deterministically), Movability Flag, title, and cues. Exactly seven per week; rest is an explicit day, never a gap.
_Avoid_: session (reserved for actual executed activity), planned ride

## Attribution

The recorded origin of a Plan Version: `generated`, `adapted_llm`, `adapted_deterministic`, or `user_edit`. Keeps "coach said vs user did" auditable and gives the adaptation loop its learning history.
_Avoid_: change reason, edit log

## Athlete Snapshot

The structured, canonical view of one athlete that is fed to the LLM (plan generation; weekly adaptation in v2). Assembled by a deterministic collector: fitness (FTP/wCP, 42-day CTL/ATL/TSB trend, ramp rate), load distribution, weight trend, wellness states, nutrition compliance, goals & constraints, session context. Raw daily wellness values never enter the Snapshot — only baseline-classified rolling states (normal/elevated/depressed) over rolling averages.
_Avoid_: athlete profile, dashboard payload

## Training Calendar

The availability model on which generated plans are placed. Combines a weekly Availability Template with rare per-date Overrides, merged into effective availability for the planning horizon. Weeks are Monday-start.
_Avoid_: schedule, plan grid

## Availability Template

The weekly recurring availability grid on the User: per weekday, either Rest or Available with hours (e.g. Mon 1h, Tue 0h, Wed 2h). Lives on the User like Preferences.
_Avoid_: default week, calendar settings

## Availability Override

A per-date exception to the Availability Template (travel, race day, holiday). Merged over the template. Rare by design.
_Avoid_: exception day, calendar edit

## Check-In

The minimal daily self-report: fatigue feel (1-5) plus an optional free-text note that flows into the Athlete Snapshot's session context verbatim. Session outcome (planned vs actual) is automatic from activity data; soreness flags are deliberately dropped as noisy. Stored as MetricEntry rows (category: recovery), riding the existing /me/metrics plumbing.
_Avoid_: wellness survey, morning readiness

## Movability Flag

Per-workout attribute set at plan-generation time: `pinned` (hard sessions with built-in recovery) or `swappable` (easy/endurance). Consumed by the v2 daily swap layer — when this morning's wellness states go red, today's `swappable` hard session is deterministically moved out and an endurance session pulled in (no LLM call).
_Avoid_: flexibility, lock flag

## Fitness-Floor Rule

Plan validity constraint: no high-intensity session on consecutive days without a recovery day between, max one high-intensity session per available day, and no violation of the nutrition engine's deterministic bounds. Shape validated by schema, content by the deterministic engine. A plan violating the Fitness-Floor Rule is invalid regardless of LLM intent.
_Avoid_: safety check, guardrail

## Segment

A defined section of road or trail used for performance tracking. Segments are global (shared across all users) and direction-sensitive (a climb ridden in reverse is a different segment). Three types exist:

- **Climb** — Auto-detected based on `length(m) × grade(%)` score. Categorized as HC, Cat 1-4, or uncategorized.
- **Sprint** — Auto-detected based on length (150-600m) and flat grade (-3% to +3%).
- **Arbitrary** — Manually created by a user for any purpose.

Segments have a lifecycle: `suggested` → `approved`. The system auto-detects potential segments and suggests them to users who have ridden them 3+ times. The first user to approve a suggestion becomes the segment's owner (`created_by_user_id`). Dismissed suggestions are deleted.

Duplicate detection uses start/end point proximity (25m) + path overlap (95%) + same direction.

## Segment Effort

A single traversal of a Segment within an Activity. Stores elapsed time, power, HR, speed metrics, and a per-user PR flag. An activity can have multiple efforts if it crosses multiple segments, or crosses the same segment multiple times.

## Pacing Plan

A prediction of how a rider should distribute power across a Course to finish in a given time or intensity. A plan is always shaped by the rider's own riding behavior (coasting on descents, stops, cornering) applied to the course's terrain; the rider supplies either a target intensity (time is computed) or a target time (the profile is scaled until it hits). Carries a Sustainability level. Contains per-segment power targets, estimated speeds and times, total time, average and Normalized Power, and a W'bal prediction.

## Sustainability

A plan's traffic-light level: green (sustainable), yellow (very hard, near the rider's limit), or red (beyond the rider's capability). Red plans are still generated and shown, flagged. Only a physically impossible request is rejected outright.

## Riding Behavior

The rider's learned baseline of how they actually ride, distinct from their physiology: how much power they hold on descents (Descent Multiplier), how much ride time they spend coasting or stopped, per terrain type. Learned from ingested activities and modulated by Plan Type — a race tightens coasting and stops, a tour loosens them.

## Descent Multiplier

The fraction of target power a rider actually holds while descending. Learned from the rider's activities; near zero = full coasting, near one = pedaling descents. Applied by the pacing model on descents instead of the grade-power formula.

## Plan Type

The character of ride a plan is for: race, gran fondo, training, or touring. Plan Type does not change the rider's learned Behavior — it modulates it and sets cornering aggressiveness and expected stop time for the plan. Concretely (ADR 0005 #636): each preset carries a coast modulation factor applied to the learned Descent Multiplier — training is the identity (the baseline exactly as learned), race and gran fondo pedal descents more (races strongest), touring coasts more. The plan response exposes both the learned and the modulated values so the UI can show what changed.

## Pacing Coefficients

The learned parameters of the pacing model, calibrated per user and bike from that rider's real activities. They control how power targets adapt to grade and how fast the rider is predicted to corner and descend. Coefficients are recalibrated automatically after activities are ingested.

## Curvature

How sharply the road bends at a point, measured as the reciprocal of the corner radius. Used to predict Cornering Speed; computed identically wherever it is used (runtime planning and calibration).

## Cornering Speed

The maximum speed a rider can hold through a corner of a given Curvature without exceeding their lateral acceleration comfort, which scales with descent aggressiveness. A plan never predicts speeds above this limit.

## Braking Envelope

The constraint that a plan's predicted speed must be reachable given the distance available to brake before a corner. Ensures predicted speeds drop *before* corners rather than at them.

## Segment Suggestion

A pending proposal to create a segment, tied to a specific user. Created when the system detects a climb/sprint on a user's ride. Tracks repetition count and expires after 90 days of inactivity. Multiple users can have suggestions for the same underlying segment; first to approve owns it.
