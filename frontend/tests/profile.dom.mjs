import test, { after, afterEach, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost:5173/profile' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
// A signed-in session, so the shared API client has a token to send.
window.localStorage.setItem('pack-referrals.session.v1', JSON.stringify({
  access: 'test-access', refresh: 'test-refresh', user: { id: 1, email: 'jane@ncsu.edu' },
}));
const { createElement } = await import('react');
const { render, screen, cleanup, waitFor } = await import('@testing-library/react');
const { default: userEvent } = await import('@testing-library/user-event');
const vite = await createServer({ server: { middlewareMode: true, hmr: false } });
const { default: Profile } = await vite.ssrLoadModule('/src/pages/Profile.jsx');
after(async () => { await vite.close(); dom.window.close(); });

const json = (data, status = 200) => new Response(JSON.stringify(data), { status });
const company = (id, name) => ({ id, name, industry_tag: '', logo_url: '' });
const freshProfile = () => ({
  user_id: 1, email: 'jane@ncsu.edu', name: 'Jane Doe', first_name: 'Jane', last_name: 'Doe',
  major: 'Computer Science', grad_year: 2028, bio: 'Junior, backend.', current_role: '',
  current_company: null, open_to_connect: true, account_status: 'active',
  past_roles: [
    { id: 1, company: company(1, 'Google'), role_title: 'SWE Intern', start_date: '2025-05-01', end_date: '2025-08-01' },
    { id: 2, company: company(2, 'Red Hat'), role_title: 'Co-op', start_date: '2024-01-01', end_date: null },
  ],
});

let stored;
let calls;
let originalFetch;

beforeEach(() => {
  stored = freshProfile();
  calls = [];
  originalFetch = globalThis.fetch;
  // A tiny stand-in for the server's /api/accounts/me/ endpoint.
  globalThis.fetch = async (url, options = {}) => {
    const method = options.method || 'GET';
    const body = options.body ? JSON.parse(options.body) : undefined;
    calls.push({ url, method, headers: options.headers, body });
    if (url !== '/api/accounts/me/') return json({ detail: 'Not found.' }, 404);
    if (method === 'GET') return json(stored);
    if (method === 'PATCH') {
      if (body.grad_year != null && body.grad_year < 2000) {
        return json({ grad_year: ['Ensure this value is greater than or equal to 2000.'] }, 400);
      }
      stored = { ...stored, ...body };
      return json(stored);
    }
    return json({ detail: 'Method not allowed.' }, 405);
  };
});
afterEach(() => { cleanup(); globalThis.fetch = originalFetch; });

test('loads the signed-in profile with the Bearer token', async () => {
  render(createElement(Profile));
  assert.ok(screen.getByText('Loading...'));
  assert.ok(await screen.findByRole('heading', { name: 'Jane Doe' }));
  assert.ok(screen.getByText('Computer Science - Class 2028'));
  assert.ok(screen.getByText(/Google/));
  assert.ok(screen.getByText(/Red Hat/));
  assert.equal(calls[0].url, '/api/accounts/me/');
  assert.equal(calls[0].headers.Authorization, 'Bearer test-access');
});

test('Edit shows inputs pre-filled from the server', async () => {
  render(createElement(Profile));
  const user = userEvent.setup({ document: dom.window.document });
  await screen.findByRole('heading', { name: 'Jane Doe' });
  await user.click(screen.getByRole('button', { name: 'Edit Profile' }));
  assert.equal(screen.getByLabelText('First name').value, 'Jane');
  assert.equal(screen.getByLabelText('Last name').value, 'Doe');
  assert.equal(screen.getByLabelText('Major').value, 'Computer Science');
  assert.equal(screen.getByLabelText('Graduation Year').value, '2028');
  assert.ok(screen.getByDisplayValue('Junior, backend.'));
});

test('Save sends PATCH with the right body and shows the stored result', async () => {
  render(createElement(Profile));
  const user = userEvent.setup({ document: dom.window.document });
  await screen.findByRole('heading', { name: 'Jane Doe' });
  await user.click(screen.getByRole('button', { name: 'Edit Profile' }));
  const bio = screen.getByDisplayValue('Junior, backend.');
  await user.clear(bio);
  await user.type(bio, 'Now a senior.');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  assert.ok(await screen.findByText('Now a senior.'));
  assert.ok(screen.getByRole('button', { name: 'Edit Profile' }));
  const patch = calls.find((c) => c.method === 'PATCH');
  assert.equal(patch.url, '/api/accounts/me/');
  assert.deepEqual(patch.body, {
    first_name: 'Jane', last_name: 'Doe', major: 'Computer Science',
    grad_year: 2028, bio: 'Now a senior.', open_to_connect: true,
  });
  assert.equal(stored.bio, 'Now a senior.');
});

test('Cancel discards edits and sends no PATCH', async () => {
  render(createElement(Profile));
  const user = userEvent.setup({ document: dom.window.document });
  await screen.findByRole('heading', { name: 'Jane Doe' });
  await user.click(screen.getByRole('button', { name: 'Edit Profile' }));
  const bio = screen.getByDisplayValue('Junior, backend.');
  await user.clear(bio);
  await user.type(bio, 'Should not be saved.');
  await user.click(screen.getByRole('button', { name: 'Cancel' }));
  assert.ok(screen.getByText('Junior, backend.'));
  assert.equal(screen.queryByText('Should not be saved.'), null);
  assert.equal(calls.filter((c) => c.method === 'PATCH').length, 0);
});

test('a server validation error is shown and the form keeps the draft', async () => {
  render(createElement(Profile));
  const user = userEvent.setup({ document: dom.window.document });
  await screen.findByRole('heading', { name: 'Jane Doe' });
  await user.click(screen.getByRole('button', { name: 'Edit Profile' }));
  const year = screen.getByLabelText('Graduation Year');
  await user.clear(year);
  await user.type(year, '1999');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => assert.match(screen.getByRole('alert').textContent, /grad year/i));
  assert.equal(screen.getByLabelText('Graduation Year').value, '1999');
  assert.equal(stored.grad_year, 2028);
});

