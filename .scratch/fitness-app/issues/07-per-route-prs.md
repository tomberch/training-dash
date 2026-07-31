# 07 — Per-route PRs

**What to build:** Per-route records (fastest time on Route X) computed via `min(elapsed_time) GROUP BY route_id, user_id`, shown on the records view alongside the lifetime PRs from ticket 06. Each route's PR shows the route id/name, fastest elapsed time, and the activity that holds it. Only routes with matched rides appear.

**Blocked by:** 04 (route matching — needs `route_id` populated on activities), 06 (records view — extends it)

**Status:** ready-for-agent

- [ ] `GET /records` extended to return per-route PRs in addition to lifetime PRs
- [ ] Per-route PRs computed: `min(elapsed_time) GROUP BY route_id, user_id`, joined to `routes` for display
- [ ] Records view renders per-route PRs alongside lifetime PRs
- [ ] Another user's per-route PRs are not returned for this user
- [ ] Integration test: seed two rides on the same route with different elapsed times, assert the faster one holds the route PR; assert cross-user isolation
- [ ] Component test: records view renders per-route PR tiles when route data is present; omits them when no routes matched yet