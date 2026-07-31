# 09 — Admin screen: user provisioning, password reset, manual sync trigger

**What to build:** An admin-only UI (visible only to users with `is_admin = true`) to create new user accounts, reset an existing user's password, and manually trigger a user's Xert sync (enqueue `sync_xert` for that user — the job itself is a stub until ticket 10 lands). No self-serve signup; only the admin provisions accounts.

**Blocked by:** 01 (tracer-bullet spine — needs auth and a seed admin user)

**Status:** ready-for-agent

- [ ] Admin-only routes gated by `is_admin = true` on the authenticated user
- [ ] `POST /admin/users` creates a new account (username, initial password); returns the new user
- [ ] `POST /admin/users/:id/reset-password` sets a new password for that user
- [ ] `GET /admin/users` lists all users (admin only)
- [ ] Admin screen renders a user list with create-account and reset-password actions
- [ ] Admin screen has a "Trigger sync" button per user that enqueues `sync_xert(user_id)` (job stub no-ops until ticket 10)
- [ ] Non-admin users cannot reach admin routes or see the admin screen
- [ ] Integration test: admin creates a user, the new user can log in; admin resets password, the user can log in with the new password; non-admin `POST /admin/users` is rejected
- [ ] Component test: admin screen renders user list and actions for an admin; non-admin sees no admin link