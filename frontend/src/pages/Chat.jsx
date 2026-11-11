import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { listConversations, listMessages, orderMessages, pollMessages, sendMessage } from '../api/chat';
import { useAuth } from '../auth/AuthProvider';
import ChatWindow from '../components/ChatWindow';
import ConnectionRequests from '../components/ConnectionRequests';
import ConversationListItem from '../components/ConversationListItem';
import { BlockButton, BlockedNotice, ReportButton } from '../components/SafetyActions';

export function mergeHistory(history, current = []) {
  const rows = new Map(history.map((row) => [row.id, row]));
  current.forEach((row) => rows.set(row.id, row));
  return orderMessages([...rows.values()]);
}

export default function Chat() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { conversationId } = useParams();
  const selectedId = conversationId ? Number(conversationId) : null;
  const [conversations, setConversations] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState('');
  const [listVersion, setListVersion] = useState(0);
  const [threads, setThreads] = useState({});
  const [threadVersion, setThreadVersion] = useState(0);
  const [pollVersion, setPollVersion] = useState(0);
  const [focusConversation, setFocusConversation] = useState(null);
  const [blocked, setBlocked] = useState(null);
  const threadSnapshot = useRef(threads);
  threadSnapshot.current = threads;
  const mounted = useRef(false);
  const sending = useRef(new Set());
  const active = conversations.find((row) => row.id === selectedId);

  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    const controller = new AbortController();
    setListLoading(true); setListError('');
    listConversations({ signal: controller.signal }).then((rows) => {
      if (!controller.signal.aborted) setConversations(rows);
    }).catch((error) => { if (!controller.signal.aborted) setListError(error.message); })
      .finally(() => { if (!controller.signal.aborted) setListLoading(false); });
    return () => controller.abort();
  }, [listVersion]);

  useEffect(() => {
    if (!conversationId && conversations.length) navigate(`/chat/${conversations[0].id}`, { replace: true });
  }, [conversationId, conversations, navigate]);

  useEffect(() => {
    if (!active) return;
    const id = active.id;
    const controller = new AbortController();
    setThreads((current) => ({ ...current, [id]: { ...current[id], loading: true, error: '' } }));
    listMessages(id, { signal: controller.signal }).then((messages) => {
      if (!controller.signal.aborted) setThreads((current) => ({ ...current, [id]: { messages: mergeHistory(messages, current[id]?.messages), cursor: messages.reduce((max, row) => Math.max(max, row.id), 0), loading: false, error: '', pollError: '' } }));
    }).catch((error) => {
      if (!controller.signal.aborted) setThreads((current) => ({ ...current, [id]: { ...current[id], loading: false, error: error.message } }));
    });
    return () => controller.abort();
  }, [active?.id, threadVersion]);

  const historyReady = !!active && !!threads[selectedId] && !threads[selectedId].loading && !threads[selectedId].error;
  useEffect(() => {
    if (!historyReady) return;
    const id = active.id;
    const controller = new AbortController();
    let timer;
    let running = false;
    let failures = 0;
    async function poll() {
      if (running || controller.signal.aborted) return;
      clearTimeout(timer);
      if (document.visibilityState === 'hidden') { timer = setTimeout(poll, 3000); return; }
      running = true;
      try {
        const cursor = threadSnapshot.current[id]?.cursor || 0;
        const incoming = await pollMessages(id, cursor, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setThreads((current) => {
          const thread = current[id];
          const known = new Set(thread.messages.map((row) => row.id));
          // GET can see a sent message before its POST acknowledgement arrives.
          const waiting = thread.messages.some((row) => row.delivery === 'pending');
          const deferred = incoming.filter((row) => waiting && row.sender_id === user.id && !known.has(row.id));
          const deferredIds = new Set(deferred.map((row) => row.id));
          const safe = incoming.filter((row) => !deferredIds.has(row.id));
          const last = incoming.reduce((max, row) => Math.max(max, row.id), cursor);
          return { ...current, [id]: { ...thread, messages: mergeHistory(safe, thread.messages),
            cursor: deferred.length ? deferred.reduce((min, row) => Math.min(min, row.id), Infinity) - 1 : last, pollError: '' } };
        });
        if (incoming.length) preview(id, incoming[incoming.length - 1]);
        failures = 0;
      } catch (error) {
        if (!controller.signal.aborted) {
          failures += 1;
          setThreads((current) => ({ ...current, [id]: { ...current[id], pollError: error.message } }));
        }
      } finally {
        running = false;
        if (!controller.signal.aborted) timer = setTimeout(poll, Math.min(30000, 3000 * 2 ** failures));
      }
    }
    function resume() { if (document.visibilityState !== 'hidden') poll(); }
    if (pollVersion) poll(); else timer = setTimeout(poll, 3000);
    window.addEventListener('focus', resume);
    document.addEventListener('visibilitychange', resume);
    return () => { controller.abort(); clearTimeout(timer); window.removeEventListener('focus', resume); document.removeEventListener('visibilitychange', resume); };
  }, [active?.id, historyReady, pollVersion, user.id]);

  function preview(id, message) {
    setConversations((rows) => rows.map((row) => row.id === id && (Date.parse(message.created_at) || 0) >= (Date.parse(row.updated_at) || 0) ? { ...row, last_message: message.body_text, updated_at: message.created_at } : row)
      .sort((a, b) => (Date.parse(b.updated_at) || 0) - (Date.parse(a.updated_at) || 0)));
  }

  async function submit(id, message) {
    if (sending.current.has(message.id)) return;
    sending.current.add(message.id);
    setThreads((current) => ({ ...current, [id]: { ...current[id], messages: current[id].messages.map((row) => row.id === message.id ? { ...row, delivery: 'pending' } : row) } }));
    try {
      const saved = await sendMessage(id, message.body_text);
      if (!mounted.current) return;
      setThreads((current) => {
        const without = (current[id]?.messages || []).filter((row) => row.id !== message.id && row.id !== saved.id);
        return { ...current, [id]: { ...current[id], messages: orderMessages([...without, { ...saved, client_id: message.id }]) } };
      });
      preview(id, saved);
    } catch (error) {
      if (mounted.current) setThreads((current) => ({ ...current, [id]: { ...current[id], messages: current[id].messages.map((row) => row.id === message.id ? { ...row, delivery: 'failed', error: error.message } : row) } }));
    } finally { sending.current.delete(message.id); }
  }

  function compose(bodyText) {
    const id = selectedId;
    const thread = threads[id];
    if (!active || !thread || thread.loading || thread.error || !bodyText.trim() || Array.from(bodyText).length > 2000) return false;
    const message = { id: `local-${crypto.randomUUID()}`, sender_id: user.id, conversation_id: id, body_text: bodyText, created_at: new Date().toISOString(), delivery: 'pending' };
    setThreads((current) => ({ ...current, [id]: { ...current[id], messages: [...(current[id]?.messages || []), message] } }));
    preview(id, message);
    // Start after the optimistic state update; the queued updater sees the new row.
    submit(id, message);
    return true;
  }

  return <main id="main-content" tabIndex={-1} className="main-content live-chat-page">
    <div className="section-heading"><div><h1>Messages</h1><p>Continue a conversation with an accepted connection.</p></div><button className="button-secondary" disabled={listLoading} onClick={() => setListVersion((value) => value + 1)}>Refresh conversations</button></div>
    {listError && <p role="alert" className="feedback feedback-error">{listError} <button className="button-secondary" onClick={() => setListVersion((value) => value + 1)}>Retry conversations</button></p>}
    {blocked && !blocked.undone && <BlockedNotice key={blocked.id} userId={blocked.id} name={blocked.name} onUnblocked={() => { setBlocked({ ...blocked, undone: true }); setListVersion((value) => value + 1); }} />}
    {blocked?.undone && <p role="status" className="feedback">You unblocked {blocked.name}. Their conversation is back in your list.</p>}
    <ConnectionRequests onAccepted={(id) => { setFocusConversation(id); setListVersion((value) => value + 1); navigate(`/chat/${id}`); }} />
    <div className="chat-layout">
      <aside className="conversation-sidebar" aria-label="Conversation list"><div className="sidebar-heading">Messages <span>{conversations.length}</span></div>
        {listLoading && <p role="status" className="empty-state">Loading conversations…</p>}
        {!listLoading && !listError && !conversations.length && <p className="empty-state">No conversations yet. An accepted connection starts a conversation.</p>}
        {conversations.map((row) => <ConversationListItem key={row.id} conversation={row} selected={row.id === selectedId} onSelect={(id) => navigate(`/chat/${id}`)} />)}
      </aside>
      <div className="chat-thread-panel">{active && <p><Link to={`/referrals?recipient=${active.other_user.id}`}>Ask {active.other_user.name} for a referral</Link></p>}
      {active && <div className="safety-actions" key={`safety-${active.id}`}>
        <ReportButton targetType="user" targetId={active.other_user.id} subject={active.other_user.name} />
        <BlockButton userId={active.other_user.id} name={active.other_user.name} onBlocked={() => {
          setBlocked({ id: active.other_user.id, name: active.other_user.name, undone: false });
          setConversations((rows) => rows.filter((row) => row.id !== active.id));
          navigate('/chat');
          setListVersion((value) => value + 1);
        }} />
      </div>}
      {active ? <ChatWindow key={active.id} conversation={active} messages={threads[selectedId]?.messages || []} currentUser={{ id: user.id, name: 'You' }}
        onSend={compose} focusOnReady={focusConversation === active.id} onFocused={() => setFocusConversation(null)} loading={!!threads[selectedId]?.loading || !threads[selectedId]} error={threads[selectedId]?.error}
        pollError={threads[selectedId]?.pollError} onPollRetry={() => setPollVersion((value) => value + 1)}
        onReload={() => setThreadVersion((value) => value + 1)} onRetry={(message) => submit(active.id, message)} />
        : <section className="chat-window empty-state" aria-label="Conversation"><p>{listLoading ? 'Loading…' : selectedId && !listError ? 'This conversation is unavailable.' : 'Select a conversation to see its messages.'}</p></section>}
      </div>
    </div>
  </main>;
}
