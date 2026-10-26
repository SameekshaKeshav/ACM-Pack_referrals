# API route map

One place that lists every route the backend serves, so both frontends can code against the same list. Live, always-current version: **`/api/docs/`** (Swagger UI) and **`/api/schema/`** (OpenAPI), generated from the code by `drf-spectacular`. If this page and `/api/docs/` disagree, the docs endpoint is right; please fix this page.

- Base path: `/api/`. JSON in, JSON out. Timestamps are UTC ISO-8601.
- **Auth:** every route needs `Authorization: Bearer <access token>` unless the *Public* column says yes. A missing or expired token returns 401.
- **Status:** *Scoped* means the server checks that the caller may see or change the data. *Open* means any logged-in user can read and write every row; these are being replaced (see "Not built yet").
- Exact chat request and response shapes: [`api-contract-chat.md`](api-contract-chat.md).

## Accounts: `accounts/` (BE1)

| Method and path | Public | What it does | Status |
|---|---|---|---|
| `POST /api/accounts/auth/signup/` | yes | Create an unverified account and email a 6-digit code (`@ncsu.edu` only) | Scoped (rate limited) |
| `POST /api/accounts/auth/verify/` | yes | Exchange the code for an access and refresh token | Scoped (rate limited, 5 wrong guesses) |
| `POST /api/accounts/auth/login/` | yes | Email a fresh code to a returning user | Scoped (rate limited) |
| `POST /api/accounts/auth/refresh/` | yes | Exchange a refresh token for a new access token | Scoped |
| ~~`/api/accounts/profiles/`~~ | - | Removed; use `/api/accounts/users/` or `/api/accounts/me/` | Closed |
| `GET, POST /api/accounts/past-roles/`, `GET, PUT, PATCH, DELETE /api/accounts/past-roles/<id>/` | no | Past roles | **Open** |

## Companies: `companies/` (BE1)

| Method and path | Public | What it does | Status |
|---|---|---|---|
| `GET, POST /api/companies/`, `GET, PUT, PATCH, DELETE /api/companies/<id>/` | no | Company directory | **Open** |

## Connections: `connections/` (BE2, PM for accept and decline)

| Method and path | Public | What it does | Status |
|---|---|---|---|
| `POST /api/connections/` | no | Send a connection request (201, 400, 403, 404, 409, 429) | Scoped |
| `GET /api/connections/?type=incoming\|outgoing` | no | The caller's request queue | Scoped |
| `GET /api/connections/<id>/` | no | One request; only its sender or recipient (else 404) | Scoped |
| `PATCH /api/connections/<id>/accept/` | no | Recipient accepts; creates the conversation; returns `{id, status, conversation_id}`; 409 if already resolved | Scoped |
| `PATCH /api/connections/<id>/decline/` | no | Recipient declines; returns `{id, status, conversation_id: null}`; 409 if already resolved | Scoped |
| `POST /api/connections/referrals/` | no | Ask a connection for a referral (201, 400, 403, 404, 409). Body: `recipient_id`, `role_title`, `message_text` (max 500), optional `company_id` (on the recipient's profile), `job_url`, `resume_url` (http/https only). 403 unless an accepted connection exists and neither side blocked the other. 409 if you already have a **pending** ask for the same role (compared ignoring case) at the same company, to the same person. Until accept/decline ships (Week 8) nothing leaves pending, so for now that means one ask per role; clients should not offer a retry on a 409 | Scoped |
| `GET /api/connections/referrals/?type=incoming\|outgoing[&status=pending\|accepted\|declined]` | no | The caller's referral asks, newest first; blocked users' asks are hidden. Paged like the people directory: `?limit=` (default 20, max 100) and `?offset=`; the body is `{count, next, previous, results}` | Scoped |
| `GET /api/connections/referrals/<id>/` | no | One ask; only its sender or recipient (else 404) | Scoped |
| `POST /api/reports/` | no | File a report. Body: `target_type` (`user` or `message`), `target_id`, `reason` (one of a fixed set), optional `details` (max 1000). The reporter is the caller; the target must exist. Create-only: nothing can list or edit reports through the API, use the admin | Scoped |
| `POST, DELETE /api/connections/users/<id>/block/` | no | Block (201, or 200 if already blocked; 400 for yourself; 404 unknown user) or unblock (204). Blocking never deletes messages | Scoped |
| `GET, POST /api/companies/<id>/experiences/`, `DELETE /api/companies/<id>/experiences/<experience_id>/` | no | Anonymous interview experiences. Active members only. The author is never returned (`is_mine` says whether a post is yours); posts show month and year only; 5 posts a day (429); you can delete only your own (403); hidden posts are not listed | Scoped |

## Chat: `chat/` (PM)

All chat routes are scoped to the caller's own conversations. A user who is not a participant gets **403**; an unknown conversation gets **404**. A conversation with someone you have blocked, or who has blocked you, is hidden from the list and returns **403** everywhere (the messages are kept; unblocking restores it).

| Method and path | Public | What it does |
|---|---|---|
| `GET /api/chat/conversations/` | no | The caller's conversations: the other person, last message, unread count; newest activity first |
| `GET /api/chat/conversations/<id>/messages/` | no | History (latest `limit`, oldest first), older history (`before` + `before_id`), or a poll (`after`). `limit` is 1 to 100, default 50 |
| `POST /api/chat/messages/` | no | Send a message `{conversation_id, body_text}` (1 to 2000 characters); the sender is taken from the token. Limited to 30 a minute per user (429 beyond that; `THROTTLE_MESSAGE_SEND` changes it) |
| `POST /api/chat/conversations/<id>/read/` | no | Mark the other person's messages as read; returns `{conversation_id, updated_count}` |

Polling: ask for `?after=<last message id>` about every 3 seconds. If a poll returns exactly `limit` messages, ask again straight away until it returns fewer.

## Health and docs

| Method and path | Public | What it does |
|---|---|---|
| `GET /api/health/` | yes | Status and the deployed `commit_hash` |
| `GET /api/<app>/health/` | yes | Per-app status (`accounts`, `companies`, `connections`, `chat`) |
| `GET /api/schema/` | yes | OpenAPI schema |
| `GET /api/docs/` | yes | Swagger UI (use *Authorize* to paste a token) |

## Not built yet (planned in the tracker)

- Referral accept and decline: `PATCH /api/connections/referrals/<id>/accept|decline/` (PM, Week 8), and the email to the recipient when an ask is created (PM, Week 8, needs real email on staging).

## Adding a route

1. Put it in your app's `urls.py` (never the root `urls.py`).
2. Use a DRF view with a `serializer_class` (or `@extend_schema`) so it shows up properly in `/api/docs/`.
3. Add it to this page.
