import { apiRequest, ApiError } from './client';

export const REFERRALS_ROUTE = '/api/connections/referrals/';
export const REFERRAL_PAGE_SIZE = 20;
const validId = (value) => Number.isSafeInteger(value) && value > 0;
const mismatch = () => new ApiError('Could not read the referral response. Refresh the page and try again.');

export function safeReferralUrl(value) {
  if (typeof value !== 'string' || !value) return null;
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null;
  } catch { return null; }
}

export function normalizeReferral(row) {
  if (!validId(row?.id) || !validId(row?.sender?.id) || !validId(row?.recipient?.id)
    || typeof row.sender.name !== 'string' || typeof row.recipient.name !== 'string'
    || typeof row.role_title !== 'string' || typeof row.message_text !== 'string'
    || !['pending', 'accepted', 'declined'].includes(row.status)
    || !Number.isFinite(Date.parse(row.created_at))
    || (row.company !== null && (!validId(row.company?.id) || typeof row.company.name !== 'string'))) throw mismatch();
  return { ...row, contact_email: typeof row.contact_email === 'string' ? row.contact_email : '', job_url: safeReferralUrl(row.job_url), resume_url: safeReferralUrl(row.resume_url) };
}

export async function listReferrals(type, { offset = 0, signal } = {}) {
  if (!['incoming', 'outgoing'].includes(type) || !Number.isSafeInteger(offset) || offset < 0) throw new TypeError('Invalid referral list options.');
  const params = new URLSearchParams({ type, limit: String(REFERRAL_PAGE_SIZE), offset: String(offset) });
  const data = await apiRequest(`${REFERRALS_ROUTE}?${params}`, { signal });
  if (!Number.isSafeInteger(data?.count) || data.count < 0 || !Array.isArray(data.results)) throw mismatch();
  // Build our own same-origin page requests; never follow API-supplied URLs.
  return { count: data.count, results: data.results.map(normalizeReferral) };
}

export async function createReferral(fields, { signal } = {}) {
  const body = { recipient_id: Number(fields.recipientId), role_title: fields.role.trim(), contact_email: fields.contactEmail.trim(), message_text: fields.message };
  if (fields.companyId) body.company_id = Number(fields.companyId);
  if (fields.jobUrl.trim()) body.job_url = fields.jobUrl.trim();
  if (fields.resumeUrl.trim()) body.resume_url = fields.resumeUrl.trim();
  return normalizeReferral(await apiRequest(REFERRALS_ROUTE, { method: 'POST', body, signal }));
}


// PR #57 returns the full persisted referral, not a connection/conversation id.
export async function respondToReferral(id, action, { signal } = {}) {
  if (!validId(id) || !['accept', 'decline'].includes(action)) throw new TypeError('Invalid referral action.');
  const row = normalizeReferral(await apiRequest(`${REFERRALS_ROUTE}${id}/${action}/`, { method: 'PATCH', signal }));
  const expected = action === 'accept' ? 'accepted' : 'declined';
  if (row.id !== id || row.status !== expected || !Number.isFinite(Date.parse(row.resolved_at))) throw mismatch();
  return row;
}
