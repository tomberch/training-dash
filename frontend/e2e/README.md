# E2E Test Suite

End-to-end tests using Playwright for the TrainDash fitness application.

## Quick Start

```bash
# Start the test stack (first time or after changes)
docker compose -f ../docker-compose.e2e.yml up -d

# Run all tests
npm run test:e2e

# Run with UI (interactive mode)
npm run test:e2e -- --ui

# Run specific journey
npm run test:e2e -- e2e/journeys/J001-smoke.spec.ts

# Run all journeys only
npm run test:e2e -- e2e/journeys/

# Run views only
npm run test:e2e -- e2e/views/

# View last report
npx playwright show-report e2e-report
```

## Test Organization

```
e2e/
├── journeys/           # Complete user flows (run in order)
│   ├── J001-smoke.spec.ts
│   ├── J002-auth.spec.ts
│   ├── J003-manual-onboarding.spec.ts
│   ├── J004-xert-sync.spec.ts
│   ├── J005-breakthrough.spec.ts
│   ├── J006-admin-approval.spec.ts
│   ├── J007-upload-to-provider.spec.ts
│   ├── J008-events.spec.ts
│   └── J009-race-planner.spec.ts
├── views/              # Page-specific tests
│   ├── activity-list.spec.ts
│   ├── activity-detail.spec.ts
│   ├── records.spec.ts
│   ├── settings.spec.ts
│   ├── upload.spec.ts
│   └── admin.spec.ts
├── api/                # Backend verification
│   ├── pagination.spec.ts
│   └── fitness-calculations.spec.ts
├── fixtures/           # Test data (FIT files, mocks)
├── auth.setup.ts       # Auth state setup
└── global-setup.ts     # DB seeding
```

## User Journeys

### J001: Smoke Tests
Basic health checks - app loads, API responds, auth redirects work.

### J002: Auth Flows
```
Login → Dashboard → Logout → Redirect to login
```
- Valid/invalid credentials
- Session persistence across refresh
- Protected route redirects

### J003: Manual Onboarding
```
Register → Set FTP manually (250W) → Upload FIT → See TSS/IF metrics
```
- New user registration
- Manual threshold setup
- File upload flow
- Metric calculations with manual FTP

### J004: Xert Sync
```
Register → Connect Xert → Sync activities → Auto-threshold ≈220W → Backfill metrics
```
- OAuth mock flow
- Activity import from external service
- CP model auto-calculates threshold
- TSS/IF backfilled for all activities

### J005: Breakthrough
```
[After J004] → Upload PR ride (5min @ 295W) → Threshold updates to ≈240W
```
- Depends on J004 baseline (CP=220W)
- New personal record triggers recalculation
- Threshold history updated

### J006: Admin Approval
```
Admin enables approval → New user registers → Sees pending screen → Admin approves → User gains access
```
- Runs without pre-auth (fresh browser state)
- Admin settings management
- User approval workflow

### J007: Upload to Provider
File upload with provider sync integration.

### J008: Events
```
Create event → View list → Filter by type → View details → Edit (links, entries) → Delete
```
- Full event CRUD lifecycle
- Single-day vs multi-day display differences
- Markdown description rendering
- Journal entry management
- Event filtering by type (race, tour, bikepacking, event)

### J009: Race Planner
```
Navigate → Upload GPX → View course → Generate plan → View plan → Browse lists → Delete
```
- Sidebar navigation to Race Planner
- GPX course upload workflow
- Course detail with segments
- Plan generation with FTP input
- Plan detail with segment targets
- Course and plan list views
- Delete with confirmation dialogs

## Journey Dependency Map

```
J001-smoke ─────────────────────────────────────────────┐
    │                                                   │
    v                                                   │
J002-auth                                               │
    │                                                   │
    ├───────────────────┬───────────────────┐           │
    v                   v                   v           v
J003-manual        J004-xert-sync      J006-admin    views/*
                        │                            api/*
                        v
                   J005-breakthrough
```

## Test Fixtures

### FIT Files (`fixtures/fit-files/`)
Pre-generated files with known power profiles for CP model verification:

| File | Duration | Peak Powers | Purpose |
|------|----------|-------------|---------|
| `cp-test-1.fit` | 60min | 345W@2min, 270W@5min | Baseline ride 1 |
| `cp-test-2.fit` | 60min | 340W@2min, 268W@5min | Baseline ride 2 |
| `cp-test-3.fit` | 60min | 342W@2min, 265W@5min | Baseline ride 3 |
| `cp-test-4.fit` | 60min | 338W@2min, 272W@5min | Baseline ride 4 |
| `cp-test-5.fit` | 60min | 343W@2min, 269W@5min | Baseline ride 5 |
| `breakthrough.fit` | 30min | 295W@5min sustained | Triggers CP update |

**Expected CP model output** (from 5 baseline files): CP ≈ 220W, W' ≈ 15000J

### Xert Mock (`fixtures/mocks/`)
Mock responses for Xert API endpoints - OAuth, activity list, FIT downloads.

## CI Integration

In CI, Playwright generates:
- **GitHub annotations**: Inline failure markers in PR diffs
- **HTML report**: Downloadable artifact with screenshots/traces
- **JSON results**: Parsed for job summary table

See `.github/workflows/e2e.yml` for CI configuration.

## Debugging Failed Tests

```bash
# Run with headed browser
npm run test:e2e -- --headed

# Run with debug mode (step through)
npm run test:e2e -- --debug

# Run specific test with trace
npm run test:e2e -- --trace on -g "test name"

# View trace from failed test
npx playwright show-trace e2e-results/test-name/trace.zip
```

## Adding New Tests

1. **New journey**: Create `journeys/J00X-name.spec.ts`, update this README
2. **New view test**: Add to existing file in `views/` or create new
3. **New API test**: Add to `api/` folder

Naming conventions:
- Journeys: `J001`-`J999` prefix, sorted by dependency order
- Views: Named after the page/component
- API: Named after the endpoint/feature
