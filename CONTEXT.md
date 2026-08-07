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
