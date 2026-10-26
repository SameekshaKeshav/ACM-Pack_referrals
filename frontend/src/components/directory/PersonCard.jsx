import { Link } from 'react-router-dom';
import Avatar from '../Avatar';

const PersonCard = ({ person }) => {
  const company = person.current_company;
  const details = [person.major, person.grad_year ? `Class of ${person.grad_year}` : ''].filter(Boolean).join(' · ');

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
      <p className="meta person-availability">{person.open_to_connect ? 'Open to connect' : 'Not taking requests right now'}</p>
    </li>
  );
};

export default PersonCard;
