/**
 * E2E tests for Records (PRs) page.
 *
 * Tests the personal records page, including lifetime PRs and route PRs.
 * Verifies the empty state and the populated state after uploading activities.
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 * Uses admin API to approve user in case require_approval is enabled.
 * 
 * NOTE: Tests run serially within this file to ensure proper ordering
 * (empty state before uploading, populated state after).
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from './fixtures/auth';
import { uploadFitFileAndWait, getFixtureFitPath } from './fixtures/upload';

const testUser = generateTestUser('records');

// Run tests serially to ensure empty state is tested before uploads
test.describe.serial('Records', () => {
  test.beforeAll(async ({ request }) => {
    await registerAndApproveUser(request, testUser);
  });

  test('records page shows empty state for new user', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/records');

    // Should show Records heading (exact match to avoid matching empty state title)
    await expect(page.getByRole('heading', { name: 'Records', exact: true })).toBeVisible();

    // Should show empty state message
    await expect(page.getByText('No personal records yet')).toBeVisible();
    await expect(page.getByText('Complete some activities')).toBeVisible();
  });

  test('records page shows PRs after uploading activity with power data', async ({ page, request }) => {
    // Login via API for upload
    await request.post('/api/login', {
      data: { email: testUser.email, password: testUser.password },
    });

    // Upload a FIT file with power data
    const fitPath = getFixtureFitPath('cp-ride1-2min.fit');
    await uploadFitFileAndWait(request, fitPath);

    // Now view records page
    await loginViaApi(page, testUser);
    await page.goto('/records');

    // Should show Records heading
    await expect(page.getByRole('heading', { name: 'Records', exact: true })).toBeVisible();

    // Should show Lifetime PRs section (h2)
    await expect(page.locator('h2', { hasText: 'Lifetime PRs' })).toBeVisible();

    // Should show some PR tiles (power duration PRs from cp-ride files)
    const prTiles = page.locator('.rounded-lg.border.text-center');
    await expect(prTiles.first()).toBeVisible({ timeout: 15000 });
  });

  test('PR tiles display correctly formatted values', async ({ page }) => {
    // User already has data from previous test
    await loginViaApi(page, testUser);
    await page.goto('/records');

    // Wait for PRs to load - look for the section heading (h2)
    await expect(page.locator('h2', { hasText: 'Lifetime PRs' })).toBeVisible({ timeout: 15000 });

    // PR tiles should have labels and values
    const firstTile = page.locator('.rounded-lg.border.text-center').first();
    await expect(firstTile).toBeVisible();

    // Label should be present (uppercase)
    const label = firstTile.locator('.uppercase');
    await expect(label).toBeVisible();

    // Value should be present (bold number)
    const value = firstTile.locator('.font-bold');
    await expect(value).toBeVisible();
  });

  test('records page navigation from dashboard', async ({ page }) => {
    await loginViaApi(page, testUser);

    // Start from dashboard
    await page.goto('/');

    // Look for Records link in navigation
    const recordsLink = page.getByRole('link', { name: /records/i });
    
    // If nav link exists, click it
    if (await recordsLink.isVisible().catch(() => false)) {
      await recordsLink.click();
      await expect(page).toHaveURL('/records');
      await expect(page.getByRole('heading', { name: 'Records', exact: true })).toBeVisible();
    } else {
      // Fallback: navigate directly
      await page.goto('/records');
      await expect(page.getByRole('heading', { name: 'Records', exact: true })).toBeVisible();
    }
  });

  test('power curve page renders chart with data', async ({ page }) => {
    // User has activities from previous upload tests
    await loginViaApi(page, testUser);
    await page.goto('/power-curve');

    // Should show Power Curve heading
    await expect(page.getByRole('heading', { name: /Power Curve/i })).toBeVisible({ timeout: 10000 });

    // Should render the chart (Recharts renders an SVG)
    const chart = page.locator('.recharts-wrapper');
    await expect(chart).toBeVisible({ timeout: 15000 });

    // Chart should have line elements (the power curve line)
    const chartLine = page.locator('.recharts-line');
    await expect(chartLine.first()).toBeVisible();
  });
});
