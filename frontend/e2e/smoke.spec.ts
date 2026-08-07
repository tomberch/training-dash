import { test, expect } from '@playwright/test';
import { createAndLoginUser, registerUser, loginUser, generateTestUser } from './fixtures';

/**
 * Smoke tests to verify the E2E infrastructure is working correctly.
 * These tests validate:
 * - App is accessible
 * - Health endpoint works
 * - User registration and login work
 * - Basic navigation works
 */

test.describe('Smoke Tests', () => {
  test('health endpoint returns healthy', async ({ request }) => {
    const response = await request.get('/api/health');
    expect(response.ok()).toBeTruthy();
    
    const body = await response.json();
    expect(body.status).toBe('healthy');
    expect(body.database).toBe('connected');
  });

  test('app loads and shows login page', async ({ page }) => {
    // Clear any existing session from storageState
    await page.context().clearCookies();
    
    await page.goto('/');
    
    // Should redirect to login or show login form
    // Check for common login page elements
    await expect(page.locator('text=Login').or(page.locator('text=Sign in')).first()).toBeVisible({ timeout: 10000 });
  });

  test('user can register and login', async ({ page }) => {
    const user = generateTestUser('smoke');
    
    // Register
    await registerUser(page, user);
    
    // Should be logged in after registration
    // Navigate to home to verify auth state
    await page.goto('/');
    
    // Should not be redirected to login (authenticated)
    // Check that we're not on the login page
    const url = page.url();
    expect(url).not.toContain('/login');
  });

  test('user can login with existing account', async ({ page }) => {
    // First register a user via API
    const user = generateTestUser('smoke-login');
    await registerUser(page, user);
    
    // Logout by clearing cookies
    await page.context().clearCookies();
    
    // Now login
    await loginUser(page, user);
    
    // Verify we're authenticated by checking /api/me
    // Use page.request to share the page's cookie context
    const meResponse = await page.request.get('/api/me');
    expect(meResponse.ok()).toBeTruthy();
    
    const me = await meResponse.json();
    expect(me.email).toBe(user.email);
  });

  test('unauthenticated user is redirected to login', async ({ page }) => {
    // Clear any existing session
    await page.context().clearCookies();
    
    // Try to access a protected route
    await page.goto('/activities');
    
    // Should be on login page or see login prompt
    await expect(page.locator('text=Login').or(page.locator('text=Sign in')).first()).toBeVisible({ timeout: 10000 });
  });

  test('authenticated user can access dashboard', async ({ page }) => {
    // Create and login a fresh user
    await createAndLoginUser(page, 'smoke-dashboard');
    
    // Navigate to root
    await page.goto('/');
    
    // Should see some dashboard content (not login)
    // Wait for the page to load and check we're authenticated
    await page.waitForLoadState('networkidle');
    
    const url = page.url();
    expect(url).not.toContain('/login');
  });
});
