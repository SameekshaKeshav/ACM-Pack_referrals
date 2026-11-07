import { useEffect, useRef, useState } from 'react';
import { listPeople } from '../../api/directory';
import { getSession } from '../../auth/session';
import { useConnectionStates } from '../../connections/useConnectionStates';
import ConnectDialog from '../ConnectDialog';
import FilterSidebar from './FilterSidebar';
import PersonCard from './PersonCard';

const countText = (count) => (count === 1 ? '1 member found' : `${count} members found`);

// The people directory: filters on the left, matching members on the right.
// GET /api/accounts/users/ does the filtering; this only builds the query.
// With `companyId`, only people connected to that company (current or past).
const PeopleDirectory = ({ companyId = null }) => {
  const [majors, setMajors] = useState([]);
  const [gradYear, setGradYear] = useState('');
  const [people, setPeople] = useState([]);
  const [count, setCount] = useState(null);
  const [announcement, setAnnouncement] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const generation = useRef(0);
  const myId = getSession()?.user?.id ?? null;
  const { states, mark, reload } = useConnectionStates();
  const [connecting, setConnecting] = useState(null);
  const [sentNotice, setSentNotice] = useState('');

  const majorsKey = [...majors].sort().join('|');

  useEffect(() => {
    const controller = new AbortController();
    const mine = ++generation.current;
    setLoading(true);
    setError('');
    listPeople({ majors, gradYear, companyId, signal: controller.signal })
      .then(({ count: total, results }) => {
        if (generation.current !== mine) return;
        setPeople(results);
        setCount(total);
        // The status region is only updated here, so a screen reader hears the
        // new total once per search, not while it loads.
        setAnnouncement(countText(total));
        setLoading(false);
      })
      .catch((failure) => {
        if (failure.name === 'AbortError' || generation.current !== mine) return;
        setError(failure.message || 'Could not load the directory. Please try again.');
        setLoading(false);
      });
    return () => controller.abort();
    // `majors` is covered by majorsKey, which changes whenever the selection does.
  }, [majorsKey, gradYear, companyId, attempt]);

  const showMore = async () => {
    const mine = generation.current;
    setLoadingMore(true);
    try {
      const page = await listPeople({ majors, gradYear, companyId, offset: people.length });
      if (generation.current !== mine) return;
      setPeople((current) => {
        const seen = new Set(current.map((person) => person.user_id));
        return [...current, ...page.results.filter((person) => !seen.has(person.user_id))];
      });
      setCount(page.count);
    } catch (failure) {
      if (generation.current === mine) setError(failure.message || 'Could not load more members.');
    } finally {
      setLoadingMore(false);
    }
  };

  const clear = () => { setMajors([]); setGradYear(''); };
  const hasMore = count !== null && people.length < count;

  return (
    <section className="directory-layout" aria-labelledby="people-heading">
      <FilterSidebar
        majors={majors}
        gradYear={gradYear}
        onMajorsChange={setMajors}
        onGradYearChange={setGradYear}
        onClear={clear}
      />

      <div className="people-results">
        <div className="section-heading">
          <h2 id="people-heading">Members</h2>
          <p className="meta" role="status" aria-live="polite">{announcement}</p>
        </div>

        {error && (
          <div className="feedback feedback-error" role="alert">
            {error}{' '}
            <button type="button" className="button-secondary" onClick={() => setAttempt((value) => value + 1)}>Try again</button>
          </div>
        )}

        {!error && loading && people.length === 0 && <p className="empty-state">Loading members…</p>}
        {!error && !loading && count === 0 && (
          <p className="empty-state">{majors.length || gradYear ? 'No members match these filters. Try removing one.' : 'No members are listed for this company yet.'}</p>
        )}

        {people.length > 0 && (
          <ul className="people-grid" aria-busy={loading}>
            {people.map((person) => (
              <PersonCard key={person.user_id} person={person} isMe={person.user_id === myId}
                state={states.get(person.user_id) || null} onConnect={(target) => { setSentNotice(''); setConnecting(target); }} />
            ))}
          </ul>
        )}

        <p className="local-notice" aria-live="polite">{sentNotice}</p>

        {connecting && (
          <ConnectDialog
            person={connecting}
            onClose={() => setConnecting(null)}
            onConflict={reload}
            onSent={() => { mark(connecting.user_id, { kind: 'sent' }); setSentNotice(`Request sent to ${connecting.name}.`); setConnecting(null); }}
          />
        )}

        {hasMore && !error && (
          <button type="button" className="button-secondary show-more" onClick={showMore} disabled={loadingMore || loading}>
            {loadingMore ? 'Loading…' : `Show more (${people.length} of ${count})`}
          </button>
        )}
      </div>
    </section>
  );
};

export default PeopleDirectory;
