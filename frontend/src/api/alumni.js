import { publicRequest } from './client';

// Public: an alum has no account yet, so no Authorization header is sent.
// Limits and rules mirror AlumniAccessRequest in accounts/models.py.
export const ALUMNI_LIMITS = { fullName: 150, unityId: 32, major: 255, linkedin: 200, note: 500 };
export const UNITY_ID_PATTERN = /^[A-Za-z][A-Za-z0-9]*$/;
export const ALUMNI_FIELDS = ['email', 'full_name', 'unity_id', 'grad_year', 'major', 'linkedin_url', 'note'];

const FALLBACK_DETAIL = 'Thanks - your request is with the team.';

// Returns the server's confirmation text. The backend answers 202 with the same
// text whether the request was stored, was a duplicate, or tripped the spam
// trap, so the page must not say anything more specific than this.
export async function requestAlumniAccess(fields, { signal } = {}) {
  const body = {
    email: fields.email.trim().toLowerCase(),
    full_name: fields.full_name.trim(),
    unity_id: fields.unity_id.trim(),
    grad_year: Number(fields.grad_year),
    major: fields.major.trim(),
    // The hidden spam-trap input. Real people leave it empty; bots fill it in.
    confirm_email: fields.confirm_email ?? '',
  };
  if (fields.linkedin_url.trim()) body.linkedin_url = fields.linkedin_url.trim();
  if (fields.note.trim()) body.note = fields.note.trim();
  const data = await publicRequest('/api/accounts/alumni-access-requests/', { method: 'POST', body, signal });
  return typeof data?.detail === 'string' && data.detail ? data.detail : FALLBACK_DETAIL;
}
