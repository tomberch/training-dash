# TrainingDash — Domain Glossary

## User

A person with an account in the system. Users are provisioned by an Admin; there is no self-serve signup. Each User owns their own Activities, Records, and Routes — data is isolated per user.

## Admin

A User with `is_admin = true`. Admins can create accounts, reset passwords, and trigger syncs for other users. Admins cannot access other users' preferences or credentials.

## Preferences

Per-user display settings stored on the User record. Currently includes:

- **Unit System** — either *Metric* (km, m, km/h) or *Imperial* (mi, ft, mph). Affects all distance, elevation, and speed displays throughout the app. Default: Metric.

## Integration

A connection to an external service that syncs data into TrainingDash. Each integration has its own credentials stored per user. Users can configure multiple integrations; if the same activity appears in both, the first one synced wins (duplicates detected by `started_at` within 60s and `total_distance_m` within 1%).

- **Xert Integration** — stores encrypted Xert email and password. When configured, a nightly job (2 AM) syncs the user's activities from Xert. Credentials are validated on save by attempting a Xert login.

- **Garmin Integration** — stores encrypted Garmin email and password. When configured, a nightly job (3 AM) syncs the user's activities from Garmin Connect by downloading FIT files. Credentials are validated on save; if MFA is enabled, validation is a two-step flow (credentials first, then MFA code).

## Activity

A single workout session (ride, run, etc.) parsed from a FIT file. Belongs to one User. Contains summary stats and links to Records.

## Record

A single data point within an Activity — one row per timestamp with lat/lon, HR, power, speed, altitude, etc.

## Route

A cluster of Activities that follow the same geographic path, identified via Hausdorff distance on simplified polylines. Used for per-route PRs and ride comparison.
