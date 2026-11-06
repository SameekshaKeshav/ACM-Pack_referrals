import { useEffect, useRef, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { ALUMNI_FIELDS, ALUMNI_LIMITS, UNITY_ID_PATTERN, requestAlumniAccess } from '../api/alumni';
import { useAuth } from '../auth/AuthProvider';
import { AuthShell } from './Auth';

const EMPTY = { email: '', full_name: '', unity_id: '', grad_year: '', major: '', linkedin_url: '', note: '' };
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function isWebAddress(value) {
  try { return ['http:', 'https:'].includes(new URL(value).protocol); } catch { return false; }
}

// Checks the same rules as the backend, so the person sees a problem next to the
// field instead of after a round trip. The backend still checks everything.
export function validate(fields) {
  const errors = {};
  const email = fields.email.trim();
  if (!email) errors.email = 'Enter your email address.';
  else if (!EMAIL_PATTERN.test(email)) errors.email = 'Enter a valid email address, like you@example.com.';
  const name = fields.full_name.trim();
  if (!name) errors.full_name = 'Enter your full name.';
  else if (name.length > ALUMNI_LIMITS.fullName) errors.full_name = `Use ${ALUMNI_LIMITS.fullName} characters or fewer.`;
  const unity = fields.unity_id.trim();
  if (!unity) errors.unity_id = 'Enter your Unity ID.';
  else if (!UNITY_ID_PATTERN.test(unity) || unity.length > ALUMNI_LIMITS.unityId) {
    errors.unity_id = 'A Unity ID is letters and digits, starting with a letter, like jdoe or jdoe2.';
  }
  const year = fields.grad_year.trim();
  if (!year) errors.grad_year = 'Enter your graduation year.';
  else if (!/^\d{4}$/.test(year) || Number(year) < 1900 || Number(year) > 2100) errors.grad_year = 'Enter a four-digit graduation year, like 2019.';
  const major = fields.major.trim();
  if (!major) errors.major = 'Enter your major.';
  else if (major.length > ALUMNI_LIMITS.major) errors.major = `Use ${ALUMNI_LIMITS.major} characters or fewer.`;
  const linkedin = fields.linkedin_url.trim();
  if (linkedin && (!isWebAddress(linkedin) || linkedin.length > ALUMNI_LIMITS.linkedin)) {
    errors.linkedin_url = 'Enter a web address starting with https://, or leave this empty.';
  }
  if (fields.note.trim().length > ALUMNI_LIMITS.note) errors.note = `Use ${ALUMNI_LIMITS.note} characters or fewer.`;
  return errors;
}

// The backend reports field mistakes as { field: ["message"] }. Put each one next
// to its input; anything else goes in the general message.
function fromServer(data) {
  const errors = {};
  for (const key of ALUMNI_FIELDS) {
    const message = Array.isArray(data?.[key]) ? data[key][0] : null;
    if (typeof message === 'string') errors[key] = message;
  }
  return errors;
}

function Field({ id, label, hint, error, children }) {
  const describedBy = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(' ') || undefined;
  return <>
    <label htmlFor={id}>{label}</label>
    {children({ id, name: id, 'aria-invalid': error ? 'true' : undefined, 'aria-describedby': describedBy })}
    {hint && <p id={`${id}-hint`} className="meta field-hint">{hint}</p>}
    {error && <p id={`${id}-error`} className="field-error">{error}</p>}
  </>;
}

export default function AlumniRequestPage() {
  const { session } = useAuth();
  const [fields, setFields] = useState(EMPTY);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState('');
  const [pending, setPending] = useState(false);
  const [confirmation, setConfirmation] = useState('');
  const [toFocus, setToFocus] = useState(null);
  const busy = useRef(false);
  const request = useRef(null);
  const form = useRef(null);
  const confirmationHeading = useRef(null);
  useEffect(() => () => request.current?.abort(), []);
  useEffect(() => { if (confirmation) confirmationHeading.current?.focus(); }, [confirmation]);
  // Focus waits until the inputs are enabled again: a disabled input cannot take focus.
  useEffect(() => {
    if (toFocus && !pending) { form.current?.elements[toFocus]?.focus(); setToFocus(null); }
  }, [toFocus, pending]);
  if (session) return <Navigate to="/chat" replace />;

  const set = (key) => (event) => {
    setFields((current) => ({ ...current, [key]: event.target.value }));
    setErrors((current) => (current[key] ? { ...current, [key]: undefined } : current));
  };
  const focusFirst = (found) => {
    const first = ALUMNI_FIELDS.find((key) => found[key]);
    if (first) setToFocus(first);
  };

  async function submit(event) {
    event.preventDefault();
    if (busy.current) return;
    const found = validate(fields);
    setFormError('');
    if (Object.keys(found).length) { setErrors(found); focusFirst(found); return; }
    busy.current = true; setPending(true); setErrors({});
    const controller = new AbortController(); request.current = controller;
    try {
      const detail = await requestAlumniAccess(
        { ...fields, confirm_email: form.current.elements.confirm_email?.value ?? '' },
        { signal: controller.signal },
      );
      if (controller.signal.aborted) return;
      setFields(EMPTY); // do not keep a stranger's details in memory once they are sent
      setConfirmation(detail);
    } catch (err) {
      if (controller.signal.aborted) return;
      const mapped = err.status === 400 ? fromServer(err.data) : {};
      if (Object.keys(mapped).length) { setErrors(mapped); focusFirst(mapped); }
      else setFormError(err.message);
    } finally { busy.current = false; setPending(false); }
  }

  if (confirmation) {
    return <AuthShell title="Request received" headingRef={confirmationHeading}>
      <p role="status">{confirmation}</p>
      <p>The team reviews requests by hand, and we do not send an email about the decision yet. When it is approved, <Link to="/signup">sign up</Link> with the same email address you used here.</p>
      <p><Link to="/login">Back to log in</Link></p>
    </AuthShell>;
  }

  const text = (key, extra = {}) => ({ type: 'text', value: fields[key], onChange: set(key), disabled: pending, ...extra });
  return <AuthShell title="Request alumni access">
    <p>Sign-up is open to current NC State students with an @ncsu.edu email. If you are an alum, tell us a little about yourself and the team will review your request by hand. Please do not send a Student ID number.</p>
    <form ref={form} onSubmit={submit} noValidate>
      <Field id="email" label="Email address (required)" hint="Any email address you check. You will sign in with it if approved." error={errors.email}>
        {(props) => <input {...props} {...text('email', { type: 'email', autoComplete: 'email', placeholder: 'you@example.com' })} />}
      </Field>
      <Field id="full_name" label="Full name (required)" error={errors.full_name}>
        {(props) => <input {...props} {...text('full_name', { autoComplete: 'name', maxLength: ALUMNI_LIMITS.fullName })} />}
      </Field>
      <Field id="unity_id" label="Unity ID (required)" hint="Letters and digits, starting with a letter, like jdoe or jdoe2." error={errors.unity_id}>
        {(props) => <input {...props} {...text('unity_id', { autoComplete: 'off', autoCapitalize: 'none', spellCheck: false, maxLength: ALUMNI_LIMITS.unityId })} />}
      </Field>
      <Field id="grad_year" label="Graduation year (required)" hint="Four digits, like 2019." error={errors.grad_year}>
        {(props) => <input {...props} {...text('grad_year', { inputMode: 'numeric', autoComplete: 'off', maxLength: 4 })} />}
      </Field>
      <Field id="major" label="Major (required)" error={errors.major}>
        {(props) => <input {...props} {...text('major', { autoComplete: 'off', maxLength: ALUMNI_LIMITS.major })} />}
      </Field>
      <Field id="linkedin_url" label="LinkedIn profile (optional)" hint="Helps the team check your request." error={errors.linkedin_url}>
        {(props) => <input {...props} {...text('linkedin_url', { type: 'url', autoComplete: 'url', placeholder: 'https://www.linkedin.com/in/...', maxLength: ALUMNI_LIMITS.linkedin })} />}
      </Field>
      <Field id="note" label="Anything else the team should know (optional)" hint={`${ALUMNI_LIMITS.note - fields.note.length} characters remaining.`} error={errors.note}>
        {(props) => <textarea {...props} rows="4" value={fields.note} onChange={set('note')} disabled={pending} maxLength={ALUMNI_LIMITS.note} />}
      </Field>
      {/* Spam trap: real people never see or fill this in, so a bot that does is ignored. */}
      <div className="honeypot" aria-hidden="true">
        <label htmlFor="confirm_email">Leave this field empty</label>
        <input id="confirm_email" name="confirm_email" type="text" defaultValue="" tabIndex={-1} autoComplete="off" />
      </div>
      {formError && <p role="alert" className="feedback feedback-error">{formError}</p>}
      <button className="button-primary" disabled={pending}>{pending ? 'Sending request…' : 'Send request'}</button>
    </form>
    <p>Current NC State student? <Link to="/signup">Sign up</Link> or <Link to="/login">log in</Link>.</p>
  </AuthShell>;
}
