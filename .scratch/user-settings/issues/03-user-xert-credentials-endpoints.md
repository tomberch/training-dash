# 03 — User Xert credentials endpoints

**What to build:** Endpoints for users to manage their own Xert integration (distinct from the admin endpoints). Users can check connection status, save credentials (with validation), and disconnect. Includes a "sync since" date that controls how far back the first sync pulls activities.

**Blocked by:** None — can start immediately.

**Status:** done

- [x] Database migration adds `sync_since` column (DATE, nullable) to `xert_credentials` table
- [x] `GET /me/xert-credentials` returns `{ configured: false, xert_email: null, sync_since: null }` when not configured
- [x] `GET /me/xert-credentials` returns `{ configured: true, xert_email: "...", sync_since: "..." }` when configured (never returns password)
- [x] `PUT /me/xert-credentials` accepts `{ xert_email, xert_password, sync_since? }` and validates by attempting Xert login
- [x] `PUT /me/xert-credentials` returns 200 and saves encrypted credentials if validation succeeds
- [x] `PUT /me/xert-credentials` returns 400 with `{ detail: "Invalid Xert credentials" }` if validation fails
- [x] `sync_since` defaults to 90 days ago if not provided
- [x] `DELETE /me/xert-credentials` removes stored credentials and returns 200
- [x] `DELETE /me/xert-credentials` returns 200 even if no credentials were configured (idempotent)
- [x] All endpoints return 401 if not authenticated
- [x] Integration test: `test_get_xert_credentials_when_not_configured`
- [x] Integration test: `test_get_xert_credentials_when_configured_shows_email_and_sync_since`
- [x] Integration test: `test_put_xert_credentials_validates_and_saves` (mock Xert API)
- [x] Integration test: `test_put_xert_credentials_rejects_invalid_credentials` (mock Xert API)
- [x] Integration test: `test_put_xert_credentials_with_custom_sync_since`
- [x] Integration test: `test_delete_xert_credentials_removes_credentials`
