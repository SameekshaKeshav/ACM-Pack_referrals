import { useEffect, useRef, useState } from 'react';
import { createExperience, deleteExperience, EXPERIENCE_OUTCOMES, listExperiences } from '../api/experiences';
import { ReportButton } from './SafetyActions';

const initialFields = { role: '', outcome: '', difficulty: '', process: '' };
const count = (value) => Array.from(value).length;
const limit = (value, max) => Array.from(value).slice(0, max).join('');

export default function InterviewExperiences({ companyId }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [unavailable, setUnavailable] = useState(false);
  const [version, setVersion] = useState(0);
  const [fields, setFields] = useState(initialFields);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [confirmation, setConfirmation] = useState(null);
  const [removing, setRemoving] = useState(null);
  const post = useRef(null);
  const deletion = useRef(null);
  const mutationVersion = useRef(0);
  const title = useRef(null);
  const summary = useRef(null);
  const listHeading = useRef(null);
  const deleteOpeners = useRef({});
  const restoreDeleteFocus = useRef(null);
  useEffect(() => {
    if (confirmation === null && restoreDeleteFocus.current !== null) {
      deleteOpeners.current[restoreDeleteFocus.current]?.focus();
      restoreDeleteFocus.current = null;
    }
  }, [confirmation]);

  useEffect(() => () => { post.current?.abort(); deletion.current?.abort(); }, []);
  useEffect(() => {
    const controller = new AbortController();
    const revision = mutationVersion.current;
    setLoading(true); setLoadError(''); setUnavailable(false);
    listExperiences(companyId, { signal: controller.signal }).then((data) => {
      if (!controller.signal.aborted && revision === mutationVersion.current) setRows(data);
    }).catch((failure) => {
      if (controller.signal.aborted) return;
      setUnavailable(failure.status === 404 || failure.status === 501);
      setLoadError(failure.status === 404 || failure.status === 501
        ? 'Interview experiences are not available for this company yet. You can still browse members.' : failure.message);
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [companyId, version]);

  function change(key, value) { setFields((current) => ({ ...current, [key]: value })); setError(''); }
  async function submit(event) {
    event.preventDefault();
    if (post.current || loading || unavailable || loadError) return;
    if (!fields.role.trim() || !fields.process.trim() || !Object.hasOwn(EXPERIENCE_OUTCOMES, fields.outcome) || !['1', '2', '3', '4', '5'].includes(fields.difficulty)) {
      setError('Complete all fields. Role and interview process must contain more than spaces.');
      summary.current?.focus(); return;
    }
    const controller = new AbortController(); post.current = controller;
    setSending(true); setError(''); setNotice('');
    try {
      const saved = await createExperience(companyId, fields, { signal: controller.signal });
      if (controller.signal.aborted) return;
      mutationVersion.current++;
      setRows((current) => [saved, ...current.filter((row) => row.id !== saved.id)]);
      setFields(initialFields);
      setNotice('Your interview experience has been posted anonymously to other members.');
      title.current?.focus();
    } catch (failure) {
      if (!controller.signal.aborted) { setError(failure.message); summary.current?.focus(); }
    } finally { post.current = null; if (!controller.signal.aborted) setSending(false); }
  }
  async function remove(row) {
    if (deletion.current) return;
    const controller = new AbortController(); deletion.current = controller;
    setRemoving(row.id); setError(''); setNotice('');
    try {
      try {
        await deleteExperience(companyId, row.id, { signal: controller.signal });
      } catch (failure) {
        if (failure.status !== 404) throw failure;
        // Another session already removed it. The desired state is the same.
      }
      if (controller.signal.aborted) return;
      mutationVersion.current++;
      setRows((current) => current.filter((item) => item.id !== row.id));
      setConfirmation(null); setNotice('Your interview experience was deleted.');
      listHeading.current?.focus();
    } catch (failure) {
      if (!controller.signal.aborted) { setError(failure.message); summary.current?.focus(); }
    } finally { deletion.current = null; if (!controller.signal.aborted) setRemoving(null); }
  }

  return <section className="experiences-section" aria-labelledby="experiences-heading">
    <div className="section-heading"><h2 id="experiences-heading" ref={listHeading} tabIndex={-1}>Interview experiences</h2>
      <button className="button-secondary" disabled={loading || sending || removing !== null} onClick={() => setVersion((value) => value + 1)}>Refresh experiences</button></div>
    <p>Learn about the interview process from other members. Posts show a role and month, without an author name.</p>
    <p className="feedback" role="status">{notice}</p>
    <p className={error ? 'feedback feedback-error' : 'visually-hidden'} role="alert" tabIndex={-1} ref={summary}>{error}</p>
    {loading && <p role="status">Loading interview experiences…</p>}
    {loadError && <p role="alert" className="feedback feedback-error">{loadError} <button className="button-secondary" onClick={() => setVersion((value) => value + 1)}>Try loading experiences again</button></p>}
    {!loading && !loadError && <>
      {!rows.length && <p className="empty-state">No interview experiences yet. Be the first to share.</p>}
      <ul className="experience-list" aria-label="Interview experiences">{rows.map((row) => <li key={row.id}>
        <article className="experience-card" aria-labelledby={`experience-${row.id}`}>
          <h3 id={`experience-${row.id}`}>{row.role_title}</h3>
          <p className="meta">Anonymous member{row.is_mine ? ' · Your post' : ''} · <time dateTime={`${String(row.year).padStart(4, '0')}-${String(row.month).padStart(2, '0')}`}>{new Date(Date.UTC(row.year, row.month - 1)).toLocaleDateString(undefined, { month: 'long', year: 'numeric', timeZone: 'UTC' })}</time></p>
          <dl className="experience-details"><div><dt>Outcome</dt><dd>{EXPERIENCE_OUTCOMES[row.outcome]}</dd></div><div><dt>Difficulty</dt><dd>{row.difficulty} out of 5</dd></div></dl>
          <p className="experience-process">{row.process_text}</p>
          {!row.is_mine && <ReportButton targetType="experience" targetId={row.id} subject={`the ${row.role_title} experience`} />}
          {row.is_mine && (confirmation === row.id ? <div className="experience-confirmation" role="group" aria-label={`Delete your ${row.role_title} experience?`}>
            <p>Delete this experience? This cannot be undone.</p><button className="button-secondary" disabled={removing !== null} onClick={() => { restoreDeleteFocus.current = row.id; setConfirmation(null); }}>Keep experience</button>
            <button className="button-primary" disabled={removing !== null} onClick={() => remove(row)}>{removing === row.id ? 'Deleting…' : 'Confirm delete'}</button>
          </div> : <button className="button-secondary" ref={(node) => { deleteOpeners.current[row.id] = node; }} disabled={removing !== null} onClick={() => setConfirmation(row.id)}>Delete my {row.role_title} experience</button>)}
        </article>
      </li>)}</ul>
    </>}
    <form className="experience-form" onSubmit={submit} aria-labelledby="share-experience-heading">
      <h3 id="share-experience-heading" tabIndex={-1} ref={title}>Share an interview experience</h3>
      <p id="experience-privacy">Your identity is hidden from other members. Moderators can access authorship. Avoid names, contact details and confidential interview material in your post.</p>
      <fieldset disabled={sending || loading || !!loadError} aria-describedby="experience-privacy">
        <legend className="visually-hidden">All experience fields are required</legend>
        <label htmlFor="experience-role">Role title (required)</label><input id="experience-role" required value={fields.role} onChange={(event) => change('role', limit(event.target.value, 255))} autoComplete="off" />
        <label htmlFor="experience-outcome">Outcome (required)</label><select id="experience-outcome" required value={fields.outcome} onChange={(event) => change('outcome', event.target.value)}><option value="">Choose an outcome</option>{Object.entries(EXPERIENCE_OUTCOMES).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select>
        <label htmlFor="experience-difficulty">Difficulty (required)</label><select id="experience-difficulty" required value={fields.difficulty} onChange={(event) => change('difficulty', event.target.value)}><option value="">Choose difficulty</option>{[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}{value === 1 ? ' — Easiest' : value === 5 ? ' — Hardest' : ''}</option>)}</select>
        <label htmlFor="experience-process">Interview process (required)</label><textarea id="experience-process" required rows="6" value={fields.process} aria-describedby="experience-process-count experience-privacy" onChange={(event) => change('process', limit(event.target.value, 5000))} />
        <p id="experience-process-count" className="meta" aria-live="polite">{5000 - count(fields.process)} characters remaining</p>
        <button className="button-primary" disabled={sending}>{sending ? 'Posting experience…' : 'Post experience'}</button>
      </fieldset>
    </form>
  </section>;
}
