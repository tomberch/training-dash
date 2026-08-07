/**
 * Playwright auth setup - creates authenticated storageState for tests.
 *
 * This setup project runs once before test projects and saves the
 * authenticated session to .auth/user.json. Test projects then load
 * this state to skip login in each test.
 *
 * Uses the baseline test user created by globalSetup.
 */
import { test as setup, expect } from '@playwright/test';
import { BASELINE_USER } from './fixtures/auth';

const authFile = '.auth/user.json';

setup('authenticate', async ({ page }): Promise<void> => {
  // Login via API
  const response = await page.request.post('/api/login', {
    data: {
      email: BASELINE_USER.email,
      password: BASELINE_USER.password,
    },
  });

  expect(response.ok()).toBeTruthy();

  // Verify we're logged in by checking /api/me
  const meResponse = await page.request.get('/api/me');
  expect(meResponse.ok()).toBeTruthy();

  const me = await meResponse.json();
  expect(me.email).toBe(BASELINE_USER.email);

  // Save signed-in state to file
  await page.context().storageState({ path: authFile });
});
