import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => { await page.goto('/chat-mock'); });

async function prepareRequest(page, text = 'Hello from a fellow NC State student!') {
  await page.getByText('API test panel', { exact: true }).click();
  await page.getByLabel('Access token', { exact: true }).fill('test-jwt');
  await page.getByLabel('Recipient user ID').fill('31');
  await page.getByLabel('Your note').fill(text);
}

test('three incoming requests, five messages; Accept is local and logs intended PATCH', async ({ page }) => {
  await expect(page.getByRole('article')).toHaveCount(3);
  await expect(page.getByRole('list', { name: 'Messages', exact: true }).getByRole('listitem')).toHaveCount(5);
  const logs = [];
  const calls = [];
  page.on('console', (entry) => logs.push(entry.text()));
  page.on('request', (request) => { if (request.url().includes('/api/')) calls.push(request.method()); });
  await page.getByRole('button', { name: 'Accept Maya Patel', exact: true }).click();
  await expect(page.getByRole('article')).toHaveCount(2);
  await expect(page.getByRole('article', { name: 'Request from Maya Patel' })).toHaveCount(0);
  await expect(page.getByRole('tab', { name: 'Incoming 2' })).toBeVisible();
  expect(logs.some((text) => text.includes('PATCH /api/connections/123/accept/'))).toBe(true);
  expect(calls).toEqual([]);
  await page.getByRole('button', { name: 'Decline Alex Rivera' }).click();
  await page.getByRole('button', { name: 'Decline Jordan Lee' }).click();
  await expect(page.getByText('You’re all caught up. No incoming requests.')).toBeVisible();
  await page.getByRole('button', { name: 'Reset demo' }).click();
  await expect(page.getByRole('article')).toHaveCount(3);
});

test('outgoing list and selectable sidebar render', async ({ page }) => {
  await page.getByRole('tab', { name: 'Outgoing 2' }).click();
  await expect(page.getByRole('article')).toHaveCount(2);
  await expect(page.getByRole('button', { name: /^Accept / })).toHaveCount(0);
  await page.getByRole('button', { name: /Sam Wilson/ }).click();
  await expect(page.getByRole('region', { name: 'Conversation with Sam Wilson' })).toBeVisible();
  await page.getByRole('button', { name: /Avery Chen/ }).click();
  await expect(page.getByRole('listitem')).toHaveCount(5);
  await page.getByLabel('Chat message').fill('A local draft');
  await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeDisabled();
});

test('500 characters shows zero, 501st keystroke and oversized paste are blocked', async ({ page }) => {
  const note = page.getByLabel('Your note');
  await note.fill('a'.repeat(500));
  await expect(page.getByText('0 remaining', { exact: true })).toBeVisible();
  await note.press('End');
  await note.pressSequentially('b');
  await expect(note).toHaveValue('a'.repeat(500));
  await note.fill('b'.repeat(501));
  await expect(note).toHaveValue('b'.repeat(500));
  await note.fill('🐺'.repeat(500));
  await expect(page.getByText('0 remaining', { exact: true })).toBeVisible();
  await note.press('End');
  await note.pressSequentially('x');
  await expect(note).toHaveValue('🐺'.repeat(500));
});

test('POST sends exact body and auth, only once while pending, then appends outgoing', async ({ page }) => {
  const bodies = [];
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/connections/', async (route) => {
    const request = route.request();
    expect(request.method()).toBe('POST');
    expect(request.headers().authorization).toBe('Bearer test-jwt');
    bodies.push(request.postDataJSON());
    await gate;
    await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ id: 203, status: 'pending' }) });
  });
  await prepareRequest(page, 'z'.repeat(500));
  await page.getByRole('button', { name: 'Send Request', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Sending…' })).toBeDisabled();
  release();
  await expect(page.getByRole('status').filter({ hasText: 'Request #203 sent' })).toBeVisible();
  expect(bodies).toEqual([{ recipient_id: 31, message_text: 'z'.repeat(500) }]);
  await expect(page.getByLabel('Your note')).toHaveValue('');
  await page.getByRole('tab', { name: 'Outgoing 3' }).click();
  await expect(page.getByRole('article', { name: 'Request to User 31' })).toBeVisible();
  await page.reload();
  await page.getByText('API test panel', { exact: true }).click();
  await expect(page.getByLabel('Access token', { exact: true })).toHaveValue('');
});

test('409 and network failure keep the draft and allow retry', async ({ page }) => {
  let attempt = 0;
  await page.route('**/api/connections/', async (route) => {
    attempt += 1;
    if (attempt === 1) await route.fulfill({ status: 409, contentType: 'application/json', body: '{"detail":"Duplicate"}' });
    else if (attempt === 2) await route.abort('failed');
    else await route.fulfill({ status: 201, contentType: 'application/json', body: '{"id":204,"status":"pending"}' });
  });
  await prepareRequest(page);
  await page.getByRole('button', { name: 'Send Request', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText('A request already exists for this person.');
  await expect(page.getByLabel('Your note')).not.toHaveValue('');
  await page.getByRole('button', { name: 'Send Request', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Could not reach the server');
  await page.getByRole('button', { name: 'Send Request', exact: true }).click();
  await expect(page.getByText('Request #204 sent. Status: pending.')).toBeVisible();
});

test('no token sends no request, and whitespace-only note is rejected', async ({ page }) => {
  const calls = [];
  page.on('request', (request) => { if (request.url().includes('/api/')) calls.push(request.url()); });
  await page.getByLabel('Recipient user ID').fill('31');
  await page.getByLabel('Your note').fill('Hi there');
  await page.getByRole('button', { name: 'Send Request', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Add an access token');
  await page.getByLabel('Your note').fill('   ');
  await page.getByRole('button', { name: 'Send Request', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Add a short note');
  expect(calls).toEqual([]);
});

test('mobile layout stays within viewport and composer stays in its panel', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(page.getByRole('heading', { name: 'Chat & Connect' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByLabel('Chat message').scrollIntoViewIfNeeded();
  await expect(page.getByLabel('Chat message')).toBeInViewport();
});
