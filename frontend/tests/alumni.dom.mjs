import test, { after, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';

const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173/signup' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.sessionStorage = dom.window.sessionStorage;
globalThis.HTMLElement = dom.window.HTMLElement;
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { createElement: h } = await import('react');
const { render, screen, cleanup, waitFor, act, fireEvent } = await import('@testing-library/react');
const { default: userEvent } = await import('@testing-library/user-event');
const { MemoryRouter } = await import('react-router-dom');
const vite = await createServer({ server: { middlewareMode: true, hmr: false } });
const { default: App } = await vite.ssrLoadModule('/src/App.jsx');
const { AuthProvider } = await vite.ssrLoadModule('/src/auth/AuthProvider.jsx');
const session = await vite.ssrLoadModule('/src/auth/session.js');
const { validate } = await vite.ssrLoadModule('/src/pages/AlumniRequest.jsx');
const originalFetch = globalThis.fetch;
afterEach(() => { cleanup(); session.signOut(); dom.window.localStorage.clear(); dom.window.sessionStorage.clear(); globalThis.fetch = originalFetch; });
after(async () => { await vite.close(); dom.window.close(); });

const URL = '/api/accounts/alumni-access-requests/';
const THANKS = 'Thanks - your request is with the team. If it is approved you will be able to sign in with this email address.';
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const gate = () => { let resolve; const promise = new Promise((done) => { resolve = done; }); return { promise, resolve }; };
const user = () => userEvent.setup({ document: dom.window.document });
const mount = (path = '/alumni-access') => render(h(MemoryRouter, { initialEntries: [path] }, h(AuthProvider, null, h(App))));
const field = (name) => screen.getByLabelText(new RegExp(`^${name}`));

function recordFetch(handler) {
  const calls = [];
  globalThis.fetch = async (path, options = {}) => {
    calls.push({ path, ...options, body: options.body ? JSON.parse(options.body) : undefined });
    return handler(path, options, calls);
  };
  return calls;
}

async function fillValid(actor, overrides = {}) {
  const values = {
    'Email address': '  Jo.Alum@Gmail.com ', 'Full name': ' Jo Alum ', 'Unity ID': 'JAlum2',
    'Graduation year': '2019', Major: 'Computer Science', ...overrides,
  };
  for (const [label, value] of Object.entries(values)) await actor.type(field(label), value);
}

test('the signup page links to the form, and so does a rejected non-NC State address', async () => {
  const actor = user();
  recordFetch((path) => {
    if (path === '/api/accounts/auth/signup/') return json({ email: ['Email must be an @ncsu.edu address.'] }, 400);
    throw new Error(`Unexpected request ${path}`);
  });
  mount('/signup');
  assert.equal(screen.getAllByRole('link', { name: 'Request alumni access' }).length, 1);
  await actor.type(screen.getByLabelText('University email'), 'jo@gmail.com');
  await actor.click(screen.getByRole('button', { name: 'Sign up' }));
  const alert = await screen.findByRole('alert');
  assert.match(alert.textContent, /@ncsu\.edu address/);
  assert.equal(screen.getAllByRole('link', { name: 'Request alumni access' }).length, 2);
  await actor.click(screen.getAllByRole('link', { name: 'Request alumni access' })[1]);
  assert.ok(screen.getByRole('heading', { name: 'Request alumni access' }));
});

test('the login page does not advertise the form, and the form needs no sign-in', async () => {
  recordFetch(() => { throw new Error('no request expected'); });
  mount('/login');
  assert.equal(screen.queryByRole('link', { name: 'Request alumni access' }), null);
  cleanup();
  mount('/alumni-access');
  assert.ok(screen.getByRole('heading', { name: 'Request alumni access' }));
});

test('an empty form shows an error next to each required field, sends nothing and focuses the first', async () => {
  const actor = user();
  const calls = recordFetch(() => { throw new Error('no request expected'); });
  mount();
  await actor.click(screen.getByRole('button', { name: 'Send request' }));
  assert.equal(calls.length, 0);
  for (const [label, message] of [
    ['Email address', 'Enter your email address.'], ['Full name', 'Enter your full name.'],
    ['Unity ID', 'Enter your Unity ID.'], ['Graduation year', 'Enter your graduation year.'], ['Major', 'Enter your major.'],
  ]) {
    const input = field(label);
    assert.equal(input.getAttribute('aria-invalid'), 'true', label);
    const described = input.getAttribute('aria-describedby').split(' ').map((id) => document.getElementById(id)?.textContent);
    assert.ok(described.includes(message), `${label} is described by "${message}"`);
  }
  assert.equal(field('LinkedIn profile').getAttribute('aria-invalid'), null);
  assert.equal(document.activeElement.id, 'email');
});

test('validate() applies the backend rules to each field', () => {
  const ok = { email: 'a@b.co', full_name: 'A', unity_id: 'jdoe2', grad_year: '2019', major: 'CS', linkedin_url: '', note: '' };
  assert.deepEqual(validate(ok), {});
  assert.ok(validate({ ...ok, email: 'not-an-email' }).email);
  assert.ok(validate({ ...ok, unity_id: '2jdoe' }).unity_id, 'starts with a letter');
  assert.ok(validate({ ...ok, unity_id: 'j doe' }).unity_id);
  assert.ok(validate({ ...ok, unity_id: 'a'.repeat(33) }).unity_id);
  assert.ok(validate({ ...ok, grad_year: '19' }).grad_year);
  assert.ok(validate({ ...ok, grad_year: '1899' }).grad_year);
  assert.ok(validate({ ...ok, grad_year: '2101' }).grad_year);
  assert.equal(validate({ ...ok, grad_year: '2100' }).grad_year, undefined);
  assert.ok(validate({ ...ok, linkedin_url: 'javascript:alert(1)' }).linkedin_url);
  assert.ok(validate({ ...ok, linkedin_url: 'linkedin.com/in/jo' }).linkedin_url);
  assert.equal(validate({ ...ok, linkedin_url: 'https://www.linkedin.com/in/jo' }).linkedin_url, undefined);
  assert.ok(validate({ ...ok, full_name: 'x'.repeat(151) }).full_name);
  assert.ok(validate({ ...ok, note: 'x'.repeat(501) }).note);
  assert.ok(validate({ ...ok, full_name: '   ' }).full_name, 'spaces only is empty');
});

test('a valid request sends the exact public body with no Authorization, then confirms and clears the form', async () => {
  const actor = user();
  const calls = recordFetch(() => json({ detail: THANKS }, 202));
  mount();
  await fillValid(actor);
  await actor.click(screen.getByRole('button', { name: 'Send request' }));
  const heading = await screen.findByRole('heading', { name: 'Request received' });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, URL);
  assert.equal(calls[0].method, 'POST');
  assert.equal(calls[0].headers.Authorization, undefined);
  assert.deepEqual(calls[0].body, {
    email: 'jo.alum@gmail.com', full_name: 'Jo Alum', unity_id: 'JAlum2', grad_year: 2019,
    major: 'Computer Science', confirm_email: '',
  });
  assert.ok(document.activeElement === heading, 'focus moves to the confirmation heading');
  assert.equal(screen.getByRole('status').textContent, THANKS);
  assert.equal(screen.queryByLabelText(/^Email address/), null, 'the form is gone');
  assert.match(document.body.textContent, /do not send an email about the decision/);
  assert.ok(screen.getByRole('link', { name: 'sign up' }));
});

