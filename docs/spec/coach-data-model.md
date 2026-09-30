# Coach Spec: Data Model & Migrations

> Wayfinder ticket #717 (map #706). Consolidates the Coach data model from spec docs
> #713 (snapshot/calendar), #714 (nutrition), #715 (goal/plan), #716 (adaptation loop).
> Codebase patterns followed: `repositories/postgres/models.py` (35 models), alembic under
> `backend/migrations/`, filesystem photos (`Bike.photo_path`), JSONB payloads, MetricEntry reuse.

## 0. Reuse (no new storage)

- **User BMR inputs**: `weight_kg` / `height_cm` / `date_of_birth` / `gender` already on `User` —
  the #711 engine needs no new user fields.
- **Weight tracking (MVP)**: `MetricEntry` (`weight_kg`, `source: manual`,
  `source_detail: coach_daily_log`); Garmin Index/body-comp sync later writes the same table
  with `source: device` — device-vs-manual precedence: **manual wins for same-day** (deliberate
  weigh-in ritual per #713 spec).
- **Check-In**: `MetricEntry` rows (`category: recovery`, fatigue 1–5 + note).
- **Wellness sync**: `MetricEntry` rows (`source: device`; sleep/RHR/HRV keys).

## 1. New tables

All follow house style: BigInteger PKs, `user_id` FK CASCADE, CheckConstraints for enums,
`created_at/updated_at` server defaults. Names carry the `coach_` prefix to keep the feature
addressable.

### `coach_goals`

| Column | Type | Notes |
|--------|------|-------|
| id | BigInteger PK | |
| user_id | FK users CASCADE | |
| focus | String(20) CHECK in 5 foci | threshold / endurance / climbing / sprint_anaerobic / event_prep |
| is_primary | Boolean | §715: one primary per active plan |
| event_date | Date NULL | event_prep only |
| baseline / target | JSONB | e.g. `{"ftp_pct": 10}`, `{"weight_kg": 15}` |
| status | String(20) CHECK | active / achieved / archived |
| created_at / updated_at | | |

### `coach_plans`

| Column | Type | Notes |
|--------|------|-------|
| id | BigInteger PK | |
| user_id | FK CASCADE | |
| goal_ids / primary_goal_id | FK coach_goals | |
| status | String(20) CHECK | draft / active / archived |
| start_date | Date | |
| n_weeks | Integer CHECK 2..16 | |
| created_at / updated_at | | |

### `coach_plan_versions`

The content carrier. **Immutable by INSERT-only lifecycle** (#715: any change = new row).

| Column | Type | Notes |
|--------|------|-------|
| id | BigInteger PK | |
| plan_id | FK coach_plans CASCADE | |
| supersedes_id | FK coach_plan_versions NULL | version chain (chain, not tree) |
| attribution | String(30) CHECK | generated / adapted_llm / adapted_deterministic / user_edit |
| model_id | String(80) | pinned model used (AppSettings at generation time) |
| schema_version | String(10) | Zod shape version |
| header | JSONB | user-facing header incl. narrative |
| weeks | JSONB | the validated Zod `weeks` payload (#715 §2) |
| validation_report | JSONB | deterministic envelope results at save time |
| created_at | | INSERT-only |

### `coach_plan_days`

Materialized per-day rows for the **current version only** — the hot path
("what's today's workout", adherence joins). Rebuilt from `weeks` JSONB on version switch.

| Column | Type | Notes |
|--------|------|-------|
| id | BigInteger PK | |
| version_id | FK coach_plan_versions CASCADE | |
| date | Date | Monday-start week grouping via date_trunc |
| workout_type | String(20) CHECK | #715 enum incl. rest & strength |
| duration_min | Integer | |
| target_intensity | String(10) CHECK | zone1..zone7 |
| est_tss | Numeric | LLM estimate |
| computed_tss | Numeric | deterministic recompute (#715) |
| movability | String(10) CHECK | pinned / swappable |
| title | String(200) | |
| cues | Text | attached, never parsed |

Index: `(version_id, date)`; day uniqueness within version.

### `coach_availability_overrides`

| Column | Type | Notes |
|--------|------|-------|
| id | BigInteger PK | |
| user_id | FK users CASCADE | |
| date | Date | |
| available | Boolean | false = rest (travel/holiday), true = available(hours) |
| hours | Numeric(3,1) NULL | when available |
| note | String(200) NULL | |
| UNIQUE(user_id, date) | | |

### Availability Template — **User JSONB column** (locked)

`User.availability_template` JSONB: 7 slots, per weekday `rest | {hours: n}` — user-preference-
shaped like `power_zone_percentages`; merged with overrides at read time (#713).

### `coach_meals`

| Column | Type | Notes |
|--------|------|-------|
| id | BigInteger PK | |
| user_id | FK users CASCADE | |
| local_date | Date | the logged calendar day (#714 §3) |
| status | String(20) CHECK | draft / confirmed |
| photo_path | String(500) NULL | filesystem, retained by default (#713 Notes) |
| vlm_model_id | String(80) NULL | provenance of the identification call |
| created_at / confirmed_at / updated_at | | draft → confirmed is a state transition; drafts excluded from compliance |

Uniqueness not enforced across meals (multiple meals per day are normal).

### `coach_meal_items`

| Column | Type | Notes |
|--------|------|-------|
| id | BigInteger PK | |
| meal_id | FK coach_meals CASCADE | |
| display_name | String(200) | VLM label / user label |
| quantity | JSONB | `{"household": "2 slices"}` + grams for computation |
| food_db | String(20) CHECK | usda_fdc / off / manual |
| food_ref | String(100) | FDC ID / OFF barcode+product id; NULL for manual |
| provenance | String(20) CHECK | estimate / correction / edit (#714 §3 retroactive-edit rule) |
| kcal / protein_g / carbs_g / fat_g | Numeric | computed at save from food_ref match — never stored from VLM output |

## 2. Config

- **Model pinning: AppSettings rows** (locked) — keys like `coach.vision_model`,
  `coach.plan_model`, `coach.adapt_model` (runtime-editable by admin, survives deploys;
  #707 churn response). Defaults ship in seed migration: `glm-5.3-flash` / `glm-5.3-flash`
  / `deepseek-v4.1-flash`.
- Ollama Cloud tier/concurrency is environment config (ops, not per-user).

## 3. Snapshot audit view (locked)

The Coach's snapshot view renders **the exact JSON payload sent to the LLM**. One deterministic
collector service + serializer; no separate presentation model that could drift from what the
LLM actually received. Auditability is: "this is byte-for-byte what the model saw."

## 4. Migrations

- One alembic migration per table group is unnecessary — a single
  `add_coach_*` migration creating all 8 tables + User template column + AppSettings seeds,
  ordered FK-safe (goals → plans → versions → days; meals → items).
- All coach tables are additive; no existing table changes except `users` (new nullable JSONB
  column) — zero-risk deploy.
- Nuke variants (#glossary): **Reset Activities** scope decision needed at implementation —
  recommendation: coach data is **not** activity data; leave coach tables intact on
  Reset Activities, include them in Delete User (FK CASCADE covers).

## Glossary deltas

- **Plan Version immutability** is INSERT-only at the storage layer — deletion of a Plan
  cascades versions and days.
- **Draft Meal** = `coach_meals.status = draft`. **Meal Entry** = confirmed.
- **Availability Template** = `users.availability_template`. **Availability Override** =
  `coach_availability_overrides` row.