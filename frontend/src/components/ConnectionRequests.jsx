import { useEffect, useRef, useState } from 'react';
import { listConnectionRequests, respondToRequest } from '../api/connections';
import { notifyRequestsChanged } from '../connections/requestsChanged';
import RequestQueue from './RequestQueue';

const TABS = [{ id: 'incoming', label: 'Incoming' }, { id: 'outgoing', label: 'Outgoing' }];

// The request inbox on the Messages page: who wants to connect with me (accept or
// decline) and the requests I sent. `onAccepted(conversationId)` lets the page open the new chat.
export default function ConnectionRequests({ onAccepted }) {
  const [tab, setTab] = useState('incoming');
  const [incoming, setIncoming] = useState([]);
  const [outgoing, setOutgoing] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [version, setVersion] = useState(0);
  const [busyId, setBusyId] = useState(null);
  const [errors, setErrors] = useState({});
  const [notice, setNotice] = useState('');
  const answering = useRef(false);
  const tabRefs = useRef({});
  // Requests answered since the current list fetch began. That fetch may have been
  // answered by the server before the answer landed, so it can still list them.
  const answeredSinceFetch = useRef(new Set());

  useEffect(() => {
    const controller = new AbortController();
    answeredSinceFetch.current = new Set();
    setLoading(true);
    setError('');
    Promise.all([
      listConnectionRequests('incoming', { signal: controller.signal }),
      listConnectionRequests('outgoing', { signal: controller.signal }),
    ]).then(([inbound, outbound]) => {
      if (controller.signal.aborted) return;
      setIncoming(inbound.filter((row) => !answeredSinceFetch.current.has(row.id)));
      setOutgoing(outbound);
    }).catch((failure) => {
      if (failure.name === 'AbortError' || controller.signal.aborted) return;
      setError(failure.message || 'Could not load your requests.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [version]);

  async function answer(id, action) {
    if (answering.current) return; // one answer at a time, so a double click cannot send two
    answering.current = true;
    setBusyId(id);
    setErrors((current) => ({ ...current, [id]: '' }));
    setNotice('');
    const request = incoming.find((row) => row.id === id);
    try {
      const result = await respondToRequest(id, action);
      answeredSinceFetch.current.add(id);
      setIncoming((rows) => rows.filter((row) => row.id !== id));
      setNotice(action === 'accept' ? `You are now connected with ${request?.sender.name || 'them'}.` : 'Request declined.');
      notifyRequestsChanged();
      if (action === 'accept') onAccepted?.(result.conversation_id);
    } catch (failure) {
      setErrors((current) => ({ ...current, [id]: failure.message || 'Could not answer this request.' }));
      // Someone else already answered it, or it is gone: the list is out of date.
      if (failure.status === 404 || failure.status === 409) setVersion((value) => value + 1);
    } finally {
      answering.current = false;
      setBusyId(null);
    }
  }

  const onKeyDown = (event) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const index = TABS.findIndex((item) => item.id === tab);
    const next = TABS[(index + step + TABS.length) % TABS.length].id;
    setTab(next);
    tabRefs.current[next]?.focus();
  };

  const rows = tab === 'incoming' ? incoming : outgoing;

  return (
    <section className="requests-section" aria-labelledby="requests-heading">
      <div className="section-heading">
        <h2 id="requests-heading">Connection requests</h2>
        <button type="button" className="button-secondary" disabled={loading} onClick={() => setVersion((value) => value + 1)}>Refresh requests</button>
      </div>
      <div className="tabs" role="tablist" aria-label="Request direction" onKeyDown={onKeyDown}>
        {TABS.map((item) => (
          <button
            key={item.id}
            ref={(node) => { tabRefs.current[item.id] = node; }}
            type="button"
            role="tab"
            id={`${item.id}-tab`}
            aria-selected={tab === item.id}
            aria-controls="requests-panel"
            tabIndex={tab === item.id ? 0 : -1}
            onClick={() => setTab(item.id)}
          >
            {item.label} <span>{item.id === 'incoming' ? incoming.length : outgoing.length}</span>
          </button>
        ))}
      </div>
      <div id="requests-panel" role="tabpanel" aria-labelledby={`${tab}-tab`}>
        {error && (
          <p role="alert" className="feedback feedback-error">
            {error} <button type="button" className="button-secondary" onClick={() => setVersion((value) => value + 1)}>Retry requests</button>
          </p>
        )}
        {loading && !error && rows.length === 0 && <p className="empty-state" role="status">Loading requests…</p>}
        {!error && !(loading && rows.length === 0) && (
          <RequestQueue requests={rows} direction={tab} onAccept={(id) => answer(id, 'accept')} onDecline={(id) => answer(id, 'decline')} busyId={busyId} errors={errors} />
        )}
      </div>
      <p className="local-notice" aria-live="polite">{notice}</p>
    </section>
  );
}
