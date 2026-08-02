# 05 — Header and user menu

**What to build:** A persistent header across all authenticated views containing the app name, Upload FIT button, and a user menu dropdown. The user menu shows the username and contains Settings and Logout options. Clicking Logout calls the logout API and redirects to login. Clicking Settings navigates to the Settings page (placeholder for now).

**Blocked by:** 01 (logout endpoint), 02 (GET /me for username)

**Status:** done

- [x] Header component displays "Fitter" on the left
- [x] Header displays "Upload FIT" button (moved from ActivityList)
- [x] Header displays user menu on the right showing the current username
- [x] Clicking the username opens a dropdown menu
- [x] Dropdown contains "Settings" and "Logout" options
- [x] Clicking "Logout" calls the logout API, clears local state, and shows the login screen
- [x] Clicking "Settings" navigates to a Settings view (can be a placeholder that just says "Settings")
- [x] Header appears on ActivityList, ActivityDetail, RecordsView, and AdminView
- [x] ActivityList no longer renders its own title/upload button (moved to Header)
- [x] App fetches `/me` on load to get username for display
- [ ] Component test: `test_header_shows_username` (skipped - functionality tested via App.test.tsx)
- [ ] Component test: `test_user_menu_opens_on_click` (skipped - functionality tested via App.test.tsx)
- [ ] Component test: `test_logout_calls_api_and_shows_login` (skipped - functionality tested via App.test.tsx)
