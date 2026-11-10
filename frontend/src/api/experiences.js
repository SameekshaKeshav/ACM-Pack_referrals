import { apiRequest, ApiError } from './client';

export const EXPERIENCE_OUTCOMES = { offer: 'Offer', rejected: 'Rejected', no_response: 'No response' };
const validId = (value) => Number.isSafeInteger(value) && value > 0;
const mismatch = () => new ApiError('The interview experience response could not be read. Please refresh and try again.');
function route(companyId) {
  if (!validId(companyId)) throw new TypeError('A valid company is required.');
  return `/api/companies/${companyId}/experiences/`;
}
export function normalizeExperience(row) {
  if (!validId(row?.id) || typeof row.role_title !== 'string' || !row.role_title.trim()
    || !Object.hasOwn(EXPERIENCE_OUTCOMES, row.outcome) || !Number.isInteger(row.difficulty) || row.difficulty < 1 || row.difficulty > 5
    || typeof row.process_text !== 'string' || typeof row.is_mine !== 'boolean'
    || !Number.isInteger(row.month) || row.month < 1 || row.month > 12 || !Number.isInteger(row.year) || row.year < 1 || row.year > 9999) throw mismatch();
  // Whitelist public fields: no author, email, profile, or exact timestamp enters the UI.
  return { id: row.id, role_title: row.role_title, outcome: row.outcome, difficulty: row.difficulty,
    process_text: row.process_text, is_mine: row.is_mine, month: row.month, year: row.year };
}
export async function listExperiences(companyId, { signal } = {}) {
  const rows = await apiRequest(route(companyId), { signal });
  if (!Array.isArray(rows)) throw mismatch();
  return rows.map(normalizeExperience);
}
export async function createExperience(companyId, fields, { signal } = {}) {
  const body = { role_title: fields.role.trim(), outcome: fields.outcome, difficulty: Number(fields.difficulty), process_text: fields.process.trim() };
  return normalizeExperience(await apiRequest(route(companyId), { method: 'POST', body, signal }));
}
export async function deleteExperience(companyId, experienceId, { signal } = {}) {
  if (!validId(experienceId)) throw new TypeError('A valid experience is required.');
  await apiRequest(`${route(companyId)}${experienceId}/`, { method: 'DELETE', signal });
}
