# Pack Referrals — Security Checklist

Security pass over the backend API and the staging deployment.

- **Audited:** 2026-10-21, commit `c4aa761` (current `main`, and the commit staging was running at audit time)
- **Staging:** https://acm-packreferrals-production.up.railway.app/
- **Status key:** **PASS**, **FAIL** (issue filed), **BLOCKED** (cannot be completed as things stand)

## Summary

| # | Item | Status | Issue |
|---|------|--------|-------|
| 1.1 | `message_text` limited to 500 characters server-side | **PASS** | — |
| 1.2 | `body_text` limited to 2000 characters server-side | **PASS** | — |
| 1.3 | Other POST/PATCH text fields have a length limit | **FAIL** | #27 |
| 1.4 | Server-controlled fields (`sender`, `user`, `reporter`, `account_status`) are read-only | **FAIL** | #26 |
| 2.1 | `SECRET_KEY` read from the environment, never hardcoded | **PASS** | — |
| 2.2 | Staging `SECRET_KEY` is a unique, random value | **PASS** | — |
| 2.3 | Email credentials read from the environment, never hardcoded | **PASS** | — |
| 2.4 | `DEBUG=False` on staging | **PASS** | — |
| 3 | Every endpoint returns only data the caller may see | **FAIL** | #19, #20, #22, #23, #24, #25 (see [section 3](#3-permission-audit)) |
| 4 | Throttles identify clients reliably behind Railway's proxy (`NUM_PROXIES`) | **PASS** | #28 |
| 5 | Signup code reaches an @ncsu.edu inbox (not spam) within 1 minute | **BLOCKED** | — |

## How the findings were checked

Each finding was checked by reading the code and confirmed with automated tests against a local test database. No write requests were sent to staging. The staging checks in 2.4 and section 3 were read-only `GET` requests.

## 1. Server-side input validation

All POST/PATCH bodies go through DRF serializers. The question is whether those serializers enforce the limits themselves, rather than relying on the frontend.

### 1.1 `message_text` ≤ 500 — PASS

[`connections/serializers.py:48`](../connections/serializers.py) declares `message_text` with `max_length=500` and `allow_blank=False`. `validate_message_text` (line 60) also rejects whitespace-only text. A request with 501 characters is rejected with a 400 and a field error.

The model field (`ConnectionRequest.message_text`) is an unbounded `TextField`, so the serializer is the only check. A DB constraint like the one on `body_text` would add a second layer, but isn't required for this item.

### 1.2 `body_text` ≤ 2000 — PASS

[`chat/models.py:61`](../chat/models.py) has `CharField(max_length=2000)`, which the `ModelSerializer` turns into a 2000-character serializer limit. The `message_body_text_max_2000` check constraint (line 72) enforces the same limit in the database, since SQLite ignores `VARCHAR` lengths. A request with 2001 characters is rejected with a 400 and a field error.

### 1.3 Other text fields have a length limit — FAIL

`Profile.bio` ([`accounts/models.py:23`](../accounts/models.py)) and `Report.reason` ([`connections/models.py:59`](../connections/models.py)) are `TextField`s with no `max_length`, and their serializers add none, so the server accepts text of any size in these fields.

**Fix:** add a `max_length` to both fields in the serializer (and optionally a DB constraint), with limits the frontend also shows.

### 1.4 Server-controlled fields are read-only — FAIL

These serializers use `fields = "__all__"`, which makes all of the model's editable fields writable from the request body, including fields the server should set:

| Serializer | Server-controlled field(s) that are writable |
|------------|---------------------------------------------|
| `MessageSerializer` ([`chat/serializers.py`](../chat/serializers.py)) | `sender` |
| `ReportSerializer` ([`connections/serializers.py`](../connections/serializers.py)) | `reporter` |
| `ProfileSerializer` ([`accounts/serializers.py`](../accounts/serializers.py)) | `user`, `account_status` |
| `PastRoleSerializer` ([`accounts/serializers.py`](../accounts/serializers.py)) | `user` |
| `ConversationSerializer` ([`chat/serializers.py`](../chat/serializers.py)) | `created_from_connection_request` (should only be set by the accept flow) |

[`docs/api-contract-chat.md`](api-contract-chat.md) says the authenticated user supplies sender/reporter identity and "client input must never control it". (`CompanySerializer` also uses `"__all__"`, but `Company` has no server-controlled fields, since `name_normalized` is non-editable.)

**Fix:** list fields explicitly and mark the fields above read-only. Set identity fields in the view from `request.user` (the way `ConnectionRequestViewSet.create` does with `serializer.save(sender=request.user)`).

## 2. Secrets and DEBUG

