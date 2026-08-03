# Test Suite Audit - #45

## Summary

| Suite | Tests | Time | Coverage |
|-------|-------|------|----------|
| Backend Unit | 109 | ~0.8s | N/A (pure logic) |
| Backend Integration | 190 | ~3min | 72% overall |
| Frontend | 43 | ~2.7s | N/A (mocked) |
| **Total** | **342** | **~3.5min** | |

## 1. Redundancy Analysis

### No significant redundancy found

The test suite is well-structured with clear separation:
- **Unit tests** cover pure algorithms (metrics, peaks, wbal, crypto, resampler, FIT parsing)
- **Integration tests** cover API behavior with real database operations

Example of good test design:
- `test_upload.py` tests data persistence (records, laps, raw bytes)
- `test_activities.py` tests API responses (GeoJSON format, ordering)
- These complement each other without duplication

### Minor overlaps (acceptable)

1. **Activity creation** appears in multiple test files (`test_activities.py`, `test_upload.py`, `test_records.py`) but each tests different aspects
2. **Auth checks** (`test_auth.py`, `test_admin.py`) test similar patterns but for different endpoints - this is appropriate

**Recommendation: No tests to remove.**

## 2. Coverage Gaps

### Backend - Critical gaps (sorted by risk)

| Module | Coverage | Risk | Notes |
|--------|----------|------|-------|
| `garmin.py` | 29% | **HIGH** | External API client, critical for Garmin Connect sync |
| `init_db.py` | 0% | LOW | One-time initialization, not runtime code |
| `peaks.py` | 41% | MEDIUM | Power curve logic, but unit tests exist |
| `app.py` | 46% | LOW | Startup/middleware, covered by integration |
| `jobs.py` | 47% | MEDIUM | Background job wrappers |

### Backend - Well covered (>80%)

- `pmc.py` - 98% (good integration tests)
- `route_matching.py` - 98%
- `thresholds.py` - 97%
- `models.py` - 98%
- `config.py`, `db.py` - 100%

### Frontend - Missing test files

| Component | Has Tests | Priority |
|-----------|-----------|----------|
| `Dashboard.tsx` | No | MEDIUM |
| `PMCView.tsx` | No | LOW |
| `PowerCurveView.tsx` | No | LOW |
| `Header.tsx` | No | LOW |
| `Settings.tsx` | No | MEDIUM |
| `Sidebar.tsx` | No | LOW |
| `ErrorDisplay.tsx` | No | LOW |
| `prs.ts` | No | MEDIUM |

**Recommendation:** Add tests for `Settings.tsx` (user-facing settings management) and `prs.ts` (PR detection logic).

## 3. Test Quality Assessment

### Strengths

1. **Meaningful assertions**: Tests verify actual business behavior, not just "200 OK"
   - Example: `test_upload_with_thresholds_computes_np_if_tss` checks NP > 0, IF in range, TSS > 0
   
2. **Edge cases covered**: 
   - `test_upload_no_gps_still_succeeds`
   - `test_upload_only_stores_peaks_for_valid_durations`
   
3. **Isolation**: User A cannot see User B's activities (multi-tenant security tested)

4. **Real database**: PostGIS spatial queries tested against real PostgreSQL

### Areas for improvement

1. **No mocking of external APIs**: `garmin.py` and `xert.py` call external services. Unit tests with mocked HTTP responses would:
   - Run faster
   - Not require network access
   - Allow testing error scenarios

2. **No negative test cases for some modules**: 
   - What happens when FIT file is corrupted?
   - What if Xert API returns invalid JSON?

## 4. Test Tier Structure Recommendation

### Tier 1: Fast unit tests (~1s)
- `tests/unit/` - already exists, 109 tests
- **Run on**: every file save, pre-commit hook
- **Add**: Mocked API client tests for `garmin.py`, `xert.py`

### Tier 2: Integration tests (~3min)
- `tests/integration/` - already exists, 190 tests
- **Run on**: pre-push, CI
- **Consider**: Marking slow tests (>5s) with `@pytest.mark.slow` for selective runs

### Tier 3: Frontend tests (~3s)
- `frontend/src/*.test.tsx` - 43 tests
- **Run on**: pre-push, CI
- **Add**: Settings, Dashboard tests

### Suggested markers

```python
# conftest.py
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (>5s)")

# In tests
@pytest.mark.slow
async def test_bulk_upload_15_activities(...):
    ...
```

## 5. Actionable Recommendations

### High priority

1. **Add unit tests for `garmin.py`** with mocked HTTP responses
   - Test authentication flow
   - Test activity download parsing
   - Test error handling (rate limits, timeouts)
   - Estimated: 10-15 tests, ~0.5s runtime

2. **Add `@pytest.mark.slow` marker** to tests >5s
   - `test_bulk_upload_15_activities_single_notification` (7s)
   - `test_finalize_creates_single_summary_notification` (7s)
   - Allows `pytest -m "not slow"` for faster local runs

### Medium priority

3. **Add `Settings.test.tsx`** for frontend
   - Unit preferences persistence
   - Integration disconnection flows

4. **Add error scenario tests**
   - Corrupted FIT file handling
   - External API failure handling

### Low priority

5. **Add `Dashboard.test.tsx`** (mostly visual, lower risk)
6. **Consider property-based testing** for metrics calculations (hypothesis library)

## 6. Files to Modify

None to remove. Add:
- `backend/tests/unit/test_garmin.py` - mocked HTTP tests
- `frontend/src/Settings.test.tsx` - settings component tests
- Update `backend/tests/integration/conftest.py` - add `slow` marker

## Conclusion

The test suite is **healthy with no dead weight**. The 72% backend coverage is reasonable for an integration-focused test strategy. The main gap is the `garmin.py` module at 29% coverage - this is the highest-risk untested code because it handles external API interactions that are prone to failures.
