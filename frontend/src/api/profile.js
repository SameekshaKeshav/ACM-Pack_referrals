import { apiRequest } from './client';

// Real GET/PATCH /api/accounts/me/. See docs/api-contract-accounts-companies.md.
// The server's shape is converted to the one the profile components use:
// company is a name string, and an ongoing role has end_date ''.

// Writable on /me/. Roles go through /api/accounts/past-roles/ (separate PR).
const WRITABLE_FIELDS = ['first_name', 'last_name', 'major', 'grad_year', 'bio', 'open_to_connect'];

function fromServer(data) {
  return {
    first_name: data.first_name ?? '',
    last_name: data.last_name ?? '',
    major: data.major ?? '',
    grad_year: data.grad_year ?? '',
    bio: data.bio ?? '',
    current_role: data.current_role ?? '',
    current_company: data.current_company?.name ?? '',
    open_to_connect: Boolean(data.open_to_connect),
    past_roles: (data.past_roles ?? []).map((role) => ({
      id: role.id,
      company: role.company?.name ?? '',
      role_title: role.role_title ?? '',
      start_date: role.start_date ?? '',
      end_date: role.end_date ?? '',
    })),
  };
}

export async function getMyProfile({ signal } = {}) {
  return fromServer(await apiRequest('/api/accounts/me/', { signal }));
}

export async function updateMyProfile(changes) {
  const body = Object.fromEntries(
    WRITABLE_FIELDS.filter((key) => key in changes).map((key) => [key, changes[key]]),
  );
  await apiRequest('/api/accounts/me/', { method: 'PATCH', body });
  // Re-read so the page shows exactly what the server stored.
  return getMyProfile();
}