/**
 * Regression test for Dashboard chart clipping.
 *
 * Bug: ResponsiveContainer with height="100%" inside a fixed-height container
 * (h-32 / h-40) fell back to Recharts' 200px default height because the
 * measurement div collapsed to 0x0. The chart rendered taller than its
 * container, and `overflow-hidden` clipped the bottom — cutting off data.
 *
 * Fix: use explicit pixel heights on ResponsiveContainer matching the
 * container's height.
 */
import { test, expect } from '@playwright/test';
import { generateTestUser, registerAndApproveUser, loginViaApi } from '../fixtures/auth';
import { uploadFitFileAndWait, getFixtureFitPath } from '../fixtures/upload';

const testUser = generateTestUser('dashboard-charts');

test.describe('Dashboard chart sizing', () => {
  test.beforeAll(async ({ request }) => {
    await registerAndApproveUser(request, testUser);
    // Upload an activity with power data so the Power Curve card renders
    await uploadFitFileAndWait(request, getFixtureFitPath('breakthrough-5min.fit'));
  });

  test('Power Curve chart fits its container (not clipped)', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Power Curve' })).toBeVisible();
    // Give Recharts a moment to render + measure
    await page.waitForTimeout(1500);

    const geometry = await page.evaluate(() => {
      const powerHeading = Array.from(document.querySelectorAll('h2')).find(
        (h) => h.textContent === 'Power Curve'
      );
      const card = powerHeading?.closest('div.bg-card') || powerHeading?.closest('div');
      const container = card?.querySelector('.recharts-responsive-container')?.parentElement;
      const wrapper = card?.querySelector('.recharts-wrapper');
      if (!container || !wrapper) {
        return {
          found: false as const,
          debug: {
            headingFound: !!powerHeading,
            cardClass: card?.className?.slice(0, 60),
            cardHasRc: !!card?.querySelector('.recharts-responsive-container'),
            cardHasWrapper: !!card?.querySelector('.recharts-wrapper'),
          },
        };
      }
      const cBox = container.getBoundingClientRect();
      const wBox = wrapper.getBoundingClientRect();
      return {
        found: true as const,
        containerHeight: Math.round(cBox.height),
        chartHeight: Math.round(wBox.height),
        chartBottom: Math.round(wBox.bottom),
        containerBottom: Math.round(cBox.bottom),
      };
    });

    expect(geometry.found, `Power Curve chart rendered: ${JSON.stringify(geometry)}`).toBe(true);
    // The chart must not render taller than its container (the bug made it 200px in a 128px box)
    expect(geometry.chartHeight).toBeLessThanOrEqual(geometry.containerHeight);
    // Nothing in the chart should extend below the container's bottom edge
    expect(geometry.chartBottom).toBeLessThanOrEqual(geometry.containerBottom);
  });

  test('PMC sparkline fits its container (not clipped)', async ({ page }) => {
    await loginViaApi(page, testUser);
    await page.goto('/');
    await expect(page.getByRole('heading', { name: 'Performance Management' })).toBeVisible();
    await page.waitForTimeout(1500);

    const geometry = await page.evaluate(() => {
      const pmcHeading = Array.from(document.querySelectorAll('h2')).find(
        (h) => h.textContent === 'Performance Management'
      );
      const card = pmcHeading?.closest('div.bg-card') || pmcHeading?.closest('div');
      const container = card?.querySelector('.recharts-responsive-container')?.parentElement;
      const wrapper = card?.querySelector('.recharts-wrapper');
      if (!container || !wrapper) {
        return {
          found: false as const,
          debug: {
            headingFound: !!pmcHeading,
            cardClass: card?.className?.slice(0, 60),
            cardHasRc: !!card?.querySelector('.recharts-responsive-container'),
            cardHasWrapper: !!card?.querySelector('.recharts-wrapper'),
          },
        };
      }
      const cBox = container.getBoundingClientRect();
      const wBox = wrapper.getBoundingClientRect();
      return {
        found: true as const,
        containerHeight: Math.round(cBox.height),
        chartHeight: Math.round(wBox.height),
        chartBottom: Math.round(wBox.bottom),
        containerBottom: Math.round(cBox.bottom),
      };
    });

    expect(geometry.found, `PMC chart rendered: ${JSON.stringify(geometry)}`).toBe(true);
    expect(geometry.chartHeight).toBeLessThanOrEqual(geometry.containerHeight);
    expect(geometry.chartBottom).toBeLessThanOrEqual(geometry.containerBottom);
  });
});