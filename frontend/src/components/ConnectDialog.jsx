import { useEffect, useId, useRef, useState } from 'react';
import { connectErrorText, sendConnectionRequest } from '../api/connections';
import { capMessage, characterCount } from './SendRequestForm';

const FOCUSABLE = 'button:not([disabled]), textarea:not([disabled]), a[href], input:not([disabled])';

// A modal that asks for a short note and sends the connection request.
// `onSent(result)` runs after a 201; `onConflict()` after a 409 (so the page can
// refresh what it knows); `onClose()` for Cancel, Escape, or a click outside.
export default function ConnectDialog({ person, onSent, onConflict, onClose }) {
  const titleId = useId();
  const counterId = useId();
  const dialogRef = useRef(null);
  const noteRef = useRef(null);
  const sending = useRef(false);
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const remaining = 500 - characterCount(message);

  // Focus goes into the dialog on open and back to the button that opened it on close.
  useEffect(() => {
    const opener = document.activeElement;
    noteRef.current?.focus();
    return () => { if (opener instanceof HTMLElement && opener.isConnected) opener.focus(); };
  }, []);

  const onKeyDown = (event) => {
    if (event.key === 'Escape' && !pending) {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== 'Tab') return;
    const items = [...dialogRef.current.querySelectorAll(FOCUSABLE)];
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  };

  async function submit(event) {
    event.preventDefault();
    if (sending.current) return;
    if (!message.trim()) { setError('Add a short note before sending.'); noteRef.current?.focus(); return; }
    sending.current = true;
    setPending(true);
    setError('');
    try {
      const result = await sendConnectionRequest({ recipientId: person.user_id, messageText: message });
      onSent(result);
    } catch (failure) {
      setError(connectErrorText(failure));
      if (failure.status === 409) onConflict?.();
    } finally {
      sending.current = false;
      setPending(false);
    }
  }

  return (
    <div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !pending) onClose(); }}>
      <div ref={dialogRef} className="dialog" role="dialog" aria-modal="true" aria-labelledby={titleId} onKeyDown={onKeyDown}>
        <form onSubmit={submit}>
          <h2 id={titleId}>Connect with {person.name}</h2>
          <p className="meta">A short, personal note goes a long way. They can accept or decline.</p>
          <label htmlFor={`${titleId}-note`}>Your note</label>
          <textarea
            id={`${titleId}-note`}
            ref={noteRef}
            rows="4"
            value={message}
            disabled={pending}
            onChange={(event) => setMessage(capMessage(event.target.value))}
            aria-describedby={counterId}
            placeholder="Hi! I’m a fellow NC State student interested in…"
          />
          <p id={counterId} className={`meta ${remaining === 0 ? 'limit-reached' : ''}`} aria-live="polite">{remaining} remaining</p>
          {error && <p className="feedback feedback-error" role="alert">{error}</p>}
          <div className="dialog-actions">
            <button type="button" className="button-secondary" onClick={onClose} disabled={pending}>Cancel</button>
            <button type="submit" className="button-primary" disabled={pending}>{pending ? 'Sending…' : 'Send request'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
