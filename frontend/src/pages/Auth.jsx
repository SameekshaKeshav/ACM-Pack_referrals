import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { publicRequest } from '../api/client';
import { useAuth } from '../auth/AuthProvider';
import { safeDestination, signIn } from '../auth/session';

const PENDING = 'pack-referrals.pending-auth';
function readPending() {
  try {
    const value = JSON.parse(sessionStorage.getItem(PENDING));
    return value && typeof value.email === 'string' && ['signup', 'login'].includes(value.mode) ? value : null;
  } catch { return null; }
}
function rememberPending(value) { try { sessionStorage.setItem(PENDING, JSON.stringify(value)); } catch { /* Navigation state remains usable. */ } }
function AuthShell({ title, children }) {
  return <main className="auth-shell"><Link className="brand" to="/login"><span className="brand-mark">PR</span>Pack Referrals</Link><section className="auth-card"><h1>{title}</h1>{children}</section></main>;
}

export function EmailPage({ mode }) {
  const { session } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const busy = useRef(false);
  const request = useRef(null);
  useEffect(() => () => request.current?.abort(), []);
  const destination = safeDestination(location.state?.from);
  if (session) return <Navigate to={destination} replace />;

  async function submit(event) {
    event.preventDefault();
    if (busy.current) return;
    busy.current = true; setPending(true); setError('');
    const normalized = email.trim().toLowerCase();
    const controller = new AbortController(); request.current = controller;
    try {
      await publicRequest(`/api/accounts/auth/${mode}/`, { method: 'POST', body: { email: normalized }, signal: controller.signal });
      if (controller.signal.aborted) return;
      const next = { email: normalized, mode, from: destination };
      rememberPending(next);
      navigate('/enter-code', { state: next });
    } catch (err) { if (!controller.signal.aborted) setError(err.message); }
    finally { busy.current = false; setPending(false); }
  }

  const signup = mode === 'signup';
  return <AuthShell title={signup ? 'Create your account' : 'Welcome back'}>
    <p>Use your NC State email. We will email you a sign-in code; no password is needed.</p>
    <form onSubmit={submit}>
      <label htmlFor="auth-email">University email</label>
      <input id="auth-email" type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} disabled={pending} placeholder="you@ncsu.edu" />
      {error && <p role="alert" className="feedback feedback-error">{error}</p>}
      <button className="button-primary" disabled={pending}>{pending ? 'Sending code…' : signup ? 'Sign up' : 'Send login code'}</button>
    </form>
    <p>{signup ? 'Already have an account?' : 'New to Pack Referrals?'} <Link to={signup ? '/login' : '/signup'} state={{ from: destination }}>{signup ? 'Log in' : 'Sign up'}</Link></p>
  </AuthShell>;
}

export function EnterCodePage() {
  const { session } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [details] = useState(() => location.state?.email ? location.state : readPending());
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [pending, setPending] = useState('');
  const busy = useRef(false);
  const request = useRef(null);
  useEffect(() => () => request.current?.abort(), []);
  if (session) return <Navigate to={safeDestination(details?.from)} replace />;
  if (!details) return <Navigate to="/login" replace />;

  async function verify(event) {
    event.preventDefault();
    if (busy.current) return;
    if (!/^\d{6}$/.test(code)) { setError('Enter the six-digit code from your email.'); return; }
    busy.current = true; setPending('verify'); setError(''); setNotice('');
    const controller = new AbortController(); request.current = controller;
    try {
      const tokens = await publicRequest('/api/accounts/auth/verify/', { method: 'POST', body: { email: details.email, code }, signal: controller.signal });
      if (controller.signal.aborted) return;
      signIn(tokens);
      try { sessionStorage.removeItem(PENDING); } catch { /* No stored code or token here. */ }
      navigate(safeDestination(details.from), { replace: true });
    } catch (err) { if (!controller.signal.aborted) setError(err.message); }
    finally { busy.current = false; setPending(''); }
  }

  async function resend() {
    if (busy.current) return;
    busy.current = true; setPending('resend'); setError(''); setNotice('');
    const controller = new AbortController(); request.current = controller;
    try {
      await publicRequest(`/api/accounts/auth/${details.mode === 'signup' ? 'signup' : 'login'}/`, { method: 'POST', body: { email: details.email }, signal: controller.signal });
      if (controller.signal.aborted) return;
      setNotice('If this account can receive a code, a new one has been sent. Check your inbox.');
    } catch (err) { if (!controller.signal.aborted) setError(err.message); }
    finally { busy.current = false; setPending(''); }
  }

  return <AuthShell title="Check your email">
    <p>{details.mode === 'login' ? 'If your account exists, a code has been sent to' : 'Enter the code sent to'} <strong>{details.email}</strong>.</p>
    <form onSubmit={verify}>
      <label htmlFor="email-code">Six-digit code</label>
      <input id="email-code" type="text" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" required value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))} disabled={!!pending} />
      {error && <p role="alert" className="feedback feedback-error">{error}</p>}
      {notice && <p role="status" className="feedback">{notice}</p>}
      <button className="button-primary" disabled={!!pending}>{pending === 'verify' ? 'Verifying…' : 'Verify and sign in'}</button>
      <button type="button" className="button-secondary" disabled={!!pending} onClick={resend}>{pending === 'resend' ? 'Sending…' : 'Resend code'}</button>
    </form>
    <Link to={details.mode === 'signup' ? '/signup' : '/login'} state={{ from: safeDestination(details.from) }}>Use a different email</Link>
  </AuthShell>;
}
