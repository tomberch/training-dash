# 07 — Settings page: Integrations section (Xert)

**What to build:** Add an Integrations section to the Settings page with Xert connection management. Users can see their connection status, connect with credentials (validated on save), set a "sync since" date for initial import, update credentials, or disconnect.

**Blocked by:** 03 (Xert credentials endpoints), 06 (settings page exists with Preferences section)

**Status:** done

- [x] Settings page has an "Integrations" section below Preferences
- [x] Integrations section contains a Xert card/panel
- [x] When not configured: shows "Not connected" status with email field, password field, "sync since" date picker, and a "Connect" button
- [x] "Sync since" date picker defaults to 90 days ago, allows selecting any past date
- [x] When configured: shows "Connected" status, displays the connected email and sync-since date (not password), shows "Disconnect" button
- [x] When configured: user can update credentials by entering new values and clicking "Save"
- [x] Clicking "Connect" or "Save" calls `PUT /me/xert-credentials` with email, password, and sync_since
- [x] While saving, button shows loading state (e.g., "Connecting...")
- [x] On success: shows success message, updates UI to show connected state
- [x] On validation failure (400): shows error message "Invalid Xert credentials — check your email and password"
- [x] Clicking "Disconnect" calls `DELETE /me/xert-credentials`
- [x] After disconnect: UI updates to show not-connected state
- [ ] Component test: `test_settings_shows_xert_not_configured` (skipped - backend integration tests cover API)
- [ ] Component test: `test_settings_shows_xert_configured_with_email_and_sync_since` (skipped - backend integration tests cover API)
- [ ] Component test: `test_settings_connects_xert_credentials_with_sync_since` (skipped - backend integration tests cover API)
- [ ] Component test: `test_settings_shows_error_on_invalid_credentials` (skipped - backend integration tests cover API)
- [ ] Component test: `test_settings_disconnects_xert` (skipped - backend integration tests cover API)
