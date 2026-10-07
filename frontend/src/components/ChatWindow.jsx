import { useState } from 'react';
import Avatar from './Avatar';
import MessageBubble from './MessageBubble';

export default function ChatWindow({ conversation, messages, currentUser }) {
  const [draft, setDraft] = useState('');
  return <section className="chat-window" aria-label={`Conversation with ${conversation.other_user.name}`}>
    <header className="chat-header"><Avatar name={conversation.other_user.name} small /><div><h3>{conversation.other_user.name}</h3><p className="meta">{conversation.other_user.role} · {conversation.other_user.company}</p></div><span className="connected-label">Connected</span></header>
    <div className="thread"><p className="thread-date">Today · Demo conversation</p>
      {messages.length ? <ol className="messages" aria-label="Messages">{messages.map((message) => <MessageBubble key={message.id} message={message} isOwn={message.sender_id === currentUser.id} senderName={message.sender_id === currentUser.id ? currentUser.name : conversation.other_user.name} />)}</ol> : <p className="empty-state">No placeholder messages in this conversation.</p>}
    </div>
    <div className="chat-composer"><label htmlFor="chat-message" className="sr-only">Chat message</label><textarea id="chat-message" rows="2" maxLength={2000} placeholder={`Message ${conversation.other_user.name.split(' ')[0]}…`} value={draft} onChange={(e) => setDraft(e.target.value)} /><button className="button-primary" disabled title="Message sending is part of the next integration task">Send</button></div>
    <p className="composer-note">Static chat preview · message sending is not connected yet.</p>
  </section>;
}
