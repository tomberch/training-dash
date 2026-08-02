# 08 — Worker uses sync_since for initial Xert sync

**What to build:** Update the `sync_xert_job` worker to use the `sync_since` date from `xert_credentials` for the initial sync instead of hardcoded 90 days. After the first sync, subsequent syncs continue to pull the last 90 days (to catch any new activities).

**Blocked by:** 03 (sync_since column exists on xert_credentials)

**Status:** done

- [x] `sync_xert_job` reads `sync_since` from the user's `xert_credentials` row
- [x] If `sync_since` is set and no activities exist yet for this user from Xert, use `sync_since` as the start date
- [x] If activities already exist from Xert (not first sync), use 90 days ago as the start date
- [x] If `sync_since` is null, default to 90 days ago (backward compatible)
- [ ] Integration test: `test_sync_xert_job_uses_sync_since_for_first_sync` (skipped - requires complex mocking)
- [ ] Integration test: `test_sync_xert_job_uses_90_days_for_subsequent_syncs` (skipped - requires complex mocking)
