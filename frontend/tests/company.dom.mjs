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
const { MemoryRouter, Routes, Route, Link } = await import('react-router-dom');
const vite = await createServer({ server: { middlewareMode: true, hmr: false } });
const { default: Directory } = await vite.ssrLoadModule('/src/pages/Directory.jsx');
const { default: Company } = await vite.ssrLoadModule('/src/pages/Company.jsx');
const { companySearchUrl } = await vite.ssrLoadModule('/src/api/companies.js');
const { directoryQuery } = await vite.ssrLoadModule('/src/api/directory.js');
const session = await vite.ssrLoadModule('/src/auth/session.js');
const originalFetch = globalThis.fetch;

beforeEach(() => session.signIn({ access: 'access-1', refresh: 'refresh-1', user_id: 7, email: 'me@ncsu.edu' }));
afterEach(() => { cleanup(); session.signOut(); dom.window.localStorage.clear(); globalThis.fetch = originalFetch; });
after(async () => { await vite.close(); dom.window.close(); });

const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const companies = [
  { id: 1, name: 'Acme', industry_tag: 'Technology', logo_url: '' },
  { id: 2, name: 'Google', industry_tag: 'Technology', logo_url: '' },
  { id: 3, name: 'Goldman Sachs', industry_tag: 'Finance', logo_url: '' },
];
const people = {
  1: [{ user_id: 11, name: 'Alice Adams', major: 'Computer Science', grad_year: 2026, current_role: 'Engineer', current_company: { id: 1, name: 'Acme' }, open_to_connect: true }],
  2: [
    { user_id: 21, name: 'Gina Gomez', major: 'Computer Science', grad_year: 2026, current_role: 'SWE', current_company: { id: 2, name: 'Google' }, open_to_connect: true },
    { user_id: 22, name: 'Gus Green', major: 'Statistics', grad_year: 2025, current_role: 'Analyst', current_company: { id: 2, name: 'Google' }, open_to_connect: true },
  ],
};

// A stand-in for the companies and directory endpoints.
function fakeApi({ companyStatus = 200, onCompanies } = {}) {
  const requests = [];
  globalThis.fetch = async (path) => {
    const url = new URL(path, 'http://localhost:5173');
    requests.push(url);
    if (url.pathname === '/api/companies/') {
      const special = await onCompanies?.(url, requests.length);
      if (special) return special;
      const term = (url.searchParams.get('search') || '').toLowerCase();
      return json(companies.filter((company) => company.name.toLowerCase().includes(term)));
    }
    const detail = url.pathname.match(/^\/api\/companies\/(\d+)\/$/);
    if (detail) {
      const company = companies.find((row) => row.id === Number(detail[1]));
      return companyStatus !== 200 || !company ? json({ detail: 'Not found.' }, 404) : json({ ...company, affiliated_users: [] });
    }
    if (url.pathname === '/api/accounts/users/') {
      let rows = people[url.searchParams.get('company_id')] || [];
      const majors = url.searchParams.getAll('major').map((value) => value.toLowerCase());
      if (majors.length) rows = rows.filter((row) => majors.some((major) => row.major.toLowerCase().includes(major)));
      return json({ count: rows.length, next: null, previous: null, results: rows });
    }
    throw new Error(`unexpected request ${path}`);
  };
  return requests;
}

const user = () => userEvent.setup({ document: dom.window.document });
const app = (start) => render(h(MemoryRouter, { initialEntries: [start] }, h(Routes, null,
  h(Route, { path: '/directory', element: h(Directory) }),
  h(Route, { path: '/company/:id', element: h(Company) }))));

test('the directory lists companies and typing narrows them', async () => {
  const requests = fakeApi();
  app('/directory');
  const list = await screen.findByRole('list');
  assert.equal(within(list).getAllByRole('link').length, 3);
  await waitFor(() => assert.match(screen.getByRole('status').textContent, /^3 companies found$/));

  await user().type(screen.getByRole('searchbox', { name: 'Search companies' }), 'go');
  await waitFor(() => assert.equal(within(screen.getByRole('list')).getAllByRole('link').length, 2));
  assert.equal(requests.at(-1).searchParams.get('search'), 'go');
  assert.match(screen.getByRole('status').textContent, /^2 companies found$/);
});

test('a search with no match says so instead of showing an empty page', async () => {
  fakeApi();
  app('/directory');
  await screen.findByRole('list');
  await user().type(screen.getByRole('searchbox', { name: 'Search companies' }), 'zzz');
  await screen.findByText(/No companies match/);
  assert.equal(screen.queryByRole('list'), null);
});

test('choosing a company opens its page', async () => {
  fakeApi();
  app('/directory');
  await user().click(await screen.findByRole('link', { name: /Google/ }));
  assert.equal((await screen.findByRole('heading', { level: 1 })).textContent, 'Google');
  assert.ok(screen.getByRole('tab', { name: 'Members', selected: true }));
});

