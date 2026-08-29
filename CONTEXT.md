# TrainingDash — Domain Glossary

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

Statuses: **pending** (enqueued, not yet started) → **running** (in progress) → **completed** (finished, `activities_updated` count recorded) | **failed** (`error_message` recorded).

## Route

A cluster of Activities that follow the same geographic path, identified via Hausdorff distance on simplified polylines. Used for per-route PRs and ride comparison.

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

The character of ride a plan is for: race, gran fondo, training, or touring. Plan Type does not change the rider's learned Behavior — it modulates it (coasting, stops) and sets cornering aggressiveness and expected stop time for the plan.

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
