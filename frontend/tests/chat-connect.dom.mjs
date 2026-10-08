import test, { after, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';

const dom = new JSDOM('<!doctype html><html><body></body></html>', { url: 'http://localhost:5173/chat-mock' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
globalThis.HTMLElement = dom.window.HTMLElement;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { createElement } = await import('react');
const { render, screen, cleanup, waitFor } = await import('@testing-library/react');
const { default: userEvent } = await import('@testing-library/user-event');
const vite = await createServer({ server: { middlewareMode: true, hmr: false } });
const { default: ChatMockPage } = await vite.ssrLoadModule('/src/ChatMockPage.jsx');
afterEach(cleanup);
after(async () => { await vite.close(); dom.window.close(); });

test('initial fixtures and local Accept/Decline log with no network call', async () => {
  const user = userEvent.setup({ document: dom.window.document });
  const calls = [];
  const logs = [];
  const originalInfo = console.info;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (...args) => { calls.push(args); throw new Error('unexpected network call'); };
  console.info = (...args) => logs.push(args);
  try {
    render(createElement(ChatMockPage));
    assert.equal(screen.getAllByRole('article').length, 3);
    assert.equal(screen.getAllByRole('listitem').length, 5);
    await user.click(screen.getByRole('button', { name: 'Accept Maya Patel' }));
    assert.equal(screen.getAllByRole('article').length, 2);
    assert.equal(logs[0][0], 'PATCH /api/connections/123/accept/');
    assert.deepEqual(logs[0][1], { mock: true });
    await user.click(screen.getByRole('button', { name: 'Decline Alex Rivera' }));
    await user.click(screen.getByRole('button', { name: 'Decline Jordan Lee' }));
    assert.ok(screen.getByText('You’re all caught up. No incoming requests.'));
    assert.equal(calls.length, 0);
    await user.click(screen.getByRole('button', { name: 'Reset demo' }));
    assert.equal(screen.getAllByRole('article').length, 3);
  } finally { console.info = originalInfo; globalThis.fetch = originalFetch; }
});

test('500/501 typed and pasted characters; Unicode code points counted correctly', async () => {
  render(createElement(ChatMockPage));
  const user = userEvent.setup({ document: dom.window.document });
  const note = screen.getByLabelText('Your note');
  await user.type(note, 'a'.repeat(500));
  assert.ok(screen.getByText('0 remaining'));
  await user.type(note, 'b');
  assert.equal(note.value, 'a'.repeat(500));
  await user.clear(note);
  await user.click(note);
  await user.paste('z'.repeat(501));
  assert.equal(note.value, 'z'.repeat(500));
  await user.clear(note);
  await user.paste('🐺'.repeat(501));
  assert.equal(Array.from(note.value).length, 500);
  assert.ok(screen.getByText('0 remaining'));
});

test('outgoing and sidebar selection plus editable static composer', async () => {
  render(createElement(ChatMockPage));
  const user = userEvent.setup({ document: dom.window.document });
  await user.click(screen.getByRole('tab', { name: 'Outgoing 2' }));
  assert.equal(screen.getAllByRole('article').length, 2);
  assert.equal(screen.queryAllByRole('button', { name: /^Accept / }).length, 0);
  await user.click(screen.getByRole('button', { name: /Sam Wilson/ }));
  assert.ok(screen.getByRole('region', { name: 'Conversation with Sam Wilson' }));
  await user.click(screen.getByRole('button', { name: /Avery Chen/ }));
  assert.equal(screen.getAllByRole('listitem').length, 5);
  await user.type(screen.getByLabelText('Chat message'), 'Local draft');
  assert.equal(screen.getByRole('button', { name: 'Send', exact: true }).disabled, true);
});

test('exact POST payload/auth, single in-flight call and success append', async () => {
  render(createElement(ChatMockPage));
  const user = userEvent.setup({ document: dom.window.document });
  const originalFetch = globalThis.fetch;
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, ...options });
    await gate;
    return new Response(JSON.stringify({ id: 203, status: 'pending' }), { status: 201 });
  };
  try {
    await user.click(screen.getByText('API test panel'));
    await user.type(screen.getByLabelText('Access token', { exact: true }), 'test-jwt');
    await user.type(screen.getByLabelText('Recipient user ID'), '31');
    await user.type(screen.getByLabelText('Your note'), 'Hello Wolfpack');
    await user.click(screen.getByRole('button', { name: 'Send Request', exact: true }));
    assert.equal(screen.getByRole('button', { name: 'Sending…' }).disabled, true);
    await user.click(screen.getByRole('button', { name: 'Sending…' }));
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, '/api/connections/');
    assert.equal(calls[0].method, 'POST');
    assert.equal(calls[0].headers.Authorization, 'Bearer test-jwt');
    assert.deepEqual(JSON.parse(calls[0].body), { recipient_id: 31, message_text: 'Hello Wolfpack' });
    release();
    await waitFor(() => assert.ok(screen.getByText('Request #203 sent. Status: pending.')));
    assert.equal(screen.getByLabelText('Your note').value, '');
    await user.click(screen.getByRole('tab', { name: 'Outgoing 3' }));
    assert.ok(screen.getByRole('article', { name: 'Request to User 31' }));
  } finally { globalThis.fetch = originalFetch; }
});

test('missing token, conflict, network failure, stub and bad response retain note; retry succeeds', async () => {
  render(createElement(ChatMockPage));
  const user = userEvent.setup({ document: dom.window.document });
  const originalFetch = globalThis.fetch;
  let count = 0;
  globalThis.fetch = async () => {
    count += 1;
    if (count === 1) return new Response('{}', { status: 409 });
    if (count === 2) throw new TypeError('Failed to fetch');
    if (count === 3) return new Response('', { status: 501 });
    if (count === 4) return new Response('{"id":9,"status":"pending"}', { status: 200 });
    return new Response('{"id":204,"status":"pending"}', { status: 201 });
  };
  try {
    await user.type(screen.getByLabelText('Recipient user ID'), '31');
    await user.type(screen.getByLabelText('Your note'), 'Hello');
    const send = () => user.click(screen.getByRole('button', { name: 'Send Request', exact: true }));
    await send();
    assert.match(screen.getByRole('alert').textContent, /Add an access token/);
    assert.equal(count, 0);
    await user.click(screen.getByText('API test panel'));
    await user.type(screen.getByLabelText('Access token', { exact: true }), 'test-jwt');
    for (const expected of [/already exists/, /Could not reach/, /still a stub/, /did not match/]) {
      await send();
      await waitFor(() => assert.match(screen.getByRole('alert').textContent, expected));
      assert.equal(screen.getByLabelText('Your note').value, 'Hello');
    }
    await send();
    await waitFor(() => assert.ok(screen.getByText('Request #204 sent. Status: pending.')));
  } finally { globalThis.fetch = originalFetch; }
});
