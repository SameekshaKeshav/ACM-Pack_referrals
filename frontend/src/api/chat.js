import { apiRequest, ApiError } from './client';

const validId = (id) => Number.isSafeInteger(id) && id > 0;
const date = (value) => Number.isFinite(Date.parse(value));
const mismatch = () => new ApiError('The chat response does not match the API contract. Confirm the endpoint and response fields with the chat backend owner.');

function pageOf(data) {
  if (Array.isArray(data)) return { rows: data, next: null, paginated: false };
  if (Array.isArray(data?.results) && (data.next === null || typeof data.next === 'string')) return { rows: data.results, next: data.next, paginated: true };
  throw mismatch();
}

// Never follow an API-supplied next link off-origin or outside this collection.
function nextPath(value, collection) {
  const url = new URL(value, window.location.origin);
  if (url.origin !== window.location.origin || url.pathname !== collection || url.username || url.password || url.hash) throw mismatch();
  return url.pathname + url.search;
}

export function normalizeMessage(row, conversationId) {
  const sender = row?.sender_id ?? row?.sender;
  const owner = row?.conversation_id ?? row?.conversation;
  if (!validId(row?.id) || !validId(sender) || typeof row.body_text !== 'string'
    || !date(row.created_at) || (owner !== undefined && owner !== conversationId)) throw mismatch();
  return { ...row, sender_id: sender, conversation_id: conversationId };
}

export function orderMessages(messages) {
  return [...messages].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)
    || (typeof a.id === 'number' && typeof b.id === 'number' ? a.id - b.id : 0));
}

export async function listConversations({ signal } = {}) {
  const collection = '/api/chat/conversations/';
  let path = collection;
  const seen = new Set();
  const rows = new Map();
  while (path) {
    if (seen.has(path)) throw mismatch();
    seen.add(path);
    const page = pageOf(await apiRequest(path, { signal }));
    for (const row of page.rows) {
      if (!validId(row?.id) || !validId(row?.other_user?.id)) throw mismatch();
      rows.set(row.id, { ...row, other_user: { ...row.other_user, name: row.other_user.name || row.other_user.email || `User ${row.other_user.id}` },
        last_message: typeof row.last_message === 'string' ? row.last_message : row.last_message?.body_text || '', unread_count: row.unread_count || 0 });
    }
    path = page.next ? nextPath(page.next, collection) : null;
  }
  return [...rows.values()];
}

export async function listMessages(conversationId, { signal } = {}) {
  if (!validId(conversationId)) throw mismatch();
  const collection = `/api/chat/conversations/${conversationId}/messages/`;
  let path = collection + '?limit=100';
  const seen = new Set();
  const rows = new Map();
  while (path) {
    if (seen.has(path)) throw mismatch();
    seen.add(path);
    const page = pageOf(await apiRequest(path, { signal }));
    const batch = page.rows.map((row) => normalizeMessage(row, conversationId));
    batch.forEach((row) => rows.set(row.id, row));
    if (page.paginated) path = page.next ? nextPath(page.next, collection) : null;
    else if (batch.length === 100) {
      const oldest = orderMessages(batch)[0];
      path = collection + '?' + new URLSearchParams({ limit: '100', before: oldest.created_at, before_id: String(oldest.id) });
    } else path = null;
  }
  return orderMessages([...rows.values()]);
}

export async function sendMessage(conversationId, bodyText) {
  const row = await apiRequest('/api/chat/messages/', { method: 'POST', body: { conversation_id: conversationId, body_text: bodyText } });
  return normalizeMessage(row, conversationId);
}
