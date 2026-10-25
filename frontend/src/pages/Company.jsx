import { useEffect, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { getCompany } from '../api/companies';
import PeopleDirectory from '../components/directory/PeopleDirectory';

// Step two of the directory. To add a tab, add an entry here and a panel below.
// The active tab lives in the URL (?tab=interviews) so a link opens that tab.
const TABS = [
  { id: 'members', label: 'Members' },
  { id: 'interviews', label: 'Interview experiences' },
];

const Company = () => {
  // useParams reads the :id from the URL
  const { id } = useParams();
  const companyId = /^[1-9]\d*$/.test(id) ? Number(id) : null;
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = searchParams.get('tab');
  const active = TABS.some((tab) => tab.id === requested) ? requested : TABS[0].id;

  const [company, setCompany] = useState(null);
  const [error, setError] = useState('');
  const [notFound, setNotFound] = useState(companyId === null);
  const tabRefs = useRef({});

  useEffect(() => {
    if (companyId === null) return undefined;
    const controller = new AbortController();
    setCompany(null);
    setError('');
    setNotFound(false);
    getCompany(companyId, { signal: controller.signal })
      .then((row) => { if (!controller.signal.aborted) setCompany(row); })
      .catch((failure) => {
        if (failure.name === 'AbortError' || controller.signal.aborted) return;
        if (failure.status === 404) setNotFound(true);
        else setError(failure.message || 'Could not load this company. Please try again.');
      });
    return () => controller.abort();
  }, [companyId]);

  const selectTab = (tabId, { focus = false } = {}) => {
    setSearchParams({ tab: tabId }, { replace: true });
    if (focus) tabRefs.current[tabId]?.focus();
  };

  // Arrow keys move between tabs, as screen-reader users expect of a tablist.
  const onKeyDown = (event) => {
    const focused = TABS.findIndex((tab) => tabRefs.current[tab.id] === event.target);
    const index = focused === -1 ? TABS.findIndex((tab) => tab.id === active) : focused;
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (step) {
      event.preventDefault();
      selectTab(TABS[(index + step + TABS.length) % TABS.length].id, { focus: true });
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      selectTab(TABS[event.key === 'Home' ? 0 : TABS.length - 1].id, { focus: true });
    }
  };

  if (notFound) {
    return (
      <main className="main-content">
        <p className="empty-state">That company could not be found.</p>
        <Link to="/directory">Back to the directory</Link>
      </main>
    );
  }

  return (
    <main className="main-content">
      <p className="meta"><Link to="/directory">← All companies</Link></p>

      {error && <div className="feedback feedback-error" role="alert">{error}</div>}

      <div className="page-heading company-heading">
        <div>
          <p className="eyebrow">{company?.industry_tag || 'COMPANY'}</p>
          <h1>{company ? company.name : 'Loading…'}</h1>
        </div>
      </div>

      <div className="tabs" role="tablist" aria-label="Company sections" onKeyDown={onKeyDown}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            ref={(node) => { tabRefs.current[tab.id] = node; }}
            type="button"
            role="tab"
            id={`tab-${tab.id}`}
            aria-selected={active === tab.id}
            aria-controls={`panel-${tab.id}`}
            tabIndex={active === tab.id ? 0 : -1}
            onClick={() => selectTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${active}`} aria-labelledby={`tab-${active}`}>
        {active === 'members' && companyId !== null && <PeopleDirectory companyId={companyId} />}
        {active === 'interviews' && (
          <p className="empty-state">
            Interview experiences will appear here: how the process went, the rounds, and what was asked.
          </p>
        )}
      </div>
    </main>
  );
};

export default Company;