### 2.1 `SECRET_KEY` from the environment — PASS

[`pack_referrals/settings.py:25`](../pack_referrals/settings.py) reads `os.getenv("SECRET_KEY")` and raises `RuntimeError` if it's missing, so there is no fallback key to deploy by accident. `.env` is gitignored, and `.env.example` only contains a placeholder.

Early commits (`31ffe48`, `4a26978`) contained development keys. They are public in git history, so they are only safe if staging uses none of them (see 2.2).

### 2.2 Staging key is unique and random — PASS

The key can't be checked from the repo, so this was verified on Railway. The staging `SECRET_KEY` was generated randomly and set directly on Railway. On 2026-10-21, Danny confirmed that the value on Railway:

- is at least 50 characters, with no stray whitespace or quotes from pasting;
- isn't the `.env.example` placeholder, doesn't start with `django-insecure-`, and doesn't match any key in the repo's history;
- isn't used in any local `.env`.

**To re-verify** (for example, after the key is rotated), check the value in the service's **Variables** tab on Railway, or run Django's check against staging's environment variables without printing the key:

```bash
railway run python manage.py check --deploy
```

If warning `security.W009` is absent, the key is at least 50 characters with at least 5 unique characters and isn't a `django-insecure-` key. That rules out every key known from the repo's history and `.env.example`.

### 2.3 Email credentials from the environment — PASS

`EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_PORT` and `EMAIL_USE_TLS` are all read with `os.getenv` ([`pack_referrals/settings.py:41-45`](../pack_referrals/settings.py)). There are no credentials in the code or in git history (`.env.example` has empty values).

### 2.4 `DEBUG=False` on staging — PASS

[`pack_referrals/settings.py:31`](../pack_referrals/settings.py) defaults `DEBUG` to `False`, and staging has it off: a request for a nonexistent URL returns Django's plain "Not Found" page, not the debug page.

**Note:** this relies on nobody setting `DEBUG=True` on Railway. Nothing in the code prevents it. If the team wants it enforced, settings could refuse to start when `DEBUG` is on in a Railway environment.

## 3. Permission audit

Since #14, every endpoint requires a valid JWT by default (`IsAuthenticated`, [`pack_referrals/settings.py:160`](../pack_referrals/settings.py)), and staging returns 401 to unauthenticated requests. Being logged in is all most endpoints check, though. Six are plain `ModelViewSet`s with `queryset = <Model>.objects.all()` and no object-level permission, so they don't limit which rows a logged-in user can read or change.

| Endpoint | View | Status | Issue | Problem |
|----------|------|--------|-------|---------|
| `/api/chat/messages/` | `MessageViewSet` ([`chat/views.py:22`](../chat/views.py)) | **FAIL** | #19 | Not limited to the user's own conversations |
| `/api/chat/conversations/` | `ConversationViewSet` ([`chat/views.py:17`](../chat/views.py)) | **FAIL** | #20 | Not limited to conversations the user participates in |
| `/api/connections/reports/` | `ReportViewSet` ([`connections/views.py:213`](../connections/views.py)) | **FAIL** | #22 | Not limited to reports the user filed; status changes aren't restricted to moderators |
| `/api/accounts/profiles/` | `ProfileViewSet` ([`accounts/views.py:56`](../accounts/views.py)) | **FAIL** | #23 | Writes aren't restricted to the profile's owner |
| `/api/accounts/past-roles/` | `PastRoleViewSet` ([`accounts/views.py:61`](../accounts/views.py)) | **FAIL** | #24 | Writes aren't restricted to the role's owner |
| `/api/companies/` | `CompanyViewSet` ([`companies/views.py:17`](../companies/views.py)) | **FAIL** | #25 | Writes aren't restricted to admins |
| `/api/connections/` (list, create) | `ConnectionRequestViewSet` | **PASS** | — | Queryset filtered to `sender=user OR recipient=user` (`get_queryset`, line 43) |
| `/api/connections/<id>/` | `ConnectionRequestDetailView` | **PASS** | — | Same filter (line 165); other users get 404 |
| `/api/connections/<id>/accept/`, `decline/` | `_ConnectionActionView` | **PASS** | — | `_get_pending_for_recipient` ([`connections/services.py:32`](../connections/services.py)) returns 404 to outsiders and 403 to the sender |
| `/api/health/`, `/api/<app>/health/` | `HealthCheckView`, `AppHealthView` | **PASS** | — | Public on purpose (`AllowAny`); return no user data |
| `/api/accounts/auth/signup/`, `login/`, `verify/` | `SignupView`, `LoginView`, `VerifyView` | **PASS** | — | Public on purpose (`AllowAny`, throttled); return tokens only for a valid code |
| `/api/accounts/auth/refresh/` | SimpleJWT `TokenRefreshView` | **PASS** | — | No permission classes, as designed; returns a new access token only for a valid refresh token |
| `/api/accounts/`, `/api/chat/` | DRF router root (`APIRootView`) | **PASS** | — | Requires login; lists endpoint URLs only, no user data |

