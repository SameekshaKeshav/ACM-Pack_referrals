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
const { render, screen, cleanup, waitFor, fireEvent } = await import('@testing-library/react');
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
let nextRoleId;
let failRoleCalls;
let holdRoleCalls;

beforeEach(() => {
  stored = freshProfile();
  calls = [];
  nextRoleId = 100;
  failRoleCalls = false;
  holdRoleCalls = null;
  originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options = {}) => {
    const method = options.method || 'GET';
    const body = options.body ? JSON.parse(options.body) : undefined;
    calls.push({ url, method, headers: options.headers, body });
    if (url === '/api/accounts/me/') {
      if (method === 'GET') return json(stored);
      if (method === 'PATCH') {
        if (body.grad_year != null && body.grad_year < 2000) {
          return json({ grad_year: ['Ensure this value is greater than or equal to 2000.'] }, 400);
        }
        const { current_company_name, ...rest } = body;
        stored = { ...stored, ...rest };
        if (current_company_name !== undefined) {
          stored.current_company = current_company_name ? company(50, current_company_name) : null;
        }
        return json(stored);
      }
      return json({ detail: 'Method not allowed.' }, 405);
    }
    if (url === '/api/accounts/past-roles/' && method === 'POST') {
      if (failRoleCalls) return json({ detail: 'Could not save the role.' }, 500);
      if (holdRoleCalls) await holdRoleCalls;
      const id = nextRoleId++;
      const role = {
        id, company: company(id, body.company_name), role_title: body.role_title,
        start_date: body.start_date, end_date: body.end_date,
      };
      stored.past_roles = [...stored.past_roles, role];
      return json(role, 201);
    }
    const match = url.match(/^\/api\/accounts\/past-roles\/(\d+)\/$/);
    if (match && method === 'DELETE') {
      if (failRoleCalls) return json({ detail: 'Could not remove the role.' }, 500);
      if (holdRoleCalls) await holdRoleCalls;
      const exists = stored.past_roles.some((r) => r.id === Number(match[1]));
      if (!exists) return json({ detail: 'No PastRole matches the given query.' }, 404);
      stored.past_roles = stored.past_roles.filter((r) => r.id !== Number(match[1]));
      return new Response(null, { status: 204 });
    }
    return json({ detail: 'Not found.' }, 404);
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
    current_role: '', current_company_name: '',
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
    current_role: '', current_company_name: '',
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

test('a profile with no grad year shows the major without a dangling "Class"', async () => {
  stored.grad_year = null;
  render(createElement(Profile));
  await screen.findByRole('heading', { name: 'Jane Doe' });
  assert.ok(screen.getByText('Computer Science'));
  assert.equal(screen.queryByText(/Class/), null);
});

async function openEditor() {
  render(createElement(Profile));
  const user = userEvent.setup({ document: dom.window.document });
  await screen.findByRole('heading', { name: 'Jane Doe' });
  await user.click(screen.getByRole('button', { name: 'Edit Profile' }));
  return user;
}

async function fillNewRole(user) {
  await user.type(screen.getByLabelText('Company'), 'Amazon');
  await user.type(screen.getByLabelText('Role title'), 'SDE Intern');
  fireEvent.change(screen.getByLabelText('Start date'), { target: { value: '2025-06-01' } });
}

test('adding a role posts company_name and shows the new row', async () => {
  const user = await openEditor();
  await fillNewRole(user);
  await user.click(screen.getByRole('button', { name: 'Add role' }));
  assert.ok(await screen.findByText(/Amazon/));
  const post = calls.find((c) => c.method === 'POST');
  assert.equal(post.url, '/api/accounts/past-roles/');
  assert.deepEqual(post.body, {
    company_name: 'Amazon', role_title: 'SDE Intern', start_date: '2025-06-01', end_date: null,
  });
  assert.equal(screen.getByLabelText('Company').value, '');
});

test('Enter in an add-role field adds the role and does not save the profile form', async () => {
  const user = await openEditor();
  await fillNewRole(user);
  await user.type(screen.getByLabelText('Role title'), '{Enter}');
  assert.ok(await screen.findByText(/Amazon/));
  assert.equal(calls.filter((c) => c.method === 'POST').length, 1);
  assert.equal(calls.filter((c) => c.method === 'PATCH').length, 0);
  // Still editing: Enter did not submit the outer form.
  assert.ok(screen.getByRole('heading', { name: 'Edit profile' }));
});

test('adding a role without required fields shows an alert and sends nothing', async () => {
  const user = await openEditor();
  await user.click(screen.getByRole('button', { name: 'Add role' }));
  assert.match(screen.getByRole('alert').textContent, /required/i);
  assert.equal(calls.filter((c) => c.method === 'POST').length, 0);
});

test('an end date before the start date is rejected before any request', async () => {
  const user = await openEditor();
  await fillNewRole(user);
  fireEvent.change(screen.getByLabelText('End date (leave blank if ongoing)'), { target: { value: '2025-01-01' } });
  await user.click(screen.getByRole('button', { name: 'Add role' }));
  assert.match(screen.getByRole('alert').textContent, /end date/i);
  assert.equal(calls.filter((c) => c.method === 'POST').length, 0);
});

test('removing a role sends DELETE and the row disappears', async () => {
  const user = await openEditor();
  await user.click(screen.getByRole('button', { name: 'Remove Google SWE Intern' }));
  await waitFor(() => assert.equal(screen.queryByText(/Google/), null));
  const del = calls.find((c) => c.method === 'DELETE');
  assert.equal(del.url, '/api/accounts/past-roles/1/');
  assert.ok(screen.getByText(/Red Hat/));
});

test('Cancel keeps roles that were already added', async () => {
  const user = await openEditor();
  await fillNewRole(user);
  await user.click(screen.getByRole('button', { name: 'Add role' }));
  await screen.findByText(/Amazon/);
  await user.click(screen.getByRole('button', { name: 'Cancel' }));
  assert.ok(screen.getByRole('button', { name: 'Edit Profile' }));
  assert.ok(screen.getByText(/Amazon/));
});

test('a failed add shows an alert and no row', async () => {
  failRoleCalls = true;
  const user = await openEditor();
  await fillNewRole(user);
  await user.click(screen.getByRole('button', { name: 'Add role' }));
  await waitFor(() => assert.ok(screen.getByRole('alert')));
  assert.equal(screen.queryByText(/Amazon · /), null);
});

test('saving current role and company sends them and shows them', async () => {
  const user = await openEditor();
  await user.type(screen.getByLabelText('Current role'), 'Engineer');
  await user.type(screen.getByLabelText('Current company'), 'Red Hat');
  await user.click(screen.getByRole('button', { name: 'Save' }));
  assert.ok(await screen.findByText('Engineer at Red Hat'));
  const patch = calls.find((c) => c.method === 'PATCH');
  assert.equal(patch.body.current_role, 'Engineer');
  assert.equal(patch.body.current_company_name, 'Red Hat');
});

test('double-clicking Add role posts once and disables the button while busy', async () => {
  let release;
  holdRoleCalls = new Promise((resolve) => { release = resolve; });
  const user = await openEditor();
  await fillNewRole(user);
  const add = screen.getByRole('button', { name: 'Add role' });
  await user.dblClick(add);
  assert.equal(add.disabled, true);
  assert.equal(calls.filter((c) => c.method === 'POST').length, 1);
  release();
  assert.ok(await screen.findByText(/Amazon/));
  assert.equal(calls.filter((c) => c.method === 'POST').length, 1);
  assert.equal(stored.past_roles.filter((r) => r.company.name === 'Amazon').length, 1);
});

test('double-clicking Remove sends one DELETE and shows no error', async () => {
  const user = await openEditor();
  const remove = screen.getByRole('button', { name: 'Remove Google SWE Intern' });
  await user.dblClick(remove);
  await waitFor(() => assert.equal(stored.past_roles.length, 1), { timeout: 3000 });
  assert.equal(calls.filter((c) => c.method === 'DELETE').length, 1);
  assert.equal(screen.queryByRole('alert'), null);
});

test('removing a role that is already gone on the server counts as success', async () => {
  const user = await openEditor();
  stored.past_roles = stored.past_roles.filter((r) => r.id !== 1);
  await user.click(screen.getByRole('button', { name: 'Remove Google SWE Intern' }));
  await waitFor(() => assert.equal(screen.queryByText(/Google/), null));
  assert.equal(screen.queryByRole('alert'), null);
});