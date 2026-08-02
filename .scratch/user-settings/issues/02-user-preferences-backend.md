# 02 — User preferences backend (unit_system)

**What to build:** Backend support for user preferences. Add a `unit_system` column to the `users` table (values: `metric` or `imperial`, default: `metric`). Provide endpoints for users to read and update their own preferences.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [x] Database migration adds `unit_system` column to `users` table with default `'metric'`
- [x] `GET /me` returns current user info: `{ id, username, is_admin, unit_system }`
- [x] `GET /me` returns 401 if not authenticated
- [x] `PATCH /me` accepts `{ unit_system: "metric" | "imperial" }` and updates the user
- [x] `PATCH /me` returns 400 if `unit_system` value is invalid
- [x] `PATCH /me` returns 401 if not authenticated
- [x] Integration test: `test_get_me_returns_user_info_with_unit_system`
- [x] Integration test: `test_patch_me_updates_unit_system`
- [x] Integration test: `test_patch_me_rejects_invalid_unit_system`