test('optional LinkedIn and note are sent when filled in', async () => {
  const actor = user();
  const calls = recordFetch(() => json({ detail: THANKS }, 202));
  mount();
  await fillValid(actor, { 'LinkedIn profile': 'https://www.linkedin.com/in/jo', 'Anything else': 'Class of 2019.' });
  await actor.click(screen.getByRole('button', { name: 'Send request' }));
  await screen.findByRole('heading', { name: 'Request received' });
  assert.equal(calls[0].body.linkedin_url, 'https://www.linkedin.com/in/jo');
  assert.equal(calls[0].body.note, 'Class of 2019.');
});

test('the spam trap is hidden from people, out of the tab order, and sent as typed when a bot fills it', async () => {
  const actor = user();
  const calls = recordFetch(() => json({ detail: THANKS }, 202));
  mount();
  const trap = document.getElementById('confirm_email');
  assert.equal(trap.getAttribute('name'), 'confirm_email');
  assert.equal(trap.getAttribute('tabindex'), '-1');
  assert.equal(trap.getAttribute('autocomplete'), 'off');
  assert.equal(trap.value, '');
  assert.equal(trap.closest('[aria-hidden="true"]')?.className, 'honeypot');
  await fillValid(actor);
  fireEvent.change(trap, { target: { value: 'bot@spam.example' } });
  await actor.click(screen.getByRole('button', { name: 'Send request' }));
  await screen.findByRole('heading', { name: 'Request received' });
  assert.equal(calls[0].body.confirm_email, 'bot@spam.example');
});

