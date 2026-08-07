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

/**
 * Extended test fixture with authenticated user.
 */
export const test = base.extend<{
  authenticatedPage: Page;
  testUser: TestUser;
}>({
  // Provides a page with a freshly registered and logged-in user
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

export { expect };
