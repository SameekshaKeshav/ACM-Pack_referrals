import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { mockApi, seedSession } from './helpers/mock-api';

async function audit(page, testInfo, name) {
  const results = await new AxeBuilder({ page }).analyze();
  await testInfo.attach(`axe-${name}`, { body: JSON.stringify(results, null, 2), contentType: 'application/json' });
  const blockers = results.violations.filter((violation) => ['serious', 'critical'].includes(violation.impact));
  expect(blockers.map(({ id, impact, nodes }) => ({ id, impact, nodes: nodes.map(({ target, failureSummary }) => ({ target, failureSummary })) })), `Serious/critical axe violations in ${name}`).toEqual([]);
}

// Main's a11y.spec.js retains the baseline page scans. These tests add
// keyboard behaviour and interaction/error/mobile states rather than duplicating it.
test('skip links reach main on public and authenticated pages', async ({ page }) => {
  await mockApi(page);
  await page.goto('/signup');
  await expect(page.getByLabel('University email')).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
  await seedSession(page);
  await page.goto('/referrals');
  await expect(page.getByRole('article', { name: 'Referral to Maya Patel' })).toBeVisible();
  await page.keyboard.press('Tab');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('main')).toBeFocused();
});

test('code verification normal and error states pass axe', async ({ page }, testInfo) => {
  await mockApi(page); await page.goto('/signup');
  await page.getByLabel('University email').fill('sanjana@ncsu.edu');
  await page.getByRole('button', { name: 'Sign up', exact: true }).click();
  await expect(page.getByLabel('Six-digit code')).toBeVisible();
  await audit(page, testInfo, 'enter-code');
  await page.route('**/api/accounts/auth/verify/', (route) => route.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ detail: 'Code expired. Request a new code.' }) }));
  await page.getByLabel('Six-digit code').fill('123456');
  await page.getByRole('button', { name: 'Verify and sign in' }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await audit(page, testInfo, 'enter-code-error');
});

test('Connect dialog passes axe and keyboard focus returns to its opener', async ({ page }, testInfo) => {
  await seedSession(page); await mockApi(page); await page.goto('/company/3');
  const opener = page.getByRole('button', { name: 'Connect with Maya Patel' });
  // The mocked incoming queue makes the directory show Respond for Maya; use a
  // separate empty connection queue to exercise the Connect interaction instead.
  await page.route('**/api/connections/?*', (route) => route.fulfill({ contentType: 'application/json', body: '[]' }));
  await page.route('**/api/chat/conversations/', (route) => route.fulfill({ contentType: 'application/json', body: '[]' }));
  await page.reload();
  await opener.click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await expect(page.getByLabel('Your note')).toBeFocused();
  await audit(page, testInfo, 'connect-dialog');
  await page.keyboard.press('Shift+Tab');
  await expect(page.getByRole('button', { name: 'Send request', exact: true })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Your note')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(opener).toBeFocused();
});

for (const state of ['populated', 'empty', 'unavailable']) {
  test(`interview experiences ${state} state passes axe`, async ({ page }, testInfo) => {
    await seedSession(page);
    await mockApi(page, state === 'empty' ? { experiences: [] } : state === 'unavailable' ? { experienceStatus: 404 } : {});
    await page.goto('/company/3?tab=interviews');
    await expect(page.getByRole('heading', { name: 'Share an interview experience' })).toBeVisible();
    if (state === 'populated') await expect(page.getByRole('article', { name: 'Software engineer' })).toBeVisible();
    if (state === 'empty') await expect(page.getByText('No interview experiences yet. Be the first to share.')).toBeVisible();
    if (state === 'unavailable') await expect(page.getByRole('alert').filter({ hasText: 'not available' })).toBeVisible();
    await audit(page, testInfo, `experiences-${state}`);
    if (state === 'populated') {
      await page.getByRole('button', { name: 'Delete my Software engineer experience' }).click();
      await audit(page, testInfo, 'experience-delete-confirmation');
      await page.getByRole('button', { name: 'Keep experience' }).click();
      await expect(page.getByRole('button', { name: 'Delete my Software engineer experience' })).toBeFocused();
      await page.route((url) => url.pathname === '/api/companies/3/experiences/', (route) => route.request().method() === 'POST'
        ? route.fulfill({ status: 429, contentType: 'application/json', body: JSON.stringify({ detail: 'Daily posting limit reached.' }) }) : route.fallback());
      await page.getByLabel('Role title (required)').fill('Intern');
      await page.getByLabel('Outcome (required)').selectOption('offer');
      await page.getByLabel('Difficulty (required)').selectOption('2');
      await page.getByLabel('Interview process (required)').fill('A phone interview.');
      await page.getByRole('button', { name: 'Post experience', exact: true }).click();
      await expect(page.getByRole('alert')).toContainText('Daily posting limit reached.');
      await audit(page, testInfo, 'experience-post-error');
    }
  });
}

test('mobile company posts and referral form pass axe', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await seedSession(page); await mockApi(page);
  await page.goto('/company/3?tab=interviews');
  await expect(page.getByRole('article', { name: 'Software engineer' })).toBeVisible();
  await audit(page, testInfo, 'mobile-experiences');
  await page.goto('/referrals');
  await expect(page.getByRole('article', { name: 'Referral to Maya Patel' })).toBeVisible();
  await audit(page, testInfo, 'mobile-referrals');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