test('the answer is the same whatever the server did, so a duplicate shows no "already applied" message', async () => {
  const actor = user();
  recordFetch(() => json({ detail: THANKS }, 202));
  mount();
  await fillValid(actor);
  await actor.click(screen.getByRole('button', { name: 'Send request' }));
  await screen.findByRole('heading', { name: 'Request received' });
  assert.doesNotMatch(document.body.textContent, /already/i);
});

test('server field errors appear next to their inputs and the draft is kept', async () => {
  const actor = user();
  recordFetch(() => json({ unity_id: ['A Unity ID is letters and digits, starting with a letter.'], grad_year: ['Enter a four-digit graduation year.'] }, 400));
  mount();
  await fillValid(actor);
  await actor.click(screen.getByRole('button', { name: 'Send request' }));
  await waitFor(() => assert.equal(field('Unity ID').getAttribute('aria-invalid'), 'true'));
  assert.match(document.getElementById('unity_id-error').textContent, /letters and digits/);
  assert.match(document.getElementById('grad_year-error').textContent, /four-digit/);
  assert.equal(field('Unity ID').value, 'JAlum2');
  assert.equal(field('Email address').value, 'Jo.Alum@Gmail.com'); // email inputs drop surrounding spaces
  assert.equal(document.activeElement.id, 'unity_id');
});

test('a rate limit keeps the draft, says so, and the same form can be sent again', async () => {
  const actor = user();
  let attempt = 0;
  const calls = recordFetch(() => (++attempt === 1 ? json({ detail: 'Request was throttled.' }, 429) : json({ detail: THANKS }, 202)));
  mount();
  await fillValid(actor);
  await actor.click(screen.getByRole('button', { name: 'Send request' }));
  assert.match((await screen.findByRole('alert')).textContent, /throttled|Too many/);
  assert.equal(field('Full name').value, ' Jo Alum ');
  await actor.click(screen.getByRole('button', { name: 'Send request' }));
  await screen.findByRole('heading', { name: 'Request received' });
  assert.equal(calls.length, 2);
});

test('a network failure shows a message and keeps the draft', async () => {
  const actor = user();
  recordFetch(() => { throw new TypeError('Failed to fetch'); });
  mount();
  await fillValid(actor);
  await actor.click(screen.getByRole('button', { name: 'Send request' }));
  assert.match((await screen.findByRole('alert')).textContent, /Could not reach the server/);
  assert.equal(field('Major').value, 'Computer Science');
});

test('double clicks send once while a request is pending, and the button says so', async () => {
  const actor = user();
  const held = gate();
  const calls = recordFetch(() => held.promise);
  mount();
  await fillValid(actor);
  const button = screen.getByRole('button', { name: 'Send request' });
  await actor.click(button);
  await actor.click(screen.getByRole('button', { name: 'Sending request…' }));
  assert.equal(calls.length, 1);
  assert.equal(field('Email address').disabled, true);
  await act(async () => { held.resolve(json({ detail: THANKS }, 202)); });
  await screen.findByRole('heading', { name: 'Request received' });
  assert.equal(calls.length, 1);
});

test('the note shows how many characters are left and stops at 500', async () => {
  const actor = user();
  mount();
  const note = field('Anything else');
  assert.equal(note.getAttribute('maxlength'), '500');
  await actor.type(note, 'Hello');
  assert.match(document.getElementById('note-hint').textContent, /495 characters remaining/);
});

test('someone who is already signed in is sent away from the form', async () => {
  session.signIn({ access: 'access', refresh: 'refresh', user_id: 7, email: 'sam@ncsu.edu' });
  globalThis.fetch = async () => json([]);
  mount();
  assert.equal(screen.queryByRole('heading', { name: 'Request alumni access' }), null);
});
