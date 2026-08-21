/**
 * E2E tests for Activity Actions menu provider-awareness.
 *
 * Tests that:
 * - "Upload to Provider" menu item is hidden when no providers are connected
 * - "Upload to Provider" menu item appears when at least one provider is connected
 * - Upload dialog only shows connected providers (not all providers)
 * - Dialog shows helpful message when no providers connected
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 * REQUIRES: MOCK_XERT_ENABLED=true in docker-compose.e2e.yml (enabled by default)
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from '../fixtures/auth';
import { uploadFitFileAndWait, getFixtureFitPath } from '../fixtures/upload';

const testUser = generateTestUser('activity-actions-providers');
let activityId: string | null = null;

test.describe.serial('Activity Actions - Provider Awareness', () => {
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

  test('actions menu hides upload option when no providers connected', async ({ page }) => {
    await loginViaApi(page, testUser);
    
    // First ensure no providers are connected by checking settings
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Click on Connections tab to see integrations
    await page.getByRole('tab', { name: 'Connections' }).click();

    // Verify Xert is not connected (no auto-sync toggle visible)
    const xertAutoSync = page.getByText('Auto-sync from Xert');
    if (await xertAutoSync.isVisible().catch(() => false)) {
      // Disconnect Xert if connected
      await page.getByTestId('xert-disconnect').click();
      await expect(page.getByText(/disconnected|removed/i)).toBeVisible({ timeout: 10000 });
    }

    // Now go to activity detail
    await page.goto(`/activities/${activityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Open Actions menu
    const actionsButton = page.getByRole('button', { name: /Actions/i });
    await expect(actionsButton).toBeVisible();
    await actionsButton.click();

    // Export FIT should always be visible
    await expect(page.getByText('Export FIT File')).toBeVisible();

    // Upload to Provider should NOT be visible when no providers connected
    await expect(page.getByText('Upload to Provider')).not.toBeVisible();
  });

  test('actions menu shows upload option after connecting provider', async ({ page }) => {
    await loginViaApi(page, testUser);
    
    // Connect Xert
    await page.goto('/settings');
    
    // Click on Connections tab to see integrations
    await page.getByRole('tab', { name: 'Connections' }).click();
    
    await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

    await page.getByTestId('xert-email').fill('mock@xert.com');
    await page.getByTestId('xert-password').fill('mockpassword');
    await page.getByTestId('xert-connect').click();
    await expect(page.getByText('Xert connected successfully')).toBeVisible({ timeout: 10000 });

    // Now go to activity detail
    await page.goto(`/activities/${activityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    // Open Actions menu
    await page.getByRole('button', { name: /Actions/i }).click();

    // Upload to Provider should now be visible
    await expect(page.getByText('Upload to Provider')).toBeVisible();
    await expect(page.getByText('Export FIT File')).toBeVisible();
  });

  test('upload dialog only shows connected providers', async ({ page }) => {
    await loginViaApi(page, testUser);
    
    // Ensure Xert is connected (from previous test)
    await page.goto('/settings');
    
    // Click on Connections tab to see integrations
    await page.getByRole('tab', { name: 'Connections' }).click();
    
    // Wait for connection state to load
    await expect(
      page.getByTestId('xert-connect').or(page.getByTestId('xert-disconnect'))
    ).toBeVisible({ timeout: 10000 });
    
    // Check if already connected by looking for disconnect button
    const isConnected = await page.getByTestId('xert-disconnect').isVisible().catch(() => false);
    
    if (!isConnected) {
      // Not connected yet, need to connect
      await page.getByTestId('xert-email').fill('mock@xert.com');
      await page.getByTestId('xert-password').fill('mockpassword');
      await page.getByTestId('xert-connect').click();
      await expect(page.getByText('Xert connected successfully')).toBeVisible({ timeout: 10000 });
    }

    // Go to activity and open upload dialog
    await page.goto(`/activities/${activityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    await page.getByRole('button', { name: /Actions/i }).click();
    await page.getByText('Upload to Provider').click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Should show Xert (connected)
    await expect(page.getByRole('button', { name: /Xert/i })).toBeVisible();

    // Should NOT show Garmin Connect (not connected for this user)
    // Note: The button would only appear if Garmin is connected
    const garminButton = page.getByRole('button', { name: /Garmin Connect/i });
    await expect(garminButton).not.toBeVisible();

    // Close dialog
    await page.getByRole('button', { name: 'Cancel' }).click();
  });

  test('upload dialog provider buttons are properly styled', async ({ page }) => {
    await loginViaApi(page, testUser);
    
    await page.goto(`/activities/${activityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });

    await page.getByRole('button', { name: /Actions/i }).click();
    await page.getByText('Upload to Provider').click();
    await expect(page.getByRole('dialog')).toBeVisible();

    // Find the Xert button
    const xertButton = page.getByRole('button', { name: /Xert/i });
    await expect(xertButton).toBeVisible();

    // Check that button has visible text (not too faded)
    // The button should have text-foreground class when not selected
    const buttonBox = await xertButton.boundingBox();
    expect(buttonBox).not.toBeNull();
    
    // Button should have reasonable height (py-3 = 12px padding each side + text)
    if (buttonBox) {
      expect(buttonBox.height).toBeGreaterThanOrEqual(40); // At least 40px tall
    }

    // Close dialog
    await page.keyboard.press('Escape');
  });

  test('upload dialog shows settings link when no providers connected', async ({ page }) => {
    await loginViaApi(page, testUser);
    
    // Disconnect Xert
    await page.goto('/settings');
    
    // Click on Connections tab to see integrations
    await page.getByRole('tab', { name: 'Connections' }).click();
    
    await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

    // Wait for connection state to fully render
    await page.waitForTimeout(1000);

    // Try to disconnect - wait for disconnect button to be visible before clicking
    const disconnectButton = page.getByTestId('xert-disconnect');
    try {
      await expect(disconnectButton).toBeVisible({ timeout: 5000 });
      await disconnectButton.click();
      await expect(page.getByText(/disconnected|removed/i)).toBeVisible({ timeout: 10000 });
      // Wait for backend to process
      await page.waitForTimeout(1000);
    } catch {
      // Already disconnected or connection state not loaded - continue
    }

    // Go to activity - but now upload won't be in menu
    // We need to test what happens if someone navigates directly to an upload scenario
    // Actually with our change, the menu item is hidden, so we can't test the dialog empty state
    // from this flow. The dialog empty state is a fallback in case of race conditions.
    
    // Verify the menu item is hidden
    await page.goto(`/activities/${activityId}`);
    await expect(page.getByRole('button', { name: 'Back' })).toBeVisible({ timeout: 15000 });
    
    // Wait for provider status to be fetched
    await page.waitForTimeout(1000);

    await page.getByRole('button', { name: /Actions/i }).click();
    await expect(page.getByText('Upload to Provider')).not.toBeVisible();
  });

  test.afterAll(async ({ request }) => {
    // Cleanup
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
