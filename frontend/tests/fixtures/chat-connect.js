export const session = { access: 'synthetic-access', refresh: 'synthetic-refresh', user: { id: 7, email: 'demo@ncsu.edu' } };
export const company = { id: 1, name: 'Red Hat', industry_tag: 'Software', logo_url: '' };
export const person = { user_id: 41, name: 'Avery Chen', major: 'Computer Science', grad_year: 2026, current_role: 'Engineer', current_company: company, open_to_connect: true };
const created = '2026-10-20T12:00:00Z';
export const conversation = { id: 5, other_user: { id: 44, name: 'Morgan Park', company: 'IBM' }, last_message: 'Happy to connect', updated_at: created };
export const reply = (id, body_text, sender_id = 44) => ({ id, conversation_id: 5, sender_id, body_text, created_at: `2026-10-20T12:${String(id).padStart(2, '0')}:00Z` });
export async function mockChatConnect(page, options = {}) {
  const state = { accepted: options.accepted !== false, requests: [], messages: options.empty ? [] : [reply(1, 'Happy to connect'), reply(2, 'Thank you!', 7)], failSend: false, failPoll: false, ...options };
  const unknown = [];
  await page.addInitScript((value) => localStorage.setItem('pack-referrals.session.v1', JSON.stringify(value)), session);
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    const json = (data, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(data) });
    if (state.loading) await state.loading;
    if (state.failLoad && method === 'GET' && (path.startsWith('/api/chat/') || path === '/api/connections/')) return json({ detail: 'Temporarily unavailable' }, 503);
    if (path === '/api/companies/1/') return json(company);
    if (path === '/api/accounts/users/') return json({ count: 1, next: null, previous: null, results: [person] });
    if (path === '/api/connections/' && method === 'POST') {
      state.requests.push({ id: 12, recipient: { id: 41, name: person.name }, status: 'pending', ...route.request().postDataJSON(), created_at: created });
      return json({ id: 12, status: 'pending' }, 201);
    }
    if (path === '/api/connections/' && method === 'GET') return json(url.searchParams.get('type') === 'incoming'
      ? state.accepted || state.empty ? [] : [{ id: 11, sender: { id: 44, name: 'Morgan Park', company: 'IBM' }, message_text: 'Let’s talk about interviews.', status: 'pending', created_at: created }]
      : state.requests);
    if (path === '/api/connections/11/accept/' && method === 'PATCH') { state.accepted = true; return json({ id: 11, status: 'accepted', conversation_id: 5 }); }
    if (path === '/api/chat/conversations/') return json(state.accepted && !state.empty ? [conversation] : []);
    if (path === '/api/chat/conversations/5/messages/') {
      if (url.searchParams.has('after')) return state.failPoll ? json({ detail: 'Updates unavailable' }, 503) : json(state.messages.filter((row) => row.id > Number(url.searchParams.get('after'))));
      return json(state.messages);
    }
    if (path === '/api/chat/messages/' && method === 'POST') {
      state.sendCalls = (state.sendCalls || 0) + 1;
      if (state.failSend) return json({ detail: 'Temporary send failure' }, 503);
      const row = reply(Math.max(0, ...state.messages.map((item) => item.id)) + 1, route.request().postDataJSON().body_text, 7);
      state.messages.push(row); return json(row, 201);
    }
    unknown.push(`${method} ${path}`);
    return json({ detail: 'Unexpected fixture request' }, 500);
  });
  return { state, unknown };
}
