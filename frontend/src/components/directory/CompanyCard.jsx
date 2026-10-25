import { Link } from 'react-router-dom';

// One search result. The whole card is a single link to the company page.
const CompanyCard = ({ company }) => (
  <li className="company-card">
    <Link to={`/company/${company.id}`}>
      <span className="company-mark" aria-hidden="true">{company.name.slice(0, 1).toUpperCase()}</span>
      <span className="company-card-copy">
        <strong>{company.name}</strong>
        {company.industry_tag && <span className="meta">{company.industry_tag}</span>}
      </span>
    </Link>
  </li>
);

export default CompanyCard;
