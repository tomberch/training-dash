# 03 — Activity list page

**What to build:** The homepage lists the authenticated user's activities newest-first, each row showing date, total distance, moving time, and elevation gain. Clicking a row opens the activity detail page. Only the authenticated user's activities appear; another user's activities are never visible.

**Blocked by:** 01 (tracer-bullet spine)

**Status:** ready-for-agent

- [ ] `GET /activities` returns the authenticated user's activities newest-first with totals (date, distance, moving time, elevation gain)
- [ ] The homepage renders the list as a table or list; clicking a row navigates to `GET /activities/:id` detail
- [ ] Another user's activities are not returned by `GET /activities` for this user
- [ ] Empty state renders when the user has no activities yet
- [ ] Integration test: seed two users with activities, assert each user only sees their own, assert newest-first ordering
- [ ] Component test: list renders rows from mocked API response; empty state renders when list is empty