The `companies` and `connections` routers also generate a root view, but it's unreachable: `/api/companies/` resolves to the company list (that router is registered at `r""`), and `/api/connections/` resolves to the connection-request list, which is registered first. The Django admin (`/admin/`) is staff-only and outside this audit.

Reading profiles and companies may be intended, since browsing affiliations is the product. **Fix direction:** scope `get_queryset()` to the requesting user where the data is private (messages and conversations they participate in, reports they filed), restrict writes to the owner for profiles and past roles, and restrict company writes and report status changes to admins.

## 4. Throttles behind Railway's proxy (`NUM_PROXIES`) — PASS

The signup, login and verify throttles key on the client IP from DRF's `get_ident()` ([`accounts/throttling.py:29`](../accounts/throttling.py)). At audit time `NUM_PROXIES` was not set in `REST_FRAMEWORK`. When it's unset, DRF builds the client identity from the whole `X-Forwarded-For` header, which a client can fill with fake values, so the throttles couldn't be relied on to tell clients apart. See DRF's [throttling docs on identifying clients](https://www.django-rest-framework.org/api-guide/throttling/#how-clients-are-identified).

**Fix:** settings read `NUM_PROXIES` from the environment, with tests for spoofed headers and separate per-client budgets. Staging sets `NUM_PROXIES=2`.

**Measured on staging (2026-10-24, commit `3b1c2e0`)** with temporary forwarding-header logging, since removed:

- A plain request arrives with `X-Forwarded-For: <client IP>, <CDN77 node IP>` from a Railway-internal `REMOTE_ADDR`. Two proxies sit in front of the app and the client IP is second from the end, so N = 2.
- A request sent with `X-Forwarded-For: 1.2.3.4` arrives with the same two entries, so one of the proxies drops client-supplied values. N = 2 doesn't depend on this.

**Confirmed on staging:** the running app's process environment contains `NUM_PROXIES=2`. Twelve `POST`s to `/api/accounts/auth/verify/`, each with a different fake `X-Forwarded-For` and an unregistered email (nothing is written), returned `400` ten times and then `429`, so the 10/15min limit holds. Because the proxies already drop fake values, this throttle result would look the same with the variable unset. The environment check is what confirms the setting.

## 5. Real email on staging — BLOCKED

**Requirement:** a signup on staging delivers the code to an NC State inbox, not spam, within 1 minute.

**Blocker:** staging runs on Railway's free plan. Railway allows outbound SMTP (ports 25, 465, 587, 2525) only on the Pro plan and above ([Railway docs: Outbound Networking](https://docs.railway.com/networking/outbound-networking)). Any SMTP provider (Gmail app password, SendGrid SMTP, etc.) would time out from staging.

**Options (team decision):**

| Option | Code change | Other requirements |
|--------|-------------|--------------------|
| A. Upgrade the workspace to Pro and use a Gmail app password over SMTP | None. Django's SMTP backend switches on when `EMAIL_HOST` is set | Paid plan; a team Gmail account with 2FA |
| B. Stay on the free plan and use a provider's HTTPS API (e.g. Resend, SendGrid) through [`django-anymail`](https://anymail.dev/) | New dependency and an `EMAIL_BACKEND` setting | Provider account and API key. Most providers need a verified sending domain to email arbitrary addresses, so the team likely needs a domain it owns (DNS records can't be added to `*.up.railway.app`). Check each provider's current free tier before choosing |

**Needed under either option:**

- **Set `DEFAULT_FROM_EMAIL`.** The default, `no-reply@packreferrals.ncsu.edu` ([`pack_referrals/settings.py:196`](../pack_referrals/settings.py)), is on a domain the team doesn't control. Mail from it fails SPF/DMARC and lands in spam or is rejected. Use an address the provider is authorized to send as.
- **Set `EMAIL_TIMEOUT`** (e.g. 10 seconds). Without it, a send that can't connect hangs the signup request until gunicorn kills the worker (a 502 for the user).

**How to verify once unblocked:** note the time, sign up on staging with a real @ncsu.edu address, and record a screenshot of the message in the inbox (not spam) with its received time.

## Outside this checklist

`python manage.py check --deploy` also warns about `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE`. None of these were in scope. They're worth a follow-up, since staging sits behind Railway's HTTPS proxy and `SECURE_PROXY_SSL_HEADER` is already set.
