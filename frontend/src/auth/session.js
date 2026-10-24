const KEY = 'pack-referrals.session.v1';
let snapshot;
let version = 0;
const listeners = new Set();

function valid(value) {
  return value && typeof value.access === 'string' && value.access.trim()
    && typeof value.refresh === 'string' && value.refresh.trim()
    && Number.isSafeInteger(value.user?.id) && value.user.id > 0
    && typeof value.user.email === 'string' && value.user.email.trim();
}

function read() {
  try {
    const value = JSON.parse(window.localStorage.getItem(KEY));
    return valid(value) ? value : null;
  } catch { return null; }
}

export function getSession() {
  if (snapshot === undefined) snapshot = read();
  return snapshot;
}

export const getSessionVersion = () => version;
export const subscribeSession = (listener) => { listeners.add(listener); return () => listeners.delete(listener); };
function notify() { listeners.forEach((listener) => listener()); }

export function signIn(credentials) {
  const value = {
    access: credentials.access,
    refresh: credentials.refresh,
    user: { id: credentials.user_id, email: credentials.email },
  };
  if (!valid(value)) throw new Error('The sign-in response was incomplete. Please try again.');
  try { window.localStorage.setItem(KEY, JSON.stringify(value)); }
  catch { throw new Error('Could not save your session. Allow site storage in this browser and try again.'); }
  version += 1;
  snapshot = value;
  notify();
}

export function signOut() {
  try { window.localStorage.removeItem(KEY); } catch { /* Still end the in-memory session. */ }
  version += 1;
  snapshot = null;
  notify();
}

// Refresh never revives a session that logged out or changed users mid-request.
export function saveRefreshedSession(tokens, expectedVersion, expectedRefresh) {
  const current = getSession();
  if (version !== expectedVersion || current?.refresh !== expectedRefresh) return false;
  const next = { ...current, access: tokens.access, refresh: tokens.refresh || current.refresh };
  if (!valid(next)) throw new Error('The refresh response was incomplete.');
  window.localStorage.setItem(KEY, JSON.stringify(next));
  snapshot = next;
  notify();
  return true;
}

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key === KEY || event.key === null) {
      version += 1;
      snapshot = read();
      notify();
    }
  });
}

export function safeDestination(value) {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || value.includes('\\') || /[\x00-\x1f\x7f]/.test(value)) return '/chat';
  const pathname = value.split(/[?#]/)[0];
  return /^\/(login|signup|enter-code)(\/|$)/.test(pathname) ? '/chat' : value;
}
