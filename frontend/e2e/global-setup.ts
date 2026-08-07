/**
 * Playwright global setup - runs once before all tests.
 *
 * Seeds the E2E database with baseline data:
 * - Admin user (for admin flows)
 * - Test user (for baseline authenticated tests)
 *
 * This runs after the webServer is ready (health check passed).
 */

import { request } from '@playwright/test';

const BASE_URL = 'http://localhost:8001';

// Baseline users (credentials match BASELINE_USER in fixtures/auth.ts)
const BASELINE_USER = {
  email: 'testuser@example.com',
  password: 'testpass',
};

const ADMIN_USER = {
  email: 'admin@example.com',
  password: 'adminpass',
};

async function globalSetup() {
  console.log('[globalSetup] Starting E2E database seeding...');

  const context = await request.newContext({
    baseURL: BASE_URL,
  });

  try {
    // Wait for health endpoint to be ready (should already be ready via webServer config)
    const healthResponse = await context.get('/api/health');
    if (!healthResponse.ok()) {
      throw new Error(`Health check failed: ${healthResponse.status()}`);
    }
    console.log('[globalSetup] Health check passed');

    // Seed baseline test user
    await seedUser(context, BASELINE_USER, 'baseline');

    // Seed admin user (if not auto-created by init_db)
    await seedUser(context, ADMIN_USER, 'admin');

    console.log('[globalSetup] Database seeding complete');
  } finally {
    await context.dispose();
  }
}

async function seedUser(
  context: Awaited<ReturnType<typeof request.newContext>>,
  user: { email: string; password: string },
  label: string
): Promise<void> {
  const response = await context.post('/api/register', {
    data: {
      email: user.email,
      password: user.password,
    },
  });

  if (response.ok()) {
    console.log(`[globalSetup] Created ${label} user: ${user.email}`);
  } else if (response.status() === 409) {
    // User already exists (from previous run or init_db) - that's fine
    console.log(`[globalSetup] ${label} user already exists: ${user.email}`);
  } else {
    const body = await response.text();
    console.warn(`[globalSetup] Failed to create ${label} user: ${response.status()} ${body}`);
    // Don't throw - some users may be created by init_db with different passwords
  }
}

export default globalSetup;
