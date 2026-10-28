import { Link } from 'react-router-dom';
import Avatar from '../Avatar';

// `state` is what we know about my link to this person (see useConnectionStates);
// `isMe` hides the actions on my own card; `onConnect` opens the request dialog.
const PersonCard = ({ person, state = null, isMe = false, onConnect }) => {
  const company = person.current_company;
  const details = [person.major, person.grad_year ? `Class of ${person.grad_year}` : ''].filter(Boolean).join(' · ');

  let action = null;
  if (isMe) {
    action = <span className="status">You</span>;
  } else if (state?.kind === 'connected') {
    action = <Link className="button-secondary" to={state.conversationId ? `/chat/${state.conversationId}` : '/chat'} aria-label={`Message ${person.name}`}>Message</Link>;
  } else if (state?.kind === 'sent') {
    action = <button type="button" className="button-secondary" disabled aria-label={`Connection request sent to ${person.name}`}>Request sent</button>;
  } else if (state?.kind === 'received') {
    action = <Link className="button-primary" to="/chat" aria-label={`Respond to the request from ${person.name}`}>Respond</Link>;
  } else if (person.open_to_connect) {
    action = <button type="button" className="button-primary" onClick={() => onConnect(person)} aria-label={`Connect with ${person.name}`}>Connect</button>;
  }

  return (
    <li className="person-card">
      <div className="person-row">
        <Avatar name={person.name} />
        <div className="person-copy">
          <h3>{person.name}</h3>
          {(person.current_role || company) && (
            <p>
              {person.current_role}
              {person.current_role && company ? ' at ' : ''}
              {company && <Link to={`/company/${company.id}`}>{company.name}</Link>}
            </p>
          )}
          {details && <p>{details}</p>}
        </div>
      </div>
      <div className="person-footer">
        <p className="meta person-availability">{state?.kind === 'connected' ? 'Connected' : person.open_to_connect ? 'Open to connect' : 'Not taking requests right now'}</p>
        {action}
      </div>
    </li>
  );
};

export default PersonCard;
