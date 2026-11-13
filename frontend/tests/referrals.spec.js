import { test, expect } from '@playwright/test';

const person = (id, name) => ({ id, name, company: 'Example' });
const row = { id: 1, sender: person(7, 'Me'), recipient: person(12, 'Maya'), company: null, role_title: 'Engineer', contact_email: 'maya.contact@example.com', message_text: 'Relevant experience', status: 'pending', job_url: '', resume_url: '', created_at: '2026-11-01T12:00:00Z' };
const json = (route, data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
async function setup(page, conflict = false) {
  let saved = [];
  await page.addInitScript(() => localStorage.setItem('pack-referrals.session.v1', JSON.stringify({ access: 'access', refresh: 'refresh', user: { id: 7, email: 'me@ncsu.edu' } })));
  // Match backend requests only. A glob like **/api/** also matches
  // Vite modules under /src/api/ and replaces JavaScript with JSON.
  await page.route((url) => url.pathname.startsWith('/api/'), (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/chat/conversations/') return json(route, [{ id: 9, other_user: person(12, 'Maya') }]);
    if (url.pathname === '/api/companies/' || url.pathname === '/api/connections/') return json(route, []);
    if (url.pathname === '/api/connections/referrals/') {
      if (route.request().method() === 'POST') {
        expect(route.request().postDataJSON()).toEqual({ recipient_id: 12, role_title: 'Engineer', contact_email: 'me@ncsu.edu', message_text: 'Relevant experience' });
        expect(route.request().headers().authorization).toBe('Bearer access');
        if (conflict) return json(route, { detail: 'Duplicate ask' }, 409);
        saved = [row]; return json(route, row, 201);
      }
      return json(route, { count: saved.length, results: saved, next: null, previous: null });
    }
    return json(route, {}, 404);
  });
  await page.goto('/referrals?recipient=12');
  await expect(page).toHaveURL(/\/referrals\?recipient=12$/);
  await expect(page.getByRole('heading', { name: 'Referral requests', exact: true })).toBeVisible();
  await expect(page.getByRole('option', { name: 'Maya', exact: true })).toBeAttached();
  await expect(page.getByLabel('Accepted connection (required)')).toHaveValue('12');
  await page.getByLabel('Role title (required)').fill('Engineer');
  await page.getByLabel('Why you fit (required)').fill('Relevant experience');
}

test('referral sends, appears in outgoing and persists on reload', async ({ page }) => {
  await setup(page);
  await page.getByRole('button', { name: 'Send referral request' }).click();
  await expect(page.getByRole('article', { name: 'Referral to Maya' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('article', { name: 'Referral to Maya' })).toBeVisible();
});

test('mobile conflict keeps note and form stays within viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await setup(page, true);
  await page.getByRole('button', { name: 'Send referral request' }).click();
  await expect(page.getByRole('alert')).toContainText('already have a pending');
  await expect(page.getByLabel('Why you fit (required)')).toHaveValue('Relevant experience');
  await expect(page.getByRole('button', { name: 'Send referral request' })).toBeDisabled();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

async function incomingFixture(page, { conflict = false, failure = false } = {}) {
  let inbound = { ...row, sender: person(12, 'Maya'), recipient: person(7, 'Me') };
  const patches = [];
  await page.addInitScript(() => localStorage.setItem('pack-referrals.session.v1', JSON.stringify({ access: 'access', refresh: 'refresh', user: { id: 7, email: 'me@ncsu.edu' } })));
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request(); const url = new URL(request.url());
    if (url.pathname === '/api/chat/conversations/' || url.pathname === '/api/companies/' || url.pathname === '/api/connections/') return json(route, []);
    if (request.method() === 'PATCH') {
      patches.push(request);
      expect(request.postData()).toBeNull();
      expect(request.headers().authorization).toBe('Bearer access');
      if (failure) return json(route, { detail: 'Could not answer. Try again.' }, 500);
      inbound = { ...inbound, status: conflict || url.pathname.endsWith('/decline/') ? 'declined' : 'accepted', resolved_at: '2026-11-07T12:00:00Z' };
      return conflict ? json(route, { detail: 'Already answered.' }, 409) : json(route, inbound);
    }
    if (url.pathname === '/api/connections/referrals/') return json(route, { count: 1, results: [url.searchParams.get('type') === 'incoming' ? inbound : { ...row, status: 'accepted' }] });
    return json(route, {}, 404);
  });
  await page.goto('/referrals');
  await page.getByRole('button', { name: 'Incoming', exact: true }).click();
  await expect(page.getByRole('article', { name: 'Referral from Maya' })).toBeVisible();
  return patches;
}

for (const action of ['accept', 'decline']) {
  test(`recipient can ${action} using keyboard; status persists after reload`, async ({ page }) => {
    const patches = await incomingFixture(page);
    await expect(page.getByRole('link', { name: 'maya.contact@example.com' })).toHaveAttribute('href', 'mailto:maya.contact@example.com');
    const button = page.getByRole('button', { name: `${action === 'accept' ? 'Accept' : 'Decline'} referral for Engineer from Maya` });
    await button.focus(); await page.keyboard.press('Enter');
    const status = action === 'accept' ? 'accepted' : 'declined';
    await expect(page.getByText(`Status: ${status}`, { exact: true })).toBeFocused();
    await expect(page.getByRole('button', { name: /^(Accept|Decline) referral/ })).toHaveCount(0);
    expect(patches).toHaveLength(1);
    expect(new URL(patches[0].url()).pathname).toBe(`/api/connections/referrals/1/${action}/`);
    await page.reload(); await page.getByRole('button', { name: 'Incoming', exact: true }).click();
    await expect(page.getByText(`Status: ${status}`, { exact: true })).toBeVisible();
    await page.getByRole('button', { name: 'Outgoing', exact: true }).click();
    await expect(page.getByRole('article', { name: 'Referral to Maya' })).toBeVisible();
    await expect(page.getByRole('button', { name: /^(Accept|Decline) referral/ })).toHaveCount(0);
  });
}

test('conflict displays the server answer rather than accepting locally', async ({ page }) => {
  await incomingFixture(page, { conflict: true });
  await page.getByRole('button', { name: 'Accept referral for Engineer from Maya' }).click();
  await expect(page.getByText('Status: declined', { exact: true })).toBeVisible();
  await expect(page.getByText('Status: accepted', { exact: true })).toHaveCount(0);
});

test('referral action controls, errors and resolved status pass axe', async ({ page }) => {
  const { default: AxeBuilder } = await import('@axe-core/playwright');
  await incomingFixture(page, { failure: true });
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole('button', { name: 'Accept referral for Engineer from Maya' }).click();
  await expect(page.getByRole('alert')).toContainText('Could not answer.');
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.route((url) => url.pathname === '/api/connections/referrals/1/accept/', (route) => json(route, {
    ...row, sender: person(12, 'Maya'), recipient: person(7, 'Me'), status: 'accepted', resolved_at: '2026-11-07T12:00:00Z',
  }));
  await page.getByRole('button', { name: 'Accept referral for Engineer from Maya' }).click();
  await expect(page.getByText('Status: accepted', { exact: true })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
