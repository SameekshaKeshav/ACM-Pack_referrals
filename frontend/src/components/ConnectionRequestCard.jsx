import Avatar from './Avatar';

export default function ConnectionRequestCard({ request, direction = 'incoming', onAccept, onDecline }) {
  const person = direction === 'incoming' ? request.sender : request.recipient;
  return (
    <article className="request-card" aria-label={`Request ${direction === 'incoming' ? 'from' : 'to'} ${person.name}`}>
      <div className="person-row">
        <Avatar name={person.name} />
        <div className="person-copy"><h3>{person.name}</h3><p>{person.company}</p></div>
        <span className={`status status-${request.status}`}>{request.status}</span>
      </div>
      {person.role && <p className="meta role">{person.role}</p>}
      <p className="request-note">{request.message_text}</p>
      <div className="card-footer"><span className="meta">{request.created_at}</span>
        {direction === 'incoming' && <div className="actions">
          <button className="button-secondary" onClick={() => onDecline(request.id)} aria-label={`Decline ${person.name}`}>Decline</button>
          <button className="button-primary" onClick={() => onAccept(request.id)} aria-label={`Accept ${person.name}`}>Accept</button>
        </div>}
      </div>
    </article>
  );
}
