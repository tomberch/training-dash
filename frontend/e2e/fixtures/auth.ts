import { test as base, expect, Page } from '@playwright/test';

/**
 * Authentication helpers and fixtures for E2E tests.
 */

export interface TestUser {
  email: string;
  password: string;
}

/**
 * Generate a unique test user to avoid conflicts between parallel tests.
 */
export function generateTestUser(prefix = 'e2e'): TestUser {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substring(2, 8);
  // Use example.com - RFC 2606 reserved domain for documentation/testing
  return {
    email: `${prefix}-${timestamp}-${random}@example.com`,
    password: 'TestPass123!',
  };
}

/**
 * Register a new user via the API.
 */
export async function registerUser(page: Page, user: TestUser): Promise<void> {
  const response = await page.request.post('/api/register', {
    data: {
      email: user.email,
      password: user.password,
    },
  });
  
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Failed to register user ${user.email}: ${response.status()} ${body}`);
  }
}

/**
 * Login a user via the API and store the session cookie.
 */
export async function loginUser(page: Page, user: TestUser): Promise<void> {
  const response = await page.request.post('/api/login', {
    data: {
      email: user.email,
      password: user.password,
    },
  });
  
  if (!response.ok()) {
    const body = await response.text();
    throw new Error(`Failed to login user ${user.email}: ${response.status()} ${body}`);
  }
}

/**
 * Register and login a new unique user.
 * Returns the user credentials for reference.
 */
export async function createAndLoginUser(page: Page, prefix = 'e2e'): Promise<TestUser> {
  const user = generateTestUser(prefix);
  await registerUser(page, user);
  // Registration auto-logs in, but we explicitly login to ensure cookie is set
  await loginUser(page, user);
  return user;
}

/**
 * Logout the current user.
 */
export async function logoutUser(page: Page): Promise<void> {
  await page.request.post('/api/logout');
}

/**
 * Check if the user is logged in by checking for session cookie.
 */
export async function isLoggedIn(page: Page): Promise<boolean> {
  const cookies = await page.context().cookies();
  return cookies.some(c => c.name === 'session');
}

// Well-known test user for baseline tests (created by globalSetup)
export const BASELINE_USER: TestUser = {
  email: 'testuser@example.com',
  password: 'testpass',
};

// Seed admin user (created by globalSetup/init_db)
export const ADMIN_USER: TestUser = {
  email: 'admin@example.com',
  password: 'admin',
};

/**
 * Register a user, approve them via admin API (handles require_approval setting),
 * and login as the user. This ensures the user can access the dashboard regardless
 * of whether require_approval is enabled.
 * 
 * @param request - Playwright API request context
 * @param user - User credentials to register
 */
export async function registerAndApproveUser(
  request: import('@playwright/test').APIRequestContext,
  user: TestUser
): Promise<void> {
  // Register the user
  const registerResponse = await request.post('/api/register', {
    data: { email: user.email, password: user.password },
  });
  
  if (!registerResponse.ok()) {
    // User might already exist, try to login
    const loginResponse = await request.post('/api/login', {
      data: { email: user.email, password: user.password },
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
    data: { email: user.email, password: user.password },
  });
}

/**
 * Login a user via page's request context.
 */
export async function loginViaApi(
  page: import('@playwright/test').Page,
  user: TestUser
): Promise<void> {
  await page.request.post('/api/login', {
    data: { email: user.email, password: user.password },
  });
}

/**
 * Extended test fixture with authenticated user.
 * 
 * Note: Playwright fixtures use a `use()` callback pattern that oxlint
 * incorrectly flags as a React hook violation. The eslint-disable comments
 * suppress these false positives.
 */
/* eslint-disable react-hooks/rules-of-hooks, no-empty-pattern */
export const test = base.extend<{
  authenticatedPage: Page;
  testUser: TestUser;
}>({
  testUser: async ({}, use) => {
    const user = generateTestUser();
    await use(user);
  },
  
  authenticatedPage: async ({ page, testUser }, use) => {
    await registerUser(page, testUser);
    await loginUser(page, testUser);
    await use(page);
  },
});
/* eslint-enable react-hooks/rules-of-hooks, no-empty-pattern */

export { expect };
