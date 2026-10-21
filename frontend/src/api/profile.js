// Mock stand-in for GET/PATCH /api/accounts/me/.
// Week 6: replace the bodies with fetch calls like the ones in connections.js.
// The accessToken argument is unused for now but matches the real call's signature.

let mockProfile = {
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

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export async function getMyProfile({ accessToken } = {}) {
  await delay(300);
  return { ...mockProfile };
}

// The PATCH body is {major, grad_year, bio}.
export async function updateMyProfile({ major, grad_year, bio, accessToken }) {
  await delay(300);
  mockProfile = { ...mockProfile, major, grad_year, bio };
  return { ...mockProfile };
}