import { useEffect, useRef, useState } from 'react';
import { blockUser, REPORT_DETAILS_LIMIT, REPORT_REASONS, sendReport, unblockUser } from '../api/safety';

// A Report button that opens a short form under it. `subject` finishes the
// sentence "Report ..." for people using a screen reader, for example
// "Sanjana" or "the Software Engineer experience".
export function ReportButton({ targetType, targetId, subject }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [details, setDetails] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);
  const opener = useRef(null);
  const firstField = useRef(null);
  const flight = useRef(false);
  const mounted = useRef(true);
  // Set true on every mount: React's dev StrictMode mounts, unmounts and mounts again.
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { if (open) firstField.current?.focus(); }, [open]);

  function close() { setOpen(false); setError(''); requestAnimationFrame(() => opener.current?.focus()); }

  async function submit(event) {
    event.preventDefault();
    if (flight.current || !reason) return;
    flight.current = true; setBusy(true); setError('');
    try {
      await sendReport({ targetType, targetId, reason, details });
      if (!mounted.current) return;
      setSent(true); setOpen(false); setReason(''); setDetails('');
    } catch (failure) {
      if (mounted.current) setError(failure.message || 'Could not send the report. Please try again.');
    } finally { flight.current = false; if (mounted.current) setBusy(false); }
  }

  return <div className="safety-control">
    {sent
      ? <p className="feedback" role="status">Thanks. Your report was sent to the moderators.</p>
      : <button type="button" className="button-secondary" ref={opener} aria-expanded={open} aria-label={`Report ${subject}`} onClick={() => (open ? close() : setOpen(true))}>Report</button>}
    {open && <form className="safety-form" onSubmit={submit} aria-label={`Report ${subject}`}>
      <label htmlFor={`report-reason-${targetType}-${targetId}`}>Reason (required)</label>
      <select id={`report-reason-${targetType}-${targetId}`} ref={firstField} required value={reason} onChange={(event) => setReason(event.target.value)}>
        <option value="">Choose a reason</option>
        {Object.entries(REPORT_REASONS).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select>
      <label htmlFor={`report-details-${targetType}-${targetId}`}>Details (optional)</label>
      <textarea id={`report-details-${targetType}-${targetId}`} rows="3" maxLength={REPORT_DETAILS_LIMIT} value={details} onChange={(event) => setDetails(event.target.value)} />
      {error && <p role="alert" className="feedback feedback-error">{error}</p>}
      <div className="safety-form-actions">
        <button type="button" className="button-secondary" disabled={busy} onClick={close}>Cancel</button>
        <button className="button-primary" disabled={busy || !reason}>{busy ? 'Sending report…' : 'Send report'}</button>
      </div>
    </form>}
  </div>;
}

// A Block button that asks first. Blocking hides the conversation for both
// people on the server, so the page that owns the conversation list is told
// through `onBlocked`.
export function BlockButton({ userId, name, onBlocked }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const opener = useRef(null);
  const confirmButton = useRef(null);
  const flight = useRef(false);
  const mounted = useRef(true);
  // Set true on every mount: React's dev StrictMode mounts, unmounts and mounts again.
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { if (confirming) confirmButton.current?.focus(); }, [confirming]);

  function cancel() { setConfirming(false); setError(''); requestAnimationFrame(() => opener.current?.focus()); }

  async function confirm() {
    if (flight.current) return;
    flight.current = true; setBusy(true); setError('');
    try {
      await blockUser(userId);
      if (mounted.current) setConfirming(false);
      onBlocked?.();
    } catch (failure) {
      if (mounted.current) setError(failure.message || 'Could not block this person. Please try again.');
    } finally { flight.current = false; if (mounted.current) setBusy(false); }
  }

  return <div className="safety-control">
    {!confirming && <button type="button" className="button-secondary" ref={opener} aria-label={`Block ${name}`} onClick={() => setConfirming(true)}>Block</button>}
    {confirming && <div className="safety-form" role="group" aria-label={`Block ${name}?`}>
      <p>Block {name}? This conversation will be hidden for both of you, and they will not be able to message you or send you requests.</p>
      {error && <p role="alert" className="feedback feedback-error">{error}</p>}
      <div className="safety-form-actions">
        <button type="button" className="button-secondary" disabled={busy} onClick={cancel}>Keep conversation</button>
        <button type="button" className="button-primary" ref={confirmButton} disabled={busy} onClick={confirm}>{busy ? 'Blocking…' : `Block ${name}`}</button>
      </div>
    </div>}
  </div>;
}

// Shown right after a block, so a mis-click can be undone. The conversation
// list does not show blocked people, so this is the one place to unblock.
export function BlockedNotice({ userId, name, onUnblocked }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const flight = useRef(false);
  const mounted = useRef(true);
  // Set true on every mount: React's dev StrictMode mounts, unmounts and mounts again.
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  async function undo() {
    if (flight.current) return;
    flight.current = true; setBusy(true); setError('');
    try {
      await unblockUser(userId);
      // The page replaces this notice when someone else is blocked. A late answer
      // for the earlier person must not overwrite the newer notice.
      if (mounted.current) onUnblocked?.();
    } catch (failure) {
      if (mounted.current) setError(failure.message || `Could not unblock ${name}. Please try again.`);
    } finally { flight.current = false; if (mounted.current) setBusy(false); }
  }

  return <div className="safety-control">
    <p role="status" className="feedback">You blocked {name}. Their conversation is hidden.</p>
    {error && <p role="alert" className="feedback feedback-error">{error}</p>}
    <button type="button" className="button-secondary" disabled={busy} onClick={undo}>{busy ? 'Unblocking…' : `Unblock ${name}`}</button>
  </div>;
}
