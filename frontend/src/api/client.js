import { getSession, getSessionVersion, saveRefreshedSession, signOut } from '../auth/session';

export class ApiError extends Error {
  constructor(message, status = 0, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

function errorText(data, status) {
  if (typeof data?.detail === 'string') return data.detail;
  if (data && typeof data === 'object') {
    const field = Object.entries(data).find(([, value]) => Array.isArray(value) && typeof value[0] === 'string');
    if (field) return `${field[0].replaceAll('_', ' ')}: ${field[1][0]}`;
  }
  return ({ 401: 'Your session has expired. Sign in again.', 403: 'You do not have access to this resource.',
    404: 'This API endpoint or resource is not available yet.', 429: 'Too many attempts. Please wait before trying again.',
    501: 'This backend endpoint is not implemented yet.' })[status] || 'The request could not be completed. Please try again.';
}

async function send(path, { method = 'GET', body, signal, access } = {}) {
  if (!path.startsWith('/api/') || path.includes('\\')) throw new ApiError('Invalid API path.');
  let response;
  try {
    response = await fetch(path, {
      method, signal, credentials: 'omit',
      headers: { ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...(access ? { Authorization: `Bearer ${access}` } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError('Could not reach the server. Check your connection and try again.');
  }
  let data = null;
  if (response.status !== 204) {
    try { data = await response.json(); }
    catch { if (response.ok) throw new ApiError('The server returned an invalid JSON response.', response.status); }
  }
  if (!response.ok) throw new ApiError(errorText(data, response.status), response.status, data);
  return data;
}

// Auth bootstrap endpoints must omit Authorization, even if old tokens exist.
export const publicRequest = (path, options) => send(path, options);
let refreshFlight = null;

async function refresh(version, refreshToken) {
  if (!refreshFlight || refreshFlight.version !== version) {
    const flight = { version };
    flight.promise = (async () => {
      try {
        const tokens = await publicRequest('/api/accounts/auth/refresh/', { method: 'POST', body: { refresh: refreshToken } });
        if (typeof tokens?.access !== 'string' || !tokens.access.trim()
          || (tokens.refresh !== undefined && (typeof tokens.refresh !== 'string' || !tokens.refresh.trim()))) {
          throw new ApiError('The refresh response was incomplete.', 401);
        }
        if (!saveRefreshedSession(tokens, version, refreshToken)) throw new ApiError('Your session changed. Please sign in again.', 401);
      } catch (error) {
        if ((error.status === 400 || error.status === 401 || error.status === 403) && getSessionVersion() === version) signOut();
        throw error;
      }
    })().finally(() => { if (refreshFlight === flight) refreshFlight = null; });
    refreshFlight = flight;
  }
  await refreshFlight.promise;
}

export async function apiRequest(path, options = {}) {
  const current = getSession();
  const version = getSessionVersion();
  if (!current) throw new ApiError('Sign in to continue.', 401);
  try {
    const result = await send(path, { ...options, access: current.access });
    if (getSessionVersion() !== version) throw new ApiError('Your session changed.', 401);
    return result;
  } catch (error) {
    if (error.status !== 401 || getSessionVersion() !== version || options.signal?.aborted) throw error;
  }
  // Another caller may already have replaced the rejected access token.
  if (getSession()?.access === current.access) await refresh(version, current.refresh);
  if (getSessionVersion() !== version || !getSession()) throw new ApiError('Sign in to continue.', 401);
  if (options.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
  try {
    const result = await send(path, { ...options, access: getSession().access });
    if (getSessionVersion() !== version) throw new ApiError('Your session changed.', 401);
    return result;
  } catch (error) {
    // Retry once only; a second 401 must not produce a refresh loop.
    if (error.status === 401 && getSessionVersion() === version) signOut();
    throw error;
  }
}
