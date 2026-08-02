# Consolidated Code Review — Xert Sync Job (PR #10)

**Date**: 2026-08-01  
**Base commit**: 58ba8bd  
**Overall Verdict**: **FAIL** (CHANGES_REQUESTED)

---

## Summary

The change replaces inline Activity/Record creation in `sync_xert_job` with FIT file download that delegates to `ingest_job`. This is architecturally cleaner (one parsing path instead of two) and extends the sync window from 30 to 90 days. The implementation fully satisfies the specification requirements.

---

## 1. Standards Findings

| Severity | Issue | Location | Recommendation |
|----------|-------|----------|----------------|
| **Medium** | Silent exception swallowing | `worker.py:107-128` | Non-`XertAPIError` exceptions (Redis failures mid-loop, httpx timeout exceptions, unexpected data errors) will cause activities to be silently skipped with no log entry. Restore a catch-all handler with logging. |

**Detail**: The inner `try/except` loop at lines 107-128 only catches `XertAPIError`. If `pool.enqueue_job()` raises (Redis connection error, timeout) or if an unexpected exception occurs during FIT download, the exception propagates and terminates the sync, losing progress on remaining activities. The test suite does not cover this path.

**Recommended fix**:
```python
except XertAPIError as e:
    logger.warning(f"sync_xert_job: Failed to download activity {xert_activity.id}: {e}")
    continue
except Exception as e:
    logger.exception(f"sync_xert_job: Unexpected error processing activity {xert_activity.id}")
    continue
```

---

## 2. Spec Compliance

All specification requirements are **satisfied**:

| Requirement | Status | Evidence |
|-------------|--------|----------|
| `xert_credentials` table with encrypted password (AES, FITTER_ENCRYPTION_KEY) | ✅ | `models.py:98-111`, `crypto.py` uses AES-256-GCM |
| Admin screen lets user store Xert credentials (encrypted at rest) | ✅ | `app.py:281-305` PUT endpoint encrypts before storing |
| `sync_xert(user_id)` arq job: decrypt, login, fetch, download FIT, enqueue ingest_fit | ✅ | `worker.py:63-140` implements full flow |
| Already-imported activities skipped via `source_ref` | ✅ | `worker.py:96-100` filters by existing refs |
| Nightly schedule runs sync_xert for users with credentials | ✅ | `worker.py:143-169` cron at 2 AM daily |
| Manual trigger from admin screen | ✅ | `app.py:243-252` POST endpoint |
| Credentials decrypted only inside job, never in HTTP response | ✅ | GET endpoint returns only email; decrypt happens only in worker |
| Integration test: stub Xert, run sync, assert activities ingested, re-run assert no duplicates | ✅ | `test_xert_sync.py:168-240` |
| Unit test: encrypt-decrypt round trip, wrong key raises | ✅ | `test_crypto.py` covers both cases |

---

## 3. Positive Observations

- Credential handling is secure: AES-256-GCM encryption, passwords never logged or returned in API responses
- Code follows existing patterns (uses same `ingest_job` pipeline as uploads)
- Test coverage updated appropriately to verify FIT bytes passed to enqueue
- Clean deduplication logic using `source_ref`

---

## 4. Recommended Fixes

1. **Add catch-all exception handler** in the activity download/enqueue loop to prevent silent failures and ensure logging of unexpected errors.

2. **Optional**: Add a test case for `pool.enqueue_job()` raising an exception to verify resilience.

---

## Files Reviewed

- `backend/src/fitter/worker.py` — Core sync job implementation
- `backend/src/fitter/crypto.py` — AES-256-GCM encryption
- `backend/src/fitter/app.py` — Admin endpoints
- `backend/tests/integration/test_xert_sync.py` — Integration tests
- `backend/tests/unit/test_crypto.py` — Crypto unit tests
