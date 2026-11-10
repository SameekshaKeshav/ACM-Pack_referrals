import test, { afterEach, after } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'vite';

// The API client turns a response into a message a person can read. DRF's default throttle
// text ("Request was throttled. Expected available in 900 seconds.") must not reach the screen,
// but a 429 that carries its own explanation must keep it.
const vite = await createServer({ server: { middlewareMode: true, hmr: false } });
const { publicRequest } = await vite.ssrLoadModule('/src/api/client.js');
const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });
after(async () => { await vite.close(); });

const respond = (data, status) => { globalThis.fetch = async () => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } }); };
const failure = (path = '/api/accounts/alumni-access-requests/') => publicRequest(path, { method: 'POST', body: {} }).then(() => assert.fail('expected a failure'), (error) => error);

test("DRF's throttle text becomes a friendly message with the wait in minutes", async () => {
  respond({ detail: 'Request was throttled. Expected available in 900 seconds.' }, 429);
  const error = await failure();
  assert.equal(error.status, 429);
  assert.equal(error.message, 'Too many attempts. Please wait about 15 minutes before trying again.');
});

test('a short wait is singular, and a throttle with no wait still reads well', async () => {
  respond({ detail: 'Request was throttled. Expected available in 30 seconds.' }, 429);
  assert.equal((await failure()).message, 'Too many attempts. Please wait about 1 minute before trying again.');
  respond({ detail: 'Request was throttled.' }, 429);
  assert.equal((await failure()).message, 'Too many attempts. Please wait before trying again.');
});

test('a 429 that explains itself keeps its own message', async () => {
  respond({ detail: 'You have reached the daily interview experience limit.' }, 429);
  assert.equal((await failure()).message, 'You have reached the daily interview experience limit.');
});

test('other errors still show the server detail', async () => {
  respond({ detail: 'This user is not open to connection requests.' }, 403);
  assert.equal((await failure()).message, 'This user is not open to connection requests.');
});
