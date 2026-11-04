import { test, expect } from '@playwright/test';
import { mockApi, seedSession } from './helpers/mock-api';

async function open(page, options) {
  await seedSession(page); const state = await mockApi(page, options);
  await page.goto('/company/3?tab=interviews');
  await expect(page.getByRole('heading', { name: 'Share an interview experience' })).toBeVisible();
  return state;
}
async function fill(page) {
  await page.getByLabel('Role title (required)').fill('Summer intern');
  await page.getByLabel('Outcome (required)').selectOption('no_response');
  await page.getByLabel('Difficulty (required)').selectOption('2');
  await page.getByLabel('Interview process (required)').fill('Phone screen and technical interview.');
}

test('create and reload anonymous post, then confirm own deletion', async ({ page }) => {
  const state = await open(page);
  await expect(page.getByRole('article', { name: 'Software engineer' })).toBeVisible();
  await fill(page);
  await page.getByRole('button', { name: 'Post experience', exact: true }).click();
  const card = page.getByRole('article', { name: 'Summer intern' });
  await expect(card).toContainText('Anonymous member · Your post');
  const request = state.calls.find((call) => call.method === 'POST');
  expect(request).toMatchObject({ path: '/api/companies/3/experiences/', authorization: 'Bearer test-access', body: { role_title: 'Summer intern', outcome: 'no_response', difficulty: 2, process_text: 'Phone screen and technical interview.' } });
  await page.reload(); await expect(card).toBeVisible();
  await card.getByRole('button', { name: 'Delete my Summer intern experience' }).click();
  expect(state.calls.filter((call) => call.method === 'DELETE')).toHaveLength(0);
  await card.getByRole('button', { name: 'Confirm delete' }).click();
  await expect(card).toHaveCount(0);
  expect(state.calls.some((call) => call.path === '/api/companies/3/experiences/99/' && call.method === 'DELETE')).toBe(true);
  await expect(page.getByRole('article', { name: 'Analyst' }).getByRole('button')).toHaveCount(0);
});

test('daily limit keeps draft; large Unicode paste is capped', async ({ page }) => {
  await open(page); await expect(page.getByRole('article', { name: 'Software engineer' })).toBeVisible();
  await page.route((url) => url.pathname === '/api/companies/3/experiences/', (route) => route.request().method() === 'POST'
    ? route.fulfill({ status: 429, contentType: 'application/json', body: JSON.stringify({ detail: 'Daily limit reached.' }) }) : route.fallback());
  await fill(page); await page.getByRole('button', { name: 'Post experience', exact: true }).click();
  await expect(page.getByRole('alert')).toContainText('Daily limit reached.');
  await expect(page.getByLabel('Interview process (required)')).toHaveValue('Phone screen and technical interview.');
  await page.getByLabel('Interview process (required)').fill('😀'.repeat(5001));
  await expect(page.getByLabel('Interview process (required)')).toHaveValue('😀'.repeat(5000));
  await expect(page.getByText('0 characters remaining')).toBeVisible();
});

test('unmerged backend shows unavailable state, and company tabs work with keyboard', async ({ page }) => {
  await open(page, { experienceStatus: 404 });
  await expect(page.getByRole('alert').filter({ hasText: 'not available' })).toBeVisible();
  await expect(page.getByLabel('Role title (required)')).toBeDisabled();
  const interviews = page.getByRole('tab', { name: 'Interview experiences' });
  await interviews.focus(); await page.keyboard.press('Home');
  await expect(page.getByRole('tab', { name: 'Members' })).toBeFocused();
  await page.keyboard.press('End'); await expect(interviews).toBeFocused();
  await expect(interviews).toHaveAttribute('aria-selected', 'true');
});
