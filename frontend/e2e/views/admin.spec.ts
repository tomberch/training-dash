/**
 * E2E tests for Admin Panel.
 *
 * Tests admin-only functionality including user management, settings, and access control.
 *
 * Uses:
 * - Seed admin user (admin@example.com) for admin access tests
 * - Generated test user for non-admin access denial tests
 *
 * ISOLATION: Uses seed admin for admin tests, generates own user for non-admin tests.
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi, ADMIN_USER } from '../fixtures/auth';

// Non-admin test user
const regularUser = generateTestUser('admintest');

test.describe('Admin Panel', () => {
  test.beforeAll(async ({ request }) => {
    await registerAndApproveUser(request, regularUser);
  });

  test('admin can access admin panel', async ({ page }) => {
    await loginViaApi(page, ADMIN_USER);
    await page.goto('/admin');

    // Should show Admin Panel heading
    await expect(page.getByRole('heading', { name: 'Admin Panel' })).toBeVisible();

    // Should show main sections
    await expect(page.getByText('Registration Settings')).toBeVisible();
    await expect(page.getByText('Create User')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible();
  });

  test('admin sees users table with correct columns', async ({ page }) => {
    await loginViaApi(page, ADMIN_USER);
    await page.goto('/admin');

    // Wait for users table to load
    await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible();

    // Table headers
    await expect(page.getByRole('columnheader', { name: 'ID' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Email' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Status' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Created' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Actions' })).toBeVisible();

    // Should have at least one user row (the admin user)
    const userRows = page.locator('[data-testid^="user-row-"]');
    await expect(userRows.first()).toBeVisible();
  });

  test('admin can create a new user', async ({ page }) => {
    await loginViaApi(page, ADMIN_USER);
    await page.goto('/admin');

    // Fill in create user form
    const testEmail = `newuser-${Date.now()}@test.local`;
    const testPassword = 'testpass123';

    await page.getByTestId('new-username').fill(testEmail);
    await page.getByTestId('new-password').fill(testPassword);
    await page.getByTestId('create-user-btn').click();

    // Wait for form to clear (indicates success)
    await expect(page.getByTestId('new-username')).toHaveValue('');

    // New user should appear in the table
    await expect(page.getByText(testEmail)).toBeVisible({ timeout: 10000 });
  });

  test('admin can toggle registration approval setting', async ({ page }) => {
    await loginViaApi(page, ADMIN_USER);
    await page.goto('/admin');

    // Find the toggle button for require approval
    const settingsSection = page.locator('section', { hasText: 'Registration Settings' });
    const toggleButton = settingsSection.locator('button[class*="rounded-full"]');

    await expect(toggleButton).toBeVisible();

    // Get initial state and toggle
    const initialClass = await toggleButton.getAttribute('class');
    await toggleButton.click();

    // Wait for toggle class to change (indicates state update)
    await expect(toggleButton).not.toHaveClass(initialClass!);

    // Toggle back to restore state
    await toggleButton.click();
  });

  test('admin sees action buttons for each user', async ({ page }) => {
    await loginViaApi(page, ADMIN_USER);
    await page.goto('/admin');

    // Wait for users table to load
    const firstUserRow = page.locator('[data-testid^="user-row-"]').first();
    await expect(firstUserRow).toBeVisible();

    // Get the user ID from the first row
    const testIdAttr = await firstUserRow.getAttribute('data-testid');
    const userId = testIdAttr?.replace('user-row-', '');

    if (userId) {
      // Check action buttons exist
      await expect(page.getByTestId(`reset-btn-${userId}`)).toBeVisible();
      await expect(page.getByTestId(`import-btn-${userId}`)).toBeVisible();
      await expect(page.getByTestId(`nuke-btn-${userId}`)).toBeVisible();
    }
  });

  test('non-admin user is denied access to admin panel', async ({ page }) => {
    await loginViaApi(page, regularUser);

    // Try to access admin panel directly
    await page.goto('/admin');

    // Should NOT show Admin Panel - instead should redirect or show error
    // The app might redirect to dashboard or show an error
    await expect(page.getByRole('heading', { name: 'Admin Panel' })).not.toBeVisible({ timeout: 5000 });
  });

  test('admin can access password reset UI', async ({ page }) => {
    await loginViaApi(page, ADMIN_USER);
    await page.goto('/admin');

    // Wait for users table to load
    const firstUserRow = page.locator('[data-testid^="user-row-"]').first();
    await expect(firstUserRow).toBeVisible();

    // Get user ID from first row
    const testIdAttr = await firstUserRow.getAttribute('data-testid');
    const userId = testIdAttr?.replace('user-row-', '');

    if (userId) {
      // Click reset password button
      await page.getByTestId(`reset-btn-${userId}`).click();

      // Password input should appear
      await expect(page.getByTestId(`reset-password-input-${userId}`)).toBeVisible();

      // Cancel button should work
      await page.getByRole('button', { name: 'Cancel' }).click();
      await expect(page.getByTestId(`reset-password-input-${userId}`)).not.toBeVisible();
    }
  });

  test('admin back button navigates away', async ({ page }) => {
    await loginViaApi(page, ADMIN_USER);
    await page.goto('/admin');

    // Verify we're on admin page
    await expect(page.getByRole('heading', { name: 'Admin Panel' })).toBeVisible();

    // Click back button (first one that starts with "← Back")
    await page.getByRole('button', { name: '← Back' }).first().click();

    // Should navigate away from admin
    await expect(page).not.toHaveURL('/admin');
  });
});
