import { apiRequest } from './client';

// Real GET/PATCH /api/accounts/me/ and /api/accounts/past-roles/.
// See docs/api-contract-accounts-companies.md. The server's shape is converted
// to the one the profile components use: company is a name string, and an
// ongoing role has end_date ''.

const WRITABLE_FIELDS = [
  'first_name', 'last_name', 'major', 'grad_year', 'bio', 'open_to_connect',
  'current_role', 'current_company_name',
];

function roleFromServer(role) {
  return {
    id: role.id,
    company: role.company?.name ?? '',
    role_title: role.role_title ?? '',
    start_date: role.start_date ?? '',
    end_date: role.end_date ?? '',
  };
}

function fromServer(data) {
  return {
    first_name: data.first_name ?? '', 
    email: data.email ?? '',
    last_name: data.last_name ?? '',
    major: data.major ?? '',
    grad_year: data.grad_year ?? '',
    bio: data.bio ?? '',
    current_role: data.current_role ?? '',
    current_company: data.current_company?.name ?? '',
    open_to_connect: Boolean(data.open_to_connect),
    past_roles: (data.past_roles ?? []).map(roleFromServer),
  };
}

export async function getMyProfile({ signal } = {}) {
  return fromServer(await apiRequest('/api/accounts/me/', { signal }));
}

export async function updateMyProfile(changes) {
  // The form calls it current_company; the API wants current_company_name.
  const named = { ...changes, current_company_name: changes.current_company };
  const body = Object.fromEntries(
    WRITABLE_FIELDS.filter((key) => key in named).map((key) => [key, named[key]]),
  );
  await apiRequest('/api/accounts/me/', { method: 'PATCH', body });
  // Re-read so the page shows exactly what the server stored.
  return getMyProfile();
}

export async function addPastRole({ company, role_title, start_date, end_date }) {
  const data = await apiRequest('/api/accounts/past-roles/', {
    method: 'POST',
    body: { company_name: company, role_title, start_date, end_date: end_date || null },
  });
  return roleFromServer(data);
}

export async function removePastRole(id) {
  try {
    await apiRequest(`/api/accounts/past-roles/${id}/`, { method: 'DELETE' });
  } catch (err) {
    // Already gone (for example a double click): the goal is met.
    if (err.status !== 404) throw err;
  }
}