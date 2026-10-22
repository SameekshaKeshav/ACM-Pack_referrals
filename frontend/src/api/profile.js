// Mock stand-in for GET/PATCH /api/accounts/me/.
// Week 6: replace the bodies with fetch calls like the ones in connections.js.
// The real call will also need an accessToken.
// TODO: confirm with Karthik which fields go through /api/accounts/me/
// and which (past_roles) go through the past-role endpoints.

const initialProfile = {
  id: 1,
  name: 'Jane Doe',
  major: 'Computer Science',
  grad_year: 2028,
  bio: 'Sophomore interested in backend development and cloud infrastructure.',
  open_to_connect: true,
  past_roles: [
    { id: 'role-1', company: 'Google', role_title: 'Software Engineering Intern', start_date: '2025-05', end_date: '2025-08' },
    { id: 'role-2', company: 'Red Hat', role_title: 'Co-op', start_date: '2024-01', end_date: '' },
  ],
};

let mockProfile = structuredClone(initialProfile);

const EDITABLE_FIELDS = ['name', 'major', 'grad_year', 'bio', 'open_to_connect', 'past_roles'];

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function getMyProfile() {
  await delay(300);
  return structuredClone(mockProfile);
}

export async function updateMyProfile(changes) {
  await delay(300);
  const patch = Object.fromEntries(
    Object.entries(changes).filter(([key]) => EDITABLE_FIELDS.includes(key)),
  );
  mockProfile = { ...mockProfile, ...structuredClone(patch) };
  return structuredClone(mockProfile);
}