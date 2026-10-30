import test, { after, afterEach, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';

const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173/directory' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLElement = dom.window.HTMLElement;
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { createElement: h } = await import('react');
const { render, screen, cleanup, waitFor, within } = await import('@testing-library/react');
const { default: userEvent } = await import('@testing-library/user-event');
const { MemoryRouter } = await import('react-router-dom');
const vite = await createServer({ server: { middlewareMode: true, hmr: false } });
const { default: PeopleDirectory } = await vite.ssrLoadModule('/src/components/directory/PeopleDirectory.jsx');
const { directoryQuery } = await vite.ssrLoadModule('/src/api/directory.js');
const session = await vite.ssrLoadModule('/src/auth/session.js');
const originalFetch = globalThis.fetch;

beforeEach(() => session.signIn({ access: 'access-1', refresh: 'refresh-1', user_id: 7, email: 'me@ncsu.edu' }));
afterEach(() => { cleanup(); session.signOut(); dom.window.localStorage.clear(); globalThis.fetch = originalFetch; });
after(async () => { await vite.close(); dom.window.close(); });

const member = (id, name, major, gradYear, company = null, role = '') => ({
  user_id: id, name, major, grad_year: gradYear, current_role: role,
  current_company: company ? { id: company, name: `Company ${company}`, industry_tag: '', logo_url: '' } : null, open_to_connect: true,
});
const everyone = [
  member(1, 'Alice Adams', 'Computer Science', 2026, 7, 'Engineer'),
  member(2, 'Bob Brown', 'Computer Science', 2027),
  member(3, 'Carol Chen', 'Statistics', 2026),
  member(4, 'Dan Diaz', 'Data Science', 2028),
];

const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });

// A stand-in for GET /api/accounts/users/ with the same rules as the backend:
// repeated major = any of them (substring), grad_year exact, limit/offset paging.
function fakeDirectory(rows = everyone, { onRequest } = {}) {
  const requests = [];
  globalThis.fetch = async (path) => {
    const url = new URL(path, 'http://localhost:5173');
    // Connection state lookups (Connect buttons) are not what these tests are about: nobody is connected.
    if (url.pathname === '/api/connections/' || url.pathname === '/api/chat/conversations/') return json([]);
    requests.push(url);
    const special = await onRequest?.(url, requests.length);
    if (special) return special;
    const majors = url.searchParams.getAll('major').map((value) => value.toLowerCase());
    const year = url.searchParams.get('grad_year');
    const limit = Number(url.searchParams.get('limit') || 20);
    const offset = Number(url.searchParams.get('offset') || 0);
    const matches = rows.filter((row) => (!majors.length || majors.some((major) => row.major.toLowerCase().includes(major)))
      && (!year || String(row.grad_year) === year));
    return json({ count: matches.length, next: null, previous: null, results: matches.slice(offset, offset + limit) });
  };
  return requests;
}

const mount = () => render(h(MemoryRouter, null, h(PeopleDirectory)));
const user = () => userEvent.setup({ document: dom.window.document });
const names = () => screen.queryAllByRole('heading', { level: 3 }).map((node) => node.textContent);
const status = () => screen.getByRole('status').textContent;

test('lists verified members from the API with a count', async () => {
  const requests = fakeDirectory();
  mount();

  await waitFor(() => assert.equal(status(), '4 members found'));
  assert.deepEqual(names(), ['Alice Adams', 'Bob Brown', 'Carol Chen', 'Dan Diaz']);
  assert.equal(requests[0].pathname, '/api/accounts/users/');
  assert.equal(requests[0].searchParams.get('limit'), '20');
});

