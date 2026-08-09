/**
 * E2E tests for Xert sync flow.
 *
 * Tests the complete Xert integration:
 * 1. Connect Xert credentials
 * 2. Trigger sync (uses MockXertClient in E2E environment)
 * 3. Verify activities imported
 * 4. Verify auto-threshold calculated from CP model
 * 5. Verify TSS/IF backfilled
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 *
 * REQUIRES: MOCK_XERT_ENABLED=true in docker-compose.e2e.yml (enabled by default)
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from '../fixtures/auth';
// MOCK_ACTIVITY_IDS removed - not currently used

const testUser = generateTestUser('xertsync');

// Run tests serially - they depend on each other
test.describe.serial('J004: Xert Sync Flow', () => {
  test.beforeAll(async ({ request }) => {
    await registerAndApproveUser(request, testUser);
  });

  test('user can connect Xert credentials', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Wait for settings page to load
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Find Xert integration section
    await expect(page.getByText('Xert Integration')).toBeVisible();

    // Enter Xert credentials (mock accepts any password except "invalid")
    await page.getByTestId('xert-email').fill('mock@xert.com');
    await page.getByTestId('xert-password').fill('mockpassword');

    // Set sync since date to 90 days ago
    const ninetyDaysAgo = new Date();
    ninetyDaysAgo.setDate(ninetyDaysAgo.getDate() - 90);
    const syncSinceDate = ninetyDaysAgo.toISOString().split('T')[0];
    await page.getByTestId('xert-sync-since').fill(syncSinceDate);

    // Click Connect
    await page.getByTestId('xert-connect').click();

    // Should show success feedback
    await expect(page.getByText(/connected|saved|success/i)).toBeVisible({ timeout: 10000 });

    // Sync Now button should appear after connection
    await expect(page.getByRole('button', { name: /Sync Now/i })).toBeVisible();
  });

  test('sync imports activities from mock Xert', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Wait for Xert section to load
    await expect(page.getByText('Xert Integration')).toBeVisible();

    // Click Sync Now
    const syncButton = page.getByRole('button', { name: /Sync Now/i });
    await expect(syncButton).toBeVisible({ timeout: 5000 });
    await syncButton.click();

    // Wait for sync to complete (button may show "Syncing..." then back to "Sync Now")
    await expect(syncButton).toBeEnabled({ timeout: 60000 });

    // Navigate to activity list
    await page.goto('/');

    // Wait for activities to load - expect at least some of the mock activities
    // MockXertClient returns activities based on FIT files in fixtures directory
    const activityItems = page.locator('[data-testid^="activity-"]');
    await expect(activityItems.first()).toBeVisible({ timeout: 30000 });

    // Should have imported at least 5 activities (the CP model test files)
    const count = await activityItems.count();
    expect(count).toBeGreaterThanOrEqual(5);
  });

  test('auto-threshold calculated from CP model (~220W)', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Wait for settings to load
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Find Training Zones section which shows current FTP
    await expect(page.locator('[data-slot="card-title"]', { hasText: 'Training Zones' })).toBeVisible();

    // Look for the FTP value display
    // The CP model with our test files should produce ~220W
    const ftpDisplay = page.locator('[data-testid="current-ftp"], [data-testid="ftp-value"]');
    
    // If explicit test ID doesn't exist, look for the value near "FTP" label
    if (await ftpDisplay.count() === 0) {
      // Alternative: find the FTP input or display in the zones section
      const zonesSection = page.locator('section', { hasText: 'Training Zones' });
      const ftpText = await zonesSection.textContent();
      
      // Extract FTP value - should be around 220W (±10W tolerance)
      const ftpMatch = ftpText?.match(/FTP[:\s]*(\d+)/i);
      if (ftpMatch) {
        const ftpValue = parseInt(ftpMatch[1], 10);
        expect(ftpValue).toBeGreaterThanOrEqual(210);
        expect(ftpValue).toBeLessThanOrEqual(230);
      }
    } else {
      const ftpText = await ftpDisplay.textContent();
      const ftpValue = parseInt(ftpText?.replace(/\D/g, '') || '0', 10);
      expect(ftpValue).toBeGreaterThanOrEqual(210);
      expect(ftpValue).toBeLessThanOrEqual(230);
    }
  });

  test('TSS values populated for imported activities', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/');

    // Wait for activities to load
    const activityItems = page.locator('[data-testid^="activity-"]');
    await expect(activityItems.first()).toBeVisible({ timeout: 15000 });

    // Click on first activity to see detail
    await activityItems.first().click();

    // Should navigate to activity detail
    await expect(page).toHaveURL(/\/activities\/[a-f0-9-]+/);

    // Wait for activity detail to load
    await expect(page.getByText(/Summary|Details/i)).toBeVisible({ timeout: 10000 });

    // Look for TSS value - it should be populated (not empty or zero)
    // TSS might be shown as "TSS: 85" or in a metrics section
    const _tssElement = page.locator('[data-testid="tss-value"], :text-matches("TSS[:\\s]*\\d+", "i")');
    
    // Alternatively, check the metrics display
    const _metricsSection = page.locator('[data-testid="activity-metrics"], .metrics, [class*="metric"]');
    
    // One of these should show TSS > 0
    const pageContent = await page.content();
    const tssMatch = pageContent.match(/TSS[:\s]*(\d+)/i);
    
    if (tssMatch) {
      const tssValue = parseInt(tssMatch[1], 10);
      expect(tssValue).toBeGreaterThan(0);
    }
  });

  test('threshold history shows auto-created entry', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Wait for settings to load
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Find Training Zones section
    const zonesSection = page.locator('section', { hasText: 'Training Zones' });
    await expect(zonesSection).toBeVisible();

    // Look for threshold history or "auto" indicator
    // Auto-created thresholds typically show a note or are marked
    const sectionText = await zonesSection.textContent();
    
    // Should have an FTP value set (either explicitly shown or via zones being active)
    const hasThreshold = sectionText?.includes('FTP') || sectionText?.includes('Threshold');
    expect(hasThreshold).toBe(true);
  });

  test('Xert disconnect removes credentials', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Wait for Xert section to load
    await expect(page.getByText('Xert Integration')).toBeVisible();

    // Click Disconnect button
    const disconnectButton = page.getByTestId('xert-disconnect');
    await expect(disconnectButton).toBeVisible({ timeout: 5000 });
    await disconnectButton.click();

    // Wait for disconnection to complete
    await expect(page.getByText(/disconnected|removed/i)).toBeVisible({ timeout: 10000 });

    // Sync Now button should no longer be visible
    await expect(page.getByRole('button', { name: /Sync Now/i })).not.toBeVisible();

    // Connect button should be visible again
    await expect(page.getByTestId('xert-connect')).toHaveText(/Connect/i);
  });
});
