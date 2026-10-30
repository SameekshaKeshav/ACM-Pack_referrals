import { apiRequest } from './client';
import { getSession } from '../auth/session';

export class ApiError extends Error {
  constructor(message, status) { super(message); this.name = 'ApiError'; this.status = status; }
}

const errors = {
  400: 'Check the recipient and message. The note must be at most 500 characters.',
  401: 'Your session expired. Sign in again before sending.',
  403: 'This person is currently unavailable to connect.',
  404: 'The connection endpoint or recipient could not be found. Confirm the API route with BE2.',
  409: 'A request already exists for this person.',
  429: 'You’ve reached the request limit. Try again later.',
  501: 'The backend connection endpoint is still a stub. Try again after BE2 implements it.',
};

export async function sendConnectionRequest({ recipientId, messageText, accessToken }) {
  // Signed-in app traffic uses the same refresh-aware client as chat. The
  // explicit-token path below supports the isolated legacy mock harness only.
  if (getSession()) {
    let result;
    try { result = await apiRequest('/api/connections/', { method: 'POST', body: { recipient_id: recipientId, message_text: messageText } }); }
    catch (error) { throw new ApiError(errors[error.status] || error.message, error.status); }
    if (!Number.isInteger(result?.id) || result.status !== 'pending') throw new ApiError('The server response did not match the agreed request shape. Confirm it with BE2.', 200);
    return result;
  }
  const response = await fetch('/api/connections/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ recipient_id: recipientId, message_text: messageText }),
  });
  let data;
  try { data = await response.json(); } catch { data = null; }
  if (!response.ok) {
    throw new ApiError(errors[response.status] || 'Could not send the request. Please try again.', response.status);
  }
  if (response.status !== 201 || !Number.isInteger(data?.id) || data.status !== 'pending') {
    throw new ApiError('The server response did not match the agreed request shape. Confirm it with BE2.', response.status);
  }
  return data;
}

// ---- Request inbox: GET /api/connections/?type=incoming|outgoing and PATCH accept/decline ----

const validId = (id) => Number.isSafeInteger(id) && id > 0;
const mismatch = () => new ApiError('The connection requests response did not match the API contract.', 200);

const listErrors = {
  401: 'Your session expired. Sign in again to see your requests.',
  429: 'Too many requests. Wait a moment and try again.',
};
const answerErrors = {
  401: 'Your session expired. Sign in again before answering.',
  403: 'Only the person who received a request can answer it.',
  404: 'This request no longer exists.',
  409: 'This request has already been answered.',
};

function personOf(row, key) {
  const person = row?.[key];
  if (!validId(person?.id) || typeof person.name !== 'string') throw mismatch();
  return { id: person.id, name: person.name, company: typeof person.company === 'string' ? person.company : '' };
}

// Incoming = pending requests sent to me. Outgoing = pending and accepted requests I sent.
export async function listConnectionRequests(type, { signal } = {}) {
  if (type !== 'incoming' && type !== 'outgoing') throw new TypeError('type must be incoming or outgoing');
  let data;
  try {
    data = await apiRequest(`/api/connections/?type=${type}`, { signal });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError(listErrors[error.status] || error.message || 'Could not load your requests.', error.status);
  }
  if (!Array.isArray(data)) throw mismatch();
  const key = type === 'incoming' ? 'sender' : 'recipient';
  return data.map((row) => {
    if (!validId(row?.id) || typeof row.message_text !== 'string' || typeof row.status !== 'string') throw mismatch();
    return { id: row.id, [key]: personOf(row, key), message_text: row.message_text, status: row.status, created_at: row.created_at };
  });
}

// action is 'accept' or 'decline'. Accepting returns the new conversation's id.
export async function respondToRequest(id, action, { signal } = {}) {
  if (action !== 'accept' && action !== 'decline') throw new TypeError('action must be accept or decline');
  let data;
  try {
    data = await apiRequest(`/api/connections/${id}/${action}/`, { method: 'PATCH', signal });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError(answerErrors[error.status] || error.message || 'Could not answer this request. Please try again.', error.status);
  }
  if (!validId(data?.id) || typeof data.status !== 'string') throw mismatch();
  if (action === 'accept' && !validId(data.conversation_id)) throw mismatch();
  return { id: data.id, status: data.status, conversation_id: action === 'accept' ? data.conversation_id : null };
}

// Friendlier text for the Connect dialog than the developer-facing messages above.
export const connectErrorText = (error) => ({
  400: 'Write a short note, up to 500 characters.',
  401: 'Your session expired. Sign in again before sending.',
  403: 'This person is not available to connect right now.',
  404: 'This member could not be found.',
  409: 'You already have a request or connection with this person.',
  429: 'You have reached today’s limit of connection requests. Try again tomorrow.',
}[error?.status] || (error?.name === 'ApiError' && error.status ? 'Could not send the request. Please try again.' : 'Could not reach the server. Your note is kept here; try again.'));
