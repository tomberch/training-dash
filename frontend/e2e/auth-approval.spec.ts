/**
 * E2E tests for user registration and admin approval flow.
 *
 * Tests:
 * - First user becomes admin automatically (verified via existing seed user)
 * - New users require approval when require_approval is enabled
 * - Unapproved users see pending approval screen
 * - Admin can approve users
 * - Approved users can access the app
 *
 * Note: The database is seeded by globalSetup with baseline users.
 * The first user (seed admin) is already admin. We test the approval
 * flow by enabling require_approval and registering a new user.
 */
import { test, expect, Page, APIRequestContext } from '@playwright/test';

// Use the seed admin user created by init_db
const ADMIN_USER = {
  email: 'admin@example.com',
  password: 'admin',
};

// User to test approval flow
const PENDING_USER = {
  email: `pending-${Date.now()}@approval-test.com`,
  password: 'PendingPass123!',
};

/**
 * Helper to register a user via API and return the response data.
 */
async function registerUser(
  request: APIRequestContext,
  email: string,
  password: string
): Promise<{ id: number; email: string; is_admin: boolean; is_approved: boolean }> {
  const response = await request.post('/api/register', {
    data: { email, password },
  });
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Registration failed: ${response.status()} ${body}`);
  }
  return response.json();
}

/**
 * Helper to login a user via API.
 */
async function loginUser(
  request: APIRequestContext,
  email: string,
  password: string
): Promise<{ id: number; email: string; is_admin: boolean; is_approved: boolean }> {
  const response = await request.post('/api/login', {
    data: { email, password },
  });
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Login failed: ${response.status()} ${body}`);
  }
  return response.json();
}

/**
 * Helper to set require_approval setting (requires admin auth).
 */
async function setRequireApproval(
  request: APIRequestContext,
  value: boolean
): Promise<void> {
  const response = await request.put('/api/admin/settings/require_approval', {
    data: { value },
  });
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Failed to set require_approval: ${response.status()} ${body}`);
  }
}

/**
 * Helper to get pending users (requires admin auth).
 */
async function getPendingUsers(
  request: APIRequestContext
): Promise<Array<{ id: number; email: string }>> {
  const response = await request.get('/api/admin/users/pending');
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Failed to get pending users: ${response.status()} ${body}`);
  }
  return response.json();
}

/**
 * Helper to approve a user (requires admin auth).
 */
async function approveUser(
  request: APIRequestContext,
  userId: number
): Promise<void> {
  const response = await request.post(`/api/admin/users/${userId}/approve`);
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Failed to approve user: ${response.status()} ${body}`);
  }
}

// Use a dedicated test describe block with serial mode to control order
test.describe.serial('User Registration and Admin Approval Flow', () => {
  let pendingUserId: number;

  test('seed admin user is admin', async ({ request }) => {
    // Login as seed admin
    const adminUser = await loginUser(request, ADMIN_USER.email, ADMIN_USER.password);

    expect(adminUser.is_admin).toBe(true);
    expect(adminUser.is_approved).toBe(true);
  });

  test('admin can enable require_approval setting', async ({ request }) => {
    // Login as admin
    await loginUser(request, ADMIN_USER.email, ADMIN_USER.password);

    // Enable require_approval
    await setRequireApproval(request, true);

    // Verify setting was saved
    const settingsResponse = await request.get('/api/admin/settings');
    const settings = await settingsResponse.json();
    expect(settings.require_approval).toBe(true);
  });

  test('new user registration requires approval when setting is enabled', async ({ request }) => {
    // Create a new request context (clear cookies by logging out first)
    await request.post('/api/logout');
    
    // Register new user - should NOT be approved
    const pendingUser = await registerUser(request, PENDING_USER.email, PENDING_USER.password);

    expect(pendingUser.is_admin).toBe(false);
    expect(pendingUser.is_approved).toBe(false);
    expect(pendingUser.email).toBe(PENDING_USER.email);

    pendingUserId = pendingUser.id;
  });

  test('unapproved user sees pending approval screen', async ({ page }) => {
    // Login as the unapproved user
    await page.goto('/');

    // Fill login form
    await page.getByPlaceholder('Enter email').fill(PENDING_USER.email);
    await page.getByPlaceholder('Enter password').fill(PENDING_USER.password);
    await page.getByRole('button', { name: 'Sign in' }).click();

    // Should see the pending approval screen
    await expect(page.getByText('Account Pending Approval')).toBeVisible({ timeout: 10000 });
    await expect(
      page.getByText('waiting for administrator approval')
    ).toBeVisible();

    // Should have a sign out button
    await expect(page.getByRole('button', { name: 'Sign out' })).toBeVisible();
  });

  test('unapproved user cannot access dashboard routes', async ({ page }) => {
    // Login as the unapproved user
    await page.goto('/');
    await page.getByPlaceholder('Enter email').fill(PENDING_USER.email);
    await page.getByPlaceholder('Enter password').fill(PENDING_USER.password);
    await page.getByRole('button', { name: 'Sign in' }).click();

    // Wait for pending screen
    await expect(page.getByText('Account Pending Approval')).toBeVisible({ timeout: 10000 });

    // Try to navigate directly to activities - should still show pending screen
    await page.goto('/activities');
    await expect(page.getByText('Account Pending Approval')).toBeVisible();

    // Try to navigate to settings - should still show pending screen
    await page.goto('/settings');
    await expect(page.getByText('Account Pending Approval')).toBeVisible();
  });

  test('admin sees pending user in admin panel', async ({ request }) => {
    // Login as admin
    await loginUser(request, ADMIN_USER.email, ADMIN_USER.password);

    // Get pending users
    const pendingUsers = await getPendingUsers(request);

    // Should include the pending user
    const foundUser = pendingUsers.find((u) => u.email === PENDING_USER.email);
    expect(foundUser).toBeDefined();
    expect(foundUser!.id).toBe(pendingUserId);
  });

  test('admin can approve pending user', async ({ request }) => {
    // Login as admin
    await loginUser(request, ADMIN_USER.email, ADMIN_USER.password);

    // Approve the pending user
    await approveUser(request, pendingUserId);

    // Verify user is no longer in pending list
    const pendingUsers = await getPendingUsers(request);
    const stillPending = pendingUsers.find((u) => u.email === PENDING_USER.email);
    expect(stillPending).toBeUndefined();
  });

  test('approved user can access dashboard', async ({ page }) => {
    // Login as the now-approved user
    await page.goto('/');
    await page.getByPlaceholder('Enter email').fill(PENDING_USER.email);
    await page.getByPlaceholder('Enter password').fill(PENDING_USER.password);
    await page.getByRole('button', { name: 'Sign in' }).click();

    // Should NOT see pending approval screen
    await expect(page.getByText('Account Pending Approval')).not.toBeVisible({ timeout: 5000 });

    // Should see dashboard content - either onboarding modal or main dashboard
    // Use .first() to avoid strict mode violation since "Dashboard" appears multiple times
    const dashboardLoaded = page.locator('[data-slot="dialog-title"]').or(
      page.getByRole('heading', { name: 'Activities' })
    ).or(
      page.getByText('No activities yet')
    ).first();
    await expect(dashboardLoaded).toBeVisible({ timeout: 10000 });
  });

  test('cleanup: disable require_approval setting', async ({ request }) => {
    // Login as admin
    await loginUser(request, ADMIN_USER.email, ADMIN_USER.password);

    // Disable require_approval for future tests
    await setRequireApproval(request, false);
  });
});
