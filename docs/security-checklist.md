# Pack Referrals — Security Checklist

Security status of the backend API and the staging deployment.

- **Last full review:** 2026-10-24, `main` at `986a642`. The email and error-report rows were re-checked on 2026-10-28 (`c9477bf`).
- **Staging:** https://acm-packreferrals-production.up.railway.app/

## Summary

| Area | Requirement | Status | Issue |
|------|-------------|--------|-------|
| Access | Every endpoint returns only data the caller may see | **FAIL** | #22 |
| Input | Server-controlled fields can't be set from the request body | **FAIL** | #26 |
| Input | Every text field has a server-side length limit | **FAIL** | #27 |
| Email | Signup code reaches an @ncsu.edu inbox (not spam) within 1 minute | **PASS** | #34 |
| Config | `SECRET_KEY` from the environment, unique and random on staging | **PASS** | — |
| Config | Email credentials from the environment | **PASS** | — |
| Config | `DEBUG` off on staging | **PASS** | — |
| Config | Throttles identify clients correctly behind Railway's proxy | **PASS** | #28 |
| Config | Error reports (Sentry) leave out request bodies and variable values | **PASS** | — |

## Open failures

**Reports are open to every user (#22).** `ReportViewSet` is a plain `ModelViewSet` over all reports, so any logged-in user can list every report, edit or delete any of them, and change their `status`.

**Server-controlled fields are writable (#26).** `ReportSerializer` uses `fields = "__all__"`, so `reporter` and `status` come from the request body, and a user can file a report in someone else's name. It's the last serializer using `"__all__"`.

**Two text fields have no length limit (#27).** `Profile.bio` (written through `/api/accounts/me/`) and `Report.reason` are `TextField`s with no limit in the model or serializer. Every other text field is limited: connection request `message_text` 500, chat `body_text` 2000 (also a database constraint), names 150, other short fields 255.

## Access control

Every endpoint requires a JWT unless it's deliberately public (`IsAuthenticated` is the default in `REST_FRAMEWORK`).

| Endpoint | Who can use it | Status |
|----------|----------------|--------|
| `/api/health/`, `/api/<app>/health/` | Anyone; no user data | PASS |
| `/api/accounts/auth/signup/`, `login/`, `verify/` | Anyone; throttled, tokens only for a valid code | PASS |
| `/api/accounts/auth/refresh/` | Anyone with a valid refresh token | PASS |
| `/api/schema/`, `/api/docs/` | Anyone; route and field descriptions only | PASS |
| `/api/accounts/` | Logged in; lists endpoint URLs only | PASS |
| `/api/accounts/me/` | The caller's own profile (GET, PATCH) | PASS |
| `/api/accounts/users/` | Logged in; active members only, without bio or email, max 100 per page | PASS |
| `/api/accounts/past-roles/` | Logged in to read; create, update and delete only your own | PASS |
| `/api/companies/`, `/api/companies/<id>/` | Logged in, read-only; affiliated users are active members only | PASS |
| `/api/connections/`, `/api/connections/<id>/` | Requests the caller sent or received; others get 404 | PASS |
| `/api/connections/<id>/accept/`, `decline/` | The recipient only; outsiders get 404, the sender 403 | PASS |
| `/api/chat/conversations/` | The caller's conversations, minus blocked users | PASS |
| `/api/chat/conversations/<id>/messages/`, `<id>/read/`, `/api/chat/messages/` | Participants who aren't blocked; unknown ids 404, others 403 | PASS |
| `/api/connections/reports/` | Any logged-in user, for every report | **FAIL** (#22) |

The Django admin (`/admin/`) is staff-only and not covered.

## Notes on passing items

- **`SECRET_KEY`:** the app refuses to start without it. The staging key was generated on Railway and matches no key in the repo. Commits `31ffe48` and `4a26978` contain development keys, which are public and must never be used.
- **Email:** sent through Brevo's HTTPS API with `django-anymail`, because Railway's free plan blocks outbound SMTP. `BREVO_API_KEY` is set only on Railway, and the app refuses to start if the Brevo backend is selected without it. On 2026-10-28 a staging login delivered a code to an @ncsu.edu inbox, not spam, within a minute. Signup sends through the same function (`_send_code`). If a send fails, signup returns `503` and login its usual `200`, so failures don't reveal which addresses are registered.
- **`DEBUG`:** defaults to `False`. Nothing in the code stops it being turned on through Railway's variables.
- **Throttles:** the auth throttles key on client IP. Staging sits behind two proxies (CDN77, then Railway), so `NUM_PROXIES=2`. The proxies also drop client-supplied `X-Forwarded-For` values.
- **Sentry:** `include_local_variables=False` and `max_request_body_size="never"`. Before this, staging events included users' emails and verification codes. Sentry still gets stack traces and URLs. Events recorded before the fix should be deleted from Sentry.

## Known gaps outside the checklist

- `python manage.py check --deploy` warns about `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE`.
- `/api/accounts/past-roles/` lists roles of unverified and suspended users too, though without saying whose they are.
- **Throttle counts are kept per worker.** No `CACHES` setting means each gunicorn worker counts requests in its own memory. Staging runs one worker, so the limits hold today. Raising `WEB_CONCURRENCY` would multiply every limit, including code requests and verify attempts, unless a shared cache is configured first. Found in the 2026-11-01 load test.
- **Registered emails can be discovered. Accepted until after the showcase (PR #40).** Signup returns `409` for an address with a verified account, and login takes longer for a registered address because it waits for Brevo. Accepted because only @ncsu.edu addresses can be checked, code requests are throttled to 5 per 15 minutes per IP, every check of a real account emails its owner, and the directory already shows membership to logged-in users. Fixing it needs both changes together: signup always returns `201` (emailing an existing user instead of sending a code), and the email is sent after the response so timing doesn't differ. That would also remove signup's `503` on a failed send.
