import { test, expect } from '@playwright/test';
import { createAndLoginUser } from '../fixtures';

/**
 * E2E tests for Race Planner feature.
 *
 * Tests the full race planner workflow:
 * - Navigate to Race Planner from sidebar
 * - Upload a GPX course
 * - View course details with segments
 * - Generate a race plan
 * - View plan details with segment targets
 * - Browse course and plan lists
 */

// Generate a simple GPX file for testing
function generateTestGpx(): Buffer {
  const gpx = `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="e2e-test" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>E2E Test Course</name>
  </metadata>
  <trk>
    <name>Test Ride</name>
    <trkseg>
      <trkpt lat="37.7749" lon="-122.4194"><ele>10.0</ele></trkpt>
      <trkpt lat="37.7759" lon="-122.4184"><ele>15.0</ele></trkpt>
      <trkpt lat="37.7769" lon="-122.4174"><ele>30.0</ele></trkpt>
      <trkpt lat="37.7779" lon="-122.4164"><ele>25.0</ele></trkpt>
      <trkpt lat="37.7789" lon="-122.4154"><ele>20.0</ele></trkpt>
      <trkpt lat="37.7799" lon="-122.4144"><ele>15.0</ele></trkpt>
    </trkseg>
  </trk>
</gpx>`;
  return Buffer.from(gpx);
}

