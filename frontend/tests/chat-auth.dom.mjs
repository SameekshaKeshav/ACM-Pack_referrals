import test, { after, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';

const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173/chat' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.sessionStorage = dom.window.sessionStorage;
globalThis.HTMLElement = dom.window.HTMLElement;
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { createElement: h } = await import('react');
const { render, screen, cleanup, waitFor, within, act } = await import('@testing-library/react');
const { default: userEvent } = await import('@testing-library/user-event');
const { MemoryRouter } = await import('react-router-dom');
const vite = await createServer({ server: { middlewareMode: true, hmr: false } });
const { default: App } = await vite.ssrLoadModule('/src/App.jsx');
const { AuthProvider } = await vite.ssrLoadModule('/src/auth/AuthProvider.jsx');
const session = await vite.ssrLoadModule('/src/auth/session.js');
const { apiRequest, publicRequest } = await vite.ssrLoadModule('/src/api/client.js');
const { listMessages, listConversations } = await vite.ssrLoadModule('/src/api/chat.js');
const originalFetch = globalThis.fetch;
afterEach(() => { cleanup(); session.signOut(); dom.window.localStorage.clear(); dom.window.sessionStorage.clear(); globalThis.fetch = originalFetch; });
after(async () => { await vite.close(); dom.window.close(); });

const credentials = { access: 'old-access', refresh: 'refresh-one', user_id: 7, email: 'sanjana@ncsu.edu' };
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const gate = () => { let resolve; const promise = new Promise((done) => { resolve = done; }); return { promise, resolve }; };
const user = () => userEvent.setup({ document: dom.window.document });
const mount = (path = '/chat') => render(h(MemoryRouter, { initialEntries: [path] }, h(AuthProvider, null, h(App))));
const conversations = [
  { id: 5, other_user: { id: 41, name: 'Avery Chen', company: 'Red Hat' }, last_message: { body_text: 'Existing message' }, updated_at: '2026-10-20T12:00:00Z' },
  { id: 6, other_user: { id: 42, name: 'Sam Wilson', company: 'IBM' }, last_message: null, updated_at: '2026-10-19T12:00:00Z' },
];
const message = (id, body, minute = 0, conversation = 5) => ({ id, conversation_id: conversation, sender_id: 41, body_text: body, created_at: `2026-10-20T12:${String(minute).padStart(2, '0')}:00Z` });
function chatFetch(handler = () => null) {
  globalThis.fetch = async (path, options = {}) => {
    const special = await handler(path, options);
    if (special) return special;
    if (path === '/api/chat/conversations/') return json(conversations);
    if (path.startsWith('/api/chat/conversations/5/messages/')) return json([message(3, 'Third', 3), message(2, 'Second', 1), message(1, 'First', 1)]);
    if (path.startsWith('/api/chat/conversations/6/messages/')) return json([]);
    throw new Error(`Unexpected request ${path}`);
  };
}

test('logged-out protected routes redirect to login without fetching protected data', async () => {
  let calls = 0; globalThis.fetch = async () => { calls += 1; throw new Error('unexpected'); };
  mount('/chat/5');
  assert.ok(screen.getByRole('heading', { name: 'Welcome back' }));
  assert.equal(calls, 0);
});

test('signup and verification send exact public bodies, preserve leading zero, save tokens and return to chat', async () => {
  const calls = [];
  chatFetch((path, options) => {
    calls.push({ path, ...options });
    if (path === '/api/accounts/auth/signup/') return json({ detail: 'Verification code sent.' }, 201);
    if (path === '/api/accounts/auth/verify/') return json(credentials);
  });
  mount('/signup'); const u = user();
  await u.type(screen.getByLabelText('University email'), 'SANJANA@NCSU.EDU');
  await u.click(screen.getByRole('button', { name: 'Sign up' }));
  await u.type(await screen.findByLabelText('Six-digit code'), '012345');
  await u.click(screen.getByRole('button', { name: 'Verify and sign in' }));
  await screen.findByRole('region', { name: 'Conversation with Avery Chen' });
  const auth = calls.filter((call) => call.path.includes('/auth/'));
  assert.deepEqual(JSON.parse(auth[0].body), { email: 'sanjana@ncsu.edu' });
  assert.deepEqual(JSON.parse(auth[1].body), { email: 'sanjana@ncsu.edu', code: '012345' });
  assert.ok(auth.every((call) => !call.headers.Authorization));
  assert.equal(session.getSession().refresh, credentials.refresh);
  assert.equal(JSON.parse(dom.window.localStorage.getItem('pack-referrals.session.v1')).access, credentials.access);
  assert.equal(dom.window.sessionStorage.getItem('pack-referrals.pending-auth'), null);
});

test('login restores the original protected URL after email-code verification', async () => {
  chatFetch((path) => {
    if (path === '/api/accounts/auth/login/') return json({ detail: 'If that account exists, a verification code has been sent.' });
    if (path === '/api/accounts/auth/verify/') return json(credentials);
  });
  mount('/chat/6'); const u = user();
  await u.type(screen.getByLabelText('University email'), 'sanjana@ncsu.edu');
  await u.click(screen.getByRole('button', { name: 'Send login code' }));
  await u.type(await screen.findByLabelText('Six-digit code'), '123456');
  await u.click(screen.getByRole('button', { name: 'Verify and sign in' }));
  await screen.findByRole('region', { name: 'Conversation with Sam Wilson' });
});

test('invalid/expired code stays on verification; resend uses original signup endpoint', async () => {
  dom.window.sessionStorage.setItem('pack-referrals.pending-auth', JSON.stringify({ email: 'new@ncsu.edu', mode: 'signup', from: '/chat' }));
  const calls = [];
  globalThis.fetch = async (path) => { calls.push(path); return path.endsWith('/verify/') ? json({ detail: 'That code is invalid or has expired.' }, 400) : json({ detail: 'Verification code sent.' }, 201); };
  mount('/enter-code'); const u = user();
  await u.type(screen.getByLabelText('Six-digit code'), '123456');
  await u.click(screen.getByRole('button', { name: 'Verify and sign in' }));
  assert.match((await screen.findByRole('alert')).textContent, /invalid or has expired/);
  assert.equal(session.getSession(), null);
  await u.click(screen.getByRole('button', { name: 'Resend code' }));
  assert.match((await screen.findByRole('status')).textContent, /new one has been sent/);
  assert.deepEqual(calls, ['/api/accounts/auth/verify/', '/api/accounts/auth/signup/']);
});

test('auth throttling and email validation errors show feedback without advancing', async () => {
  globalThis.fetch = async () => json({ email: ['Email must be an @ncsu.edu address.'] }, 400);
  mount('/signup'); const u = user();
  await u.type(screen.getByLabelText('University email'), 'someone@example.com');
  await u.click(screen.getByRole('button', { name: 'Sign up' }));
  assert.match((await screen.findByRole('alert')).textContent, /@ncsu.edu/);
  globalThis.fetch = async () => json({ detail: 'Too many attempts. Try again later.' }, 429);
  await u.click(screen.getByRole('button', { name: 'Sign up' }));
  await waitFor(() => assert.match(screen.getByRole('alert').textContent, /Too many attempts/));
});

test('public auth requests never attach an old access token or attempt refresh', async () => {
  session.signIn(credentials);
  let calls = 0;
  globalThis.fetch = async (_, options) => { calls += 1; assert.equal(options.headers.Authorization, undefined); return json({ detail: 'No' }, 401); };
  await assert.rejects(publicRequest('/api/accounts/auth/verify/', { method: 'POST', body: {} }), (error) => error.status === 401);
  assert.equal(calls, 1);
  assert.ok(session.getSession());
});

test('concurrent 401s share one refresh, retry exact POST body and persist rotated tokens', async () => {
  session.signIn(credentials);
  const release = gate(); let refreshes = 0; const calls = [];
  globalThis.fetch = async (path, options) => {
    calls.push({ path, ...options });
    if (path.endsWith('/auth/refresh/')) { refreshes += 1; assert.equal(options.headers.Authorization, undefined); await release.promise; return json({ access: 'fresh-access', refresh: 'rotated-refresh' }); }
    return options.headers.Authorization === 'Bearer old-access' ? json({}, 401) : json({ success: true });
  };
  const first = apiRequest('/api/chat/messages/', { method: 'POST', body: { conversation_id: 5, body_text: 'Hello' } });
  const second = apiRequest('/api/chat/conversations/');
  await waitFor(() => assert.equal(refreshes, 1)); release.resolve();
  await Promise.all([first, second]);
  assert.equal(refreshes, 1);
  const retried = calls.find((call) => call.path.endsWith('/messages/') && call.headers.Authorization === 'Bearer fresh-access');
  assert.deepEqual(JSON.parse(retried.body), { conversation_id: 5, body_text: 'Hello' });
  assert.equal(session.getSession().refresh, 'rotated-refresh');
});

test('a delayed stale 401 reuses the already-refreshed token without a second refresh', async () => {
  session.signIn(credentials); const delayed = gate(); let refreshes = 0;
  globalThis.fetch = async (path, options) => {
    if (path.endsWith('/auth/refresh/')) { refreshes += 1; return json({ access: 'fresh' }); }
    if (path.endsWith('/slow/') && options.headers.Authorization === 'Bearer old-access') { await delayed.promise; return json({}, 401); }
    return options.headers.Authorization === 'Bearer old-access' ? json({}, 401) : json({ ok: true });
  };
  const slow = apiRequest('/api/slow/');
  await apiRequest('/api/fast/'); delayed.resolve(); await slow;
  assert.equal(refreshes, 1);
});

test('expired refresh logs out and redirects the UI; no refresh loop', async () => {
  session.signIn(credentials); let refreshes = 0;
  globalThis.fetch = async (path) => { if (path.endsWith('/auth/refresh/')) refreshes += 1; return json({ detail: 'Token is invalid or expired' }, 401); };
  mount('/chat');
  await screen.findByRole('heading', { name: 'Welcome back' });
  assert.equal(session.getSession(), null); assert.equal(refreshes, 1);
});

test('a second 401 after refresh logs out instead of refreshing indefinitely', async () => {
  session.signIn(credentials); let calls = 0;
  globalThis.fetch = async (path) => { calls += 1; return path.endsWith('/refresh/') ? json({ access: 'fresh' }) : json({}, 401); };
  await assert.rejects(apiRequest('/api/chat/conversations/'), (error) => error.status === 401);
  assert.equal(calls, 3); assert.equal(session.getSession(), null);
});

test('logout while refresh is in flight cannot restore the old session', async () => {
  session.signIn(credentials); const release = gate(); const started = gate();
  globalThis.fetch = async (path) => { if (path.endsWith('/refresh/')) { started.resolve(); await release.promise; return json({ access: 'fresh' }); } return json({}, 401); };
  const call = apiRequest('/api/chat/conversations/');
  await started.promise; session.signOut(); release.resolve();
  await assert.rejects(call); assert.equal(session.getSession(), null);
  assert.equal(dom.window.localStorage.getItem('pack-referrals.session.v1'), null);
});

test('an old account response cannot clear a newer signed-in account', async () => {
  session.signIn(credentials); const release = gate();
  globalThis.fetch = async () => { await release.promise; return json({}, 401); };
  const call = apiRequest('/api/chat/conversations/');
  session.signIn({ ...credentials, user_id: 9, access: 'other-account' }); release.resolve();
  await assert.rejects(call); assert.equal(session.getSession().user.id, 9);
});

test('a refresh network failure preserves credentials for recovery', async () => {
  session.signIn(credentials);
  globalThis.fetch = async (path) => { if (path.endsWith('/refresh/')) throw new TypeError('offline'); return json({}, 401); };
  await assert.rejects(apiRequest('/api/chat/conversations/'), /Could not reach/);
  assert.equal(session.getSession().refresh, credentials.refresh);
});

test('full history walks cursor pages, deduplicates IDs and sorts timestamp ties by ID', async () => {
  session.signIn(credentials); const calls = [];
  const rows = Array.from({ length: 100 }, (_, i) => message(i + 3, `Message ${i + 3}`, 10));
  globalThis.fetch = async (path) => { calls.push(path); return json(calls.length === 1 ? rows.reverse() : [message(2, 'Second', 1), message(1, 'First', 1), rows[0]]); };
  const result = await listMessages(5);
  assert.equal(result.length, 102);
  assert.deepEqual(result.slice(0, 3).map((row) => row.id), [1, 2, 3]);
  assert.match(calls[1], /before_id=3/);
});

test('paginated conversation lists are fully loaded; off-origin next links are rejected', async () => {
  session.signIn(credentials); let calls = 0;
  globalThis.fetch = async () => json({ results: [conversations[calls++]], next: calls === 1 ? '/api/chat/conversations/?page=2' : null });
  assert.equal((await listConversations()).length, 2);
  calls = 0;
  globalThis.fetch = async () => { calls += 1; return json({ results: [], next: 'https://untrusted.example/api/chat/conversations/' }); };
  await assert.rejects(listConversations(), /does not match/); assert.equal(calls, 1);
});

test('raw/unscoped backend shapes and messages from another conversation fail visibly', async () => {
  session.signIn(credentials);
  globalThis.fetch = async () => json([{ id: 5, participants: [7, 41] }]);
  await assert.rejects(listConversations(), /does not match/);
  globalThis.fetch = async () => json([message(1, 'Wrong conversation', 0, 6)]);
  await assert.rejects(listMessages(5), /does not match/);
});

test('accepted conversation shows ordered full history; optimistic send reconciles once', async () => {
  session.signIn(credentials); const release = gate(); let payload;
  chatFetch(async (path, options) => {
    assert.equal(options.headers.Authorization, 'Bearer old-access');
    if (path === '/api/chat/messages/') { payload = JSON.parse(options.body); await release.promise; return json({ ...message(9, 'Hello Avery', 5), sender_id: 7 }, 201); }
  });
  mount('/chat/5');
  const list = await screen.findByRole('list', { name: 'Messages', exact: true });
  assert.deepEqual(within(list).getAllByRole('listitem').map((row) => row.querySelector('.message-bubble').textContent), ['Avery Chen: First', 'Avery Chen: Second', 'Avery Chen: Third']);
  const u = user(); await u.type(screen.getByLabelText('Chat message'), 'Hello Avery');
  await u.click(screen.getByRole('button', { name: 'Send', exact: true }));
  assert.equal(within(list).getAllByRole('listitem').length, 4);
  assert.ok(screen.getByText('Sending…')); assert.equal(screen.getByLabelText('Chat message').value, '');
  assert.deepEqual(payload, { conversation_id: 5, body_text: 'Hello Avery' });
  release.resolve();
  await waitFor(() => assert.ok(!screen.queryByText('Sending…')));
  assert.equal(within(list).getAllByRole('listitem').length, 4);
});

test('failed optimistic send remains visible with explicit retry; markup renders as text', async () => {
  session.signIn(credentials); let attempts = 0;
  chatFetch((path) => { if (path === '/api/chat/messages/') { attempts += 1; return attempts === 1 ? json({ detail: 'Please try again.' }, 500) : json({ ...message(10, '<b>Hello</b>', 5), sender_id: 7 }, 201); } });
  mount('/chat/5'); await screen.findByRole('list', { name: 'Messages', exact: true }); const u = user();
  await u.type(screen.getByLabelText('Chat message'), '<b>Hello</b>');
  await u.click(screen.getByRole('button', { name: 'Send', exact: true }));
  const retry = await screen.findByRole('button', { name: 'Retry message' });
  assert.equal(document.querySelector('.message-bubble b'), null);
  await u.click(retry);
  await waitFor(() => assert.ok(!screen.queryByRole('button', { name: 'Retry message' })));
  assert.equal(screen.getAllByRole('listitem').length, 4); assert.equal(attempts, 2);
});

test('switching threads during send never appends the response into the selected other thread', async () => {
  session.signIn(credentials); const release = gate();
  chatFetch(async (path) => { if (path === '/api/chat/messages/') { await release.promise; return json({ ...message(11, 'Avery only', 5), sender_id: 7 }, 201); } });
  mount('/chat/5'); await screen.findByRole('list', { name: 'Messages', exact: true }); const u = user();
  await u.type(screen.getByLabelText('Chat message'), 'Avery only'); await u.click(screen.getByRole('button', { name: 'Send', exact: true }));
  await u.click(screen.getByRole('button', { name: /Sam Wilson/ }));
  await screen.findByText('No messages yet. Say hello!');
  await act(async () => { release.resolve(); await release.promise; });
  await waitFor(() => assert.ok(!within(screen.getByRole('region', { name: 'Conversation with Sam Wilson' })).queryByText('Avery only')));
  await u.click(screen.getByRole('button', { name: /Avery Chen/ }));
  await waitFor(() => assert.equal(screen.getAllByRole('listitem').length, 4));
});

test('history error has retry, never fabricates messages, and logout clears stored session', async () => {
  session.signIn(credentials); let fail = true;
  chatFetch((path) => { if (path.includes('/5/messages/') && fail) return json({ detail: 'Not implemented yet.' }, 404); });
  mount('/chat/5'); const u = user();
  assert.match((await screen.findByRole('alert')).textContent, /Not implemented/);
  assert.equal(screen.queryByRole('list', { name: 'Messages', exact: true }), null);
  fail = false; await u.click(screen.getByRole('button', { name: 'Retry history' }));
  await screen.findByRole('list', { name: 'Messages', exact: true });
  await u.click(screen.getByRole('button', { name: 'Log out' }));
  await screen.findByRole('heading', { name: 'Welcome back' });
  assert.equal(dom.window.localStorage.getItem('pack-referrals.session.v1'), null);
});

test('unsafe post-login destinations are rejected', () => {
  for (const value of ['https://evil.example', '//evil.example', '/\\evil.example', '/login', '/signup?next=bad', '/enter-code']) assert.equal(session.safeDestination(value), '/chat');
  assert.equal(session.safeDestination('/chat/5?focus=last'), '/chat/5?focus=last');
});

test('stored sessions hydrate on a storage notification; corrupt data becomes logged out', () => {
  const stored = { access: 'stored-access', refresh: 'stored-refresh', user: { id: 7, email: 'sanjana@ncsu.edu' } };
  dom.window.localStorage.setItem('pack-referrals.session.v1', JSON.stringify(stored));
  dom.window.dispatchEvent(new dom.window.StorageEvent('storage', { key: 'pack-referrals.session.v1' }));
  assert.deepEqual(session.getSession(), stored);
  dom.window.localStorage.setItem('pack-referrals.session.v1', '{broken');
  dom.window.dispatchEvent(new dom.window.StorageEvent('storage', { key: 'pack-referrals.session.v1' }));
  assert.equal(session.getSession(), null);
});

test('changing the signed-in account remounts private UI and discards the previous thread', async () => {
  session.signIn(credentials);
  chatFetch(); mount('/chat/5');
  await screen.findByRole('list', { name: 'Messages', exact: true });
  const release = gate();
  globalThis.fetch = async () => { await release.promise; return json([]); };
  await act(async () => { session.signIn({ ...credentials, user_id: 9, email: 'other@ncsu.edu', access: 'other-access' }); });
  assert.ok(!screen.queryByRole('list', { name: 'Messages', exact: true }));
  await act(async () => { release.resolve(); await release.promise; });
  await screen.findByText('No conversations yet. An accepted connection starts a conversation.');
});

test('leaving verification while its request is pending cannot sign in the abandoned account', async () => {
  dom.window.sessionStorage.setItem('pack-referrals.pending-auth', JSON.stringify({ email: 'new@ncsu.edu', mode: 'login' }));
  const release = gate();
  globalThis.fetch = async () => { await release.promise; return json(credentials); };
  mount('/enter-code'); const u = user();
  await u.type(screen.getByLabelText('Six-digit code'), '123456');
  await u.click(screen.getByRole('button', { name: 'Verify and sign in' }));
  await u.click(screen.getByRole('link', { name: 'Use a different email' }));
  await screen.findByRole('heading', { name: 'Welcome back' });
  await act(async () => { release.resolve(); await release.promise; });
  assert.equal(session.getSession(), null);
});
