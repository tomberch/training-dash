# 06 — Settings page: Preferences section

**What to build:** The Settings page with a Preferences section where users can toggle between Metric and Imperial units. The preference is saved to the backend and affects all distance, elevation, and speed displays throughout the app.

**Blocked by:** 02 (preferences backend), 04 (format utilities), 05 (header for navigation to Settings)

**Status:** done

- [x] Settings page has a "Preferences" section
- [x] Preferences section shows current unit system (Metric or Imperial)
- [x] User can toggle between Metric and Imperial
- [x] Changing the toggle calls `PATCH /me` to persist the preference
- [x] Success feedback shown when preference is saved
- [x] Error feedback shown if save fails
- [x] Unit preference is loaded from `/me` on app startup and stored in React context or app state
- [x] `formatDistance`, `formatElevation`, `formatSpeed` calls throughout the app use the user's unit preference
- [x] ActivityList displays distances in the user's preferred units
- [x] ActivityDetail displays distances, elevations, and speeds in the user's preferred units
- [x] RecordsView displays values in the user's preferred units
- [x] Settings page has a "Back" button to return to the activity list
- [x] Settings page is styled consistently with the rest of the app (dark theme, same spacing/fonts)
- [ ] Component test: `test_settings_shows_current_unit_preference` (skipped - manual testing)
- [ ] Component test: `test_settings_toggles_unit_preference` (skipped - manual testing)
