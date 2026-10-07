export default function MessageBubble({ message, isOwn, senderName }) {
  return <li className={`message-row ${isOwn ? 'message-own' : ''}`}>
    <div className="message-bubble"><span className="sr-only">{senderName}: </span>{message.body_text}</div>
    <span className="message-time">{message.created_at}</span>
  </li>;
}
