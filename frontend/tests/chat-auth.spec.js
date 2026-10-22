import { test, expect } from '@playwright/test';

const session = { access: 'old-access', refresh: 'refresh-one', user: { id: 7, email: 'sanjana@ncsu.edu' } };
const credentials = { access: 'old-access', refresh: 'refresh-one', user_id: 7, email: 'sanjana@ncsu.edu' };
const conversations = [{ id: 5, other_user: { id: 41, name: 'Avery Chen', company: 'Red Hat' }, last_message: { body_text: 'Hello' }, updated_at: '2026-10-20T12:00:00Z' }];
const history = [
  { id: 2, conversation_id: 5, sender_id: 7, body_text: 'Second', created_at: '2026-10-20T12:01:00Z' },
  { id: 1, conversation_id: 5, sender_id: 41, body_text: 'First', created_at: '2026-10-20T12:00:00Z' },
];
const fulfill = (route, body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
async function mockChat(page) {
  await page.route('**/api/chat/conversations/', (route) => fulfill(route, conversations));
  await page.route(/\/api\/chat\/conversations\/5\/messages\//, (route) => fulfill(route, history));
}
async function signIn(page) {
  await page.goto('/login');
  await page.evaluate((value) => localStorage.setItem('pack-referrals.session.v1', JSON.stringify(value)), session);
  await page.goto('/chat/5');
}

test('protected pages redirect logged-out users to login', async ({ page }) => {
  await page.goto('/profile');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
});

test('signup, email code, persisted login on reload, then logout', async ({ page }) => {
  await mockChat(page);
  await page.route('**/api/accounts/auth/signup/', async (route) => {
    expect(route.request().postDataJSON()).toEqual({ email: 'sanjana@ncsu.edu' });
    expect(route.request().headers().authorization).toBeUndefined();
    await fulfill(route, { detail: 'Verification code sent.' }, 201);
  });
  await page.route('**/api/accounts/auth/verify/', async (route) => {
    expect(route.request().postDataJSON()).toEqual({ email: 'sanjana@ncsu.edu', code: '012345' });
    await fulfill(route, credentials);
  });
  await page.goto('/signup');
  await page.getByLabel('University email').fill('SANJANA@NCSU.EDU');
  await page.getByRole('button', { name: 'Sign up', exact: true }).click();
  await page.getByLabel('Six-digit code').fill('012345');
  await page.getByRole('button', { name: 'Verify and sign in' }).click();
  await expect(page.getByRole('region', { name: 'Conversation with Avery Chen' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('button', { name: 'Log out' })).toBeVisible();
  await expect(page.getByRole('list', { name: 'Messages', exact: true }).getByRole('listitem')).toHaveCount(2);
  await page.getByRole('button', { name: 'Log out' }).click();
  await expect(page).toHaveURL(/\/login$/);
  expect(await page.evaluate(() => localStorage.getItem('pack-referrals.session.v1'))).toBeNull();
});

test('expired access token refreshes silently and the rotated session survives reload', async ({ page }) => {
  let refreshes = 0;
  await mockChat(page);
  await page.route('**/api/accounts/auth/refresh/', async (route) => {
    refreshes += 1;
    expect(route.request().postDataJSON()).toEqual({ refresh: 'refresh-one' });
    expect(route.request().headers().authorization).toBeUndefined();
    await fulfill(route, { access: 'fresh-access', refresh: 'refresh-two' });
  });
  await page.route('**/api/chat/conversations/', (route) => route.request().headers().authorization === 'Bearer old-access'
    ? fulfill(route, { detail: 'Token expired' }, 401) : fulfill(route, conversations));
  await signIn(page);
  await expect(page.getByRole('region', { name: 'Conversation with Avery Chen' })).toBeVisible();
  expect(refreshes).toBe(1);
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem('pack-referrals.session.v1')).refresh)).toBe('refresh-two');
  await page.reload();
  await expect(page.getByRole('region', { name: 'Conversation with Avery Chen' })).toBeVisible();
  expect(refreshes).toBe(1);
});

test('history is chronological and sending appends before the server responds', async ({ page }) => {
  await mockChat(page);
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  await page.route('**/api/chat/messages/', async (route) => {
    expect(route.request().headers().authorization).toBe('Bearer old-access');
    expect(route.request().postDataJSON()).toEqual({ conversation_id: 5, body_text: 'Hello Avery' });
    await gate;
    await fulfill(route, { id: 3, sender_id: 7, conversation_id: 5, body_text: 'Hello Avery', created_at: '2026-10-20T12:02:00Z' }, 201);
  });
  await signIn(page);
  const messages = page.getByRole('list', { name: 'Messages', exact: true }).getByRole('listitem');
  await expect(messages).toHaveCount(2);
  await expect(messages.nth(0)).toContainText('First');
  await expect(messages.nth(1)).toContainText('Second');
  await page.getByLabel('Chat message').fill('Hello Avery');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(messages).toHaveCount(3);
  await expect(page.getByText('Sending…', { exact: true })).toBeVisible();
  release();
  await expect(page.getByText('Sending…', { exact: true })).toHaveCount(0);
  await expect(messages).toHaveCount(3);
});

test('failed optimistic send stays visible and retries explicitly', async ({ page }) => {
  await mockChat(page); let attempts = 0;
  await page.route('**/api/chat/messages/', async (route) => {
    attempts += 1;
    if (attempts === 1) await route.abort('failed');
    else await fulfill(route, { id: 3, sender_id: 7, conversation_id: 5, body_text: 'Please retry', created_at: '2026-10-20T12:02:00Z' }, 201);
  });
  await signIn(page);
  await expect(page.getByRole('listitem')).toHaveCount(2);
  await page.getByLabel('Chat message').fill('Please retry');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  await page.getByRole('button', { name: 'Retry message' }).click();
  await expect(page.getByRole('button', { name: 'Retry message' })).toHaveCount(0);
  await expect(page.getByRole('listitem')).toHaveCount(3);
  expect(attempts).toBe(2);
});

test('chat input uses the 2000-code-point cap and rejects blank sends', async ({ page }) => {
  await mockChat(page); await signIn(page);
  await expect(page.getByRole('listitem')).toHaveCount(2);
  await page.getByLabel('Chat message').fill('   ');
  await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeDisabled();
  await page.getByLabel('Chat message').fill('🐺'.repeat(2001));
  await expect(page.getByLabel('Chat message')).toHaveValue('🐺'.repeat(2000));
  await expect(page.getByText(/0 characters remaining/)).toBeVisible();
});

test('authenticated mobile chat fits the viewport', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await mockChat(page); await signIn(page);
  await expect(page.getByRole('listitem')).toHaveCount(2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByLabel('Chat message').scrollIntoViewIfNeeded();
  await expect(page.getByLabel('Chat message')).toBeInViewport();
});