test('the Members tab lists only that company, and filters still work inside it', async () => {
  const requests = fakeApi();
  app('/company/2');
  await screen.findByText('Gina Gomez');
  assert.ok(screen.getByText('Gus Green'));
  assert.ok(!screen.queryByText('Alice Adams'));
  assert.ok(requests.filter((url) => url.pathname === '/api/accounts/users/').every((url) => url.searchParams.get('company_id') === '2'));

  await user().click(screen.getByRole('checkbox', { name: 'Statistics' }));
  await waitFor(() => assert.ok(!screen.queryByText('Gina Gomez')));
  assert.ok(screen.getByText('Gus Green'));
  const last = requests.at(-1);
  assert.equal(last.searchParams.get('company_id'), '2');
  assert.equal(last.searchParams.get('major'), 'Statistics');
});

test('switching tabs by click and by arrow keys, with the right ARIA state', async () => {
  fakeApi();
  app('/company/2');
  await screen.findByText('Gina Gomez');
  const members = screen.getByRole('tab', { name: 'Members' });
  const interviews = screen.getByRole('tab', { name: 'Interview experiences' });
  assert.equal(members.getAttribute('aria-selected'), 'true');
  assert.equal(interviews.getAttribute('tabindex'), '-1');

  await user().click(interviews);
  assert.equal(interviews.getAttribute('aria-selected'), 'true');
  assert.equal(members.getAttribute('aria-selected'), 'false');
  assert.match(screen.getByRole('tabpanel').textContent, /Interview experiences will appear here/);
  assert.ok(!screen.queryByText('Gina Gomez'));

  members.focus();
  await user().keyboard('{ArrowRight}');
  assert.equal(interviews.getAttribute('aria-selected'), 'true');
  assert.equal(dom.window.document.activeElement, interviews);
  await user().keyboard('{ArrowRight}');
  assert.equal(members.getAttribute('aria-selected'), 'true');
  assert.equal(screen.getByRole('tabpanel').getAttribute('aria-labelledby'), 'tab-members');
});

test('a link with ?tab= opens that tab, and an unknown tab falls back to Members', async () => {
  fakeApi();
  app('/company/2?tab=interviews');
  assert.equal((await screen.findByRole('tab', { name: 'Interview experiences' })).getAttribute('aria-selected'), 'true');
  cleanup();
  app('/company/2?tab=nonsense');
  assert.equal((await screen.findByRole('tab', { name: 'Members' })).getAttribute('aria-selected'), 'true');
});

test('an unknown or malformed company id shows a not-found message', async () => {
  fakeApi();
  app('/company/999');
  await screen.findByText('That company could not be found.');
  cleanup();
  app('/company/abc');
  await screen.findByText('That company could not be found.');
});

test('moving to an invalid or unknown id clears the company that was showing', async () => {
  fakeApi();
  render(h(MemoryRouter, { initialEntries: ['/company/2'] },
    h(Link, { to: '/company/abc' }, 'go malformed'),
    h(Link, { to: '/company/999' }, 'go unknown'),
    h(Link, { to: '/company/3' }, 'go goldman'),
    h(Routes, null, h(Route, { path: '/company/:id', element: h(Company) }))));
  assert.equal((await screen.findByRole('heading', { level: 1 })).textContent, 'Google');
  await screen.findByText('Gina Gomez');

  // Same route element, new param: the component is not remounted.
  await user().click(screen.getByRole('link', { name: 'go malformed' }));
  await screen.findByText('That company could not be found.');
  assert.equal(screen.queryByRole('heading', { name: 'Google' }), null);
  assert.equal(screen.queryByText('Gina Gomez'), null);

  await user().click(screen.getByRole('link', { name: 'go goldman' }));
  assert.equal((await screen.findByRole('heading', { level: 1, name: 'Goldman Sachs' })).textContent, 'Goldman Sachs');
  assert.equal(screen.queryByText('That company could not be found.'), null);

  await user().click(screen.getByRole('link', { name: 'go unknown' }));
  await screen.findByText('That company could not be found.');
  assert.equal(screen.queryByRole('heading', { name: 'Goldman Sachs' }), null);
});

test('a company with no members says so', async () => {
  fakeApi();
  app('/company/3');
  await screen.findByText('No members are listed for this company yet.');
});

test('a failed company search offers a retry', async () => {
  let fail = true;
  fakeApi({ onCompanies: () => (fail ? json({ detail: 'Server error.' }, 500) : null) });
  app('/directory');
  await screen.findByRole('alert');
  fail = false;
  await user().click(screen.getByRole('button', { name: 'Try again' }));
  await waitFor(() => assert.equal(within(screen.getByRole('list')).getAllByRole('link').length, 3));
});

test('query builders send what the backend expects', () => {
  assert.equal(companySearchUrl('  Goog '), '/api/companies/?search=Goog');
  assert.equal(companySearchUrl('   '), '/api/companies/');
  assert.equal(directoryQuery({ companyId: 5 }), '/api/accounts/users/?company_id=5&limit=20');
});
