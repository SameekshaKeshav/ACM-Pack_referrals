import { apiRequest } from './client';

// Same choices, in the same order, as Report.Reason on the server.
export const REPORT_REASONS = {
  spam: 'Spam',
  harassment: 'Harassment',
  inappropriate_content: 'Inappropriate content',
  misinformation: 'Misinformation',
  hateful_speech: 'Hateful speech',
  graphic_content: 'Graphic content',
  fake_account: 'Fake account',
  fraud_or_scam: 'Fraud or scam',
  threats_or_violence: 'Threats or violence',
  other: 'Other',
};
export const REPORT_TARGETS = ['user', 'message', 'experience'];
export const REPORT_DETAILS_LIMIT = 1000;

const validId = (value) => Number.isSafeInteger(value) && value > 0;

// 201 for a new report, 200 if this person already reported the same thing.
// Either way the person has done what they meant to, so both count as sent.
export async function sendReport({ targetType, targetId, reason, details = '' }, { signal } = {}) {
  if (!REPORT_TARGETS.includes(targetType) || !validId(targetId) || !Object.hasOwn(REPORT_REASONS, reason)) {
    throw new TypeError('A valid report target and reason are required.');
  }
  await apiRequest('/api/reports/', { method: 'POST', body: { target_type: targetType, target_id: targetId, reason, details: details.trim() }, signal });
}

export async function blockUser(userId, { signal } = {}) {
  if (!validId(userId)) throw new TypeError('A valid user is required.');
  await apiRequest(`/api/connections/users/${userId}/block/`, { method: 'POST', signal });
}

// Removing a block that is not there is not an error on the server (204).
export async function unblockUser(userId, { signal } = {}) {
  if (!validId(userId)) throw new TypeError('A valid user is required.');
  await apiRequest(`/api/connections/users/${userId}/block/`, { method: 'DELETE', signal });
}
