import { apiRequest, ApiError } from './client';

export const PAGE_SIZE = 20;

const validId = (id) => Number.isSafeInteger(id) && id > 0;
const mismatch = () => new ApiError('The directory response does not match the API contract (docs/api-contract-accounts-companies.md).');

// GET /api/accounts/users/?major=A&major=B&grad_year=Y&limit=&offset=
// Repeating `major` means "A or B"; every other filter narrows the result.
// `companyId` limits it to people whose current employer or any past role is there.
export function directoryQuery({ majors = [], gradYear = '', companyId = null, limit = PAGE_SIZE, offset = 0 } = {}) {
  const params = new URLSearchParams();
  majors.forEach((major) => params.append('major', major));
  if (gradYear) params.set('grad_year', String(gradYear));
  if (companyId) params.set('company_id', String(companyId));
  params.set('limit', String(limit));
  if (offset) params.set('offset', String(offset));
  return `/api/accounts/users/?${params}`;
}

export async function listPeople({ signal, ...filters } = {}) {
  const data = await apiRequest(directoryQuery(filters), { signal });
  if (!Array.isArray(data?.results) || !Number.isSafeInteger(data.count) || data.count < 0) throw mismatch();
  const results = data.results.map((row) => {
    if (!validId(row?.user_id) || typeof row.name !== 'string') throw mismatch();
    return {
      user_id: row.user_id,
      name: row.name,
      major: typeof row.major === 'string' ? row.major : '',
      grad_year: Number.isInteger(row.grad_year) ? row.grad_year : null,
      current_role: typeof row.current_role === 'string' ? row.current_role : '',
      current_company: validId(row.current_company?.id) && typeof row.current_company.name === 'string' ? row.current_company : null,
      open_to_connect: row.open_to_connect !== false,
    };
  });
  return { count: data.count, results };
}
