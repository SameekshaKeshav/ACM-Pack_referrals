import { useRef, useState } from 'react';
import { sendConnectionRequest } from '../api/connections';

// Python len() counts Unicode code points. Use the same rule for the live counter.
export const characterCount = (text) => Array.from(text).length;
export const capMessage = (text) => Array.from(text).slice(0, 500).join('');

export default function SendRequestForm({ accessToken, onCreated }) {
  const [recipientId, setRecipientId] = useState('');
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState(false);
  const [feedback, setFeedback] = useState(null);
  const sending = useRef(false);
  const remaining = 500 - characterCount(message);

  async function submit(event) {
    event.preventDefault();
    if (sending.current) return;
    const id = Number(recipientId);
    if (!Number.isSafeInteger(id) || id < 1) { setFeedback({ error: true, text: 'Enter a valid recipient user ID.' }); return; }
    if (!message.trim()) { setFeedback({ error: true, text: 'Add a short note before sending.' }); return; }
    if (!accessToken) { setFeedback({ error: true, text: 'Add an access token in the API test panel before sending.' }); return; }
    sending.current = true;
    setPending(true);
    setFeedback(null);
    try {
      const result = await sendConnectionRequest({ recipientId: id, messageText: message, accessToken });
      onCreated({ ...result, recipient: { id, name: `User ${id}`, company: 'Connection request' }, message_text: message, created_at: 'Just now' });
      setMessage('');
      setFeedback({ error: false, text: `Request #${result.id} sent. Status: ${result.status}.` });
    } catch (error) {
      setFeedback({ error: true, text: error.name === 'ApiError' ? error.message : 'Could not reach the server. Your note is saved here; try sending again.' });
    } finally { sending.current = false; setPending(false); }
  }

  return <form className="send-request-form" onSubmit={submit}>
    <div className="form-heading"><div><h3>Start a connection</h3><p className="meta">A short, personal note goes a long way.</p></div><span className="status">Live API</span></div>
    <label htmlFor="recipient-id">Recipient user ID</label><input id="recipient-id" type="number" min="1" step="1" required value={recipientId} onChange={(e) => setRecipientId(e.target.value)} placeholder="e.g. 31" disabled={pending} />
    <label htmlFor="request-note">Your note</label><textarea id="request-note" required rows="4" value={message} disabled={pending} onChange={(e) => setMessage(capMessage(e.target.value))} aria-describedby="note-counter" placeholder="Hi! I’m a fellow NC State student interested in…" />
    <div className="form-footer"><span id="note-counter" className={`meta ${remaining === 0 ? 'limit-reached' : ''}`} aria-live="polite">{remaining} remaining</span><button className="button-primary" type="submit" disabled={pending}>{pending ? 'Sending…' : 'Send Request'}</button></div>
    {feedback && <p className={`feedback ${feedback.error ? 'feedback-error' : ''}`} role={feedback.error ? 'alert' : 'status'}>{feedback.text}</p>}
  </form>;
}
