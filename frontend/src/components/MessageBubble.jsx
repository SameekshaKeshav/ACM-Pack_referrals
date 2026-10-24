export function displayTime(value) {
  return Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : value;
}
export default function MessageBubble({ message, isOwn, senderName, onRetry }) {
  return <li className={`message-row ${isOwn ? 'message-own' : ''} ${message.delivery ? `message-${message.delivery}` : ''}`}>
    <div className="message-bubble"><span className="sr-only">{senderName}: </span>{message.body_text}</div>
    <span className="message-time">{displayTime(message.created_at)} {message.delivery === 'pending' && <span role="status">Sending…</span>}</span>
    {message.delivery === 'failed' && <div className="message-failure" role="alert">{message.error || 'Message not sent.'} <button className="button-secondary" onClick={() => onRetry?.(message)}>Retry message</button></div>}
  </li>;
}
