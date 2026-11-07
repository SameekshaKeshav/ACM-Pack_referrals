import Avatar from './Avatar';

// ISO timestamps from the API become "Oct 25"; anything else (the mock's "Just now") is shown as is.
export const whenText = (value) => {
  const time = Date.parse(value);
  return Number.isFinite(time) && /\d{4}-\d{2}-\d{2}/.test(String(value))
    ? new Date(time).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
    : String(value ?? '');
};

export default function ConnectionRequestCard({ request, direction = 'incoming', onAccept, onDecline, busy = false, error = '' }) {
  const person = direction === 'incoming' ? request.sender : request.recipient;
  return (
    <article className="request-card" aria-label={`Request ${direction === 'incoming' ? 'from' : 'to'} ${person.name}`} aria-busy={busy}>
      <div className="person-row">
        <Avatar name={person.name} />
        <div className="person-copy"><h3>{person.name}</h3>{person.company && <p>{person.company}</p>}</div>
        <span className={`status status-${request.status}`}>{request.status}</span>
      </div>
      {person.role && <p className="meta role">{person.role}</p>}
      <p className="request-note">{request.message_text}</p>
      {error && <p className="feedback feedback-error" role="alert">{error}</p>}
      <div className="card-footer"><span className="meta">{whenText(request.created_at)}</span>
        {direction === 'incoming' && <div className="actions">
          <button type="button" className="button-secondary" disabled={busy} onClick={() => onDecline(request.id)} aria-label={`Decline ${person.name}`}>Decline</button>
          <button type="button" className="button-primary" disabled={busy} onClick={() => onAccept(request.id)} aria-label={`Accept ${person.name}`}>{busy ? 'Working…' : 'Accept'}</button>
        </div>}
      </div>
    </article>
  );
}
