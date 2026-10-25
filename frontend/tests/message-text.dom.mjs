import test, { after, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { JSDOM } from 'jsdom';
import { createServer } from 'vite';

// Chat text is stored exactly as typed, so the browser must be the one to keep it
// inert. React escapes text children by default; these tests pin that down so a
// future change to `dangerouslySetInnerHTML` or `innerHTML` is caught.
const dom = new JSDOM('<html><body></body></html>', { url: 'http://localhost:5173/chat' });
globalThis.window = dom.window;
globalThis.document = dom.window.document;
globalThis.HTMLElement = dom.window.HTMLElement;
Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const { createElement: h } = await import('react');
const { render, screen, cleanup } = await import('@testing-library/react');
const vite = await createServer({ server: { middlewareMode: true, hmr: false } });
const { default: MessageBubble } = await vite.ssrLoadModule('/src/components/MessageBubble.jsx');
afterEach(() => cleanup());
after(async () => { await vite.close(); dom.window.close(); });

const message = (body) => ({ id: 1, conversation_id: 5, sender_id: 41, body_text: body, created_at: '2026-10-20T12:00:00Z' });
const bubble = (body) => render(h('ul', null, h(MessageBubble, { message: message(body), isOwn: false, senderName: 'Avery Chen' })));

test('a script tag in a message is shown as text and never becomes an element', () => {
  const payload = '<script>alert(1)</script>';
  const { container } = bubble(payload);

  assert.equal(container.querySelectorAll('script').length, 0);
  assert.ok(container.querySelector('.message-bubble').textContent.includes(payload));
});

test('markup in a message does not create elements or attributes', () => {
  const { container } = bubble('<img src=x onerror=alert(1)> <b>bold</b>');

  assert.equal(container.querySelectorAll('img, b').length, 0);
  assert.equal(container.querySelector('[onerror]'), null);
});

test('ampersands and angle brackets display unchanged, not double-escaped', () => {
  const { container } = bubble('Tom & Jerry <3 &amp; co');

  assert.ok(container.querySelector('.message-bubble').textContent.endsWith('Tom & Jerry <3 &amp; co'));
  assert.ok(screen.getByText(/Tom & Jerry <3 &amp; co/));
});

test('no source file injects raw HTML', () => {
  const offenders = [];
  const walk = (dir) => {
    for (const name of readdirSync(dir)) {
      const path = join(dir, name);
      if (statSync(path).isDirectory()) walk(path);
      else if (/\.(jsx?|tsx?)$/.test(name) && /dangerouslySetInnerHTML|\.innerHTML\s*=/.test(readFileSync(path, 'utf8'))) offenders.push(path);
    }
  };
  walk(new URL('../src', import.meta.url).pathname);

  assert.deepEqual(offenders, []);
});
