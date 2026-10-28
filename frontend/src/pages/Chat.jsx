import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { listConversations, listMessages, orderMessages, sendMessage } from '../api/chat';
import { useAuth } from '../auth/AuthProvider';
import ChatWindow from '../components/ChatWindow';
import ConnectionRequests from '../components/ConnectionRequests';
import ConversationListItem from '../components/ConversationListItem';

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
      if (!controller.signal.aborted) setThreads((current) => ({ ...current, [id]: { messages: mergeHistory(messages, current[id]?.messages), loading: false, error: '' } }));
    }).catch((error) => {
      if (!controller.signal.aborted) setThreads((current) => ({ ...current, [id]: { ...current[id], loading: false, error: error.message } }));
    });
    return () => controller.abort();
  }, [active?.id, threadVersion]);

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

  return <main className="main-content live-chat-page">
    <div className="section-heading"><div><h1>Messages</h1><p>Continue a conversation with an accepted connection.</p></div><button className="button-secondary" disabled={listLoading} onClick={() => setListVersion((value) => value + 1)}>Refresh conversations</button></div>
    {listError && <p role="alert" className="feedback feedback-error">{listError} <button className="button-secondary" onClick={() => setListVersion((value) => value + 1)}>Retry conversations</button></p>}
    <ConnectionRequests onAccepted={(id) => { setListVersion((value) => value + 1); navigate(`/chat/${id}`); }} />
    <div className="chat-layout">
      <aside className="conversation-sidebar" aria-label="Conversation list"><div className="sidebar-heading">Messages <span>{conversations.length}</span></div>
        {listLoading && <p role="status" className="empty-state">Loading conversations…</p>}
        {!listLoading && !listError && !conversations.length && <p className="empty-state">No conversations yet. An accepted connection starts a conversation.</p>}
        {conversations.map((row) => <ConversationListItem key={row.id} conversation={row} selected={row.id === selectedId} onSelect={(id) => navigate(`/chat/${id}`)} />)}
      </aside>
      {active ? <ChatWindow key={active.id} conversation={active} messages={threads[selectedId]?.messages || []} currentUser={{ id: user.id, name: 'You' }}
        onSend={compose} loading={!!threads[selectedId]?.loading || !threads[selectedId]} error={threads[selectedId]?.error}
        onReload={() => setThreadVersion((value) => value + 1)} onRetry={(message) => submit(active.id, message)} />
        : <section className="chat-window empty-state" aria-label="Conversation"><p>{listLoading ? 'Loading…' : selectedId && !listError ? 'This conversation is unavailable.' : 'Select a conversation to see its messages.'}</p></section>}
    </div>
  </main>;
}
