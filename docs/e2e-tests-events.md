# E2E Tests Needed for Events Feature

This document outlines the end-to-end tests required for the Events feature (RideEvents, JournalEntries, Photos). These tests should be added to `/frontend/e2e/`.

## New Journey: J008-events.spec.ts

A complete user journey test for the Events feature.

### Test Scenarios

```typescript
test.describe('J008: Events Journey', () => {
  // 1. Create a multi-day event
  test('user can create a multi-day ride event', async ({ page }) => {
    // Navigate to events page
    // Click "New Event" button
    // Fill in event details (title, start_date, end_date, description)
    // Submit form
    // Verify event appears in list
  });

  // 2. Add journal entries to event
  test('user can add journal entries with markdown', async ({ page }) => {
    // Navigate to existing event detail page
    // Click "Add Entry" 
    // Fill entry description with markdown (headers, bold, lists)
    // Save entry
    // Verify entry renders with formatted markdown
  });

  // 3. Upload photos to event
  test('user can upload photos to event', async ({ page }) => {
    // Navigate to event detail
    // Click upload photo button
    // Select image file
    // Verify photo appears in gallery
    // Verify thumbnail generated
  });

  // 4. Upload photos to journal entry
  test('user can upload photos to journal entry', async ({ page }) => {
    // Navigate to event with entry
    // Click add photo on specific entry
    // Upload image
    // Verify photo attached to correct entry
  });

  // 5. Set event cover photo
  test('user can set cover photo for event', async ({ page }) => {
    // Navigate to event with photos
    // Click "Set as cover" on a photo
    // Verify cover photo displays in hero area
    // Verify cover photo shows in event list card
  });

  // 6. Link activities to event
  test('user can link activities to event', async ({ page }) => {
    // Prerequisites: user has uploaded activities
    // Navigate to event detail
    // Open activity picker dialog
    // Select activities from date range
    // Confirm linking
    // Verify activities appear in event
    // Verify aggregate stats update (total km, elevation, time)
  });

  // 7. Add external links
  test('user can add external links to event', async ({ page }) => {
    // Navigate to event detail
    // Click "Add Link"
    // Enter URL, title, select link type (strava, komoot, etc)
    // Save link
    // Verify link appears with correct icon
    // Verify link opens in new tab
  });

  // 8. Delete event (cascade behavior)
  test('deleting event removes all associated data', async ({ page }) => {
    // Create event with entries, photos, links, activities
    // Delete event
    // Verify event gone from list
    // Verify activities are unlinked (not deleted)
    // Verify photos removed from filesystem
  });
});
```

## New View Tests: views/event-list.spec.ts

Page-specific tests for the events list view.

```typescript
test.describe('Event List View', () => {
  test('shows empty state when no events exist', async ({ page }) => {
    // Login as fresh user with no events
    // Navigate to /events
    // Verify empty state message
    // Verify "Create your first event" CTA button
  });

  test('displays events sorted by date (newest first)', async ({ page }) => {
    // Create multiple events with different dates
    // Verify list order
  });

  test('event cards show cover photo or placeholder', async ({ page }) => {
    // Event with cover: shows photo thumbnail
    // Event without cover: shows gradient placeholder
  });

  test('event cards show aggregate stats', async ({ page }) => {
    // Event with linked activities shows:
    // - Total distance (km)
    // - Total elevation (m)
    // - Total duration
    // - Activity count
  });

  test('event cards show date range correctly', async ({ page }) => {
    // Single-day event: "Jul 15, 2026"
    // Multi-day event: "Jul 15-20, 2026"
    // Cross-month: "Jul 28 - Aug 2, 2026"
  });

  test('clicking event card navigates to detail', async ({ page }) => {
    // Click event card
    // Verify navigation to /events/{id}
  });

  test('pagination works with many events', async ({ page }) => {
    // Create 25+ events
    // Verify pagination controls appear
    // Navigate pages
    // Verify correct events shown
  });
});
```

## New View Tests: views/event-detail.spec.ts

Page-specific tests for event detail view.

