import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for E2E tests.
 *
 * Local development:
 *   - Start stack manually: docker compose -f ../docker-compose.e2e.yml up -d
 *   - Run tests: npm run test:e2e (reuses running server)
 *
 * CI:
 *   - Playwright starts the stack via webServer command
 *   - Fresh DB each run (no volumes in docker-compose.e2e.yml)
 */
export default defineConfig({
  testDir: './e2e',
  
  /* Run tests in files in parallel */
  fullyParallel: true,
  
  /* Fail the build on CI if you accidentally left test.only in the source code */
  forbidOnly: !!process.env.CI,
  
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  
  /* Opt out of parallel tests on CI for more predictable resource usage */
  workers: process.env.CI ? 1 : undefined,
  
  /* Reporter to use */
  reporter: [
    ['html', { outputFolder: 'e2e-report' }],
    ['list'],
  ],
  
  /* Shared settings for all projects */
  use: {
    /* Base URL to use in actions like `await page.goto('/')` */
    baseURL: 'http://localhost:8001',

    /* Collect trace when retrying the failed test */
    trace: 'on-first-retry',
    
    /* Screenshot on failure */
    screenshot: 'only-on-failure',
    
    /* Video on failure */
    video: 'on-first-retry',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // Uncomment to add more browsers:
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  /* Run your local dev server before starting the tests */
  webServer: {
    command: 'docker compose -f ../docker-compose.e2e.yml up --build',
    url: 'http://localhost:8001/api/health',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000, // 2 minutes for Docker build + startup
    stdout: 'pipe',
    stderr: 'pipe',
  },
  
  /* Global timeout for each test */
  timeout: 30_000,
  
  /* Expect timeout */
  expect: {
    timeout: 10_000,
  },
  
  /* Output directory for test artifacts */
  outputDir: 'e2e-results',
});
