import { useEffect, useState } from 'react';
import { listConnectionRequests } from '../api/connections';

// Anything that changes the pending-request count (accepting, declining) calls
// this, so the badge in the header updates without waiting for the next poll.
const EVENT = 'connection-requests-changed';
export const notifyRequestsChanged = () => window.dispatchEvent(new window.Event(EVENT));

// Number of pending requests sent to me, or null until the first answer.
// Refreshes on navigation (`refreshKey`), when the tab regains focus, on
// notifyRequestsChanged(), and once a minute. A failed refresh keeps the last count.
export function usePendingRequestCount(refreshKey, intervalMs = 60000) {
  const [count, setCount] = useState(null);

  useEffect(() => {
    let controller;
    const refresh = () => {
      controller?.abort();
      controller = new AbortController();
      const mine = controller;
      listConnectionRequests('incoming', { signal: mine.signal })
        .then((rows) => { if (!mine.signal.aborted) setCount(rows.length); })
        .catch(() => { /* keep the previous count */ });
    };
    refresh();
    const timer = setInterval(refresh, intervalMs);
    const onVisible = () => { if (document.visibilityState === 'visible') refresh(); };
    window.addEventListener(EVENT, refresh);
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      controller?.abort();
      clearInterval(timer);
      window.removeEventListener(EVENT, refresh);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [refreshKey, intervalMs]);

  return count;
}