test('Computer Science and 2026 narrow the list within one second', async () => {
  const requests = fakeDirectory();
  const actor = user();
  mount();
  await waitFor(() => assert.equal(names().length, 4));

  const started = Date.now();
  await actor.click(screen.getByRole('checkbox', { name: 'Computer Science' }));
  await actor.selectOptions(screen.getByLabelText('Graduation year'), '2026');
  await waitFor(() => assert.deepEqual(names(), ['Alice Adams']));

  assert.ok(Date.now() - started < 1000);
  assert.equal(status(), '1 member found');
  const last = requests.at(-1);
  assert.deepEqual(last.searchParams.getAll('major'), ['Computer Science']);
  assert.equal(last.searchParams.get('grad_year'), '2026');
});

test('several majors are sent as repeated parameters and mean any of them', async () => {
  const requests = fakeDirectory();
  const actor = user();
  mount();
  await waitFor(() => assert.equal(names().length, 4));

  await actor.click(screen.getByRole('checkbox', { name: 'Statistics' }));
  await actor.click(screen.getByRole('checkbox', { name: 'Data Science' }));
  await waitFor(() => assert.deepEqual(names(), ['Carol Chen', 'Dan Diaz']));

  assert.deepEqual(requests.at(-1).searchParams.getAll('major').sort(), ['Data Science', 'Statistics']);
});

test('unchecking a major and clearing filters bring everyone back', async () => {
  fakeDirectory();
  const actor = user();
  mount();
  await waitFor(() => assert.equal(names().length, 4));
  const clear = screen.getByRole('button', { name: 'Clear filters' });
  assert.equal(clear.disabled, true);

  await actor.click(screen.getByRole('checkbox', { name: 'Statistics' }));
  await waitFor(() => assert.equal(names().length, 1));
  await actor.click(screen.getByRole('checkbox', { name: 'Statistics' }));
  await waitFor(() => assert.equal(names().length, 4));

  await actor.click(screen.getByRole('checkbox', { name: 'Computer Science' }));
  await actor.selectOptions(screen.getByLabelText('Graduation year'), '2027');
  await waitFor(() => assert.deepEqual(names(), ['Bob Brown']));
  await actor.click(screen.getByRole('button', { name: 'Clear filters' }));
  await waitFor(() => assert.equal(names().length, 4));
  assert.equal(screen.getByLabelText('Graduation year').value, '');
  assert.equal(screen.getByRole('checkbox', { name: 'Computer Science' }).checked, false);
});

test('every control has a visible label and works from the keyboard', async () => {
  fakeDirectory();
  const actor = user();
  mount();
  await waitFor(() => assert.equal(names().length, 4));

  assert.ok(screen.getByRole('group', { name: 'Major' }));
  assert.ok(screen.getByRole('form', { name: 'Filter members' }));
  assert.ok(screen.getByLabelText('Graduation year'));
  for (const box of screen.getAllByRole('checkbox')) assert.ok(box.labels.length === 1 && box.labels[0].textContent.trim());

  await actor.tab();
  assert.equal(document.activeElement, screen.getAllByRole('checkbox')[0]);
  await actor.keyboard(' ');
  await waitFor(() => assert.deepEqual(names(), ['Alice Adams', 'Bob Brown']));
});

test('the result count is a polite live region that changes with the filters', async () => {
  fakeDirectory();
  const actor = user();
  mount();
  await waitFor(() => assert.equal(status(), '4 members found'));

  const region = screen.getByRole('status');
  assert.equal(region.getAttribute('aria-live'), 'polite');
  await actor.click(screen.getByRole('checkbox', { name: 'Statistics' }));
  await waitFor(() => assert.equal(region.textContent, '1 member found'));
});

test('the count is not announced while a search is still loading', async () => {
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  fakeDirectory(everyone, { onRequest: async (url, number) => { if (number === 2) await gate; return null; } });
  const actor = user();
  mount();
  await waitFor(() => assert.equal(status(), '4 members found'));

  await actor.click(screen.getByRole('checkbox', { name: 'Statistics' }));
  assert.equal(status(), '4 members found');
  assert.equal(screen.getByRole('list').getAttribute('aria-busy'), 'true');
  release();
  await waitFor(() => assert.equal(status(), '1 member found'));
});

