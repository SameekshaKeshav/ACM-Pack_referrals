import test, { after, afterEach, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';

const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173/referrals' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLElement = dom.window.HTMLElement;
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { createElement: h } = await import('react');
const { render, screen, cleanup, waitFor, act } = await import('@testing-library/react');
const { default: userEvent } = await import('@testing-library/user-event');
const { MemoryRouter } = await import('react-router-dom');
const vite = await createServer({ server: { middlewareMode: true, hmr: false } });
const { default: Referrals } = await vite.ssrLoadModule('/src/pages/Referrals.jsx');
const api = await vite.ssrLoadModule('/src/api/referrals.js');
const session = await vite.ssrLoadModule('/src/auth/session.js');
const originalFetch = globalThis.fetch;
beforeEach(() => session.signIn({ access: 'access', refresh: 'refresh', user_id: 7, email: 'me@ncsu.edu' }));
afterEach(() => { cleanup(); session.signOut(); globalThis.fetch = originalFetch; });
after(async () => { await vite.close(); dom.window.close(); });
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const person = (id, name) => ({ id, name, company: 'Example' });
const referral = (id = 1, extra = {}) => ({ id, sender: person(7, 'Me'), recipient: person(12, 'Maya'), company: { id: 3, name: 'Example' }, role_title: 'Engineer', message_text: 'I fit this role.', job_url: '', resume_url: '', status: 'pending', created_at: '2026-11-01T12:00:00Z', ...extra });
const actor = () => userEvent.setup({ document: dom.window.document });
function backend({ post, list, conversations = [{ id: 9, other_user: person(12, 'Maya') }], companyFailure = false } = {}) {
  const calls = [];
  let saved = [];
  globalThis.fetch = async (path, options = {}) => {
    const url = new URL(path, dom.window.location.origin);
    calls.push({ path: url.pathname + url.search, ...options });
    if (url.pathname === '/api/chat/conversations/') return json(conversations);
    if (url.pathname === '/api/companies/') return companyFailure ? json({}, 500) : json([{ id: 3, name: 'Example' }]);
    if (options.method === 'POST') {
      if (post) return post(JSON.parse(options.body));
      saved = [referral(10, { ...JSON.parse(options.body) })];
      return json(saved[0], 201);
    }
    if (url.pathname === '/api/connections/referrals/') return list ? list(url) : json({ count: saved.length, results: url.searchParams.get('type') === 'outgoing' ? saved : [], next: null, previous: null });
    throw new Error(`Unexpected ${path}`);
  };
  return calls;
}
function mount(path = '/referrals') { return render(h(MemoryRouter, { initialEntries: [path] }, h(Referrals))); }
async function fill(who = actor()) {
  await screen.findByRole('option', { name: 'Maya' });
  await who.selectOptions(screen.getByLabelText('Accepted connection (required)'), '12');
  await who.type(screen.getByLabelText('Role title (required)'), 'Engineer');
  await who.type(screen.getByLabelText('Why you fit (required)'), 'I fit this role.');
  return who;
}

test('sends exact referral body with Bearer, disables in flight, then shows outgoing card', async () => {
  let release;
  let stored = [];
  const pending = new Promise((resolve) => { release = resolve; });
  const calls = backend({ post: () => pending, list: () => json({ count: stored.length, results: stored }) });
  mount('/referrals?recipient=12');
  const who = await fill();
  await who.selectOptions(screen.getByLabelText('Company (optional)'), '3');
  await who.type(screen.getByLabelText('Job link (optional)'), 'https://example.com/job');
  await who.click(screen.getByRole('button', { name: 'Send referral request' }));
  assert.ok(screen.getByRole('button', { name: 'Sending referral request…' }).disabled);
  const posts = calls.filter((call) => call.method === 'POST');
  assert.equal(posts.length, 1);
  assert.equal(posts[0].path, '/api/connections/referrals/');
  assert.equal(posts[0].headers.Authorization, 'Bearer access');
  assert.deepEqual(JSON.parse(posts[0].body), { recipient_id: 12, role_title: 'Engineer', message_text: 'I fit this role.', company_id: 3, job_url: 'https://example.com/job' });
  stored = [referral()];
  await act(async () => release(json(stored[0], 201)));
  await screen.findByText(/Referral request sent/);
  assert.equal(screen.getByLabelText('Why you fit (required)').value, '');
  await screen.findByRole('article', { name: 'Referral to Maya' });
});

test('409 keeps draft and prevents retry of the unchanged duplicate ask', async () => {
  const calls = backend({ post: () => json({ detail: 'Duplicate' }, 409) });
  mount(); const who = await fill();
  await who.click(screen.getByRole('button', { name: 'Send referral request' }));
  await screen.findByRole('alert');
  assert.match(screen.getByRole('alert').textContent, /already have a pending/);
  assert.equal(screen.getByLabelText('Why you fit (required)').value, 'I fit this role.');
  assert.ok(screen.getByRole('button', { name: 'Send referral request' }).disabled);
  assert.equal(calls.filter((call) => call.method === 'POST').length, 1);
  await who.type(screen.getByLabelText('Role title (required)'), ' II');
  assert.ok(!screen.getByRole('button', { name: 'Send referral request' }).disabled);
});

test('server field errors and network failures preserve note and allow deliberate resubmission', async () => {
  let attempt = 0;
  backend({ post: () => { attempt++; if (attempt === 1) return json({ company_id: ['This company is not on the recipient’s profile.'] }, 400); if (attempt === 2) throw new Error('offline'); return json(referral(), 201); } });
  mount(); const who = await fill();
  await who.click(screen.getByRole('button', { name: 'Send referral request' }));
  assert.match((await screen.findByRole('alert')).textContent, /company id/);
  await who.click(screen.getByRole('button', { name: 'Send referral request' }));
  await waitFor(() => assert.match(screen.getByRole('alert').textContent, /Could not reach/));
  assert.equal(screen.getByLabelText('Why you fit (required)').value, 'I fit this role.');
  await who.click(screen.getByRole('button', { name: 'Send referral request' }));
  await screen.findByText(/Referral request sent/);
});

test('counts Unicode code points and blocks the 501st pasted character', async () => {
  backend(); mount(); const who = await fill();
  const note = screen.getByLabelText('Why you fit (required)');
  await who.clear(note); await who.click(note); await who.paste('😀'.repeat(501));
  assert.equal(Array.from(note.value).length, 500);
  assert.ok(screen.getByText('0 characters remaining'));
});

test('no accepted connections disables creation and query parameters cannot add a recipient', async () => {
  const calls = backend({ conversations: [] }); mount('/referrals?recipient=99');
  await screen.findByText(/No accepted connections yet/);
  assert.ok(screen.getByRole('button', { name: 'Send referral request' }).disabled);
  assert.ok(!screen.queryByRole('option', { name: '99' }));
  assert.equal(calls.filter((call) => call.method === 'POST').length, 0);
});

test('paginates with offset, changes direction and renders links and text safely', async () => {
  const calls = backend({ list: (url) => json({ count: 21, next: 'https://evil.example/steal', previous: null,
    results: [referral(url.searchParams.get('offset') === '20' ? 2 : 1, { message_text: '<script>alert(1)</script>', job_url: 'javascript:alert(1)', resume_url: 'https://example.com/resume' })] }) });
  mount(); const who = actor();
  await screen.findByRole('article', { name: 'Referral to Maya' });
  assert.ok(!screen.queryByRole('link', { name: 'View job' }));
  assert.equal(screen.getByRole('link', { name: 'View résumé' }).getAttribute('rel'), 'noopener noreferrer');
  assert.ok(screen.getByText('<script>alert(1)</script>'));
  await who.click(screen.getByRole('button', { name: 'Next' }));
  await waitFor(() => assert.ok(calls.some((call) => call.path.endsWith('offset=20'))));
  await screen.findByText('21–21 of 21');
  await who.click(screen.getByRole('button', { name: 'Incoming', exact: true }));
  await screen.findByRole('article', { name: 'Referral from Me' });
  assert.ok(calls.some((call) => call.path.includes('type=incoming&limit=20&offset=0')));
  assert.ok(calls.every((call) => call.path.startsWith('/api/')));
});

test('optional company failure does not prevent an otherwise valid ask', async () => {
  backend({ companyFailure: true }); mount(); const who = await fill();
  await screen.findByText(/Company choices could not load/);
  await who.click(screen.getByRole('button', { name: 'Send referral request' }));
  await screen.findByText(/Referral request sent/);
});

test('list failure offers reload without discarding the form draft', async () => {
  let fail = true;
  backend({ list: () => fail ? json({}, 500) : json({ count: 0, results: [] }) });
  mount(); await fill();
  await screen.findByRole('alert');
  fail = false;
  await actor().click(screen.getByRole('button', { name: 'Retry loading asks' }));
  await screen.findByText('No outgoing referral requests yet.');
  assert.equal(screen.getByLabelText('Why you fit (required)').value, 'I fit this role.');
});

test('malformed responses and unsafe external links are rejected', async () => {
  assert.equal(api.safeReferralUrl('data:text/html,secret'), null);
  assert.equal(api.safeReferralUrl('https://user:pass@example.com'), null);
  assert.throws(() => api.normalizeReferral({ ...referral(), recipient: null }));
  globalThis.fetch = async () => json({ count: '1', results: [] });
  await assert.rejects(api.listReferrals('outgoing'), /referral response/);
});
