import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { mockChatConnect, reply } from './fixtures/chat-connect';

async function noSeriousViolations(page) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(violations.filter((row) => ['serious', 'critical'].includes(row.impact))).toEqual([]);
}
async function capture(page, testInfo, name) {
  const phase = process.env.SCREENSHOT_PHASE || 'after';
  const directory = process.env.EVIDENCE_DIR;
  if (directory) await mkdir(directory, { recursive: true });
  await page.screenshot({ path: directory ? path.join(directory, `${phase}-${name}.png`) : testInfo.outputPath(`${phase}-${name}.png`), fullPage: true });
}
async function tabTo(page, locator) {
  for (let tries = 0; tries < 80; tries += 1) {
    if (await locator.evaluate((node) => node === document.activeElement)) return;
    await page.keyboard.press('Tab');
  }
  throw new Error('Control was unreachable using Tab');
}

for (const width of [375, 768, 1440]) {
  test(`responsive capture: chat ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    const { unknown } = await mockChatConnect(page, { accepted: true });
    await page.goto('/chat/5');
    const input = page.getByLabel('Chat message');
    await expect(page.getByRole('list', { name: 'Messages', exact: true }).getByRole('listitem')).toHaveCount(2);
    await input.fill('A message from the responsive check');
    await input.scrollIntoViewIfNeeded(); await expect(input).toBeInViewport();
    const box = await input.boundingBox();
    expect(box.width).toBeGreaterThan(100); expect(box.x).toBeGreaterThanOrEqual(0); expect(box.x + box.width).toBeLessThanOrEqual(width);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await capture(page, testInfo, `chat-${width}`);
    if (process.env.SCREENSHOT_PHASE !== 'before') await noSeriousViolations(page);
    expect(unknown).toEqual([]);
  });
  test(`responsive capture: connect ${width}px`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width, height: 900 });
    const { unknown } = await mockChatConnect(page, { accepted: false });
    await page.goto('/company/1');
    await page.getByRole('button', { name: 'Connect with Avery Chen' }).click();
    const note = page.getByLabel('Your note');
    await note.fill('I would like to learn about your work.');
    await expect(note).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await capture(page, testInfo, `connect-${width}`);
    if (process.env.SCREENSHOT_PHASE !== 'before') await noSeriousViolations(page);
    expect(unknown).toEqual([]);
  });
}

test('keyboard-only request, accept and send; focus reaches the new composer', async ({ page }) => {
  const { state, unknown } = await mockChatConnect(page, { accepted: false });
  await page.goto('/company/1');
  const connect = page.getByRole('button', { name: 'Connect with Avery Chen' });
  await expect(connect).toBeVisible(); await tabTo(page, connect); await page.keyboard.press('Enter');
  const note = page.getByLabel('Your note'); await expect(note).toBeFocused();
  await page.keyboard.type('Could we connect about internships?');
  // Modal focus wraps in both directions and Escape restores the opener.
  await page.keyboard.press('Shift+Tab'); await expect(page.getByRole('button', { name: 'Send request', exact: true })).toBeFocused();
  await page.keyboard.press('Tab'); await expect(note).toBeFocused();
  await page.keyboard.press('Escape'); await expect(connect).toBeFocused();
  await page.keyboard.press('Enter'); await expect(note).toBeFocused();
  await page.keyboard.type('Could we connect about internships?');
  await tabTo(page, page.getByRole('button', { name: 'Send request', exact: true })); await page.keyboard.press('Enter');
  await expect(page.getByRole('dialog')).toHaveCount(0); expect(state.requests).toHaveLength(1);
  await tabTo(page, page.getByRole('link', { name: /Messages/ })); await page.keyboard.press('Enter');
  const accept = page.getByRole('button', { name: 'Accept Morgan Park' });
  await expect(accept).toBeVisible(); await tabTo(page, accept); await page.keyboard.press('Enter');
  const input = page.getByLabel('Chat message'); await expect(input).toBeFocused();
  await page.keyboard.type('Thanks for accepting!');
  await page.keyboard.press('Tab'); await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('list', { name: 'Messages', exact: true }).getByText('Thanks for accepting!')).toBeVisible();
  expect(state.sendCalls).toBe(1); await noSeriousViolations(page); expect(unknown).toEqual([]);
});

test('poll announces incoming replies; failed send retries on the same bubble', async ({ page }) => {
  const { state } = await mockChatConnect(page);
  await page.goto('/chat/5');
  const messages = page.getByRole('list', { name: 'Messages', exact: true });
  await expect(messages.getByRole('listitem')).toHaveCount(2);
  state.messages.push(reply(3, 'A new reply'));
  await expect(messages.getByText('A new reply')).toBeVisible({ timeout: 10000 });
  await expect(page.locator('.chat-window [aria-live="polite"]')).toContainText('New message from Morgan Park: A new reply');
  state.failSend = true;
  await page.getByLabel('Chat message').fill('Please keep this message');
  await page.getByRole('button', { name: 'Send', exact: true }).click();
  const retry = messages.getByRole('button', { name: 'Failed to send - tap to retry' });
  await expect(retry).toBeVisible(); await noSeriousViolations(page);
  state.failSend = false; await retry.click();
  await expect(retry).toHaveCount(0); await expect(messages.getByRole('listitem')).toHaveCount(4);
  expect(state.sendCalls).toBe(2);
});

test('loading, empty and retryable error pages have no serious axe violations', async ({ page }) => {
  let release; const loading = new Promise((resolve) => { release = resolve; });
  const { state } = await mockChatConnect(page, { loading, empty: true });
  await page.goto('/chat');
  await expect(page.getByText('Loading conversations…')).toBeVisible(); await noSeriousViolations(page);
  release(); state.loading = null;
  await expect(page.getByText('No conversations yet. An accepted connection starts a conversation.')).toBeVisible(); await noSeriousViolations(page);
  state.failLoad = true; await page.getByRole('button', { name: 'Refresh conversations' }).click();
  await expect(page.getByRole('button', { name: 'Retry conversations' })).toBeVisible(); await noSeriousViolations(page);
  state.failLoad = false; await page.getByRole('button', { name: 'Retry conversations' }).click();
  await expect(page.getByRole('button', { name: 'Retry conversations' })).toHaveCount(0);
});
