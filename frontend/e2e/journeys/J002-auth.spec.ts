import { test, expect } from '@playwright/test';
import { generateTestUser, registerUser, loginUser, logoutUser, isLoggedIn } from '../fixtures/auth';

test.describe('J002: Auth Flows', () => {
  test('valid login redirects to dashboard', async ({ page }) => {
    // Create a fresh user for this test
    const user = generateTestUser('auth-login');
    await registerUser(page, user);
    
    // Logout to test the login flow (registerUser auto-logs in)
    await logoutUser(page);
    
    // Go to login page (app shows login when no session)
    await page.goto('/');
    
    // Verify we're on login page
    await expect(page.locator('input[type="email"]')).toBeVisible({ timeout: 5000 });
    
    // Fill login form
    await page.fill('input[type="email"]', user.email);
    await page.fill('input[type="password"]', user.password);
    await page.click('button[type="submit"]');
    
    // Should redirect to dashboard - wait for header to appear (indicates logged in state)
    await expect(page.locator('[data-testid="user-menu-button"]')).toBeVisible({ timeout: 10000 });
    
    // Verify we're at root path
    await expect(page).toHaveURL('/');
  });

  test('invalid credentials show error message', async ({ page }) => {
    // Clear any existing session from storageState
    await page.context().clearCookies();
    
    // Go to login page
    await page.goto('/');
    
    // Try to login with non-existent credentials
    await page.fill('input[type="email"]', 'nonexistent@example.com');
    await page.fill('input[type="password"]', 'wrongpassword');
    await page.click('button[type="submit"]');
    
    // Should show error message (error div has bg-destructive/10 class)
    const errorDiv = page.locator('.bg-destructive\\/10');
    await expect(errorDiv).toBeVisible({ timeout: 5000 });
    
    // Should still be on login page (no redirect)
    await expect(page.locator('input[type="email"]')).toBeVisible();
  });

  test('logout clears session and redirects to login', async ({ page }) => {
    // Create and login a user
    const user = generateTestUser('auth-logout');
    await registerUser(page, user);
    await loginUser(page, user);
    
    // Navigate to the app
    await page.goto('/');
    
    // Verify we're logged in - wait for user menu button (indicates authenticated state)
    await expect(page.locator('[data-testid="user-menu-button"]')).toBeVisible({ timeout: 10000 });
    
    // Click user menu to open dropdown
    await page.click('[data-testid="user-menu-button"]');
    
    // Click logout
    await page.click('[data-testid="logout-button"]');
    
    // Should be redirected to login page (login form visible)
    await expect(page.locator('input[type="email"]')).toBeVisible({ timeout: 5000 });
    
    // Verify session cookie is cleared
    const loggedIn = await isLoggedIn(page);
    expect(loggedIn).toBe(false);
  });

  test('protected routes redirect to login when unauthenticated', async ({ page }) => {
    // Clear any existing session
    await page.context().clearCookies();
    
    // Try to access protected routes directly
    const protectedRoutes = ['/activities', '/settings', '/pmc'];
    
    for (const route of protectedRoutes) {
      await page.goto(route);
      
      // Should show login form (app renders Login component when no user)
      await expect(page.locator('input[type="email"]')).toBeVisible({ timeout: 5000 });
    }
  });

  test('session persists across page refresh', async ({ page }) => {
    // Create and login a user
    const user = generateTestUser('auth-persist');
    await registerUser(page, user);
    await loginUser(page, user);
    
    // Navigate to the app
    await page.goto('/');
    
    // Verify we're logged in - user menu button indicates authenticated state
    await expect(page.locator('[data-testid="user-menu-button"]')).toBeVisible({ timeout: 10000 });
    
    // Verify session cookie exists
    let loggedIn = await isLoggedIn(page);
    expect(loggedIn).toBe(true);
    
    // Refresh the page
    await page.reload();
    
    // Should still be logged in (user menu visible, not login form)
    await expect(page.locator('[data-testid="user-menu-button"]')).toBeVisible({ timeout: 10000 });
    
    // Verify session cookie still exists
    loggedIn = await isLoggedIn(page);
    expect(loggedIn).toBe(true);
  });
});
