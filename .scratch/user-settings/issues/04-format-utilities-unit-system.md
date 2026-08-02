# 04 — Format utilities with unit system

**What to build:** Update the format utilities in `format.ts` to accept a `unitSystem` parameter and return values in metric or imperial units. This is a pure refactor with no UI changes yet — callers will be updated in later tickets.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [x] `formatDistance(m, unitSystem)` returns `"X.X km"` for metric, `"X.X mi"` for imperial
- [x] `formatElevation(m, unitSystem)` returns `"X m"` for metric, `"X ft"` for imperial
- [x] `formatSpeed(mps, unitSystem)` returns `"X.X km/h"` for metric, `"X.X mph"` for imperial
- [x] Existing `formatDistance` calls continue to work (default to metric for backward compatibility)
- [x] Unit test: `test_format_distance_metric_returns_km`
- [x] Unit test: `test_format_distance_imperial_returns_miles`
- [x] Unit test: `test_format_elevation_metric_returns_meters`
- [x] Unit test: `test_format_elevation_imperial_returns_feet`
- [x] Unit test: `test_format_speed_metric_returns_kmh`
- [x] Unit test: `test_format_speed_imperial_returns_mph`

**Conversion factors:**
- 1 km = 0.621371 miles
- 1 m = 3.28084 feet
- 1 m/s = 3.6 km/h = 2.23694 mph
