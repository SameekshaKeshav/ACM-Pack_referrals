import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Automated accessibility scans (axe-core) of the main pages, run in CI with
// the other Playwright tests. Every backend call is mocked with realistic data
// so each page is scanned in its filled-in state, not an empty or error state.
// Axe finds only some problems (roughly a third of WCAG issues): it does not
// replace a keyboard-only walkthrough or a screen reader check.

const me = { id: 7, email: 'sam@ncsu.edu' };
const created = '2026-10-20T12:00:00Z';
const companies = [
  { id: 1, name: 'Red Hat', industry_tag: 'Software', logo_url: '' },
  { id: 2, name: 'SAS', industry_tag: 'Analytics', logo_url: '' },
];
const profile = {
  first_name: 'Sam', last_name: 'Lee', major: 'Computer Science', grad_year: 2027,
  bio: 'Junior interested in backend and infrastructure work.', open_to_connect: true,
  current_role: 'Software Intern', current_company: companies[0],
  past_roles: [{ id: 3, company: companies[1], role_title: 'Data Analyst Intern', start_date: '2025-05-19', end_date: '2025-08-08' }],
};
const people = [
  { user_id: 7, name: 'Sam Lee', major: 'Computer Science', grad_year: 2027, current_role: 'Software Intern', current_company: companies[0], open_to_connect: true },
  { user_id: 41, name: 'Avery Chen', major: 'Computer Engineering', grad_year: 2026, current_role: 'Engineer', current_company: companies[0], open_to_connect: true },
  { user_id: 42, name: 'Jordan Diaz', major: 'Statistics', grad_year: 2025, current_role: 'Analyst', current_company: companies[0], open_to_connect: false },
  { user_id: 43, name: 'Priya Rao', major: 'Computer Science', grad_year: 2026, current_role: 'SRE', current_company: companies[0], open_to_connect: true },
];
const incoming = [{ id: 11, sender: { id: 44, name: 'Morgan Park', company: 'IBM' }, message_text: 'Hi! I saw your post about internships.', status: 'pending', created_at: created }];
const outgoing = [{ id: 12, recipient: { id: 45, name: 'Taylor Kim', company: 'Cisco' }, message_text: 'Hello, could we chat?', status: 'pending', created_at: created }];
const conversations = [{ id: 5, other_user: { id: 41, name: 'Avery Chen', company: 'Red Hat' }, last_message: { body_text: 'Thanks!' }, unread_count: 1, updated_at: created }];
const messages = [
  { id: 1, conversation_id: 5, sender_id: 41, body_text: 'Happy to help with your application.', created_at: '2026-10-20T12:00:00Z' },
  { id: 2, conversation_id: 5, sender_id: 7, body_text: 'Thanks!', created_at: '2026-10-20T12:01:00Z' },
];
const referral = (id, sender, recipient, status) => ({
  id, sender, recipient, company: companies[0], role_title: 'Software Engineering Intern',
  message_text: 'I have two years of Django experience.', status,
  job_url: 'https://example.com/jobs/123', resume_url: '', created_at: created,
});
const referrals = {
  incoming: [referral(21, { id: 41, name: 'Avery Chen' }, { id: 7, name: 'Sam Lee' }, 'pending')],
  outgoing: [referral(22, { id: 7, name: 'Sam Lee' }, { id: 41, name: 'Avery Chen' }, 'accepted')],
};

const json = (route, data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });

// Returns the mocked response for a backend path, or undefined if it is not mocked.
function respond(url) {
  const path = url.pathname;
  const type = url.searchParams.get('type');
  if (path === '/api/accounts/me/') return profile;
  if (path === '/api/accounts/users/') return { count: people.length, next: null, previous: null, results: people };
  if (path === '/api/companies/') return companies;
  if (path === '/api/companies/1/') return companies[0];
  if (path === '/api/connections/' && type === 'incoming') return incoming;
  if (path === '/api/connections/' && type === 'outgoing') return outgoing;
  if (path === '/api/chat/conversations/') return conversations;
  if (path === '/api/chat/conversations/5/messages/') return messages;
  if (path === '/api/connections/referrals/' && referrals[type]) {
    const rows = referrals[type];
    return { count: rows.length, next: null, previous: null, results: rows };
  }
  return undefined;
}

