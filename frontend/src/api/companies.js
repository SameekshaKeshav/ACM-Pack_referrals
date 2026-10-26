import { apiRequest, ApiError } from './client';

const validId = (id) => Number.isSafeInteger(id) && id > 0;
const mismatch = () => new ApiError('The companies response does not match the API contract (docs/api-contract-accounts-companies.md).');
const text = (value) => (typeof value === 'string' ? value : '');

function normalize(row) {
  if (!validId(row?.id) || typeof row.name !== 'string') throw mismatch();
  return { id: row.id, name: row.name, industry_tag: text(row.industry_tag), logo_url: text(row.logo_url) };
}

// GET /api/companies/?search=  (name or normalized name, case-insensitive substring)
export function companySearchUrl(search = '') {
  const term = search.trim();
  return term ? `/api/companies/?${new URLSearchParams({ search: term })}` : '/api/companies/';
}

export async function searchCompanies({ search = '', signal } = {}) {
  const data = await apiRequest(companySearchUrl(search), { signal });
  const rows = Array.isArray(data) ? data : data?.results;
  if (!Array.isArray(rows)) throw mismatch();
  return rows.map(normalize);
}

// GET /api/companies/<id>/ - only the header fields are used here; the members
// tab asks the directory endpoint for people so it can filter and page them.
export async function getCompany(id, { signal } = {}) {
  return normalize(await apiRequest(`/api/companies/${id}/`, { signal }));
}