```typescript
test.describe('Event Detail View', () => {
  test('displays hero with cover photo or gradient', async ({ page }) => {
    // With cover: full-width hero image
    // Without cover: gradient background with event title
  });

  test('displays event metadata', async ({ page }) => {
    // Title, dates, description
    // Edit button visible for owner
  });

  test('displays aggregate stats panel', async ({ page }) => {
    // Shows: distance, elevation, duration, activity count
    // Stats update when activities linked/unlinked
  });

  test('journal entries display in chronological order', async ({ page }) => {
    // Entries sorted by entry_date
    // Each entry shows formatted markdown
    // Entry photos appear inline
  });

  test('photo gallery shows all event photos', async ({ page }) => {
    // Grid layout for photos
    // Click to open lightbox
    // Lightbox navigation (prev/next)
  });

  test('activity list shows linked activities', async ({ page }) => {
    // List of linked activities with:
    // - Date, title, distance, duration
    // - Click navigates to activity detail
  });

  test('links section displays external links', async ({ page }) => {
    // Links grouped by type (strava, komoot, route, other)
    // Correct icons per link type
    // Opens in new tab
  });

  test('edit mode allows inline updates', async ({ page }) => {
    // Click edit
    // Modify title/description
    // Save
    // Verify changes persisted
  });

  test('activity picker shows available activities', async ({ page }) => {
    // Open picker
    // Shows activities in date range
    // Filter by date
    // Select/deselect activities
    // Already-linked activities pre-selected
  });

  test('returns 404 for non-existent event', async ({ page }) => {
    // Navigate to /events/invalid-uuid
    // Shows 404 page or error message
  });

  test('returns 403 for other user event', async ({ page }) => {
    // Create event as user A
    // Login as user B
    // Try to view user A's event
    // Access denied
  });
});
```

## API Tests: api/events-api.spec.ts

Backend API verification tests.

```typescript
test.describe('Events API', () => {
  test('POST /api/events creates event and returns 201', async ({ request }) => {
    // Verify response shape
    // Verify default values (end_date = start_date if not provided)
  });

  test('GET /api/events returns paginated list', async ({ request }) => {
    // Verify pagination metadata
    // Verify sort order
  });

  test('photo upload generates thumbnail', async ({ request }) => {
    // Upload image via multipart
    // Verify both original and thumbnail URLs returned
    // Verify thumbnail dimensions <= 400x400
  });

  test('aggregate stats calculation is accurate', async ({ request }) => {
    // Link known activities
    // Verify stats match sum of activity metrics
  });

  test('cascade delete removes photos from filesystem', async ({ request }) => {
    // Create event, upload photos
    // Note photo paths
    // Delete event
    // Verify files deleted (check via separate endpoint or test hook)
  });
});
```

## Test Data Requirements

### Fixtures Needed

1. **Sample images** (`fixtures/images/`)
   - `test-photo-1.jpg` - Standard JPEG, ~500KB
   - `test-photo-2.png` - PNG with transparency
   - `test-photo-large.jpg` - 8MB file (within 10MB limit)
   - `test-photo-oversized.jpg` - 12MB file (exceeds limit, for error test)
   - `test-photo-invalid.txt` - Text file with .jpg extension (for mime check)

2. **Test activities** (can reuse existing `cp-ride*.fit` files)
   - Need activities with varying dates to test activity picker date filtering

### Helper Functions Needed

Add to `fixtures/events.ts`:

```typescript
/**
 * Create a test event via API.
 */
export async function createTestEvent(
  request: APIRequestContext,
  data: {
    title: string;
    start_date: string;
    end_date?: string;
    description?: string;
  }
): Promise<{ id: string }>;

/**
 * Upload a photo to an event via API.
 */
export async function uploadEventPhoto(
  request: APIRequestContext,
  eventId: string,
  imagePath: string,
  caption?: string
): Promise<{ id: string; url: string; thumbnail_url: string }>;

/**
 * Link activities to an event via API.
 */
export async function linkActivitiesToEvent(
  request: APIRequestContext,
  eventId: string,
  activityIds: string[]
): Promise<void>;

/**
 * Create a complete test event with entries, photos, and linked activities.
 */
export async function createFullTestEvent(
  request: APIRequestContext,
  options: {
    withEntries?: number;
    withPhotos?: number;
    withActivities?: string[];
    withLinks?: number;
  }
): Promise<EventTestData>;
```

## Test Isolation Notes

- Each test should create its own user to avoid conflicts with parallel execution
- Use `generateTestUser('events-xxx')` prefix for event tests
- Clean up created events in `afterAll` if needed (or rely on per-user isolation)
- Photo uploads create real files - tests may need cleanup hook

## Priority Order

1. **P0 (Critical)**: J008 journey tests - validates core user flow
2. **P1 (High)**: event-list.spec.ts, event-detail.spec.ts - validates views work
3. **P2 (Medium)**: events-api.spec.ts - validates API contracts
4. **P3 (Low)**: Edge cases (oversized files, concurrent uploads)

## Estimated Effort

| Test File | Estimated Tests | Effort |
|-----------|-----------------|--------|
| J008-events.spec.ts | 8 tests | 4-6 hours |
| views/event-list.spec.ts | 7 tests | 2-3 hours |
| views/event-detail.spec.ts | 11 tests | 4-5 hours |
| api/events-api.spec.ts | 5 tests | 2-3 hours |
| fixtures/events.ts | N/A helpers | 1-2 hours |
| fixtures/images/* | N/A test data | 30 min |

**Total: ~31 test scenarios, ~15-20 hours implementation**