async function mockBackend(page, { signedIn }) {
  const unmocked = [];
  await page.addInitScript(({ user, signedIn: on }) => {
    if (on) localStorage.setItem('pack-referrals.session.v1', JSON.stringify({ access: 'access', refresh: 'refresh', user }));
    // The enter-code page reads the email waiting for a code from here.
    sessionStorage.setItem('pack-referrals.pending-auth', JSON.stringify({ email: user.email, mode: 'login' }));
  }, { user: me, signedIn });
  // Match backend requests only. A glob like **/api/** also matches Vite
  // modules under /src/api/ and would replace JavaScript with JSON.
  await page.route((url) => url.pathname.startsWith('/api/'), (route) => {
    const url = new URL(route.request().url());
    const data = route.request().method() === 'GET' ? respond(url) : undefined;
    if (data === undefined) {
      unmocked.push(`${route.request().method()} ${url.pathname}${url.search}`);
      return json(route, { detail: 'Not mocked in a11y.spec.js' }, 404);
    }
    return json(route, data);
  });
  return unmocked;
}

// One line per failing element, so the CI log says what to fix and where.
function describe(violations) {
  return violations.flatMap((violation) => violation.nodes.map((node) => (
    `[${violation.impact}] ${violation.id}: ${violation.help}\n    at ${node.target.join(' ')}\n    ${node.failureSummary?.replaceAll('\n', '\n    ')}`
  )));
}

async function expectNoViolations(page, unmocked) {
  const { violations } = await new AxeBuilder({ page }).analyze();
  expect(describe(violations), `axe violations on ${page.url()}`).toEqual([]);
  // A page that called an unmocked endpoint was scanned in an error state.
  expect(unmocked, 'backend calls with no mock (add them to respond())').toEqual([]);
}

const pages = [
  { name: 'login', path: '/login', signedIn: false, ready: (page) => page.getByRole('heading', { name: 'Welcome back' }) },
  { name: 'signup', path: '/signup', signedIn: false, ready: (page) => page.getByLabel('University email') },
  { name: 'enter code', path: '/enter-code', signedIn: false, ready: (page) => page.getByLabel('Six-digit code') },
  { name: 'chat and connection requests', path: '/chat/5', signedIn: true, ready: (page) => page.getByRole('list', { name: 'Messages', exact: true }).getByRole('listitem').nth(1) },
  { name: 'referrals', path: '/referrals', signedIn: true, ready: (page) => page.getByRole('article', { name: 'Referral to Avery Chen' }) },
  { name: 'directory', path: '/directory', signedIn: true, ready: (page) => page.getByRole('link', { name: /SAS/ }) },
  { name: 'company members', path: '/company/1', signedIn: true, ready: (page) => page.getByRole('heading', { name: 'Priya Rao' }) },
  { name: 'profile', path: '/profile', signedIn: true, ready: (page) => page.getByRole('button', { name: 'Edit Profile' }) },
];

for (const { name, path, signedIn, ready } of pages) {
  test(`no axe violations: ${name}`, async ({ page }) => {
    const unmocked = await mockBackend(page, { signedIn });
    await page.goto(path);
    await expect(ready(page)).toBeVisible();
    await expectNoViolations(page, unmocked);
  });
}

test('no axe violations: profile edit form', async ({ page }) => {
  const unmocked = await mockBackend(page, { signedIn: true });
  await page.goto('/profile');
  await page.getByRole('button', { name: 'Edit Profile' }).click();
  await expect(page.getByRole('button', { name: 'Add role' })).toBeVisible();
  await expectNoViolations(page, unmocked);
});

test('no axe violations: connect dialog', async ({ page }) => {
  const unmocked = await mockBackend(page, { signedIn: true });
  await page.goto('/company/1');
  await page.getByRole('button', { name: 'Connect with Priya Rao' }).click();
  await expect(page.getByRole('dialog', { name: 'Connect with Priya Rao' })).toBeVisible();
  await expectNoViolations(page, unmocked);
});