test.describe('J009: Race Planner', () => {
  test.beforeEach(async ({ page }) => {
    await createAndLoginUser(page, 'raceplanner');
  });

  test('can navigate to Race Planner from sidebar', async ({ page }) => {
    await page.goto('/');

    // Find and click Race Planner link in sidebar (use role to avoid matching section header)
    await page.getByRole('link', { name: 'Race Planner' }).click();

    // Should navigate to race planner dashboard
    await expect(page).toHaveURL('/race-planner');
    // Use exact match and level to avoid matching "Get Started with Race Planner" h2
    await expect(page.getByRole('heading', { name: 'Race Planner', exact: true, level: 1 })).toBeVisible();
  });

  test('shows getting started guide when no courses', async ({ page }) => {
    await page.goto('/race-planner');

    // Should show getting started section - wait for page to load first
    await expect(page.getByRole('heading', { name: 'Race Planner', exact: true, level: 1 })).toBeVisible();
    await expect(page.getByText(/get started/i)).toBeVisible({ timeout: 10000 });
    // Be specific - scope to main content and use first() since there may be multiple
    await expect(page.locator('main').getByRole('button', { name: 'Upload Course' }).first()).toBeVisible();
  });

  test('can upload a GPX course', async ({ page }) => {
    await page.goto('/race-planner/courses/new');

    // Should be on upload page - wait for page to fully load
    await expect(page.getByRole('heading', { name: /upload|new course/i })).toBeVisible({ timeout: 10000 });

    // Create a temp GPX file and upload
    const gpxContent = generateTestGpx();

    // Set files directly on the file input - scope to main to avoid header file input
    const fileInput = page.locator('main input[type="file"]');
    await fileInput.setInputFiles({
      name: 'test-course.gpx',
      mimeType: 'application/gpx+xml',
      buffer: gpxContent,
    });

    // Fill in name if there's a name field - scope to main content to avoid header conflicts
    const nameInput = page.locator('main').getByLabel(/name/i);
    if (await nameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await nameInput.fill('E2E Test Course');
    }

    // Submit the form - scope to main content to avoid header upload button
    await page.locator('main').getByRole('button', { name: /save|upload|create/i }).click();

    // Should redirect to course detail or show success
    await expect(page).toHaveURL(/\/race-planner\/courses\/\d+/, { timeout: 30000 });

    // Course details should be visible - UI shows "Distance" and "Elevation Gain"
    await expect(page.getByText('Distance', { exact: true })).toBeVisible();
    await expect(page.getByText('Elevation Gain', { exact: true })).toBeVisible();
  });

  test('can view course details with segments', async ({ page }) => {
    // First upload a course via API
    const gpxContent = generateTestGpx();

    const uploadResponse = await page.request.post('/api/courses', {
      multipart: {
        file: {
          name: 'test.gpx',
          mimeType: 'application/gpx+xml',
          buffer: gpxContent,
        },
        name: 'Detail Test Course',
      },
    });
    expect(uploadResponse.ok()).toBeTruthy();
    const course = await uploadResponse.json();

    // Navigate to course detail
    await page.goto(`/race-planner/courses/${course.id}`);

    // Should show course name and metrics - UI shows "Distance" and "Elevation Gain"
    const main = page.locator('main');
    await expect(main.getByText('Detail Test Course')).toBeVisible({ timeout: 10000 });
    await expect(main.getByText('Distance', { exact: true })).toBeVisible();
    await expect(main.getByText('Elevation Gain', { exact: true })).toBeVisible();

    // Should show segments section - heading includes count like "Segments (2)"
    await expect(main.getByRole('heading', { name: /Segments/i })).toBeVisible();
  });

  test('can generate a race plan from course', async ({ page }) => {
    // Upload a course first
    const gpxContent = generateTestGpx();
    const uploadResponse = await page.request.post('/api/courses', {
      multipart: {
        file: {
          name: 'plan-test.gpx',
          mimeType: 'application/gpx+xml',
          buffer: gpxContent,
        },
        name: 'Plan Test Course',
      },
    });
    expect(uploadResponse.ok()).toBeTruthy();
    const course = await uploadResponse.json();

    // Navigate to generate plan page
    await page.goto(`/race-planner/courses/${course.id}/generate`);

    // Should show plan generation form
    const main = page.locator('main');
    await expect(page.getByRole('heading', { name: 'Generate Race Plan' })).toBeVisible({ timeout: 10000 });

    // Fill in FTP (required) - use more specific locator within main
    const ftpInput = main.getByRole('spinbutton', { name: /ftp/i }).or(main.locator('input[name*="ftp"]'));
    await ftpInput.fill('280');

    // Fill in weight if visible
    const weightInput = main.getByRole('spinbutton', { name: /weight/i }).or(main.locator('input[name*="weight"]'));
    if (await weightInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await weightInput.fill('72');
    }

    // Submit - use exact name to match "Generate Plan" button
    await main.getByRole('button', { name: 'Generate Plan' }).click();

    // UI shows success modal with "Plan Generated!" - click "View Full Plan" to navigate
    await expect(page.getByRole('heading', { name: 'Plan Generated!' })).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'View Full Plan' }).click();

    // Should redirect to plan detail
    await expect(page).toHaveURL(/\/race-planner\/plans\/\d+/, { timeout: 10000 });

    // Plan details should be visible - use exact text
    await expect(page.getByText('Total Time', { exact: true })).toBeVisible();
  });

  test('can view plan details with segment targets', async ({ page }) => {
    // Upload course and generate plan via API
    const gpxContent = generateTestGpx();
    const uploadResponse = await page.request.post('/api/courses', {
      multipart: {
        file: {
          name: 'detail-plan.gpx',
          mimeType: 'application/gpx+xml',
          buffer: gpxContent,
        },
        name: 'Plan Detail Course',
      },
    });
    const course = await uploadResponse.json();

    const planResponse = await page.request.post('/api/race-plans', {
      data: {
        course_id: course.id,
        ftp_watts: 280,
        rider_weight_kg: 72,
      },
    });
    expect(planResponse.ok()).toBeTruthy();
    const plan = await planResponse.json();

    // Navigate to plan detail
    await page.goto(`/race-planner/plans/${plan.id}`);

    // Should show plan info - use exact text to avoid duplicates
    const main = page.locator('main');
    await expect(main.getByText('Total Time', { exact: true })).toBeVisible({ timeout: 10000 });

    // Should show segment targets - heading is "Segment Targets"
    await expect(main.getByRole('heading', { name: 'Segment Targets' })).toBeVisible();
  });

  test('can browse courses list', async ({ page }) => {
    // Create a couple courses via API
    const gpxContent = generateTestGpx();

    await page.request.post('/api/courses', {
      multipart: {
        file: { name: 'course1.gpx', mimeType: 'application/gpx+xml', buffer: gpxContent },
        name: 'Course Alpha',
      },
    });
    await page.request.post('/api/courses', {
      multipart: {
        file: { name: 'course2.gpx', mimeType: 'application/gpx+xml', buffer: gpxContent },
        name: 'Course Beta',
      },
    });

    // Navigate to courses list
    await page.goto('/race-planner/courses');

    // Should show both courses
    await expect(page.getByText('Course Alpha')).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Course Beta')).toBeVisible();

    // Should show upload button - be specific to avoid matching header's Upload FIT button
    await expect(page.getByRole('button', { name: 'Upload Course' })).toBeVisible();
  });

  test('can browse plans list', async ({ page }) => {
    // Create course and plans via API
    const gpxContent = generateTestGpx();
    const courseResponse = await page.request.post('/api/courses', {
      multipart: {
        file: { name: 'plans-list.gpx', mimeType: 'application/gpx+xml', buffer: gpxContent },
        name: 'Plans List Course',
      },
    });
    const course = await courseResponse.json();

    await page.request.post('/api/race-plans', {
      data: { course_id: course.id, ftp_watts: 250, name: 'Plan One' },
    });
    await page.request.post('/api/race-plans', {
      data: { course_id: course.id, ftp_watts: 280, name: 'Plan Two' },
    });

    // Navigate to plans list
    await page.goto('/race-planner/plans');

    // Should show both plans
    await expect(page.getByText('Plan One')).toBeVisible();
    await expect(page.getByText('Plan Two')).toBeVisible();
  });

  test('can delete a course', async ({ page }) => {
    // Create a course via API
    const gpxContent = generateTestGpx();
    await page.request.post('/api/courses', {
      multipart: {
        file: { name: 'delete-test.gpx', mimeType: 'application/gpx+xml', buffer: gpxContent },
        name: 'Course To Delete',
      },
    });

    // Navigate to courses list
    await page.goto('/race-planner/courses');
    await expect(page.getByText('Course To Delete')).toBeVisible();

    // Click delete button (in actions column)
    await page.getByRole('row', { name: /course to delete/i }).getByRole('button', { name: /delete/i }).click();

    // Confirm deletion in dialog
    await page.getByRole('button', { name: /delete/i }).last().click();

    // Course should be gone
    await expect(page.getByText('Course To Delete')).not.toBeVisible();
  });

  test('can delete a plan', async ({ page }) => {
    // Create course and plan via API
    const gpxContent = generateTestGpx();
    const courseResponse = await page.request.post('/api/courses', {
      multipart: {
        file: { name: 'plan-delete.gpx', mimeType: 'application/gpx+xml', buffer: gpxContent },
        name: 'Plan Delete Course',
      },
    });
    const course = await courseResponse.json();

    await page.request.post('/api/race-plans', {
      data: { course_id: course.id, ftp_watts: 250, name: 'Plan To Delete' },
    });

    // Navigate to plans list
    await page.goto('/race-planner/plans');
    await expect(page.getByText('Plan To Delete')).toBeVisible();

    // Click delete button
    await page.getByRole('row', { name: /plan to delete/i }).getByRole('button', { name: /delete/i }).click();

    // Confirm deletion
    await page.getByRole('button', { name: /delete/i }).last().click();

    // Plan should be gone
    await expect(page.getByText('Plan To Delete')).not.toBeVisible();
  });

  test('full workflow: upload → generate → view plan', async ({ page }) => {
    // Start at dashboard
    await page.goto('/race-planner');

    // Wait for page to load - use exact match with level to avoid "Get Started with Race Planner" h2
    await expect(page.getByRole('heading', { name: 'Race Planner', exact: true, level: 1 })).toBeVisible({ timeout: 10000 });

    // Click upload course button - use first() since there may be multiple
    await page.locator('main').getByRole('button', { name: 'Upload Course' }).first().click();
    await expect(page).toHaveURL('/race-planner/courses/new');

    // Upload GPX - set files directly on the input, scoped to main
    const gpxContent = generateTestGpx();
    const fileInput = page.locator('main input[type="file"]');
    await fileInput.setInputFiles({
      name: 'workflow-test.gpx',
      mimeType: 'application/gpx+xml',
      buffer: gpxContent,
    });

    // Fill name if visible - scope to main to avoid header conflicts
    const main = page.locator('main');
    const nameInput = main.getByLabel(/name/i);
    if (await nameInput.isVisible({ timeout: 2000 }).catch(() => false)) {
      await nameInput.fill('Workflow Test Course');
    }

    // Save course - scope to main
    await main.getByRole('button', { name: /save|upload|create/i }).click();

    // Should be on course detail
    await expect(page).toHaveURL(/\/race-planner\/courses\/\d+/, { timeout: 30000 });

    // Click generate plan
    await main.getByRole('button', { name: 'Generate Plan' }).click();
    await expect(page).toHaveURL(/\/race-planner\/courses\/\d+\/generate/);

    // Fill FTP - scope to main
    await main.getByRole('spinbutton', { name: /ftp/i }).or(main.locator('input[name*="ftp"]')).fill('275');

    // Generate - use exact button name
    await main.getByRole('button', { name: 'Generate Plan' }).click();

    // UI shows success modal - click "View Full Plan"
    await expect(page.getByRole('heading', { name: 'Plan Generated!' })).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'View Full Plan' }).click();

    // Should be on plan detail
    await expect(page).toHaveURL(/\/race-planner\/plans\/\d+/, { timeout: 10000 });
    await expect(page.getByText('Total Time', { exact: true })).toBeVisible();
  });
});
