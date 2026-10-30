import test, { after, afterEach, beforeEach } from 'node:test';
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
const { default: PeopleDirectory } = await vite.ssrLoadModule('/src/components/directory/PeopleDirectory.jsx');
const session = await vite.ssrLoadModule('/src/auth/session.js');
const originalFetch = globalThis.fetch;

beforeEach(() => session.signIn({ access: 'access-1', refresh: 'refresh-1', user_id: 7, email: 'me@ncsu.edu' }));
afterEach(() => { cleanup(); session.signOut(); dom.window.localStorage.clear(); globalThis.fetch = originalFetch; });
after(async () => { await vite.close(); dom.window.close(); });

const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const user = () => userEvent.setup({ document: dom.window.document });
const sender = (id, name, company = 'Red Hat') => ({ id, name, company });
const incomingRow = (id, from, text = 'Hi, can we connect?') => ({ id, sender: from, message_text: text, status: 'pending', created_at: '2026-10-20T12:00:00Z' });
const outgoingRow = (id, to, status = 'pending') => ({ id, recipient: to, message_text: 'Hello!', status, created_at: '2026-10-21T12:00:00Z' });
const person = (id, name, extra = {}) => ({
  user_id: id, name, major: 'Computer Science', grad_year: 2026, current_role: '', current_company: null, open_to_connect: true, ...extra,
});

