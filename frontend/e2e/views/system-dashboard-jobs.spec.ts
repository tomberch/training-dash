/**
 * E2E tests for the admin job-operations surface (ADR 0007, ticket #696).
 *
 * Verifies the SystemDashboard Jobs section renders the new columns/actions
 * against the live e2e compose stack:
 * - worker liveness row (N workers alive — the e2e worker is running)
 * - status filter incl. failed/aborted options
 * - per-user Last Sync column in the Admin users table
 *
 * Job action semantics (abort/retry against real SAQ rows) are covered at the
 * integration layer (tests/integration/test_resilience_e2e.py +
 * test_admin_job_ops.py) — they need real queue rows, which the seeded e2e
 * stack doesn't deterministically provide.
 */
import { test, expect } from '@playwright/test';
import { loginViaApi, ADMIN_USER } from '../fixtures/auth';

test.describe('System Dashboard — job operations', () => {
  test('admin can open the system dashboard', async ({ page }) => {
    await loginViaApi(page, ADMIN_USER);
    await page.goto('/admin');

    const systemLink = page.getByRole('link', { name: /system dashboard/i });
    if (await systemLink.count()) {
      await systemLink.click();
    } else {
      await page.goto('/admin/system');
    }

    // Stats bar renders the Jobs card
    await expect(page.getByText('Jobs', { exact: true })).toBeVisible({ timeout: 10000 });
  });

  test('jobs card shows worker liveness (e2e worker is running)', async ({ page }) => {
    await loginViaApi(page, ADMIN_USER);
    await page.goto('/admin/system');

    // The e2e stack always runs one worker; liveness must reflect it
    await expect(page.getByText(/workers? alive|no live workers/)).toBeVisible({ timeout: 10000 });
    await expect(page.getByText(/worker alive/)).toBeVisible();
  });

  test('jobs table offers status filter with failed/aborted options', async ({ page }) => {
    await loginViaApi(page, ADMIN_USER);
    await page.goto('/admin/system');

    // Wait for dashboard content, then find the select that has the status options
    await expect(page.getByText('Tile Cache')).toBeVisible({ timeout: 10000 });

    const statusFilter = page
      .locator('select')
      .filter({ has: page.locator('option[value="failed"]') });
    await expect(statusFilter).toHaveCount(1);
    const options = await statusFilter.locator('option').allTextContents();
    expect(options).toContain('Failed');
    expect(options).toContain('Aborted');
  });

  test('event stream filter includes resilience event types', async ({ page }) => {
    await loginViaApi(page, ADMIN_USER);
    await page.goto('/admin/system');

    // Wait for the dashboard content (loading skeleton → cards) before probing selects
    await expect(page.getByText('Tile Cache')).toBeVisible({ timeout: 10000 });

    const selects = page.locator('select');
    // Event-type dropdown contains the new job/sync resilience event types
    const allOptions: string[] = [];
    const count = await selects.count();
    for (let i = 0; i < count; i++) {
      const opts = await selects.nth(i).locator('option').allTextContents();
      allOptions.push(...opts);
    }
    const joined = allOptions.join('\n');
    expect(joined).toContain('job.enqueue_failed');
    expect(joined).toContain('sync.lost_tick');
    expect(joined).toContain('job.stuck');
  });

  test('admin users table shows Last Sync column', async ({ page }) => {
    await loginViaApi(page, ADMIN_USER);
    await page.goto('/admin');

    await expect(page.getByRole('columnheader', { name: 'Last Sync' })).toBeVisible({
      timeout: 10000,
    });
    // Rows render a value or an em-dash placeholder
    await expect(page.getByText('—').first()).toBeVisible();
  });
});