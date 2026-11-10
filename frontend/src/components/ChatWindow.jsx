import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import Avatar from './Avatar';
import MessageBubble from './MessageBubble';

export default function ChatWindow({ conversation, messages, currentUser, onSend, loading, error, onReload, onRetry, pollError, onPollRetry, focusOnReady, onFocused }) {
  const [draft, setDraft] = useState('');
  const thread = useRef(null);
  const composer = useRef(null);
  useEffect(() => {
    if (focusOnReady && !loading && !error) { composer.current?.focus(); onFocused?.(); }
  }, [focusOnReady, loading, error, onFocused]);
  const follow = useRef(true);
  const seen = useRef(null);
  const [announcement, setAnnouncement] = useState(null);
  useEffect(() => {
    if (loading || error) return;
    const saved = messages.filter((row) => typeof row.id === 'number');
    if (seen.current === null) { seen.current = new Set(saved.map((row) => row.id)); return; }
    const fresh = saved.filter((row) => !seen.current.has(row.id) && row.sender_id !== currentUser.id);
    saved.forEach((row) => seen.current.add(row.id));
    if (fresh.length) setAnnouncement({ id: fresh[fresh.length - 1].id,
      text: `${fresh.length === 1 ? 'New message' : `${fresh.length} new messages`} from ${conversation.other_user.name}: ${fresh[fresh.length - 1].body_text}` });
  }, [messages, loading, error, currentUser.id, conversation.other_user.name]);
  const live = typeof onSend === 'function';
  useLayoutEffect(() => {
    if (thread.current && follow.current) thread.current.scrollTop = thread.current.scrollHeight;
  }, [messages]);
  function send(event) {
    event.preventDefault();
    if (!live || loading || error || !draft.trim()) return;
    follow.current = true;
    if (onSend(draft) !== false) setDraft('');
  }
  return <section className="chat-window" aria-label={`Conversation with ${conversation.other_user.name}`}>
    <header className="chat-header"><Avatar name={conversation.other_user.name} small /><div><h3>{conversation.other_user.name}</h3><p className="meta">{[conversation.other_user.role, conversation.other_user.company].filter(Boolean).join(' · ')}</p></div><span className="connected-label">Connected</span></header>
    <p className="sr-only" aria-live="polite" aria-atomic="true">{announcement && <span key={announcement.id}>{announcement.text}</span>}</p>
    {pollError && <p role="alert" className="feedback feedback-error">New messages could not be checked. {pollError} <button className="button-secondary" onClick={onPollRetry}>Retry updates</button></p>}
    <div className="thread" role="region" aria-label="Message history" tabIndex={0} ref={thread} onScroll={() => { const node = thread.current; follow.current = node.scrollHeight - node.scrollTop - node.clientHeight < 80; }} aria-busy={!!loading}><p className="thread-date">{live ? 'Message history' : 'Today · Demo conversation'}</p>
      {loading && <p role="status">Loading message history…</p>}
      {error && <p role="alert" className="feedback feedback-error">{error} <button className="button-secondary" onClick={onReload}>Retry history</button></p>}
      {messages.length ? <ol className="messages" aria-label="Messages">{messages.map((message) => <MessageBubble key={message.client_id || message.id} message={message} isOwn={message.sender_id === currentUser.id} senderName={message.sender_id === currentUser.id ? currentUser.name : conversation.other_user.name} onRetry={onRetry} />)}</ol> : !loading && !error && <p className="empty-state">{live ? 'No messages yet. Say hello!' : 'No placeholder messages in this conversation.'}</p>}
    </div>
    <form className="chat-composer" onSubmit={send}><label htmlFor="chat-message" className="sr-only">Chat message</label><textarea ref={composer} id="chat-message" rows="2" placeholder={`Message ${conversation.other_user.name.split(' ')[0]}…`} value={draft} onChange={(e) => setDraft(live ? Array.from(e.target.value).slice(0, 2000).join('') : e.target.value.slice(0, 2000))} /><button className="button-primary" disabled={!live || !!loading || !!error || !draft.trim()} title={live ? 'Send message' : 'Message sending is part of the next integration task'}>Send</button></form>
    <p className="composer-note">{live ? `${2000 - Array.from(draft).length} characters remaining · messages appear immediately while sending` : 'Static chat preview · message sending is not connected yet.'}</p>
  </section>;
}