// One in-memory backend for everything these tests touch. `world` is mutated by accept/decline/send.
function backend(world, { onPatch, onPost } = {}) {
  const calls = [];
  globalThis.fetch = async (path, options = {}) => {
    const url = new URL(path, 'http://localhost:5173');
    const method = options.method || 'GET';
    calls.push({ method, path: url.pathname + url.search, body: options.body ? JSON.parse(options.body) : null });
    if (url.pathname === '/api/connections/' && method === 'GET') {
      return json(url.searchParams.get('type') === 'incoming' ? world.incoming : world.outgoing);
    }
    if (url.pathname === '/api/connections/' && method === 'POST') {
      const special = await onPost?.(JSON.parse(options.body), world);
      if (special) return special;
      world.outgoing.push(outgoingRow(100, { id: JSON.parse(options.body).recipient_id, name: 'x', company: '' }));
      return json({ id: 100, status: 'pending' }, 201);
    }
    const patch = url.pathname.match(/^\/api\/connections\/(\d+)\/(accept|decline)\/$/);
    if (patch && method === 'PATCH') {
      const special = await onPatch?.(Number(patch[1]), patch[2], world);
      if (special) return special;
      world.incoming = world.incoming.filter((row) => row.id !== Number(patch[1]));
      return json({ id: Number(patch[1]), status: patch[2] === 'accept' ? 'accepted' : 'declined', conversation_id: patch[2] === 'accept' ? 55 : null });
    }
    if (url.pathname === '/api/chat/conversations/') return json(world.conversations || []);
    if (/^\/api\/chat\/conversations\/\d+\/messages\//.test(url.pathname)) return json([]);
    if (url.pathname === '/api/accounts/users/') return json({ count: world.people.length, next: null, previous: null, results: world.people });
    throw new Error(`unexpected request ${method} ${path}`);
  };
  return calls;
}

const mountApp = (path = '/chat') => render(h(MemoryRouter, { initialEntries: [path] }, h(AuthProvider, null, h(App))));
const mountDirectory = () => render(h(MemoryRouter, null, h(PeopleDirectory)));
const messagesLink = () => screen.getByRole('link', { name: /^Messages/ });
const patches = (calls) => calls.filter((call) => call.method === 'PATCH');
const posts = (calls) => calls.filter((call) => call.method === 'POST');

// ---------- request inbox ----------

test('incoming requests list who wants to connect, with a count on the tab and a badge in the nav', async () => {
  backend({ incoming: [incomingRow(1, sender(31, 'Maya Patel')), incomingRow(2, sender(32, 'Alex Rivera', 'IBM'))], outgoing: [] });
  mountApp();

  await screen.findByRole('article', { name: 'Request from Maya Patel' });
  assert.ok(screen.getByRole('article', { name: 'Request from Alex Rivera' }));
  assert.equal(screen.getByRole('tab', { name: /Incoming/ }).textContent, 'Incoming 2');
  await waitFor(() => assert.match(messagesLink().textContent, /2\s*pending connection requests/));
});

test('Accept sends PATCH, removes the card, updates the badge and opens the new conversation', async () => {
  const calls = backend({ incoming: [incomingRow(1, sender(31, 'Maya Patel'))], outgoing: [], conversations: [{ id: 55, other_user: sender(31, 'Maya Patel'), last_message: null, updated_at: '2026-10-22T12:00:00Z' }] });
  const actor = user();
  mountApp();
  await waitFor(() => assert.match(messagesLink().textContent, /1\s*pending connection request/));

  await actor.click(await screen.findByRole('button', { name: 'Accept Maya Patel' }));

  await waitFor(() => assert.equal(screen.queryByRole('article', { name: 'Request from Maya Patel' }), null));
  assert.deepEqual(patches(calls).map((call) => call.path), ['/api/connections/1/accept/']);
  await screen.findByRole('region', { name: 'Conversation with Maya Patel' });
  assert.ok(calls.some((call) => call.path.startsWith('/api/chat/conversations/55/messages/')));
  await waitFor(() => assert.doesNotMatch(messagesLink().textContent, /pending/));
  assert.ok(screen.getByText('You are now connected with Maya Patel.'));
});

test('Decline sends PATCH, removes the card and does not open a conversation', async () => {
  const calls = backend({ incoming: [incomingRow(1, sender(31, 'Maya Patel'))], outgoing: [] });
  const actor = user();
  mountApp();

  await actor.click(await screen.findByRole('button', { name: 'Decline Maya Patel' }));

  await waitFor(() => assert.ok(screen.getByText('You’re all caught up. No incoming requests.')));
  assert.deepEqual(patches(calls).map((call) => call.path), ['/api/connections/1/decline/']);
  assert.equal(screen.queryByRole('region', { name: /Conversation with/ }), null);
  assert.ok(screen.getByText('Request declined.'));
});

test('a double click on Accept sends one PATCH', async () => {
  let release;
  const calls = backend({ incoming: [incomingRow(1, sender(31, 'Maya Patel'))], outgoing: [] },
    { onPatch: () => new Promise((resolve) => { release = () => resolve(json({ id: 1, status: 'accepted', conversation_id: 55 })); }) });
  const actor = user();
  mountApp();
  const accept = await screen.findByRole('button', { name: 'Accept Maya Patel' });

  await actor.dblClick(accept);
  await waitFor(() => assert.equal(patches(calls).length, 1));
  assert.equal(screen.getByRole('button', { name: 'Decline Maya Patel' }).disabled, true);
  await act(async () => { release(); });
  await waitFor(() => assert.equal(screen.queryByRole('article', { name: 'Request from Maya Patel' }), null));
  assert.equal(patches(calls).length, 1);
});

test('a request someone already answered shows the reason and the list refreshes', async () => {
  const calls = backend({ incoming: [incomingRow(1, sender(31, 'Maya Patel'))], outgoing: [] },
    { onPatch: (id, action, world) => { world.incoming = []; return json({ detail: 'Already answered.' }, 409); } });
  const actor = user();
  mountApp();

  await actor.click(await screen.findByRole('button', { name: 'Accept Maya Patel' }));

  await waitFor(() => assert.ok(screen.getByText('You’re all caught up. No incoming requests.')));
  assert.ok(calls.filter((call) => call.path === '/api/connections/?type=incoming').length >= 2);
});

test('a failed Accept keeps the card, explains, and can be retried', async () => {
  let fail = true;
  const calls = backend({ incoming: [incomingRow(1, sender(31, 'Maya Patel'))], outgoing: [] },
    { onPatch: () => (fail ? json({ detail: 'Server error' }, 500) : null) });
  const actor = user();
  mountApp();

  await actor.click(await screen.findByRole('button', { name: 'Accept Maya Patel' }));
  const card = screen.getByRole('article', { name: 'Request from Maya Patel' });
  await waitFor(() => assert.ok(within(card).getByRole('alert')));
  assert.equal(within(card).getByRole('button', { name: 'Accept Maya Patel' }).disabled, false);

  fail = false;
  await actor.click(within(card).getByRole('button', { name: 'Accept Maya Patel' }));
  await waitFor(() => assert.equal(screen.queryByRole('article', { name: 'Request from Maya Patel' }), null));
  assert.equal(patches(calls).length, 2);
});

test('the Outgoing tab shows requests I sent without Accept or Decline, and works with arrow keys', async () => {
  backend({ incoming: [], outgoing: [outgoingRow(5, sender(41, 'Pat Lee', 'Google')), outgoingRow(6, sender(42, 'Sam Ode', 'IBM'), 'accepted')] });
  const actor = user();
  mountApp();
  await screen.findByText('You’re all caught up. No incoming requests.');

  screen.getByRole('tab', { name: /Incoming/ }).focus();
  await actor.keyboard('{ArrowRight}');

  assert.equal(screen.getByRole('tab', { name: /Outgoing/ }).getAttribute('aria-selected'), 'true');
  assert.equal(document.activeElement, screen.getByRole('tab', { name: /Outgoing/ }));
  assert.ok(screen.getByRole('article', { name: 'Request to Pat Lee' }));
  assert.ok(screen.getByRole('article', { name: 'Request to Sam Ode' }));
  assert.equal(screen.queryAllByRole('button', { name: /^(Accept|Decline)/ }).length, 0);
});

test('a failed load shows an alert and Retry requests recovers', async () => {
  let fail = true;
  const world = { incoming: [incomingRow(1, sender(31, 'Maya Patel'))], outgoing: [] };
  const calls = backend(world);
  const inner = globalThis.fetch;
  globalThis.fetch = async (path, options) => (fail && String(path).startsWith('/api/connections/') ? json({ detail: 'down' }, 500) : inner(path, options));
  const actor = user();
  mountApp();

  const alert = await screen.findByRole('alert');
  assert.ok(within(alert).getByRole('button', { name: 'Retry requests' }));
  fail = false;
  await actor.click(within(alert).getByRole('button', { name: 'Retry requests' }));
  await screen.findByRole('article', { name: 'Request from Maya Patel' });
  assert.ok(calls.length > 0);
});

// ---------- Connect on member cards ----------

test('Connect opens a dialog with focus in the note, sends the request, then shows Request sent', async () => {
  const world = { incoming: [], outgoing: [], people: [person(1, 'Alice Adams')] };
  const calls = backend(world);
  const actor = user();
  mountDirectory();

  const connect = await screen.findByRole('button', { name: 'Connect with Alice Adams' });
  await actor.click(connect);
  const dialog = screen.getByRole('dialog', { name: 'Connect with Alice Adams' });
  assert.equal(document.activeElement, within(dialog).getByLabelText('Your note'));

  await actor.type(within(dialog).getByLabelText('Your note'), 'Hello Alice');
  assert.ok(within(dialog).getByText('489 remaining'));
  await actor.click(within(dialog).getByRole('button', { name: 'Send request' }));

  await waitFor(() => assert.equal(screen.queryByRole('dialog'), null));
  assert.deepEqual(posts(calls).map((call) => call.body), [{ recipient_id: 1, message_text: 'Hello Alice' }]);
  const sent = screen.getByRole('button', { name: 'Connection request sent to Alice Adams' });
  assert.equal(sent.disabled, true);
  assert.equal(screen.queryByRole('button', { name: 'Connect with Alice Adams' }), null);
  assert.ok(screen.getByText('Request sent to Alice Adams.'));
});

test('an empty note is not sent, and Escape closes the dialog and returns focus to Connect', async () => {
  const calls = backend({ incoming: [], outgoing: [], people: [person(1, 'Alice Adams')] });
  const actor = user();
  mountDirectory();
  const connect = await screen.findByRole('button', { name: 'Connect with Alice Adams' });
  await actor.click(connect);

  await actor.click(screen.getByRole('button', { name: 'Send request' }));
  assert.ok(screen.getByRole('alert').textContent.includes('Add a short note'));
  assert.equal(posts(calls).length, 0);

  await actor.keyboard('{Escape}');
  assert.equal(screen.queryByRole('dialog'), null);
  assert.equal(document.activeElement, connect);
  assert.equal(posts(calls).length, 0);
});

test('Tab stays inside the dialog', async () => {
  backend({ incoming: [], outgoing: [], people: [person(1, 'Alice Adams')] });
  const actor = user();
  mountDirectory();
  await actor.click(await screen.findByRole('button', { name: 'Connect with Alice Adams' }));
  const dialog = screen.getByRole('dialog');

  await actor.tab(); await actor.tab(); await actor.tab();
  assert.ok(dialog.contains(document.activeElement));
  await actor.tab({ shift: true });
  assert.ok(dialog.contains(document.activeElement));
});

test('the daily limit (429) is explained and the note is kept', async () => {
  backend({ incoming: [], outgoing: [], people: [person(1, 'Alice Adams')] }, { onPost: () => json({ detail: 'Throttled' }, 429) });
  const actor = user();
  mountDirectory();
  await actor.click(await screen.findByRole('button', { name: 'Connect with Alice Adams' }));
  await actor.type(screen.getByLabelText('Your note'), 'Hello');
  await actor.click(screen.getByRole('button', { name: 'Send request' }));

  await waitFor(() => assert.ok(screen.getByRole('alert').textContent.includes('limit')));
  assert.equal(screen.getByLabelText('Your note').value, 'Hello');
  assert.ok(screen.getByRole('dialog'));
});

test('a duplicate (409) explains itself and refreshes what the card shows', async () => {
  const world = { incoming: [], outgoing: [], people: [person(1, 'Alice Adams')] };
  backend(world, { onPost: (body, state) => { state.outgoing.push(outgoingRow(9, sender(1, 'Alice Adams'))); return json({ detail: 'exists' }, 409); } });
  const actor = user();
  mountDirectory();
  await actor.click(await screen.findByRole('button', { name: 'Connect with Alice Adams' }));
  await actor.type(screen.getByLabelText('Your note'), 'Hello');
  await actor.click(screen.getByRole('button', { name: 'Send request' }));

  await waitFor(() => assert.ok(screen.getByRole('alert').textContent.includes('already have')));
  await actor.click(screen.getByRole('button', { name: 'Cancel' }));
  await screen.findByRole('button', { name: 'Connection request sent to Alice Adams' });
});

test('a lookup that finishes after a send does not bring the Connect button back', async () => {
  const world = { incoming: [], outgoing: [], people: [person(1, 'Alice Adams')] };
  backend(world);
  const inner = globalThis.fetch;
  let release;
  // The first outgoing lookup is held open and will answer with the old, empty list.
  globalThis.fetch = (path, options) => {
    if (!release && String(path).startsWith('/api/connections/?type=outgoing')) {
      return new Promise((resolve) => { release = () => resolve(json([])); });
    }
    return inner(path, options);
  };
  const actor = user();
  mountDirectory();

  await actor.click(await screen.findByRole('button', { name: 'Connect with Alice Adams' }));
  await actor.type(screen.getByLabelText('Your note'), 'Hello Alice');
  await actor.click(screen.getByRole('button', { name: 'Send request' }));
  await screen.findByRole('button', { name: 'Connection request sent to Alice Adams' });
  assert.ok(release, 'the initial lookup should still be waiting');

  await act(async () => { release(); await new Promise((resolve) => setTimeout(resolve, 20)); });

  assert.ok(screen.getByRole('button', { name: 'Connection request sent to Alice Adams' }));
  assert.equal(screen.queryByRole('button', { name: 'Connect with Alice Adams' }), null);
});

for (const [verb, noun] of [['Accept', 'accepted'], ['Decline', 'declined']]) {
  test(`an older refresh that arrives after a request is ${noun} does not bring the card back`, async () => {
    const stale = [incomingRow(1, sender(31, 'Maya Patel')), incomingRow(2, sender(32, 'Alex Rivera', 'IBM'))];
    backend({ incoming: [...stale], outgoing: [] });
    const inner = globalThis.fetch;
    let hold = false;
    let release;
    // After the page has loaded, the next incoming list (the Refresh) is held and will answer with `stale`.
    globalThis.fetch = (path, options) => {
      if (hold && String(path).startsWith('/api/connections/?type=incoming')) {
        hold = false;
        return new Promise((resolve) => { release = () => resolve(json(stale)); });
      }
      return inner(path, options);
    };
    const actor = user();
    mountApp();
    await screen.findByRole('article', { name: 'Request from Maya Patel' });

    hold = true;
    await actor.click(screen.getByRole('button', { name: 'Refresh requests' }));
    await waitFor(() => assert.ok(release, 'the refresh should be waiting'));
    await actor.click(screen.getByRole('button', { name: `${verb} Maya Patel` }));
    await waitFor(() => assert.equal(screen.queryByRole('article', { name: 'Request from Maya Patel' }), null));

    await act(async () => { release(); await new Promise((resolve) => setTimeout(resolve, 20)); });

    assert.equal(screen.queryByRole('article', { name: 'Request from Maya Patel' }), null);
    assert.ok(screen.getByRole('article', { name: 'Request from Alex Rivera' }));
  });
}

test('cards reflect connection state: connected, received, not open, and me', async () => {
  backend({
    incoming: [incomingRow(3, sender(3, 'Carol Chen'))],
    outgoing: [outgoingRow(2, sender(2, 'Bob Brown'), 'accepted')],
    conversations: [{ id: 21, other_user: sender(2, 'Bob Brown'), last_message: null, updated_at: '2026-10-22T12:00:00Z' }],
    people: [person(2, 'Bob Brown'), person(3, 'Carol Chen'), person(4, 'Dan Diaz', { open_to_connect: false }), person(7, 'Me Myself')],
  });
  mountDirectory();
  await screen.findByRole('link', { name: 'Message Bob Brown' });

  assert.equal(screen.getByRole('link', { name: 'Message Bob Brown' }).getAttribute('href'), '/chat/21');
  await waitFor(() => assert.equal(screen.getByRole('link', { name: 'Respond to the request from Carol Chen' }).getAttribute('href'), '/chat'));
  assert.equal(screen.queryByRole('button', { name: 'Connect with Dan Diaz' }), null);
  assert.ok(screen.getByText('Not taking requests right now'));
  assert.equal(screen.queryByRole('button', { name: 'Connect with Me Myself' }), null);
  assert.ok(screen.getByText('You'));
});

test('if the connection lookups fail, cards still offer a plain Connect button', async () => {
  const world = { incoming: [], outgoing: [], people: [person(1, 'Alice Adams')] };
  backend(world);
  const inner = globalThis.fetch;
  globalThis.fetch = async (path, options) => (String(path).startsWith('/api/connections/') || String(path).startsWith('/api/chat/') ? json({ detail: 'down' }, 500) : inner(path, options));
  mountDirectory();

  assert.ok(await screen.findByRole('button', { name: 'Connect with Alice Adams' }));
});
