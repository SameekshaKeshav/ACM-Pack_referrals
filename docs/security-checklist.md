# Pack Referrals — Security Checklist

Security status of the backend API and the staging deployment.

- **Last verified:** 2026-10-24, `main` at `986a642` (also running on staging)
- **Staging:** https://acm-packreferrals-production.up.railway.app/

## Summary

| Area | Requirement | Status | Issue |
|------|-------------|--------|-------|
| Access | Every endpoint returns only data the caller may see | **FAIL** | #22 |
| Input | Server-controlled fields can't be set from the request body | **FAIL** | #26 |
| Input | Every text field has a server-side length limit | **FAIL** | #27 |
| Email | Signup code reaches an @ncsu.edu inbox (not spam) within 1 minute | **FAIL** | #34 |
| Config | `SECRET_KEY` from the environment, unique and random on staging | **PASS** | — |
| Config | Email credentials from the environment | **PASS** | — |
| Config | `DEBUG` off on staging | **PASS** | — |
| Config | Throttles identify clients correctly behind Railway's proxy | **PASS** | #28 |

## Access control

Every endpoint requires a JWT unless it is deliberately public (`IsAuthenticated` is the default in `REST_FRAMEWORK`). Reports were the open problem (#22): the old `ReportViewSet` is gone, and `POST /api/reports/` can only create a report, with the reporter taken from the token. Re-audit the new block and interview-experience routes before marking this check PASS.

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
| `/api/reports/` | Any logged-in user can file a report; nobody can list, read, edit or delete reports through the API | PASS |

The Django admin (`/admin/`) is staff-only and not covered.

## Input validation

**Server-controlled fields — report part fixed (#26).** `reports.ReportSerializer` lists its fields explicitly and `reporter` is read-only, so a report can no longer be filed in someone else's name and `status` no longer exists on it. Elsewhere, identity fields (`sender`, `user`, `author`) are set from the token and `account_status` is read-only. Re-check the new interview-experience and block serializers before marking this check PASS.

**Length limits — FAIL (#27).** `Profile.bio` (written through `/api/accounts/me/`) is a `TextField` with no limit in the model or serializer. A report's `reason` is now a fixed set of choices and its `details` is limited to 1000. All other text fields are limited:

| Field | Limit |
|-------|-------|
| Connection request `message_text` | 500 |
| Chat message `body_text` | 2000 (also a database constraint) |
| `first_name`, `last_name` | 150 |
| `major`, `current_role`, `role_title`, company names | 255 |
| Report `details` | 1000 |
| `bio` | **none** |

## Configuration

**`SECRET_KEY` — PASS.** Read from the environment; settings refuse to start without it. The staging key was generated randomly on Railway and matches no key in the repo. Early commits (`31ffe48`, `4a26978`) contain development keys, which are public and must never be used.

**Email credentials — PASS.** All `EMAIL_*` settings are read from the environment. None are in the code or git history.

**`DEBUG` — PASS.** Defaults to `False`, and staging serves Django's plain "Not Found" page. Nothing in the code stops it from being turned on via Railway's variables.

**Throttles behind the proxy — PASS (#28).** The signup, login and verify throttles key on the client IP. Staging sits behind two proxies (a CDN77 node and Railway), so `NUM_PROXIES=2` is set on Railway. The proxies also drop client-supplied `X-Forwarded-For` values, so the throttles hold today even without the setting.

## Email on staging — FAIL (#34)

A signup on staging doesn't deliver a code yet. Staging is on Railway's free plan, which [blocks outbound SMTP](https://docs.railway.com/networking/outbound-networking).

The team decided to stay on the free plan and send mail through an email provider's HTTPS API with [`django-anymail`](https://anymail.dev/), on the free tier of Resend, SendGrid or Brevo. No provider has been picked. Most require a verified sending domain, and the current default sender, `no-reply@packreferrals.ncsu.edu`, is on a domain the team doesn't control.

## Known gaps outside the checklist

- `python manage.py check --deploy` warns about `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE`.
- `/api/accounts/past-roles/` lists roles of unverified and suspended users too, though without saying whose they are.
