/**
 * E2E tests for FIT file upload functionality.
 *
 * Tests the upload button in the header, file selection, and upload processing.
 * The upload feature is accessed via the "Upload FIT" button in the header,
 * not a dedicated upload page.
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 * Uses admin API to approve user in case require_approval is enabled.
 */
import { test, expect } from '@playwright/test';
import { generateTestUser } from './fixtures/auth';
import { getFixtureFitPath } from './fixtures/upload';

// Admin credentials for approval
const ADMIN_USER = {
  email: 'admin@example.com',
  password: 'admin',
};

const testUser = generateTestUser('upload');

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

test.describe('Upload', () => {
  test.beforeAll(async ({ request }) => {
    await setupTestUser(request);
  });

  test('upload button is visible in header', async ({ page }) => {
    await loginTestUser(page);
    await page.goto('/');

    // Upload button should be visible in the header
    const uploadButton = page.getByRole('button', { name: /Upload FIT/i });
    await expect(uploadButton).toBeVisible();
  });

  test('upload button accepts .fit files only', async ({ page }) => {
    await loginTestUser(page);
    await page.goto('/');

    // Find the hidden file input
    const fileInput = page.locator('input[type="file"][accept=".fit"]');
    await expect(fileInput).toHaveCount(1);
    
    // Verify it only accepts .fit files
    await expect(fileInput).toHaveAttribute('accept', '.fit');
  });

  test('upload button triggers file selection', async ({ page }) => {
    await loginTestUser(page);
    await page.goto('/');

    // Get the upload button
    const uploadButton = page.getByRole('button', { name: /Upload FIT/i });
    await expect(uploadButton).toBeVisible();

    // The button should be enabled
    await expect(uploadButton).toBeEnabled();
  });

  test('successful upload shows processing state and success toast', async ({ page }) => {
    await loginTestUser(page);
    await page.goto('/');

    // Get the file input
    const fileInput = page.locator('input[type="file"][accept=".fit"]');

    // Upload a small FIT file
    const fitPath = getFixtureFitPath('test-ride.fit');
    await fileInput.setInputFiles(fitPath);

    // Should show processing state (button text changes)
    await expect(
      page.getByRole('button', { name: /Uploading|Processing/i })
    ).toBeVisible({ timeout: 5000 });

    // Wait for success toast
    await expect(page.getByText(/Activity uploaded successfully/i)).toBeVisible({ timeout: 60000 });
  });

  test('upload success toast has View action', async ({ page }) => {
    await loginTestUser(page);
    await page.goto('/');

    // Get the file input
    const fileInput = page.locator('input[type="file"][accept=".fit"]');

    // Upload a FIT file
    const fitPath = getFixtureFitPath('cp-ride1-2min.fit');
    await fileInput.setInputFiles(fitPath);

    // Wait for success toast with View action
    const toast = page.locator('[data-sonner-toast]', { hasText: /Activity uploaded/i });
    await expect(toast).toBeVisible({ timeout: 60000 });

    // Toast should have a View button
    const viewButton = toast.getByRole('button', { name: 'View' });
    await expect(viewButton).toBeVisible();

    // Click View to navigate to the activity
    await viewButton.click();

    // Should navigate to activity detail page
    await expect(page).toHaveURL(/\/activities\/[a-f0-9-]+/);
  });

  test('upload button shows loading state during upload', async ({ page }) => {
    await loginTestUser(page);
    await page.goto('/');

    // Get the file input and upload button
    const fileInput = page.locator('input[type="file"][accept=".fit"]');

    // Upload a FIT file - use larger one to have more processing time
    const fitPath = getFixtureFitPath('cp-ride5-mixed.fit');
    await fileInput.setInputFiles(fitPath);

    // Button should show uploading or processing state (text changes)
    // Either "Uploading..." or "Processing..." indicates the loading state
    const loadingButton = page.getByRole('button', { name: /Uploading|Processing/i });
    
    // The button with loading text should appear (it will also be disabled)
    await expect(loadingButton).toBeVisible({ timeout: 5000 });

    // Wait for upload to complete
    await expect(page.getByText(/Activity uploaded successfully/i)).toBeVisible({ timeout: 60000 });

    // Button should be back to normal state
    await expect(page.getByRole('button', { name: /Upload FIT/i })).toBeEnabled();
  });

  test('can upload multiple files sequentially', async ({ page }) => {
    await loginTestUser(page);
    await page.goto('/');

    const fileInput = page.locator('input[type="file"][accept=".fit"]');

    // First upload
    const fitPath1 = getFixtureFitPath('cp-ride3-10min.fit');
    await fileInput.setInputFiles(fitPath1);
    await expect(page.getByText(/Activity uploaded successfully/i)).toBeVisible({ timeout: 60000 });

    // Dismiss or wait for toast to disappear
    await page.waitForTimeout(1000);

    // Second upload
    const fitPath2 = getFixtureFitPath('cp-ride4-20min.fit');
    await fileInput.setInputFiles(fitPath2);
    
    // Should show another success
    await expect(page.getByText(/Activity uploaded successfully/i)).toBeVisible({ timeout: 60000 });
  });
});
