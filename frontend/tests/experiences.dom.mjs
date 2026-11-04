import test, { after, afterEach, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';
const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5174/company/3?tab=interviews' });
globalThis.window = dom.window; globalThis.document = dom.window.document; globalThis.HTMLElement = dom.window.HTMLElement;
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { createElement: h } = await import('react');
const { render, screen, cleanup, waitFor, act } = await import('@testing-library/react');
const { default: userEvent } = await import('@testing-library/user-event');
const vite = await createServer({ server: { middlewareMode: true, hmr: false } });
const { default: Experiences } = await vite.ssrLoadModule('/src/components/InterviewExperiences.jsx');
const api = await vite.ssrLoadModule('/src/api/experiences.js');
const session = await vite.ssrLoadModule('/src/auth/session.js');
const originalFetch = globalThis.fetch;
beforeEach(() => session.signIn({ access: 'access', refresh: 'refresh', user_id: 7, email: 'me@ncsu.edu' }));
afterEach(() => { cleanup(); session.signOut(); globalThis.fetch = originalFetch; });
after(async () => { await vite.close(); dom.window.close(); });
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const row = (id = 1, extra = {}) => ({ id, role_title: 'Engineer', outcome: 'offer', difficulty: 3, process_text: 'Two rounds.', is_mine: true, month: 10, year: 2026, ...extra });
const actor = () => userEvent.setup({ document: dom.window.document });
function backend({ rows = [row()], post, remove, get } = {}) {
  const calls = [];
  globalThis.fetch = async (path, options = {}) => {
    calls.push({ path, ...options });
    if (options.method === 'POST') return post ? post(JSON.parse(options.body)) : json(row(99, JSON.parse(options.body)), 201);
    if (options.method === 'DELETE') return remove ? remove() : new Response(null, { status: 204 });
    return get ? get(path) : json(rows);
  };
  return calls;
}
async function fill() {
  await screen.findByRole('heading', { name: 'Engineer' });
  const who = actor();
  await who.type(screen.getByLabelText('Role title (required)'), 'Intern');
  await who.selectOptions(screen.getByLabelText('Outcome (required)'), 'no_response');
  await who.selectOptions(screen.getByLabelText('Difficulty (required)'), '2');
  await who.type(screen.getByLabelText('Interview process (required)'), '  Phone screen 😀  ');
  return who;
}

test('anonymous cards strip author identity, render text safely and allow deletion only for own posts', async () => {
  backend({ rows: [row(1, { process_text: '<img src=x onerror=alert(1)>', author: { email: 'private@ncsu.edu' } }), row(2, { is_mine: false, role_title: 'Analyst' })] });
  render(h(Experiences, { companyId: 3 }));
  await screen.findByText('<img src=x onerror=alert(1)>');
  assert.ok(!document.querySelector('img'));
  assert.ok(!screen.queryByText('private@ncsu.edu'));
  assert.equal(screen.getAllByRole('button', { name: /^Delete my/ }).length, 1);
  assert.deepEqual(Object.keys(api.normalizeExperience({ ...row(), author_id: 7 })).sort(), ['id', 'role_title', 'outcome', 'difficulty', 'process_text', 'is_mine', 'month', 'year'].sort());
});

test('POST has exact fields/Bearer, is single-flight, and appends immediately on acknowledgement', async () => {
  let release; const gate = new Promise((resolve) => { release = resolve; });
  const calls = backend({ post: () => gate });
  render(h(Experiences, { companyId: 3 })); const who = await fill();
  await who.dblClick(screen.getByRole('button', { name: 'Post experience' }));
  const posts = calls.filter((call) => call.method === 'POST');
  assert.equal(posts.length, 1); assert.equal(posts[0].path, '/api/companies/3/experiences/');
  assert.equal(posts[0].headers.Authorization, 'Bearer access');
  assert.deepEqual(JSON.parse(posts[0].body), { role_title: 'Intern', outcome: 'no_response', difficulty: 2, process_text: 'Phone screen 😀' });
  await act(async () => release(json(row(99, { role_title: 'Intern' }), 201)));
  await screen.findByRole('heading', { name: 'Intern' });
  assert.equal(screen.getByLabelText('Interview process (required)').value, '');
  assert.match(screen.getByRole('status').textContent, /posted anonymously/);
});

test('429 and validation failures retain draft and permit an explicit retry', async () => {
  let attempt = 0;
  backend({ post: () => ++attempt === 1 ? json({ detail: 'Daily limit reached.' }, 429) : json({ process_text: ['Invalid text.'] }, 400) });
  render(h(Experiences, { companyId: 3 })); const who = await fill();
  await who.click(screen.getByRole('button', { name: 'Post experience' }));
  await waitFor(() => assert.match(screen.getByRole('alert').textContent, /Daily limit/));
  assert.equal(screen.getByLabelText('Interview process (required)').value, '  Phone screen 😀  ');
  await who.click(screen.getByRole('button', { name: 'Post experience' }));
  await waitFor(() => assert.match(screen.getByRole('alert').textContent, /Invalid text/));
});

test('Unicode paste is capped at 5000 code points and whitespace-only posts do not send', async () => {
  const calls = backend(); render(h(Experiences, { companyId: 3 })); const who = await fill();
  const process = screen.getByLabelText('Interview process (required)');
  await who.clear(process); await who.click(process); await who.paste('😀'.repeat(5001));
  assert.equal(Array.from(process.value).length, 5000);
  assert.ok(screen.getByText('0 characters remaining'));
  await who.clear(process); await who.type(process, '   ');
  await who.click(screen.getByRole('button', { name: 'Post experience' }));
  assert.match(screen.getByRole('alert').textContent, /more than spaces/);
  assert.equal(calls.filter((call) => call.method === 'POST').length, 0);
});

test('deletion requires confirmation and keeps a card on failure; cancel restores focus', async () => {
  let attempt = 0;
  const calls = backend({ remove: () => ++attempt === 1 ? json({ detail: 'Try again later.' }, 500) : new Response(null, { status: 204 }) });
  render(h(Experiences, { companyId: 3 })); const who = actor();
  const opener = await screen.findByRole('button', { name: 'Delete my Engineer experience' });
  await who.click(opener);
  assert.equal(calls.filter((call) => call.method === 'DELETE').length, 0);
  await who.click(screen.getByRole('button', { name: 'Keep experience' }));
  assert.equal(document.activeElement, screen.getByRole('button', { name: 'Delete my Engineer experience' }));
  await who.click(screen.getByRole('button', { name: 'Delete my Engineer experience' }));
  await who.click(screen.getByRole('button', { name: 'Confirm delete' }));
  await waitFor(() => assert.match(screen.getByRole('alert').textContent, /Try again/));
  assert.ok(screen.getByRole('article', { name: 'Engineer' }));
  await who.click(screen.getByRole('button', { name: 'Confirm delete' }));
  await waitFor(() => assert.ok(!screen.queryByRole('article', { name: 'Engineer' })));
  assert.equal(calls.filter((call) => call.method === 'DELETE').at(-1).path, '/api/companies/3/experiences/1/');
});

test('404 is clearly unavailable and disables posting instead of fabricating demo posts', async () => {
  const calls = backend({ get: () => json({}, 404) }); render(h(Experiences, { companyId: 3 }));
  await screen.findByText(/not available for this company yet/);
  assert.ok(screen.getByLabelText('Role title (required)').matches(':disabled'));
  assert.ok(!screen.queryByRole('article')); assert.equal(calls.filter((call) => call.method === 'POST').length, 0);
});

test('switching companies/unmounting ignores stale fetches and aborts in-flight posts', async () => {
  let release; const gate = new Promise((resolve) => { release = resolve; });
  backend({ get: (path) => path.includes('/3/') ? gate : json([row(2, { role_title: 'Other company' })]) });
  const view = render(h(Experiences, { key: 3, companyId: 3 }));
  view.rerender(h(Experiences, { key: 4, companyId: 4 }));
  await screen.findByRole('heading', { name: 'Other company' });
  await act(async () => release(json([row()])));
  assert.ok(!screen.queryByRole('heading', { name: 'Engineer' }));
  cleanup(); let postSignal;
  backend({ post: () => new Promise(() => {}) });
  const fetch = globalThis.fetch;
  globalThis.fetch = (path, options) => { if (options.method === 'POST') postSignal = options.signal; return fetch(path, options); };
  const posting = render(h(Experiences, { companyId: 3 })); const who = await fill();
  await who.click(screen.getByRole('button', { name: 'Post experience' }));
  posting.unmount(); assert.ok(postSignal.aborted);
});

test('malformed response fails visibly and retry can recover', async () => {
  let good = false; backend({ get: () => json(good ? [row()] : [{ ...row(), difficulty: 9 }]) });
  render(h(Experiences, { companyId: 3 }));
  await screen.findByText(/response could not be read/); good = true;
  await actor().click(screen.getByRole('button', { name: 'Try loading experiences again' }));
  await screen.findByRole('article', { name: 'Engineer' });
  assert.throws(() => api.normalizeExperience({ ...row(), is_mine: undefined }));
});


test('an already-deleted experience (404) is removed without an error', async () => {
  backend({ remove: () => json({ detail: 'Not found.' }, 404) });
  render(h(Experiences, { companyId: 3 }));
  const who = actor();
  await who.click(await screen.findByRole('button', { name: 'Delete my Engineer experience' }));
  await who.click(screen.getByRole('button', { name: 'Confirm delete' }));
  await waitFor(() => assert.ok(!screen.queryByRole('article', { name: 'Engineer' })));
  assert.equal(screen.getByRole('alert').textContent, '');
  assert.match(screen.getByRole('status').textContent, /was deleted/);
});
