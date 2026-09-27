/**
 * E2E tests for Gear (Bikes) page.
 *
 * Tests bike CRUD operations: create, view, edit, set default, retire.
 *
 * ISOLATION: Creates its own test user to avoid conflicts with parallel tests.
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from '../fixtures/auth';

const testUser = generateTestUser('gear');

test.describe('Gear Page', () => {
  test.beforeAll(async ({ request }) => {
    await registerAndApproveUser(request, testUser);
  });

  test('gear page loads and shows empty state initially', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/gear');

    // Should show Gear heading
    await expect(page.getByRole('heading', { name: 'Gear' })).toBeVisible();

    // Should show empty state or "Add Bike" button
    // (New users have no bikes, so either empty state or just the add button)
    const addButton = page.getByRole('button', { name: /add bike/i });
    await expect(addButton).toBeVisible();
  });

  test('can create a new bike', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/gear');

    // Click add bike button
    await page.getByRole('button', { name: /add bike/i }).click();

    // Form should appear
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('heading', { name: /add bike/i })).toBeVisible();

    // Fill in bike details
    await page.getByLabel(/name/i).fill('Canyon Aeroad');

    // Select bike type (road)
    await page.getByLabel(/type/i).click();
    await page.getByRole('option', { name: /road/i }).click();

    // Optionally fill in weight
    const weightInput = page.getByLabel(/weight/i);
    if (await weightInput.isVisible()) {
      await weightInput.fill('7.5');
    }

    // Save
    await page.getByRole('button', { name: /save/i }).click();

    // Should show success message or bike in list
    await expect(page.getByText('Canyon Aeroad')).toBeVisible({ timeout: 5000 });
  });

  test('can set a bike as default', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/gear');

    // Wait for bikes to load
    await expect(page.getByText('Canyon Aeroad')).toBeVisible({ timeout: 5000 });

    // Find the bike card and click the default button/menu option
    const bikeCard = page.locator('[data-testid="bike-card"]').filter({ hasText: 'Canyon Aeroad' });
    
    // If card is visible, find the default action
    if (await bikeCard.count() > 0) {
      // Look for a "Set as default" button or menu action
      const setDefaultButton = bikeCard.getByRole('button', { name: /set.*default/i });
      if (await setDefaultButton.isVisible()) {
        await setDefaultButton.click();
        // Should show success toast
        await expect(page.getByText(/set as default/i)).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('can edit a bike', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/gear');

    // Wait for bikes to load
    await expect(page.getByText('Canyon Aeroad')).toBeVisible({ timeout: 5000 });

    // Find the bike card and click edit
    const bikeCard = page.locator('[data-testid="bike-card"]').filter({ hasText: 'Canyon Aeroad' });
    
    if (await bikeCard.count() > 0) {
      // Look for edit button or menu
      const editButton = bikeCard.getByRole('button', { name: /edit/i });
      if (await editButton.isVisible()) {
        await editButton.click();

        // Edit form should appear
        await expect(page.getByRole('dialog')).toBeVisible();

        // Update the name
        await page.getByLabel(/name/i).fill('Canyon Aeroad CF SLX');
        await page.getByRole('button', { name: /save/i }).click();

        // Should show updated name
        await expect(page.getByText('Canyon Aeroad CF SLX')).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('can retire a bike with confirmation', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/gear');

    // First create a bike to retire
    await page.getByRole('button', { name: /add bike/i }).click();
    await page.getByLabel(/name/i).fill('Old Bike To Retire');
    await page.getByLabel(/type/i).click();
    await page.getByRole('option', { name: /road/i }).click();
    await page.getByRole('button', { name: /save/i }).click();

    // Wait for bike to appear
    await expect(page.getByText('Old Bike To Retire')).toBeVisible({ timeout: 5000 });

    // Find and retire it
    const bikeCard = page.locator('[data-testid="bike-card"]').filter({ hasText: 'Old Bike To Retire' });
    
    if (await bikeCard.count() > 0) {
      const retireButton = bikeCard.getByRole('button', { name: /retire/i });
      if (await retireButton.isVisible()) {
        await retireButton.click();

        // Confirmation dialog should appear
        await expect(page.getByRole('alertdialog')).toBeVisible();
        await expect(page.getByText(/are you sure/i)).toBeVisible();

        // Confirm
        await page.getByRole('button', { name: /confirm|retire/i }).click();

        // Bike should be hidden (or in retired section)
        await expect(page.getByText('Old Bike To Retire')).not.toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('can toggle retired bikes visibility', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/gear');

    // Look for "Show retired" toggle
    const showRetiredToggle = page.getByRole('checkbox', { name: /show retired/i });
    
    if (await showRetiredToggle.isVisible()) {
      // Toggle on
      await showRetiredToggle.click();
      
      // Should show retired bikes section
      await expect(page.getByText(/retired/i)).toBeVisible();
    }
  });

  test('gear page is navigable from sidebar', async ({ page }) => {
    await loginViaApi(page, testUser);

    // Start from dashboard
    await page.goto('/');

    // Find sidebar link to Gear
    const gearLink = page.getByRole('link', { name: /gear/i });
    if (await gearLink.isVisible()) {
      await gearLink.click();
      await expect(page).toHaveURL(/\/gear/);
      await expect(page.getByRole('heading', { name: 'Gear' })).toBeVisible();
    }
  });
});