test('a slow earlier search cannot overwrite a newer one', async () => {
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  fakeDirectory(everyone, { onRequest: async (url, number) => { if (number === 2) { await gate; } return null; } });
  const actor = user();
  mount();
  await waitFor(() => assert.equal(names().length, 4));

  await actor.click(screen.getByRole('checkbox', { name: 'Statistics' })); // request 2, held
  await actor.click(screen.getByRole('checkbox', { name: 'Statistics' })); // request 3, back to everyone
  await waitFor(() => assert.equal(names().length, 4));
  release();
  await new Promise((resolve) => setTimeout(resolve, 20));

  assert.equal(names().length, 4);
  assert.equal(status(), '4 members found');
});

test('no matches shows a helpful message, not a blank page', async () => {
  fakeDirectory();
  const actor = user();
  mount();
  await waitFor(() => assert.equal(names().length, 4));

  await actor.click(screen.getByRole('checkbox', { name: 'Mathematics' }));
  await waitFor(() => assert.ok(screen.getByText(/No members match these filters/)));
  assert.equal(status(), '0 members found');
  assert.equal(names().length, 0);
});

test('a failed request shows an alert and Try again recovers', async () => {
  let failing = true;
  fakeDirectory(everyone, { onRequest: () => (failing ? json({ detail: 'Server is on fire.' }, 500) : null) });
  const actor = user();
  mount();

  const alert = await screen.findByRole('alert');
  assert.match(alert.textContent, /Server is on fire|could not be completed/i);
  failing = false;
  await actor.click(within(alert).getByRole('button', { name: 'Try again' }));
  await waitFor(() => assert.equal(names().length, 4));
  assert.equal(screen.queryByRole('alert'), null);
});

test('a malformed response is reported instead of crashing', async () => {
  fakeDirectory(everyone, { onRequest: () => json({ people: [] }) });
  mount();

  const alert = await screen.findByRole('alert');
  assert.match(alert.textContent, /does not match the API contract/);
});

test('Show more loads the next page and does not duplicate anyone', async () => {
  const many = Array.from({ length: 25 }, (_, index) => member(index + 1, `Person ${String(index + 1).padStart(2, '0')}`, 'Computer Science', 2027));
  const requests = fakeDirectory(many);
  const actor = user();
  mount();
  await waitFor(() => assert.equal(names().length, 20));
  assert.equal(status(), '25 members found');

  await actor.click(screen.getByRole('button', { name: 'Show more (20 of 25)' }));
  await waitFor(() => assert.equal(names().length, 25));

  assert.equal(requests.at(-1).searchParams.get('offset'), '20');
  assert.equal(new Set(names()).size, 25);
  assert.equal(screen.queryByRole('button', { name: /Show more/ }), null);
});

test('a member card links the company to its page and shows the role', async () => {
  fakeDirectory();
  mount();
  await waitFor(() => assert.equal(names().length, 4));

  const alice = screen.getByRole('heading', { name: 'Alice Adams' }).closest('li');
  assert.ok(within(alice).getByText(/Engineer at/));
  assert.equal(within(alice).getByRole('link', { name: 'Company 7' }).getAttribute('href'), '/company/7');
  assert.ok(within(alice).getByText('Computer Science · Class of 2026'));
});

test('member text is shown as plain text', async () => {
  fakeDirectory([member(9, '<img src=x onerror=alert(1)>', '<b>CS</b>', 2026)]);
  const { container } = mount();
  await waitFor(() => assert.equal(names().length, 1));

  assert.equal(container.querySelectorAll('img, b').length, 0);
  assert.equal(names()[0], '<img src=x onerror=alert(1)>');
});

test('directoryQuery builds the query the backend expects', () => {
  assert.equal(directoryQuery(), '/api/accounts/users/?limit=20');
  assert.equal(
    directoryQuery({ majors: ['Computer Science', 'Data Science'], gradYear: '2026', offset: 20 }),
    '/api/accounts/users/?major=Computer+Science&major=Data+Science&grad_year=2026&limit=20&offset=20',
  );
});
