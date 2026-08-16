import { test, expect } from '@playwright/test';
import { createAndLoginUser } from '../fixtures';

/**
 * E2E tests for Events feature.
 * 
 * Tests the full event lifecycle:
 * - Create event
 * - View event list
 * - Filter events by type
 * - View event details
 * - Edit event (description, links, journal entries)
 * - Delete event
 */

test.describe('J008: Events', () => {
  test.beforeEach(async ({ page }) => {
    // Create a fresh user for each test
    await createAndLoginUser(page, 'events');
  });

  test('empty state shows on events page with no events', async ({ page }) => {
    await page.goto('/events');
    
    // Should show empty state
    await expect(page.getByText('No events yet')).toBeVisible();
    await expect(page.getByRole('button', { name: /create.*event/i })).toBeVisible();
  });

  test('can create a new event', async ({ page }) => {
    await page.goto('/events');
    
    // Click create button
    await page.getByRole('button', { name: /create.*event/i }).click();
    
    // Should navigate to form page
    await expect(page).toHaveURL(/\/events\/new/);
    
    // Fill out the form
    await page.getByLabel(/title/i).fill('Test Race 2024');
    await page.getByLabel(/event type/i).selectOption('race');
    await page.getByLabel(/start date/i).fill('2024-08-15');
    await page.getByLabel(/end date/i).fill('2024-08-15');
    
    // Submit
    await page.getByRole('button', { name: /create event/i }).click();
    
    // Should redirect to event detail
    await expect(page).toHaveURL(/\/events\/[a-f0-9-]+$/);
    
    // Verify event was created
    await expect(page.getByText('Test Race 2024')).toBeVisible();
    await expect(page.getByText('race')).toBeVisible();
  });

  test('can view event in list and navigate to detail', async ({ page }) => {
    // First create an event via API for speed
    const eventResponse = await page.request.post('/api/events', {
      data: {
        title: 'Summer Tour',
        event_type: 'tour',
        start_date: '2024-07-01',
        end_date: '2024-07-07',
        description: 'A week-long tour through the mountains.'
      }
    });
    expect(eventResponse.ok()).toBeTruthy();
    
    // Go to events list
    await page.goto('/events');
    
    // Should see the event card
    await expect(page.getByText('Summer Tour')).toBeVisible();
    await expect(page.getByText('tour')).toBeVisible();
    
    // Click to view details
    await page.getByText('Summer Tour').click();
    
    // Should be on detail page
    await expect(page).toHaveURL(/\/events\/[a-f0-9-]+$/);
    await expect(page.getByRole('heading', { name: 'Summer Tour' })).toBeVisible();
    await expect(page.getByText('A week-long tour through the mountains.')).toBeVisible();
  });

  test('can filter events by type', async ({ page }) => {
    // Create events of different types
    await page.request.post('/api/events', {
      data: { title: 'Race Event', event_type: 'race', start_date: '2024-08-01', end_date: '2024-08-01' }
    });
    await page.request.post('/api/events', {
      data: { title: 'Tour Event', event_type: 'tour', start_date: '2024-07-01', end_date: '2024-07-07' }
    });
    await page.request.post('/api/events', {
      data: { title: 'Bikepacking Trip', event_type: 'bikepacking', start_date: '2024-06-01', end_date: '2024-06-10' }
    });
    
    await page.goto('/events');
    
    // All events visible initially
    await expect(page.getByText('Race Event')).toBeVisible();
    await expect(page.getByText('Tour Event')).toBeVisible();
    await expect(page.getByText('Bikepacking Trip')).toBeVisible();
    
    // Filter by race
    await page.getByRole('button', { name: /^race$/i }).click();
    
    // Only race event visible
    await expect(page.getByText('Race Event')).toBeVisible();
    await expect(page.getByText('Tour Event')).not.toBeVisible();
    await expect(page.getByText('Bikepacking Trip')).not.toBeVisible();
    
    // Filter by tour
    await page.getByRole('button', { name: /^tour$/i }).click();
    
    // Only tour event visible
    await expect(page.getByText('Tour Event')).toBeVisible();
    await expect(page.getByText('Race Event')).not.toBeVisible();
    
    // Reset to all
    await page.getByRole('button', { name: /^all$/i }).click();
    
    // All visible again
    await expect(page.getByText('Race Event')).toBeVisible();
    await expect(page.getByText('Tour Event')).toBeVisible();
    await expect(page.getByText('Bikepacking Trip')).toBeVisible();
  });

  test('single-day event shows without Day by Day header', async ({ page }) => {
    // Create single-day event
    const response = await page.request.post('/api/events', {
      data: {
        title: 'Local Crit',
        event_type: 'race',
        start_date: '2024-08-15',
        end_date: '2024-08-15'
      }
    });
    const event = await response.json();
    
    // Navigate to detail
    await page.goto(`/events/${event.id}`);
    
    // Should NOT have Day by Day section
    await expect(page.getByText('Day by Day')).not.toBeVisible();
    
    // Should show full date format
    await expect(page.getByText(/august.*15.*2024/i)).toBeVisible();
  });

  test('multi-day event shows Day by Day header', async ({ page }) => {
    // Create multi-day event
    const response = await page.request.post('/api/events', {
      data: {
        title: 'Alps Tour',
        event_type: 'tour',
        start_date: '2024-07-01',
        end_date: '2024-07-05'
      }
    });
    const event = await response.json();
    
    // Navigate to detail
    await page.goto(`/events/${event.id}`);
    
    // Should have Day by Day section
    await expect(page.getByText('Day by Day')).toBeVisible();
  });

  test('can navigate to edit page and modify description', async ({ page }) => {
    // Create event
    const response = await page.request.post('/api/events', {
      data: {
        title: 'Editable Event',
        event_type: 'event',
        start_date: '2024-09-01',
        end_date: '2024-09-01',
        description: 'Original description'
      }
    });
    const event = await response.json();
    
    // Go to detail page
    await page.goto(`/events/${event.id}`);
    
    // Click edit button
    await page.getByRole('button', { name: /edit/i }).click();
    
    // Should be on edit page
    await expect(page).toHaveURL(new RegExp(`/events/${event.id}/edit`));
    
    // Should see Event Description section
    await expect(page.getByText('Event Description')).toBeVisible();
    
    // Click Done to go back
    await page.getByRole('button', { name: /done/i }).click();
    
    // Should be back on detail page
    await expect(page).toHaveURL(new RegExp(`/events/${event.id}$`));
  });

  test('can delete event from detail page', async ({ page }) => {
    // Create event
    const response = await page.request.post('/api/events', {
      data: {
        title: 'Event to Delete',
        event_type: 'event',
        start_date: '2024-10-01',
        end_date: '2024-10-01'
      }
    });
    const event = await response.json();
    
    // Go to detail page
    await page.goto(`/events/${event.id}`);
    
    // Click delete button (trash icon)
    await page.locator('button').filter({ has: page.locator('svg path[d*="M19 7l"]') }).click();
    
    // Confirmation dialog should appear
    await expect(page.getByText(/delete event/i)).toBeVisible();
    await expect(page.getByText(/are you sure/i)).toBeVisible();
    
    // Confirm delete
    await page.getByRole('button', { name: /^delete$/i }).click();
    
    // Should redirect to events list
    await expect(page).toHaveURL('/events');
    
    // Event should no longer be in the list
    await expect(page.getByText('Event to Delete')).not.toBeVisible();
  });

  test('can add a link to an event', async ({ page }) => {
    // Create event
    const response = await page.request.post('/api/events', {
      data: {
        title: 'Event with Links',
        event_type: 'tour',
        start_date: '2024-07-01',
        end_date: '2024-07-03'
      }
    });
    const event = await response.json();
    
    // Go to edit page
    await page.goto(`/events/${event.id}/edit`);
    
    // Click Add Link button
    await page.getByRole('button', { name: /add link/i }).click();
    
    // Fill out link form
    await page.getByLabel(/url/i).fill('https://example.com/route');
    await page.getByLabel(/title/i).fill('Route Map');
    
    // Submit
    await page.getByRole('button', { name: /add$/i }).click();
    
    // Link should appear in the list
    await expect(page.getByText('Route Map')).toBeVisible();
  });

  test('can add a journal entry to multi-day event', async ({ page }) => {
    // Create multi-day event
    const response = await page.request.post('/api/events', {
      data: {
        title: 'Tour with Journal',
        event_type: 'tour',
        start_date: '2024-07-01',
        end_date: '2024-07-05'
      }
    });
    const event = await response.json();
    
    // Go to edit page
    await page.goto(`/events/${event.id}/edit`);
    
    // Should see Day by Day section
    await expect(page.getByText('Day by Day')).toBeVisible();
    
    // Look for button to add new entry (plus icon or "New Entry" text)
    const addEntryButton = page.locator('button').filter({ 
      has: page.locator('svg path[d*="M12 4v16m8-8H4"]') 
    }).first();
    
    await addEntryButton.click();
    
    // Dialog should appear
    await expect(page.getByText('Add Journal Entry')).toBeVisible();
  });

  test('Markdown renders in event description', async ({ page }) => {
    // Create event with markdown description
    const response = await page.request.post('/api/events', {
      data: {
        title: 'Markdown Event',
        event_type: 'event',
        start_date: '2024-11-01',
        end_date: '2024-11-01',
        description: '# Heading\n\nThis is **bold** text and *italic* text.'
      }
    });
    const event = await response.json();
    
    // Go to detail page
    await page.goto(`/events/${event.id}`);
    
    // Markdown should be rendered (not shown as raw text)
    // Heading should be an actual h1
    await expect(page.locator('h1:has-text("Heading")')).toBeVisible();
    
    // Bold text should be in strong/b tag
    await expect(page.locator('strong:has-text("bold")')).toBeVisible();
    
    // Italic text should be in em/i tag
    await expect(page.locator('em:has-text("italic")')).toBeVisible();
  });

  test('full CRUD flow: create, view, edit, delete', async ({ page }) => {
    // 1. CREATE
    await page.goto('/events/new');
    await page.getByLabel(/title/i).fill('Complete Flow Event');
    await page.getByLabel(/event type/i).selectOption('tour');
    await page.getByLabel(/start date/i).fill('2024-12-01');
    await page.getByLabel(/end date/i).fill('2024-12-05');
    await page.locator('[data-color-mode]').first().fill('Test description with **markdown**');
    await page.getByRole('button', { name: /create event/i }).click();
    
    // Should redirect to detail
    await expect(page).toHaveURL(/\/events\/[a-f0-9-]+$/);
    const eventUrl = page.url();
    
    // 2. READ - Verify it was created
    await expect(page.getByText('Complete Flow Event')).toBeVisible();
    await expect(page.getByText('tour')).toBeVisible();
    
    // 3. UPDATE - Go to edit page
    await page.getByRole('button', { name: /edit/i }).click();
    await expect(page).toHaveURL(/\/edit$/);
    
    // Make a change (add a link)
    await page.getByRole('button', { name: /add link/i }).click();
    await page.getByLabel(/url/i).fill('https://example.com');
    await page.getByLabel(/title/i).last().fill('Test Link');
    await page.getByRole('button', { name: /add$/i }).click();
    await expect(page.getByText('Test Link')).toBeVisible();
    
    // Go back to detail
    await page.getByRole('button', { name: /done/i }).click();
    
    // 4. DELETE
    await page.locator('button').filter({ has: page.locator('svg path[d*="M19 7l"]') }).click();
    await page.getByRole('button', { name: /^delete$/i }).click();
    
    // Should be back at events list
    await expect(page).toHaveURL('/events');
    
    // Event should be gone
    await expect(page.getByText('Complete Flow Event')).not.toBeVisible();
  });
});
