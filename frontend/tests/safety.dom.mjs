import test, { after, afterEach, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';
const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5174/chat' });
globalThis.window = dom.window; globalThis.document = dom.window.document; globalThis.HTMLElement = dom.window.HTMLElement;
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
globalThis.requestAnimationFrame = (callback) => setTimeout(callback, 0);
const { createElement: h, StrictMode } = await import('react');
const { render, screen, cleanup, waitFor } = await import('@testing-library/react');
const { default: userEvent } = await import('@testing-library/user-event');
const vite = await createServer({ server: { middlewareMode: true, hmr: false } });
const { ReportButton, BlockButton, BlockedNotice } = await vite.ssrLoadModule('/src/components/SafetyActions.jsx');
const { default: Experiences } = await vite.ssrLoadModule('/src/components/InterviewExperiences.jsx');
const session = await vite.ssrLoadModule('/src/auth/session.js');
const originalFetch = globalThis.fetch;
beforeEach(() => session.signIn({ access: 'access', refresh: 'refresh', user_id: 7, email: 'me@ncsu.edu' }));
afterEach(() => { cleanup(); session.signOut(); globalThis.fetch = originalFetch; });
after(async () => { await vite.close(); dom.window.close(); });
const json = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
const actor = () => userEvent.setup({ document: dom.window.document });
function backend(respond = () => json({}, 201)) {
  const calls = [];
  globalThis.fetch = async (path, options = {}) => { calls.push({ path, ...options }); return respond(path, options); };
  return calls;
}

test('a report needs a reason, then posts the exact fields with the signed-in token', async () => {
  const calls = backend();
  render(h(ReportButton, { targetType: 'user', targetId: 12, subject: 'Maya' }));
  const who = actor();
  await who.click(screen.getByRole('button', { name: 'Report Maya' }));
  assert.equal(screen.getByRole('button', { name: 'Send report' }).disabled, true);
  await who.selectOptions(screen.getByLabelText('Reason (required)'), 'spam');
  await who.type(screen.getByLabelText('Details (optional)'), '  Sent the same link to everyone.  ');
  await who.click(screen.getByRole('button', { name: 'Send report' }));
  await screen.findByText('Thanks. Your report was sent to the moderators.');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, '/api/reports/');
  assert.equal(calls[0].method, 'POST');
  assert.equal(calls[0].headers.Authorization, 'Bearer access');
  assert.deepEqual(JSON.parse(calls[0].body), { target_type: 'user', target_id: 12, reason: 'spam', details: 'Sent the same link to everyone.' });
  assert.equal(screen.queryByRole('button', { name: 'Report Maya' }), null);
});

test('reporting the same thing twice (HTTP 200) still reads as sent', async () => {
  backend(() => json({ id: 1 }, 200));
  render(h(ReportButton, { targetType: 'message', targetId: 4, subject: 'this message' }));
  const who = actor();
  await who.click(screen.getByRole('button', { name: 'Report this message' }));
  await who.selectOptions(screen.getByLabelText('Reason (required)'), 'harassment');
  await who.click(screen.getByRole('button', { name: 'Send report' }));
  await screen.findByText(/Your report was sent/);
});

test('a throttled or failed report keeps the form open and says what happened', async () => {
  backend(() => json({ detail: 'Request was throttled. Expected available in 600 seconds.' }, 429));
  render(h(ReportButton, { targetType: 'user', targetId: 12, subject: 'Maya' }));
  const who = actor();
  await who.click(screen.getByRole('button', { name: 'Report Maya' }));
  await who.selectOptions(screen.getByLabelText('Reason (required)'), 'other');
  await who.click(screen.getByRole('button', { name: 'Send report' }));
  const alert = await screen.findByRole('alert');
  assert.match(alert.textContent, /about 10 minutes/);
  assert.ok(screen.getByLabelText('Reason (required)'));
  assert.equal(screen.getByRole('button', { name: 'Send report' }).disabled, false);
});

test('cancelling a report sends nothing and brings the button back into focus', async () => {
  const calls = backend();
  render(h(ReportButton, { targetType: 'user', targetId: 12, subject: 'Maya' }));
  const who = actor();
  await who.click(screen.getByRole('button', { name: 'Report Maya' }));
  await who.click(screen.getByRole('button', { name: 'Cancel' }));
  assert.equal(calls.length, 0);
  await waitFor(() => assert.equal(document.activeElement, screen.getByRole('button', { name: 'Report Maya' })));
});

test('blocking asks first, then posts to the block endpoint and tells the page', async () => {
  const calls = backend(() => json({ detail: 'User blocked.' }, 201));
  let blocked = 0;
  render(h(BlockButton, { userId: 12, name: 'Maya', onBlocked: () => { blocked += 1; } }));
  const who = actor();
  await who.click(screen.getByRole('button', { name: 'Block Maya' }));
  assert.equal(calls.length, 0);
  assert.match(screen.getByRole('group', { name: 'Block Maya?' }).textContent, /hidden for both of you/);
  await who.click(screen.getByRole('button', { name: 'Block Maya' }));
  await waitFor(() => assert.equal(blocked, 1));
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, '/api/connections/users/12/block/');
  assert.equal(calls[0].method, 'POST');
});

