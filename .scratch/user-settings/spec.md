# User Settings Page

**Status:** ready-for-agent

## Problem Statement

Users have no way to configure personal preferences or manage their own Xert integration. Currently:
- Unit display is hardcoded to metric (km, m, m/s)
- Xert credentials can only be managed by admins via the Admin Panel
- There is no logout functionality
- There is no proper header or user menu

Users need a self-service Settings page to control their experience without admin intervention.

## Solution

Add a header with a user menu (dropdown) containing Settings and Logout. The Settings page has two sections:

1. **Preferences** — unit system toggle (Metric/Imperial) stored on the user record
2. **Integrations** — Xert connection management with credential validation

The header appears across all authenticated views. Logout clears the session cookie. Unit preference affects all distance, elevation, and speed displays throughout the app.

## User Stories

1. As a logged-in user, I want to see a header with the app name and my user menu, so that I can access account actions from any screen.
2. As a logged-in user, I want to click my username in the header to reveal a dropdown menu, so that I can access Settings and Logout.
3. As a logged-in user, I want to click Logout in the user menu, so that I can end my session securely.
4. As a logged-in user, I want to click Settings in the user menu, so that I can access my preferences and integrations.
5. As a logged-in user, I want to see my current unit preference (Metric or Imperial) on the Settings page, so that I know what's currently selected.
6. As a logged-in user, I want to toggle between Metric and Imperial units, so that distances, elevations, and speeds display in my preferred system.
7. As a logged-in user, I want my unit preference to persist across sessions and devices, so that I don't have to reconfigure it each time.
8. As a logged-in user, I want distances displayed in kilometers (Metric) or miles (Imperial), so that I can read them in familiar units.
9. As a logged-in user, I want elevations displayed in meters (Metric) or feet (Imperial), so that I can understand elevation gain in familiar units.
10. As a logged-in user, I want speeds displayed in km/h (Metric) or mph (Imperial), so that I can interpret pace in familiar units.
11. As a logged-in user, I want to see an Integrations section on the Settings page, so that I can manage connections to external services.
12. As a logged-in user, I want to see whether my Xert account is connected or not, so that I know if auto-sync is configured.
13. As a logged-in user with Xert configured, I want to see which email is connected (but not the password), so that I can verify the right account is linked.
14. As a logged-in user without Xert configured, I want to enter my Xert email and password to connect, so that my activities sync automatically.
15. As a logged-in user, I want my Xert credentials validated when I save them, so that I know immediately if they're correct.
16. As a logged-in user, I want to see an error message if my Xert credentials are invalid, so that I can correct them.
17. As a logged-in user with Xert configured, I want to disconnect my Xert account, so that I can stop auto-sync or switch accounts.
18. As a logged-in user with Xert configured, I want to update my Xert credentials, so that I can change my password or switch accounts.
19. As a logged-in user, I want a Back button on the Settings page, so that I can return to the activity list.
20. As a logged-in user, I want the Settings page styled consistently with the rest of the app, so that it feels cohesive.

## Implementation Decisions

### Backend

**New column on `users` table:**
- `unit_system` — VARCHAR, values: `metric` (default) or `imperial`
- Requires a database migration

**New endpoints:**
- `POST /logout` — clears the session cookie, returns 200
- `GET /me` — returns current user info: `{ id, username, is_admin, unit_system }`
- `PATCH /me` — updates user preferences: accepts `{ unit_system }`, returns updated user
- `GET /me/xert-credentials` — returns `{ configured: bool, xert_email: string | null, sync_since: string | null }`
- `PUT /me/xert-credentials` — saves credentials with validation: accepts `{ xert_email, xert_password, sync_since? }`, attempts Xert login, returns success or 400 with error
- `DELETE /me/xert-credentials` — removes credentials, returns 200

**Xert credential validation:**
- On `PUT /me/xert-credentials`, call `XertClient.login()` before saving
- If login fails, return 400 with `{ detail: "Invalid Xert credentials" }`
- If login succeeds, encrypt and store credentials, return 200

**Xert sync-since date:**
- New column `sync_since` on `xert_credentials` table (DATE, nullable)
- When user connects Xert, they can optionally set a "sync since" date
- Default: 90 days ago (current behavior)
- First sync pulls from `sync_since` to now; subsequent syncs pull last 90 days
- `PUT /me/xert-credentials` accepts optional `sync_since` (ISO date string)
- `GET /me/xert-credentials` returns `sync_since` when configured

