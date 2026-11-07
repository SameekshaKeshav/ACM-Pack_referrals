# Chat and email-code auth integration

Prepared 2026-10-21. Branch: `sanjana/chat-auth-integration`, based on the shared
`front-end` branch at `3f10f9b0d822a9820e63e473357162a9de25d798` (PR #17).
That branch includes main at `c4aa7617f3af7e2f92a170898f8c6d1f581bc653`.
Profile, directory and company components from PR #17 are preserved. This task
changes frontend code only; no backend models, migrations or endpoints are changed.

## Implemented behavior

| Requirement | Implementation |
| --- | --- |
| Sidebar | Authenticated `GET /api/chat/conversations/`; loading, empty, error and retry states |
| Open accepted conversation | `/chat/:conversationId` loads its nested history endpoint |
| Full history | Follows same-origin `results/next` pages, or older bare-array batches using `limit=100`, `before`, `before_id`; deduplicates and orders by timestamp then ID |
| Optimistic send | Appends a temporary bubble immediately; acknowledgement replaces it with the server row without duplication |
| Failure and retry | Keeps the failed message in its originating thread with explicit Retry; does not silently lose text |
| Signup/login | Email-only screens matching the existing passwordless backend; both lead to the six-digit code screen |
| Verification | Sends `{email,code}`, preserves leading zeroes, supports resend/change email, then stores credentials and signs in |
| Persistence | Access, refresh and `{id,email}` saved atomically in one localStorage entry |
| Protected routes | Chat, profile, directory, company and the old mock redirect logged-out users to login, preserving a safe internal return URL |
| Silent refresh | Protected 401 shares one refresh per tab, then one retry; optional rotated refresh token is saved |
| Logout/account changes | Clears persistence, synchronizes storage events, prevents late responses restoring old sessions, and remounts private screens when accounts change |

## Routes

- `/signup`, `/login`: request a new-account or returning-user code. No password.
- `/enter-code`: enter/resend the emailed code. Only pending email/mode metadata
  persists in sessionStorage; codes and passwords are not stored there.
- `/chat`: sidebar, automatically selects the first permitted conversation.
- `/chat/5`: conversation 5, if present in the authorized sidebar list.
- `/profile`, `/directory`, `/company/:id`: existing FE1 components, now protected.
  Their mock-data/API replacement work remains FE1's responsibility.
- `/chat-mock`: earlier fictional-data demo, now protected. Its Accept/Decline
  remain local and its static chat Send stays disabled. The connection request
  form uses the signed-in session/shared client; manual token controls are only
  used when this component is mounted alone in the legacy DOM harness.

## Existing backend auth contract

Checked against accounts URLs, views and serializers on the inherited main:

| Endpoint | Body | Success |
| --- | --- | --- |
| `POST /api/accounts/auth/signup/` | `{email}` | 201 email/detail; issues an email code |
| `POST /api/accounts/auth/login/` | `{email}` | 200 enumeration-safe detail; emails a code if the account exists |
| `POST /api/accounts/auth/verify/` | `{email,code}` | 200 `{access,refresh,user_id,email}` |
| `POST /api/accounts/auth/refresh/` | `{refresh}` | 200 `{access}`; optional rotated `refresh` supported |

The backend validates its configured university domain (default `ncsu.edu`) and
controls expiry, attempt limits and throttling. These errors are shown by the UI.
Auth bootstrap requests omit Authorization: an expired token must not prevent
signup or verification. Shared-client requests omit cookies to avoid accidentally
using Django admin/session authentication and its CSRF requirements. Protected
requests attach `Authorization: Bearer <access>`.

## Chat contract consumed by the UI

Sidebar rows need `id`, `other_user: {id,name,email?,company?,role?}`, `last_message`
(null, string or `{body_text,...}`), `updated_at` and optional `unread_count`. The
backend must return only conversations the caller is permitted to access.

History is `GET /api/chat/conversations/<id>/messages/?limit=100`. Rows need `id`,
`sender_id`, `body_text`, `created_at` and preferably `conversation_id`. Numeric
legacy `sender`/`conversation` fields are normalized, but are not a substitute
for the endpoint, ownership checks or sidebar representation.

For bare arrays the backend must honor `limit=100`. A full batch triggers another
request using its oldest timestamp and ID as an exclusive `before`/`before_id`
cursor. If a server silently returns only 50 while ignoring the requested limit,
the client cannot distinguish that from complete history. `{results,next}` paging
is also supported. Next links must stay on the same origin and collection;
repeated pages/cursors fail visibly rather than loop. Empty history is `[]`.

Sending is exactly `POST /api/chat/messages/` with:

```json
{"conversation_id":5,"body_text":"Hello!"}
```

Return the saved message with server ID, sender, timestamp and conversation. The
backend must derive sender identity from the token, reject nonparticipants, enforce
the 2000-code-point limit and allow only permitted connections. The frontend
renders plain text, preserves valid whitespace, rejects blank messages and caps
input at 2000 code points. Send responses always update the originating thread,
including after navigation. Older acknowledgements do not overwrite a newer
sidebar preview.

No polling, WebSockets, read marking or real Accept/Decline wiring is added here.
History reloads on selection/retry; the sidebar has a refresh action. Later features
still require coordinated backend contracts and ownership.

## Confirmed backend dependency

On the inspected main, chat views are still generic ModelViewSets and serializers
expose raw model fields. The requested nested history route does not exist: a real
authenticated HTTP check returned 404. The raw sidebar lacks `other_user`, and raw
message creation expects model fields rather than the requested `conversation_id`.

The chat owner must implement nested history, participant-scoped list/send permissions,
the sidebar representation, and the create/response shape above. Do not expose
unscoped raw CRUD as a workaround or let the client choose a sender. Unsupported
responses/URLs show errors; they never become fabricated successful history.

Frontend chat behavior is verified with intercepted/mock responses. Real history
and sending cannot yet be called integrated. `docs/api-contract-chat.md` remains
a proposal; prepared code is not another owner's sign-off.

## Local run and acceptance

Use Node 24, at least 24.15. `.nvmrc` selects 24; the old 22.13 minimum was too low.

1. Follow the root README: set a local SECRET_KEY, install Python requirements,
   migrate and start Django at `127.0.0.1:8000`.
2. With no EMAIL_BACKEND, codes appear in Django's development console. Actual
   inbox delivery requires the Brevo settings in the root README. Use disposable
   test accounts.
3. In frontend run `npm ci`, then `npm run dev`.
4. Open `http://localhost:5173/signup`, submit an allowed test email, enter the
   emailed/console code and confirm you land signed in on `/chat`. Chat may show
   the documented contract error until its backend is implemented.
5. Hard-refresh: remain signed in. Inspect a protected request's Bearer header,
   but keep token values out of screenshots and commits.
6. Against a backend configured for short-lived access tokens, let one expire,
   then reload a protected page. Expect 401, one refresh and one successful retry,
   with no login redirect.
7. Once the chat API is compatible, accept a test connection through the backend's
   supported flow, open `/chat/<conversation_id>`, and verify ordered full history.
   Delay the send response in DevTools: the bubble should show Sending before the
   response arrives. Verify failure and explicit retry as well.
8. Log out and revisit `/chat/5`: return to login.

Vite forwards `/api` to port 8000. Override `VITE_API_PROXY_TARGET` in `.env.local`
only for a different development backend, then restart Vite. Production requires
its own same-origin API routing; no deployment is included.

## Verification on 2026-10-21

- Production Vite build passed.
- 29 DOM tests passed: 24 new chat/auth cases and the 5 existing mock cases.
- All 88 inherited Django tests passed; backend code is unchanged.
- Real local HTTP auth check passed: signup, console-email code, verification,
  persisted session authentication, deliberately expired access JWT -> 401 ->
  refresh -> successful protected retry, then logout. This used an isolated local
  database and console mail, not real SMTP delivery or an actual browser reload.
- 14 Playwright cases are included (7 new, 7 adjusted legacy cases). Chromium
  crashes at launch here, so no browser pass is claimed. On a working host/CI run
  `npx playwright install chromium` and `npm test`. The suite includes actual page
  reloads, optimistic sends and mobile viewport checks with intercepted responses.
- Real chat HTTP check confirmed the nested history endpoint returns 404.

## Storage and retry limits

The JSON-token backend has no refresh-cookie flow, so credentials persist in the
single `pack-referrals.session.v1` localStorage entry. This meets reload persistence,
but same-origin injected JavaScript could read the tokens. A production HttpOnly
refresh-cookie design needs a coordinated backend change. No tokens are logged,
committed or placed in URLs.

Logout ends this browser session and syncs through storage events. The inspected
backend has no revoke/logout endpoint, so copied credentials are not revoked.
Refresh sharing is per tab, not a distributed cross-tab lock. Network/server
refresh failures keep credentials for recovery; invalid refresh credentials or a
second protected 401 clear them. No automatic POST retry occurs except after a
rejected 401. An explicit retry after an ambiguous lost response could duplicate
a message already saved by the server; backend idempotency would be needed to
eliminate that ambiguity.
