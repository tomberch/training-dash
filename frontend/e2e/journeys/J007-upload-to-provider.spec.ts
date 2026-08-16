/**
 * E2E tests for Upload to Provider flow.
 *
 * Tests the complete upload journey:
 * 1. Upload a FIT file to create an activity
 * 2. Connect Xert credentials (mock)
 * 3. Open activity detail and use Actions menu
 * 4. Select provider and device type
 * 5. Upload to provider (mock returns success)
 * 6. Export FIT file download
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 *
 * REQUIRES: MOCK_XERT_ENABLED=true in docker-compose.e2e.yml (enabled by default)
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from '../fixtures/auth';
import { uploadFitFileAndWait, getFixtureFitPath } from '../fixtures/upload';

const testUser = generateTestUser('upload-provider');
let activityId: string | null = null;

// Run tests serially - they depend on each other
test.describe.serial('J007: Upload to Provider Flow', () => {
  test.beforeAll(async ({ request }) => {
    test.setTimeout(120000);
    await registerAndApproveUser(request, testUser);
    
    // Login and upload a test FIT file
    await request.post('/api/login', {
      data: { email: testUser.email, password: testUser.password },
    });
    
    const testFitPath = getFixtureFitPath('test-ride.fit');
    activityId = await uploadFitFileAndWait(request, testFitPath);
  });

  test('user can connect Xert credentials for upload', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/settings');

    // Wait for settings page to load
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Find Xert section
    await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

    // Enter credentials (mock accepts any password except "invalid")
    await page.getByTestId('xert-email').fill('mock@xert.com');
    await page.getByTestId('xert-password').fill('mockpassword');

    // Click Connect
    await page.getByTestId('xert-connect').click();

    // Should show success
    await expect(page.getByText('Xert connected successfully')).toBeVisible({ timeout: 10000 });
  });

  test('activity detail shows Actions menu', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto(`/activities/${activityId}`);

    // Wait for page to load
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Actions button should be visible
    const actionsButton = page.getByRole('button', { name: /Actions/i });
    await expect(actionsButton).toBeVisible();
  });

  test('upload to provider dialog loads devices', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto(`/activities/${activityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Open Upload dialog
    await page.getByRole('button', { name: /Actions/i }).click();
    await page.getByText('Upload to Provider').click();

    // Dialog should open
    await expect(page.getByRole('dialog')).toBeVisible();

    // Device input should be enabled (not loading)
    const deviceInput = page.getByPlaceholder(/Search devices/i);
    await expect(deviceInput).toBeEnabled({ timeout: 5000 });

    // Type to search
    await deviceInput.fill('Edge');
    
    // Should show Edge devices in dropdown
    await expect(page.getByText(/Edge \d+/).first()).toBeVisible({ timeout: 5000 });
  });

  test('user can upload activity to mock Xert', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto(`/activities/${activityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Open Upload dialog
    await page.getByRole('button', { name: /Actions/i }).click();
    await page.getByText('Upload to Provider').click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Select Xert provider
    await page.getByRole('button', { name: /Xert/i }).click();

    // Optionally select a device (Edge 840)
    const deviceInput = page.getByPlaceholder(/Search devices/i);
    await deviceInput.fill('Edge 840');
    await page.getByText('Edge 840').first().click();

    // Verify device is selected
    await expect(page.getByText(/Selected: Edge 840/i)).toBeVisible();

    // Click Upload
    await page.getByRole('button', { name: 'Upload' }).click();

    // Should show success toast (mock returns success)
    await expect(page.getByText(/Uploaded to Xert/i)).toBeVisible({ timeout: 10000 });

    // Dialog should close
    await expect(page.getByRole('dialog')).not.toBeVisible();
  });

  test('user can export FIT file', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto(`/activities/${activityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Open Actions menu
    await page.getByRole('button', { name: /Actions/i }).click();

    // Set up download listener before clicking
    const downloadPromise = page.waitForEvent('download');

    // Click Export FIT File
    await page.getByText('Export FIT File').click();

    // Wait for download to start
    const download = await downloadPromise;

    // Verify download filename contains .fit
    expect(download.suggestedFilename()).toMatch(/\.fit$/);
  });

  test('upload option hidden when no credentials configured', async ({ page, request }) => {
    // First disconnect Xert
    await loginViaApi(page, testUser);
    await page.goto('/settings');
    
    await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();
    
    // Disconnect if connected
    const disconnectButton = page.getByTestId('xert-disconnect');
    if (await disconnectButton.isVisible().catch(() => false)) {
      await disconnectButton.click();
      await expect(page.getByText(/disconnected|removed/i)).toBeVisible({ timeout: 10000 });
    }

    // Now go to activity
    await page.goto(`/activities/${activityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Open Actions menu
    await page.getByRole('button', { name: /Actions/i }).click();

    // Upload to Provider should be hidden when no providers are connected
    await expect(page.getByText('Upload to Provider')).not.toBeVisible();
    
    // Export FIT File should still be visible
    await expect(page.getByText('Export FIT File')).toBeVisible();
  });

  test('device selection is remembered across sessions', async ({ page }) => {
    // Reconnect Xert first
    await loginViaApi(page, testUser);
    await page.goto('/settings');
    
    await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();
    await page.getByTestId('xert-email').fill('mock@xert.com');
    await page.getByTestId('xert-password').fill('mockpassword');
    await page.getByTestId('xert-connect').click();
    await expect(page.getByText('Xert connected successfully')).toBeVisible({ timeout: 10000 });

    // Go to activity and select a device
    await page.goto(`/activities/${activityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    await page.getByRole('button', { name: /Actions/i }).click();
    await page.getByText('Upload to Provider').click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Select Edge 1040
    const deviceInput = page.getByPlaceholder(/Search devices/i);
    await deviceInput.fill('Edge 1040');
    await page.getByText('Edge 1040').first().click();
    await expect(page.getByText(/Selected: Edge 1040/i)).toBeVisible();

    // Close dialog
    await page.getByRole('button', { name: 'Cancel' }).click();

    // Reopen dialog - should remember Edge 1040
    await page.getByRole('button', { name: /Actions/i }).click();
    await page.getByText('Upload to Provider').click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Device should be pre-filled
    await expect(page.getByText(/Selected: Edge 1040/i)).toBeVisible();
  });

  test.afterAll(async ({ request }) => {
    // Cleanup: delete activity
    if (activityId) {
      try {
        await request.post('/api/login', {
          data: { email: testUser.email, password: testUser.password },
        });
        await request.delete(`/api/activities/${activityId}`);
      } catch {
        // Ignore cleanup errors
      }
    }
  });
});