### Frontend

**New components:**
- `Header` — app name left, Upload FIT button + user menu right
- `UserMenu` — dropdown with Settings and Logout
- `SettingsView` — two sections: Preferences and Integrations

**Modified components:**
- `App` — add Header, add SettingsView route/state
- `ActivityList` — remove redundant title, Upload FIT button moves to Header

**Format utilities:**
- Modify `format.ts` to accept a `unitSystem` parameter
- `formatDistance(m, unitSystem)` — returns "X km" or "X mi"
- `formatElevation(m, unitSystem)` — returns "X m" or "X ft"  
- `formatSpeed(mps, unitSystem)` — returns "X km/h" or "X mph"

**User context:**
- Fetch `/me` on app load to get user info including `unit_system`
- Pass `unitSystem` to format functions throughout the app
- Store in React context or prop-drill from App

### API module additions

```typescript
// api.ts additions
export async function logout(): Promise<void>
export async function fetchMe(): Promise<User>
export async function updatePreferences(prefs: { unit_system: string }): Promise<User>
export async function fetchMyXertCredentials(): Promise<{ configured: boolean; xert_email: string | null; sync_since: string | null }>
export async function saveMyXertCredentials(email: string, password: string, syncSince?: string): Promise<void>
export async function deleteMyXertCredentials(): Promise<void>
```

## Testing Decisions

### What makes a good test

Tests assert on external behavior: HTTP response codes and shapes, rendered DOM elements, and user interactions. Tests should survive internal refactors that preserve the API contract.

### Backend (pytest, integration)

Follow the existing pattern in `tests/integration/test_auth.py`:
- Use `auth_client` fixture for authenticated requests
- Test endpoint behavior, not implementation details

Tests:
- `test_logout_clears_session_cookie`
- `test_logout_requires_auth`
- `test_get_me_returns_user_info`
- `test_get_me_includes_unit_system`
- `test_patch_me_updates_unit_system`
- `test_patch_me_rejects_invalid_unit_system`
- `test_get_xert_credentials_when_not_configured`
- `test_get_xert_credentials_when_configured_shows_email_only`
- `test_put_xert_credentials_validates_and_saves`
- `test_put_xert_credentials_rejects_invalid_credentials`
- `test_delete_xert_credentials_removes_credentials`

### Frontend (vitest, mocked API)

Follow the existing pattern in `AdminView.test.tsx`:
- Mock API functions with `vi.mock`
- Test component rendering and user interactions

Tests:
- `test_header_shows_username`
- `test_user_menu_opens_on_click`
- `test_logout_calls_api_and_redirects`
- `test_settings_shows_current_unit_preference`
- `test_settings_toggles_unit_preference`
- `test_settings_shows_xert_not_configured`
- `test_settings_shows_xert_configured_with_email`
- `test_settings_saves_xert_credentials`
- `test_settings_shows_error_on_invalid_credentials`
- `test_settings_disconnects_xert`

### Unit tests for format functions

- `test_format_distance_metric_returns_km`
- `test_format_distance_imperial_returns_miles`
- `test_format_elevation_metric_returns_meters`
- `test_format_elevation_imperial_returns_feet`
- `test_format_speed_metric_returns_kmh`
- `test_format_speed_imperial_returns_mph`

## Out of Scope

- Theme switching (dark/light/system) — already follows system preference
- Date format preference — keep current behavior
- Default chart axis preference — keep current behavior
- Other integrations beyond Xert — future work
- Email/password change for the Fitter account itself — admin manages this
- Profile picture or avatar — not needed for family app

## Further Notes

### Migration strategy

The `unit_system` column should default to `'metric'` so existing users see no change. A simple `ALTER TABLE users ADD COLUMN unit_system VARCHAR(10) DEFAULT 'metric'` suffices.

### Conversion factors

- 1 km = 0.621371 miles
- 1 m = 3.28084 feet
- 1 m/s = 3.6 km/h = 2.23694 mph

### Existing Xert credential endpoints

Admin endpoints already exist at `/admin/users/{id}/xert-credentials`. The new `/me/xert-credentials` endpoints are for users managing their own credentials. The admin endpoints remain for admin use cases (helping a family member).
