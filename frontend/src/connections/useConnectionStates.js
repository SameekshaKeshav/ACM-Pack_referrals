import { useCallback, useEffect, useState } from 'react';
import { listConnectionRequests } from '../api/connections';
import { listConversations } from '../api/chat';

// Who I am already connected to or waiting on, by user id, so a directory card can
// show "Connect", "Request sent" or "Message" instead of a button that would 409.
//   { kind: 'connected', conversationId } | { kind: 'sent' } | { kind: 'received' }
// This is a hint only: the server still refuses duplicates, and if any of the
// three lookups fails the card falls back to a plain Connect button.
export function useConnectionStates() {
  const [states, setStates] = useState(() => new Map());
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    Promise.allSettled([
      listConnectionRequests('outgoing', { signal }),
      listConnectionRequests('incoming', { signal }),
      listConversations({ signal }),
    ]).then(([outgoing, incoming, conversations]) => {
      if (signal.aborted) return;
      const next = new Map();
      // Weakest first, so a stronger state overwrites a weaker one.
      if (incoming.status === 'fulfilled') incoming.value.forEach((row) => next.set(row.sender.id, { kind: 'received' }));
      if (outgoing.status === 'fulfilled') {
        outgoing.value.forEach((row) => next.set(row.recipient.id, row.status === 'accepted' ? { kind: 'connected' } : { kind: 'sent' }));
      }
      if (conversations.status === 'fulfilled') {
        conversations.value.forEach((row) => next.set(row.other_user.id, { kind: 'connected', conversationId: row.id }));
      }
      setStates(next);
    });
    return () => controller.abort();
  }, [attempt]);

  const mark = useCallback((userId, state) => setStates((current) => new Map(current).set(userId, state)), []);
  const reload = useCallback(() => setAttempt((value) => value + 1), []);
  return { states, mark, reload };
}
