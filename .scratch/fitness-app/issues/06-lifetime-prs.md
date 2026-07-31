# 06 — Lifetime PRs

**What to build:** A records view showing the authenticated user's lifetime PRs, computed from `activities` summary columns: longest ride by distance, longest ride by time, fastest 5/10/40km point-to-point, max speed, max HR, biggest elevation gain, highest sustained power (NP/XP if FIT carries it). Per-user isolated; another user's PRs are never shown.

**Blocked by:** 01 (tracer-bullet spine — needs activities with summary columns)

**Status:** ready-for-agent

- [ ] `GET /records` returns the authenticated user's lifetime PRs as a JSON object
- [ ] PRs computed: longest distance, longest moving time, fastest 5km, 10km, 40km point-to-point, max speed, max HR, biggest elevation gain, highest sustained power (nullable if unavailable)
- [ ] Another user's records are not returned for this user
- [ ] Records view renders PR tiles/cards from the API response
- [ ] Integration test: seed activities with known summary values, assert PRs computed correctly; seed a second user, assert cross-user isolation
- [ ] Component test: records view renders lifetime PR tiles from mocked API response