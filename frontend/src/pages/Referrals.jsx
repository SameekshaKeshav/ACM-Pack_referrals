import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { listConversations } from '../api/chat';
import { searchCompanies } from '../api/companies';
import { createReferral, listReferrals, REFERRAL_PAGE_SIZE, safeReferralUrl } from '../api/referrals';

const emptyFields = { recipientId: '', companyId: '', role: '', jobUrl: '', resumeUrl: '', message: '' };
const length = (text) => Array.from(text).length;

function ReferralForm({ initialRecipient, onCreated }) {
  const [fields, setFields] = useState({ ...emptyFields, recipientId: initialRecipient });
  const [people, setPeople] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [companyError, setCompanyError] = useState('');
  const [version, setVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const flight = useRef(null);

  useEffect(() => () => flight.current?.abort(), []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setLoadError(''); setCompanyError('');
    listConversations({ signal: controller.signal }).then((rows) => {
      if (!controller.signal.aborted) setPeople([...new Map(rows.map((row) => [row.other_user.id, row.other_user])).values()]);
    }).catch((failure) => { if (!controller.signal.aborted) setLoadError(failure.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    searchCompanies({ signal: controller.signal }).then((rows) => { if (!controller.signal.aborted) setCompanies(rows); })
      .catch(() => { if (!controller.signal.aborted) setCompanyError('Company choices could not load. You can leave company unspecified or reload the choices.'); });
    return () => controller.abort();
  }, [version]);

  function change(key, value) {
    setFields((current) => ({ ...current, [key]: value }));
    setError(''); setConflict(false);
  }
  async function submit(event) {
    event.preventDefault();
    if (flight.current || conflict) return;
    if (!people.some((person) => String(person.id) === fields.recipientId)) { setError('Choose an accepted connection.'); return; }
    if (!fields.role.trim() || length(fields.role.trim()) > 255 || !fields.message.trim() || length(fields.message) > 500) {
      setError('Enter a role up to 255 characters and a message up to 500 characters.'); return;
    }
    if ([fields.jobUrl, fields.resumeUrl].some((url) => url.trim() && (length(url.trim()) > 500 || !safeReferralUrl(url.trim())))) {
      setError('Use complete http or https links, up to 500 characters each.'); return;
    }
    const controller = new AbortController(); flight.current = controller;
    setBusy(true); setError('');
    try {
      const saved = await createReferral(fields, { signal: controller.signal });
      if (controller.signal.aborted) return;
      setFields({ ...emptyFields, recipientId: fields.recipientId });
      onCreated(saved);
    } catch (failure) {
      if (!controller.signal.aborted) {
        setConflict(failure.status === 409);
        setError(failure.status === 409 ? 'You already have a pending referral request for this role and company with this connection. Check your outgoing asks before creating another.' : failure.message);
      }
    } finally {
      flight.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return <section className="referral-panel" aria-labelledby="referral-form-heading">
    <h2 id="referral-form-heading">Ask for a referral</h2>
    <p>Choose someone you are already connected with. Explain the role and why you fit.</p>
    {loading && <p role="status">Loading connections…</p>}
    {loadError && <p role="alert" className="feedback feedback-error">{loadError} <button type="button" onClick={() => setVersion((value) => value + 1)}>Reload choices</button></p>}
    {companyError && <p role="status">{companyError} <button type="button" onClick={() => setVersion((value) => value + 1)}>Reload company choices</button></p>}
    {!loading && !loadError && !people.length && <p className="empty-state">No accepted connections yet. <Link to="/chat">Manage your connection requests</Link> first.</p>}
    <form onSubmit={submit}>
      <fieldset disabled={busy || loading || !!loadError || !people.length}>
        <legend className="visually-hidden">Referral request details</legend>
        <label htmlFor="referral-person">Accepted connection (required)</label>
        <select id="referral-person" required value={fields.recipientId} onChange={(event) => change('recipientId', event.target.value)}>
          <option value="">Choose a connection</option>{people.map((person) => <option key={person.id} value={person.id}>{person.name}</option>)}
        </select>
        <label htmlFor="referral-company">Company (optional)</label>
        <select id="referral-company" value={fields.companyId} onChange={(event) => change('companyId', event.target.value)} aria-describedby="referral-company-help">
          <option value="">Company unspecified</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.name}</option>)}
        </select>
        <p id="referral-company-help" className="meta">Choose a company on this connection’s current or past profile. The server checks eligibility.</p>
        <label htmlFor="referral-role">Role title (required)</label>
        <input id="referral-role" required value={fields.role} onChange={(event) => change('role', Array.from(event.target.value).slice(0, 255).join(''))} />
        <label htmlFor="referral-job">Job link (optional)</label>
        <input id="referral-job" type="url" value={fields.jobUrl} onChange={(event) => change('jobUrl', event.target.value)} placeholder="https://…" />
        <label htmlFor="referral-resume">Résumé link (optional)</label>
        <input id="referral-resume" type="url" value={fields.resumeUrl} onChange={(event) => change('resumeUrl', event.target.value)} placeholder="https://…" />
        <label htmlFor="referral-note">Why you fit (required)</label>
        <textarea id="referral-note" required rows="5" value={fields.message} aria-describedby="referral-note-count" onChange={(event) => change('message', Array.from(event.target.value).slice(0, 500).join(''))} />
        <p id="referral-note-count" className="meta" aria-live="polite">{500 - length(fields.message)} characters remaining</p>
        <button className="button-primary" disabled={busy || conflict || !fields.role.trim() || !fields.message.trim() || !people.some((person) => String(person.id) === fields.recipientId)}>{busy ? 'Sending referral request…' : 'Send referral request'}</button>
      </fieldset>
      {error && <p role="alert" className="feedback feedback-error">{error}</p>}
    </form>
  </section>;
}

function ReferralList({ direction, version }) {
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState({ count: 0, results: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    listReferrals(direction, { offset, signal: controller.signal }).then((data) => {
      if (!controller.signal.aborted) {
        if (offset > 0 && offset >= data.count) setOffset(0);
        else setPage(data);
      }
    }).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [direction, offset, version, reload]);
  const incoming = direction === 'incoming';
  return <section className="referral-panel" aria-label={incoming ? 'Incoming referral requests' : 'Outgoing referral requests'}>
    <div className="section-heading"><h2>{incoming ? 'Incoming asks' : 'Outgoing asks'}</h2><button className="button-secondary" disabled={loading} onClick={() => setReload((value) => value + 1)}>Refresh asks</button></div>
    {loading ? <p role="status">Loading referral requests…</p> : error ? <p role="alert" className="feedback feedback-error">{error} <button onClick={() => setReload((value) => value + 1)}>Retry loading asks</button></p> : <>
      {!page.results.length && <p className="empty-state">No {direction} referral requests yet.</p>}
      {page.results.map((row) => <article className="referral-card" key={row.id} aria-label={`Referral ${incoming ? 'from' : 'to'} ${(incoming ? row.sender : row.recipient).name}`}>
        <h3>{row.role_title}</h3><p>{incoming ? 'From' : 'To'}: {(incoming ? row.sender : row.recipient).name}</p>
        {row.company && <p>Company: {row.company.name}</p>}<p>Status: <strong>{row.status}</strong></p>
        <p className="referral-note">{row.message_text}</p>
        <div className="referral-links">{row.job_url && <a href={row.job_url} target="_blank" rel="noopener noreferrer">View job</a>}{row.resume_url && <a href={row.resume_url} target="_blank" rel="noopener noreferrer">View résumé</a>}</div>
        <p className="meta"><time dateTime={row.created_at}>{new Date(row.created_at).toLocaleString()}</time></p>
      </article>)}
      {page.count > 0 && <nav className="referral-pagination" aria-label="Referral pages"><button disabled={offset === 0} onClick={() => setOffset((value) => Math.max(0, value - REFERRAL_PAGE_SIZE))}>Previous</button><span>{offset + 1}–{Math.min(offset + page.results.length, page.count)} of {page.count}</span><button disabled={offset + REFERRAL_PAGE_SIZE >= page.count} onClick={() => setOffset((value) => value + REFERRAL_PAGE_SIZE)}>Next</button></nav>}
    </>}
  </section>;
}

export default function Referrals() {
  const [params] = useSearchParams();
  const [direction, setDirection] = useState('outgoing');
  const [version, setVersion] = useState(0);
  const [notice, setNotice] = useState('');
  const initialRecipient = params.get('recipient') || '';
  return <main className="main-content referrals-page">
    <h1>Referral requests</h1><p>A referral ask is separate from a connection request. Only accepted connections can receive an ask.</p>
    <p role="status" className="local-notice">{notice}</p>
    <div className="referral-layout"><ReferralForm key={initialRecipient} initialRecipient={initialRecipient} onCreated={() => { setNotice('Referral request sent. You can find it in your outgoing asks.'); setDirection('outgoing'); setVersion((value) => value + 1); }} />
      <div><div className="referral-directions" role="group" aria-label="Referral direction">{['outgoing', 'incoming'].map((item) => <button key={item} aria-pressed={direction === item} onClick={() => setDirection(item)}>{item === 'incoming' ? 'Incoming' : 'Outgoing'}</button>)}</div>
        <ReferralList key={`${direction}-${version}`} direction={direction} version={version} />
      </div></div>
  </main>;
}
