import { test, expect } from '@playwright/test';

const person = (id, name) => ({ id, name, company: 'Example' });
const row = { id: 1, sender: person(7, 'Me'), recipient: person(12, 'Maya'), company: null, role_title: 'Engineer', message_text: 'Relevant experience', status: 'pending', job_url: '', resume_url: '', created_at: '2026-11-01T12:00:00Z' };
const json = (route, data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
async function setup(page, conflict = false) {
  let saved = [];
  await page.addInitScript(() => localStorage.setItem('pack-referrals.session.v1', JSON.stringify({ access: 'access', refresh: 'refresh', user: { id: 7, email: 'me@ncsu.edu' } })));
  await page.route('**/api/**', (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === '/api/chat/conversations/') return json(route, [{ id: 9, other_user: person(12, 'Maya') }]);
    if (url.pathname === '/api/companies/' || url.pathname === '/api/connections/') return json(route, []);
    if (url.pathname === '/api/connections/referrals/') {
      if (route.request().method() === 'POST') {
        expect(route.request().postDataJSON()).toEqual({ recipient_id: 12, role_title: 'Engineer', message_text: 'Relevant experience' });
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
