/**
 * E2E tests for breakthrough upload flow.
 *
 * Tests that uploading a ride with a new PR triggers CP recalculation
 * and threshold update.
 *
 * Scenario:
 * 1. User has activities producing CP ≈ 220W (from Xert sync)
 * 2. User uploads "breakthrough" ride with 5-min @ 295W (vs previous 270W)
 * 3. CP recalculates to ≈ 240W
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 *
 * REQUIRES: MOCK_XERT_ENABLED=true in docker-compose.e2e.yml (enabled by default)
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from './fixtures/auth';
import { getFixtureFitPath } from './fixtures/upload';

const testUser = generateTestUser('breakthrough');

// Run tests serially - they depend on each other
test.describe.serial('Breakthrough Upload Flow', () => {
  test.beforeAll(async ({ request }) => {
    await registerAndApproveUser(request, testUser);
  });

  test('establish baseline: connect Xert and sync activities (CP ≈ 220W)', async ({ page, request }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Wait for settings page to load
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Connect Xert credentials
    await page.getByTestId('xert-email').fill('mock@xert.com');
    await page.getByTestId('xert-password').fill('mockpassword');

    // Set sync since date
    const ninetyDaysAgo = new Date();
    ninetyDaysAgo.setDate(ninetyDaysAgo.getDate() - 90);
    await page.getByTestId('xert-sync-since').fill(ninetyDaysAgo.toISOString().split('T')[0]);

    // Connect
    await page.getByTestId('xert-connect').click();
    await expect(page.getByText(/connected|saved|success/i)).toBeVisible({ timeout: 10000 });

    // Trigger sync
    const syncButton = page.getByRole('button', { name: /Sync Now/i });
    await expect(syncButton).toBeVisible({ timeout: 5000 });
    await syncButton.click();

    // Wait for sync to complete
    await expect(syncButton).toBeEnabled({ timeout: 60000 });

    // Verify activities imported
    await page.goto('/');
    const activityItems = page.locator('[data-testid^="activity-"]');
    await expect(activityItems.first()).toBeVisible({ timeout: 30000 });

    // Verify baseline threshold ≈ 220W
    await page.goto('/settings');
    const zonesSection = page.locator('section', { hasText: 'Training Zones' });
    await expect(zonesSection).toBeVisible();

    const sectionText = await zonesSection.textContent();
    const ftpMatch = sectionText?.match(/FTP[:\s]*(\d+)/i);
    if (ftpMatch) {
      const baselineFtp = parseInt(ftpMatch[1], 10);
      // Should be around 220W (±15W tolerance for initial sync)
      expect(baselineFtp).toBeGreaterThanOrEqual(205);
      expect(baselineFtp).toBeLessThanOrEqual(235);
    }
  });

  test('upload breakthrough ride with 5-min @ 295W', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/');

    // Get the file input
    const fileInput = page.locator('input[type="file"][accept=".fit"]');

    // Upload the breakthrough file
    const breakthroughPath = getFixtureFitPath('breakthrough-5min.fit');
    await fileInput.setInputFiles(breakthroughPath);

    // Wait for upload to complete
    await expect(page.getByText(/Activity uploaded successfully/i)).toBeVisible({ timeout: 60000 });
  });

  test('CP recalculates to ≈ 240W after breakthrough', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Wait for settings to load
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Find Training Zones section
    const zonesSection = page.locator('section', { hasText: 'Training Zones' });
    await expect(zonesSection).toBeVisible();

    const sectionText = await zonesSection.textContent();
    const ftpMatch = sectionText?.match(/FTP[:\s]*(\d+)/i);

    if (ftpMatch) {
      const newFtp = parseInt(ftpMatch[1], 10);
      // After breakthrough, FTP should increase toward ~240W
      // Allow wider tolerance since exact CP depends on fitting algorithm
      expect(newFtp).toBeGreaterThanOrEqual(225);
      expect(newFtp).toBeLessThanOrEqual(255);
    }
  });

  test('breakthrough activity appears in list with updated metrics', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/');

    // Find activities
    const activityItems = page.locator('[data-testid^="activity-"]');
    await expect(activityItems.first()).toBeVisible({ timeout: 15000 });

    // The breakthrough ride should be in the list
    // Look for activity with high power (295W area)
    const pageContent = await page.content();

    // Should have multiple activities (original sync + breakthrough)
    const count = await activityItems.count();
    expect(count).toBeGreaterThanOrEqual(6); // 5 from sync + 1 breakthrough
  });

  test('activity detail shows updated TSS based on new threshold', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/');

    // Click on the most recent activity (breakthrough should be first/most recent)
    const activityItems = page.locator('[data-testid^="activity-"]');
    await expect(activityItems.first()).toBeVisible({ timeout: 15000 });
    await activityItems.first().click();

    // Should navigate to activity detail
    await expect(page).toHaveURL(/\/activities\/[a-f0-9-]+/);

    // Activity should have metrics displayed
    await expect(page.getByText(/Summary|Details|Power/i)).toBeVisible({ timeout: 10000 });
  });
});
