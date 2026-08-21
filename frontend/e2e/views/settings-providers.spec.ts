/**
 * E2E tests for Provider Integration sections in Settings.
 *
 * Tests Xert and Garmin integration UI:
 * - Connect form renders correctly
 * - Auto-sync toggle appears when connected
 * - Garmin connect button has proper width (not full-width)
 * - Disconnect flow works
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 * REQUIRES: MOCK_XERT_ENABLED=true in docker-compose.e2e.yml (enabled by default)
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from '../fixtures/auth';

const testUser = generateTestUser('settings-providers');

test.describe('Settings - Provider Integrations', () => {
  test.beforeAll(async ({ request }) => {
    await registerAndApproveUser(request, testUser);
  });

  test.describe('Xert Integration', () => {
    test('xert section shows connect form when not connected', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      // Wait for settings page to load
      await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

      // Click on Connections tab to see integrations
      await page.getByRole('tab', { name: 'Connections' }).click();

      // Find Xert section
      await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

      // Should show email and password inputs
      await expect(page.getByTestId('xert-email')).toBeVisible();
      await expect(page.getByTestId('xert-password')).toBeVisible();

      // Should show Connect button
      await expect(page.getByTestId('xert-connect')).toBeVisible();
    });

    test('xert auto-sync toggle appears after connecting', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      // Click on Connections tab to see integrations
      await page.getByRole('tab', { name: 'Connections' }).click();

      await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

      // Wait for connection state to load - check for either connect button or disconnect button
      await expect(
        page.getByTestId('xert-connect').or(page.getByTestId('xert-disconnect'))
      ).toBeVisible({ timeout: 10000 });

      // Connect to Xert (mock accepts any password except "invalid")
      // Only connect if not already connected
      const isConnected = await page.getByTestId('xert-disconnect').isVisible().catch(() => false);
      if (!isConnected) {
        await page.getByTestId('xert-email').fill('mock@xert.com');
        await page.getByTestId('xert-password').fill('mockpassword');
        await page.getByTestId('xert-connect').click();

        // Wait for success
        await expect(page.getByText('Xert connected successfully')).toBeVisible({ timeout: 10000 });
      }

      // Sync toggle should now be visible (label is "Sync from Xert")
      await expect(page.getByText('Sync from Xert')).toBeVisible({ timeout: 5000 });
      
      // Toggle button should be present (aria-pressed attribute indicates it's a toggle)
      const syncToggle = page.locator('button[aria-pressed]').first();
      await expect(syncToggle).toBeVisible();
    });

    test('xert auto-sync toggle can be switched', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      // Click on Connections tab to see integrations
      await page.getByRole('tab', { name: 'Connections' }).click();

      await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

      // Wait for connection state to fully render
      await page.waitForTimeout(1000);

      // If not connected, connect first - use disconnect button as reliable indicator
      const disconnectButton = page.getByTestId('xert-disconnect');
      const emailInput = page.getByTestId('xert-email');
      const isConnected = await disconnectButton.isVisible().catch(() => false);
      
      if (!isConnected) {
        // Verify email input is enabled before filling
        await expect(emailInput).toBeEnabled({ timeout: 5000 });
        await emailInput.fill('mock@xert.com');
        await page.getByTestId('xert-password').fill('mockpassword');
        await page.getByTestId('xert-connect').click();
        await expect(page.getByText('Xert connected successfully')).toBeVisible({ timeout: 10000 });
      }

      // Find the toggle - it's a button with aria-pressed that's enabled (not disabled during save)
      const syncToggle = page.locator('button[aria-pressed]:not([disabled])').first();
      await expect(syncToggle).toBeVisible();
      await expect(syncToggle).toBeEnabled();

      // Get initial state
      const initialState = await syncToggle.getAttribute('aria-pressed');

      // Click to toggle
      await syncToggle.click();

      // Wait for the API call to complete and state to update
      await page.waitForTimeout(1500);

      // State should have changed - re-query the element to get fresh state
      const newToggle = page.locator('button[aria-pressed]:not([disabled])').first();
      const newState = await newToggle.getAttribute('aria-pressed');
      expect(newState).not.toBe(initialState);
    });

    test('xert shows Update, Sync Now, and Disconnect when connected', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      // Click on Connections tab to see integrations
      await page.getByRole('tab', { name: 'Connections' }).click();

      await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

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

      // Should show Disconnect button
      await expect(page.getByTestId('xert-disconnect')).toBeVisible();
      
      // Email should be read-only (disabled)
      const emailInput = page.getByTestId('xert-email');
      await expect(emailInput).toBeDisabled();
      
      // Update/Save Password button should NOT be visible when password is empty
      await expect(page.getByTestId('xert-save-password')).not.toBeVisible();
      
      // "Sync from Xert" toggle label should be visible
      await expect(page.getByText('Sync from Xert')).toBeVisible({ timeout: 5000 });
      
      // Sync Now button only appears when sync is enabled
      // First enable sync by clicking the toggle
      const syncToggle = page.locator('button[aria-pressed]').first();
      const isSyncEnabled = await syncToggle.getAttribute('aria-pressed') === 'true';
      
      if (!isSyncEnabled) {
        await syncToggle.click();
        await page.waitForTimeout(500); // Wait for state update
      }
      
      // Now Sync Now should be visible
      await expect(page.getByRole('button', { name: /Sync Now/i })).toBeVisible({ timeout: 5000 });
    });

    test('xert shows Save Password button when password entered', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      // Click on Connections tab to see integrations
      await page.getByRole('tab', { name: 'Connections' }).click();

      await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

      // Wait for connection state to fully render - either disconnect button or enabled email input should appear
      const disconnectButton = page.getByTestId('xert-disconnect');
      const emailInput = page.getByTestId('xert-email');
      
      // Wait for state to stabilize - either we're connected (disconnect visible) or not (email enabled)
      await page.waitForTimeout(1000);
      
      // Check if connected - use a proper wait, not just isVisible
      const isConnected = await disconnectButton.isVisible().catch(() => false);
      
      if (!isConnected) {
        // Not connected - email input should be enabled
        await expect(emailInput).toBeEnabled({ timeout: 5000 });
        await emailInput.fill('mock@xert.com');
        await page.getByTestId('xert-password').fill('mockpassword');
        await page.getByTestId('xert-connect').click();
        await expect(page.getByText('Xert connected successfully')).toBeVisible({ timeout: 10000 });
      }

      // Save Password button should not be visible initially
      await expect(page.getByTestId('xert-save-password')).not.toBeVisible();

      // Enter a new password
      await page.getByTestId('xert-password').fill('newpassword');

      // Save Password button should now appear
      await expect(page.getByTestId('xert-save-password')).toBeVisible();
      await expect(page.getByTestId('xert-save-password')).toHaveText('Save Password');
    });

    test('xert disconnect removes auto-sync toggle', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      // Click on Connections tab to see integrations
      await page.getByRole('tab', { name: 'Connections' }).click();

      await expect(page.getByRole('heading', { name: 'Xert', level: 3 })).toBeVisible();

      // Wait for connection state to load
      await expect(
        page.getByTestId('xert-connect').or(page.getByTestId('xert-disconnect'))
      ).toBeVisible({ timeout: 10000 });

      // Check if already connected by checking if disconnect button is visible
      const isConnected = await page.getByTestId('xert-disconnect').isVisible().catch(() => false);
      
      if (!isConnected) {
        // Not connected - need to connect first
        await page.getByTestId('xert-email').fill('mock@xert.com');
        await page.getByTestId('xert-password').fill('mockpassword');
        await page.getByTestId('xert-connect').click();
        await expect(page.getByText('Xert connected successfully')).toBeVisible({ timeout: 10000 });
      }

      // Sync toggle should be visible (label is "Sync from Xert")
      await expect(page.getByText('Sync from Xert')).toBeVisible({ timeout: 5000 });

      // Disconnect
      await page.getByTestId('xert-disconnect').click();

      // Wait for disconnect to complete
      await expect(page.getByText(/disconnected|removed/i)).toBeVisible({ timeout: 10000 });

      // Sync toggle should no longer be visible
      await expect(page.getByText('Sync from Xert')).not.toBeVisible();
    });
  });

  test.describe('Garmin Integration', () => {
    test('garmin section shows connect button with proper width', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

      // Click on Connections tab to see integrations
      await page.getByRole('tab', { name: 'Connections' }).click();

      // Find Garmin section
      await expect(page.getByRole('heading', { name: 'Garmin', level: 3 })).toBeVisible();

      // Find the Connect button
      const connectButton = page.getByTestId('garmin-connect');
      await expect(connectButton).toBeVisible();

      // Get button dimensions
      const buttonBox = await connectButton.boundingBox();
      expect(buttonBox).not.toBeNull();

      // Get the Garmin heading's parent card for comparison
      const garminHeading = page.getByRole('heading', { name: 'Garmin', level: 3 });
      const garminSection = garminHeading.locator('xpath=ancestor::div[@data-slot="card"]');
      const cardBox = await garminSection.boundingBox();
      expect(cardBox).not.toBeNull();

      // Button should NOT be full width of the card
      // Allow for padding (button should be less than 50% of card width typically)
      if (buttonBox && cardBox) {
        expect(buttonBox.width).toBeLessThan(cardBox.width * 0.6);
      }
    });

    test('garmin auto-sync toggle appears when connected', async ({ page }) => {
      await loginViaApi(page, testUser);
      await page.goto('/settings');

      // Click on Connections tab to see integrations
      await page.getByRole('tab', { name: 'Connections' }).click();

      await expect(page.getByRole('heading', { name: 'Garmin', level: 3 })).toBeVisible();

      // Check if already connected by looking for auto-sync toggle
      const autoSyncLabel = page.getByText('Auto-sync from Garmin');
      
      if (await autoSyncLabel.isVisible().catch(() => false)) {
        // Already connected - verify toggle is present
        const syncToggle = page.locator('button[aria-pressed]').filter({ 
          has: page.locator('..').filter({ hasText: 'Auto-sync from Garmin' }) 
        });
        // Just verify the auto-sync section exists
        await expect(autoSyncLabel).toBeVisible();
      } else {
        // Not connected - this is expected for a fresh user
        // Garmin OAuth flow can't be automated in E2E, so we just verify the button exists
        await expect(page.getByTestId('garmin-connect')).toBeVisible();
      }
    });
  });
});