test('a profile with no grad year saves with grad_year: null, not 0', async () => {
  stored.grad_year = null;
  render(createElement(Profile));
  const user = userEvent.setup({ document: dom.window.document });
  await screen.findByRole('heading', { name: 'Jane Doe' });
  await user.click(screen.getByRole('button', { name: 'Edit Profile' }));
  assert.equal(screen.getByLabelText('Graduation Year').value, '');
  const bio = screen.getByDisplayValue('Junior, backend.');
  await user.clear(bio);
  await user.type(bio, 'New bio.');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  assert.ok(await screen.findByText('New bio.'));
  const patch = calls.find((c) => c.method === 'PATCH');
  assert.deepEqual(patch.body, {
    first_name: 'Jane', last_name: 'Doe', major: 'Computer Science',
    grad_year: null, bio: 'New bio.', open_to_connect: true,
  });
  assert.equal(stored.grad_year, null);
});

test('Cancel clears the error banner after a failed save', async () => {
  render(createElement(Profile));
  const user = userEvent.setup({ document: dom.window.document });
  await screen.findByRole('heading', { name: 'Jane Doe' });
  await user.click(screen.getByRole('button', { name: 'Edit Profile' }));
  const year = screen.getByLabelText('Graduation Year');
  await user.clear(year);
  await user.type(year, '1999');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  await waitFor(() => assert.match(screen.getByRole('alert').textContent, /grad year/i));
  await user.click(screen.getByRole('button', { name: 'Cancel' }));
  assert.equal(screen.queryByRole('alert'), null);
  assert.ok(screen.getByRole('button', { name: 'Edit Profile' }));
});

test('past role dates read "May 2025 - Aug 2025" and ongoing roles read Present', async () => {
  render(createElement(Profile));
  await screen.findByRole('heading', { name: 'Jane Doe' });
  assert.ok(screen.getByText(/May 2025 - Aug 2025/));
  assert.ok(screen.getByText(/Jan 2024 - Present/));
  assert.equal(screen.queryByText(/2025-05-01/), null);
  assert.equal(screen.queryByText(/2024-01-01/), null);
});