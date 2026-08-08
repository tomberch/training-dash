/**
 * E2E tests for Settings page.
 *
 * Tests preferences, unit system toggle, theme selection, and Xert credentials.
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 * Uses admin API to approve user in case require_approval is enabled.
 */
import { test, expect } from '@playwright/test';
import { generateTestUser } from './fixtures/auth';

// Admin credentials for approval
const ADMIN_USER = {
  email: 'admin@example.com',
  password: 'admin',
};

const testUser = generateTestUser('settings');

/**
 * Helper to register, approve (if needed), and login a user via API.
 */
async function setupTestUser(request: import('@playwright/test').APIRequestContext): Promise<void> {
  // Register the user
  const registerResponse = await request.post('/api/register', {
    data: { email: testUser.email, password: testUser.password },
  });
  
  if (!registerResponse.ok()) {
    // User might already exist, try to login
    const loginResponse = await request.post('/api/login', {
      data: { email: testUser.email, password: testUser.password },
    });
    if (!loginResponse.ok()) {
      throw new Error(`Failed to setup test user: ${await registerResponse.text()}`);
    }
    return;
  }

  // Get the user ID from registration response
  const userData = await registerResponse.json();
  const userId = userData.id;

  // Login as admin to approve the user (in case require_approval is enabled)
  await request.post('/api/login', {
    data: { email: ADMIN_USER.email, password: ADMIN_USER.password },
  });

  // Approve the user (will succeed even if already approved)
  await request.post(`/api/admin/users/${userId}/approve`);

  // Login as the test user
  await request.post('/api/login', {
    data: { email: testUser.email, password: testUser.password },
  });
}

async function loginTestUser(page: import('@playwright/test').Page): Promise<void> {
  await page.request.post('/api/login', {
    data: { email: testUser.email, password: testUser.password },
  });
}

test.describe('Settings', () => {
  test.beforeAll(async ({ request }) => {
    await setupTestUser(request);
  });

  test('settings page loads with all sections', async ({ page }) => {
    await loginTestUser(page);
    await page.goto('/settings');

    // Should show Settings heading
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Should show main sections (CardTitle uses data-slot="card-title")
    await expect(page.locator('[data-slot="card-title"]', { hasText: 'Profile' })).toBeVisible();
    await expect(page.locator('[data-slot="card-title"]', { hasText: 'Preferences' })).toBeVisible();
    await expect(page.locator('[data-slot="card-title"]', { hasText: 'Thresholds' })).toBeVisible();
  });

  test('unit system toggle switches between metric and imperial', async ({ page }) => {
    await loginTestUser(page);
    await page.goto('/settings');

    // Wait for preferences section to load
    await expect(page.getByText('Unit System')).toBeVisible();

    // Find the unit toggle button
    const unitToggle = page.getByTestId('unit-toggle');
    await expect(unitToggle).toBeVisible();

    // Get current state and toggle
    const initialText = await unitToggle.textContent();
    const isMetric = initialText?.includes('Metric');

    // Click to toggle
    await unitToggle.click();

    // Wait for the toggle to complete (API call)
    await page.waitForTimeout(500);

    // Should show success feedback
    await expect(page.getByText('Preferences saved')).toBeVisible();

    // Verify the toggle changed
    if (isMetric) {
      // Should now highlight Imperial
      await expect(page.getByText('miles and feet')).toBeVisible();
    } else {
      // Should now highlight Metric
      await expect(page.getByText('kilometers and meters')).toBeVisible();
    }
  });

  test('theme selector allows choosing light, dark, or system', async ({ page }) => {
    await loginTestUser(page);
    await page.goto('/settings');

    // Wait for preferences section
    await expect(page.getByText('Theme')).toBeVisible();

    // Find theme buttons
    const lightButton = page.getByRole('button', { name: 'Light' });
    const darkButton = page.getByRole('button', { name: 'Dark' });
    const systemButton = page.getByRole('button', { name: 'System' });

    await expect(lightButton).toBeVisible();
    await expect(darkButton).toBeVisible();
    await expect(systemButton).toBeVisible();

    // Click dark theme
    await darkButton.click();

    // The button should become active (has different styling)
    // Theme is applied via data-theme attribute on html
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'mocha');

    // Click light theme
    await lightButton.click();
    await expect(page.locator('html')).toHaveAttribute('data-theme', 'latte');
  });

  test('profile section shows email and allows display name edit', async ({ page }) => {
    await loginTestUser(page);
    await page.goto('/settings');

    // Should show Profile section (CardTitle uses data-slot="card-title")
    await expect(page.locator('[data-slot="card-title"]', { hasText: 'Profile' })).toBeVisible();

    // Email should be visible (read-only)
    const emailInput = page.locator('input[type="email"][disabled]');
    await expect(emailInput).toBeVisible();
    await expect(emailInput).toHaveValue(testUser.email);

    // Display name field should be editable
    const displayNameInput = page.getByPlaceholder('How you want to be called');
    await expect(displayNameInput).toBeVisible();

    // Enter a display name
    await displayNameInput.fill('Test User');

    // Save
    await page.getByRole('button', { name: 'Save Profile' }).click();

    // Should show success
    await expect(page.getByText('Profile saved')).toBeVisible();
  });

  test('thresholds section allows adding FTP', async ({ page }) => {
    await loginTestUser(page);
    await page.goto('/settings');

    // Wait for thresholds section (CardTitle uses data-slot="card-title")
    await expect(page.locator('[data-slot="card-title"]', { hasText: 'Thresholds' })).toBeVisible();

    // Click Add/Update button to show form
    const addButton = page.getByRole('button', { name: /Add|Update/ });
    await addButton.click();

    // Form should appear
    const ftpInput = page.getByPlaceholder(/e\.g\. 250|Current:/);
    await expect(ftpInput).toBeVisible();

    // Enter FTP value
    await ftpInput.fill('220');

    // Save
    await page.getByRole('button', { name: 'Save Threshold' }).click();

    // Should show success
    await expect(page.getByText('Threshold saved')).toBeVisible();

    // Threshold should be displayed (shown in the current threshold box and in the table)
    await expect(page.locator('.text-xl', { hasText: '220W' })).toBeVisible();
  });

  test('back button navigates away from settings', async ({ page }) => {
    await loginTestUser(page);

    // Start from dashboard
    await page.goto('/');
    await expect(page.getByText('Recent Activities')).toBeVisible({ timeout: 10000 }).catch(() => {
      // New user might see welcome screen
    });

    // Navigate to settings
    await page.goto('/settings');
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();

    // Click back button
    await page.getByRole('button', { name: /Back/ }).click();

    // Should navigate away from settings
    await expect(page).not.toHaveURL('/settings');
  });
});
