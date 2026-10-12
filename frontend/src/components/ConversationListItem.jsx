import Avatar from './Avatar';

export default function ConversationListItem({ conversation, selected, onSelect }) {
  return <button className={`conversation-item ${selected ? 'selected' : ''}`} aria-pressed={selected} onClick={() => onSelect(conversation.id)}>
    <Avatar name={conversation.other_user.name} small />
    <span className="conversation-copy"><span className="conversation-name">{conversation.other_user.name}</span><span className="meta">{conversation.other_user.company}</span><span className="preview">{conversation.last_message}</span></span>
    <span className="conversation-extra"><span className="meta">{conversation.updated_at}</span>{conversation.unread_count > 0 && <span className="unread" aria-label={`${conversation.unread_count} unread messages`}>{conversation.unread_count}</span>}</span>
  </button>;
}
