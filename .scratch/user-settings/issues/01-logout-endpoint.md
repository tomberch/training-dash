# 01 — Logout endpoint and frontend

**What to build:** A way for users to end their session. The backend provides `POST /logout` which clears the session cookie. The frontend calls this endpoint and redirects to the login screen.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [x] `POST /logout` endpoint clears the session cookie and returns 200
- [x] `POST /logout` returns 401 if not authenticated
- [x] Frontend `api.ts` has a `logout()` function that calls the endpoint
- [x] Integration test: `test_logout_clears_session_cookie` — after logout, subsequent authenticated requests return 401
- [x] Integration test: `test_logout_requires_auth`