test('keeping the conversation sends nothing; a failed block shows the error and stays', async () => {
  const calls = backend(() => json({ detail: 'User not found.' }, 404));
  let blocked = 0;
  render(h(BlockButton, { userId: 12, name: 'Maya', onBlocked: () => { blocked += 1; } }));
  const who = actor();
  await who.click(screen.getByRole('button', { name: 'Block Maya' }));
  await who.click(screen.getByRole('button', { name: 'Keep conversation' }));
  assert.equal(calls.length, 0);
  await who.click(screen.getByRole('button', { name: 'Block Maya' }));
  await who.click(screen.getByRole('button', { name: 'Block Maya' }));
  assert.equal((await screen.findByRole('alert')).textContent, 'User not found.');
  assert.equal(blocked, 0);
});

test('interview experiences offer Report on other members posts only, and report the experience id', async () => {
  const rows = [
    { id: 1, role_title: 'Mine', outcome: 'offer', difficulty: 3, process_text: 'Two rounds.', is_mine: true, month: 10, year: 2026 },
    { id: 2, role_title: 'Theirs', outcome: 'rejected', difficulty: 4, process_text: 'Three rounds.', is_mine: false, month: 10, year: 2026 },
  ];
  const calls = backend((path, options) => (options.method === 'POST' ? json({ id: 9 }, 201) : json(rows)));
  render(h(Experiences, { companyId: 3 }));
  await screen.findByRole('heading', { name: 'Theirs' });
  assert.equal(screen.getAllByRole('button', { name: /^Report / }).length, 1);
  const who = actor();
  await who.click(screen.getByRole('button', { name: 'Report the Theirs experience' }));
  await who.selectOptions(screen.getByLabelText('Reason (required)'), 'inappropriate_content');
  await who.click(screen.getByRole('button', { name: 'Send report' }));
  await screen.findByText(/Your report was sent/);
  const post = calls.find((call) => call.path === '/api/reports/');
  assert.deepEqual(JSON.parse(post.body), { target_type: 'experience', target_id: 2, reason: 'inappropriate_content', details: '' });
});

test('works under StrictMode, which mounts every component twice in development', async () => {
  backend();
  render(h(StrictMode, null, h(ReportButton, { targetType: 'user', targetId: 12, subject: 'Maya' })));
  const who = actor();
  await who.click(screen.getByRole('button', { name: 'Report Maya' }));
  await who.selectOptions(screen.getByLabelText('Reason (required)'), 'spam');
  await who.click(screen.getByRole('button', { name: 'Send report' }));
  await screen.findByText(/Your report was sent/);
  cleanup();
  let blocked = 0;
  backend(() => json({ detail: 'User blocked.' }, 201));
  render(h(StrictMode, null, h(BlockButton, { userId: 12, name: 'Maya', onBlocked: () => { blocked += 1; } })));
  await who.click(screen.getByRole('button', { name: 'Block Maya' }));
  await who.click(screen.getByRole('button', { name: 'Block Maya' }));
  await waitFor(() => assert.equal(blocked, 1));
  await waitFor(() => assert.equal(screen.queryByRole('group'), null));
});

test('after a block the notice offers Unblock, which sends DELETE and tells the page', async () => {
  const calls = backend(() => new Response(null, { status: 204 }));
  let undone = 0;
  render(h(StrictMode, null, h(BlockedNotice, { userId: 12, name: 'Maya', onUnblocked: () => { undone += 1; } })));
  assert.match(screen.getByRole('status').textContent, /You blocked Maya/);
  await actor().click(screen.getByRole('button', { name: 'Unblock Maya' }));
  await waitFor(() => assert.equal(undone, 1));
  assert.equal(calls.length, 1);
  assert.equal(calls[0].path, '/api/connections/users/12/block/');
  assert.equal(calls[0].method, 'DELETE');
  assert.equal(calls[0].headers.Authorization, 'Bearer access');
});

test('a failed unblock shows the error, keeps the button and does not tell the page', async () => {
  backend(() => json({ detail: 'Server error.' }, 500));
  let undone = 0;
  render(h(BlockedNotice, { userId: 12, name: 'Maya', onUnblocked: () => { undone += 1; } }));
  await actor().click(screen.getByRole('button', { name: 'Unblock Maya' }));
  assert.equal((await screen.findByRole('alert')).textContent, 'Server error.');
  assert.equal(undone, 0);
  assert.equal(screen.getByRole('button', { name: 'Unblock Maya' }).disabled, false);
});

test('a late Unblock answer after the notice is gone does not tell the page', async () => {
  let finish;
  const calls = backend(() => new Promise((resolve) => { finish = () => resolve(new Response(null, { status: 204 })); }));
  let undone = 0;
  render(h(BlockedNotice, { userId: 12, name: 'Maya', onUnblocked: () => { undone += 1; } }));
  await actor().click(screen.getByRole('button', { name: 'Unblock Maya' }));
  await waitFor(() => assert.equal(calls.length, 1));
  cleanup(); // the page replaced the notice, for example because someone else was blocked
  finish();
  await new Promise((resolve) => setTimeout(resolve, 20));
  assert.equal(undone, 0);
});
