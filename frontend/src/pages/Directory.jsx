import { useEffect, useState } from 'react';
import { searchCompanies } from '../api/companies';
import SearchBar from '../components/directory/SearchBar';
import CompanyCard from '../components/directory/CompanyCard';

const SEARCH_DELAY_MS = 250;
const countText = (count) => (count === 1 ? '1 company found' : `${count} companies found`);

// Step one of the directory: find a company. Picking one opens its page, which
// has the members, interview experiences and so on (pages/Company.jsx).
const Directory = () => {
  const [search, setSearch] = useState('');
  const [companies, setCompanies] = useState([]);
  const [announcement, setAnnouncement] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    // Wait for a pause in typing; the first load (empty box) goes straight out.
    const timer = setTimeout(() => {
      setLoading(true);
      setError('');
      searchCompanies({ search, signal: controller.signal })
        .then((rows) => {
          if (controller.signal.aborted) return;
          setCompanies(rows);
          setAnnouncement(countText(rows.length));
          setLoading(false);
        })
        .catch((failure) => {
          if (failure.name === 'AbortError' || controller.signal.aborted) return;
          setError(failure.message || 'Could not load companies. Please try again.');
          setLoading(false);
        });
    }, search ? SEARCH_DELAY_MS : 0);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [search, attempt]);

  return (
    <main className="main-content">
      <div className="page-heading">
        <div>
          <p className="eyebrow">NC STATE NETWORK</p>
          <h1>Directory</h1>
          <p>Find a company, then see the NC State members who work or have worked there.</p>
        </div>
      </div>

      <SearchBar value={search} onChange={setSearch} />
      <p className="meta company-count" role="status" aria-live="polite">{announcement}</p>

      {error && (
        <div className="feedback feedback-error" role="alert">
          {error}{' '}
          <button type="button" className="button-secondary" onClick={() => setAttempt((value) => value + 1)}>Try again</button>
        </div>
      )}
      {!error && loading && companies.length === 0 && <p className="empty-state">Loading companies…</p>}
      {!error && !loading && companies.length === 0 && (
        <p className="empty-state">No companies match “{search.trim()}”. Check the spelling or try a shorter name.</p>
      )}
      {companies.length > 0 && (
        <ul className="company-grid" aria-busy={loading}>
          {companies.map((company) => <CompanyCard key={company.id} company={company} />)}
        </ul>
      )}
    </main>
  );
};

export default Directory;
