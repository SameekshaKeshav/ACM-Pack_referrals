export const signedInSession = { access: 'test-access', refresh: 'test-refresh', user: { id: 7, email: 'sanjana@ncsu.edu' } };
export const experience = (id = 1, extra = {}) => ({ id, role_title: 'Software engineer', outcome: 'offer', difficulty: 3, process_text: 'Phone screen followed by two technical rounds.', is_mine: true, month: 10, year: 2026, ...extra });
export const company = { id: 3, name: 'Example Company', industry_tag: 'Technology', logo_url: '' };
const person = { id: 12, name: 'Maya Patel', company: company.name };
export async function seedSession(page) {
  await page.addInitScript((session) => window.localStorage.setItem('pack-referrals.session.v1', JSON.stringify(session)), signedInSession);
}
export async function mockApi(page, { experiences = [experience(), experience(2, { is_mine: false, role_title: 'Analyst', outcome: 'no_response' })], experienceStatus = 200 } = {}) {
  const state = { experiences: [...experiences], calls: [] };
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const method = request.method();
    const body = request.postData() ? request.postDataJSON() : null;
    state.calls.push({ path, method, body, authorization: request.headers().authorization });
    const json = (data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    if (/\/auth\/(signup|login)\/$/.test(path)) return json({ detail: 'Code sent.' });
    if (path.endsWith('/auth/verify/')) return json({ access: signedInSession.access, refresh: signedInSession.refresh, user_id: 7, email: signedInSession.user.email });
    if (path.endsWith('/auth/refresh/')) return json({ access: signedInSession.access });
    if (path === '/api/connections/') {
      if (method === 'POST') return json({ id: 30, status: 'pending' }, 201);
      return json(url.searchParams.get('type') === 'incoming' ? [{ id: 21, sender: person, message_text: 'Hello, can we connect?', status: 'pending', created_at: '2026-10-20T12:00:00Z' }] : []);
    }
    if (path === '/api/chat/conversations/') return json([{ id: 5, other_user: person, last_message: { body_text: 'Hello' }, updated_at: '2026-10-20T12:00:00Z', unread_count: 1 }]);
    if (path === '/api/chat/conversations/5/messages/') return json([{ id: 1, sender_id: 12, conversation_id: 5, body_text: 'Hello', created_at: '2026-10-20T12:00:00Z' }]);
    if (path === '/api/chat/messages/') return json({ detail: 'The message could not be sent.' }, 500);
    if (path === '/api/connections/referrals/') return json({ count: 1, next: null, previous: null, results: [{ id: 10, sender: { id: 7, name: 'Sanjana' }, recipient: person, company, role_title: 'Engineer', message_text: 'I have relevant experience.', status: 'pending', job_url: 'https://example.com/job', resume_url: 'https://example.com/resume', created_at: '2026-11-01T12:00:00Z' }] });
    if (path === '/api/companies/') return json([company]);
    if (path === '/api/companies/3/') return json({ ...company, affiliated_users: [] });
    if (path === '/api/companies/3/experiences/') {
      if (experienceStatus !== 200) return json({ detail: 'Experiences unavailable' }, experienceStatus);
      if (method === 'POST') {
        const saved = experience(99, body);
        state.experiences.unshift(saved);
        return json(saved, 201);
      }
      return json(state.experiences);
    }
    if (/^\/api\/companies\/3\/experiences\/\d+\/$/.test(path) && method === 'DELETE') {
      state.experiences = state.experiences.filter((row) => row.id !== Number(path.split('/').at(-2)));
      return route.fulfill({ status: 204 });
    }
    if (path === '/api/accounts/users/') return json({ count: 1, results: [{ user_id: 12, name: 'Maya Patel', major: 'Computer Science', grad_year: 2026, current_role: 'Engineer', current_company: company, open_to_connect: true }], next: null, previous: null });
    if (path === '/api/accounts/me/') return json({ user_id: 7, first_name: 'Sanjana', last_name: 'Shetty', major: 'Computer Science', grad_year: 2026, bio: 'NC State member.', open_to_connect: true, current_role: 'Student', current_company: company, past_roles: [{ id: 1, company, role_title: 'Intern', start_date: '2025-05-01', end_date: '2025-08-01' }] });
    return json({ detail: `Unmocked API: ${method} ${path}` }, 404);
  });
  return state;
}
