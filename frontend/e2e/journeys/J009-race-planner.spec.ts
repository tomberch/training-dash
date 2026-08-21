import { test, expect, Page } from '@playwright/test';
import { createAndLoginUser, TestUser } from '../fixtures';
import * as path from 'path';
import * as fs from 'fs';

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
  let user: TestUser;

  test.beforeEach(async ({ page }) => {
    user = await createAndLoginUser(page, 'raceplanner');
  });

  test('can navigate to Race Planner from sidebar', async ({ page }) => {
    await page.goto('/');

    // Find and click Race Planner in sidebar
    const sidebar = page.locator('nav');
    await sidebar.getByText('Race Planner').click();

    // Should navigate to race planner dashboard
    await expect(page).toHaveURL('/race-planner');
    await expect(page.getByRole('heading', { name: 'Race Planner' })).toBeVisible();
  });

  test('shows getting started guide when no courses', async ({ page }) => {
    await page.goto('/race-planner');

    // Should show getting started section
    await expect(page.getByText(/get started/i)).toBeVisible();
    await expect(page.getByText(/upload.*course/i)).toBeVisible();
  });

  test('can upload a GPX course', async ({ page }) => {
    await page.goto('/race-planner/courses/new');

    // Should be on upload page
    await expect(page.getByText(/upload/i)).toBeVisible();

    // Create a temp GPX file and upload
    const gpxContent = generateTestGpx();

    // Use file chooser to upload
    const fileChooserPromise = page.waitForEvent('filechooser');

    // Click the upload area/button
    await page.locator('input[type="file"]').or(page.getByText(/drop.*file|select.*file|choose.*file/i)).first().click();

    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'test-course.gpx',
      mimeType: 'application/gpx+xml',
      buffer: gpxContent,
    });

    // Fill in name if there's a name field
    const nameInput = page.getByLabel(/name/i);
    if (await nameInput.isVisible()) {
      await nameInput.fill('E2E Test Course');
    }

    // Submit the form - look for save/upload/create button
    await page.getByRole('button', { name: /save|upload|create/i }).click();

    // Should redirect to course detail or show success
    await expect(page).toHaveURL(/\/race-planner\/courses\/\d+/);

    // Course details should be visible
    await expect(page.getByText(/distance/i)).toBeVisible();
    await expect(page.getByText(/elevation/i)).toBeVisible();
  });

  test('can view course details with segments', async ({ page }) => {
    // First upload a course via API
    const gpxContent = generateTestGpx();
    const formData = new FormData();
    formData.append('file', new Blob([gpxContent], { type: 'application/gpx+xml' }), 'test.gpx');
    formData.append('name', 'Detail Test Course');

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

    // Should show course name and metrics
    await expect(page.getByText('Detail Test Course')).toBeVisible();
    await expect(page.getByText(/distance/i)).toBeVisible();
    await expect(page.getByText(/elevation/i)).toBeVisible();

    // Should show segments section
    await expect(page.getByText(/segments/i)).toBeVisible();
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
    await expect(page.getByText(/generate.*plan/i)).toBeVisible();

    // Fill in FTP (required)
    const ftpInput = page.getByLabel(/ftp/i).or(page.locator('input[name*="ftp"]'));
    await ftpInput.fill('280');

    // Fill in weight if visible
    const weightInput = page.getByLabel(/weight/i).or(page.locator('input[name*="weight"]'));
    if (await weightInput.isVisible()) {
      await weightInput.fill('72');
    }

    // Submit
    await page.getByRole('button', { name: /generate/i }).click();

    // Should redirect to plan detail
    await expect(page).toHaveURL(/\/race-planner\/plans\/\d+/);

    // Plan details should be visible
    await expect(page.getByText(/time/i)).toBeVisible();
    await expect(page.getByText(/power/i)).toBeVisible();
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

    // Should show plan info
    await expect(page.getByText(/time/i)).toBeVisible();
    await expect(page.getByText(/power/i)).toBeVisible();

    // Should show segment targets
    await expect(page.getByText(/segment/i)).toBeVisible();
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
    await expect(page.getByText('Course Alpha')).toBeVisible();
    await expect(page.getByText('Course Beta')).toBeVisible();

    // Should show upload button
    await expect(page.getByRole('button', { name: /upload/i })).toBeVisible();
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
    const courseResponse = await page.request.post('/api/courses', {
      multipart: {
        file: { name: 'delete-test.gpx', mimeType: 'application/gpx+xml', buffer: gpxContent },
        name: 'Course To Delete',
      },
    });
    const course = await courseResponse.json();

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

    // Click upload course button
    await page.getByRole('button', { name: /upload.*course/i }).click();
    await expect(page).toHaveURL('/race-planner/courses/new');

    // Upload GPX
    const gpxContent = generateTestGpx();
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.locator('input[type="file"]').or(page.getByText(/drop.*file|select.*file|choose.*file/i)).first().click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'workflow-test.gpx',
      mimeType: 'application/gpx+xml',
      buffer: gpxContent,
    });

    // Fill name if visible
    const nameInput = page.getByLabel(/name/i);
    if (await nameInput.isVisible()) {
      await nameInput.fill('Workflow Test Course');
    }

    // Save course
    await page.getByRole('button', { name: /save|upload|create/i }).click();

    // Should be on course detail
    await expect(page).toHaveURL(/\/race-planner\/courses\/\d+/);

    // Click generate plan
    await page.getByRole('button', { name: /generate.*plan/i }).click();
    await expect(page).toHaveURL(/\/race-planner\/courses\/\d+\/generate/);

    // Fill FTP
    await page.getByLabel(/ftp/i).or(page.locator('input[name*="ftp"]')).fill('275');

    // Generate
    await page.getByRole('button', { name: /generate/i }).click();

    // Should be on plan detail
    await expect(page).toHaveURL(/\/race-planner\/plans\/\d+/);
    await expect(page.getByText(/time/i)).toBeVisible();
    await expect(page.getByText(/power/i)).toBeVisible();
  });
});
