# Pack Referrals

ACM NC State project: a verified NC State alumni/student network for browsing company affiliations and requesting referrals.

**Staging:** https://acm-packreferrals-production.up.railway.app/

## Local setup

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # then edit .env if needed (SECRET_KEY, email, etc.)
python manage.py migrate
python manage.py runserver
```

Environment variables are loaded from `.env` (see [`.env.example`](.env.example)). With `EMAIL_BACKEND` unset, outbound email is printed to the console — fine for local auth spikes.

If migrations were reset on a branch (no production data yet), reset your local DB:

```bash
rm -f db.sqlite3
python manage.py migrate
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Global health: `/api/health/` (includes `commit_hash`, which is `null` locally). Django admin: `/admin/`.

Django also serves the React app at every other path (see [Deployment](#deployment-railway)). Until you build it, those paths return `503 Frontend not built`, which is expected. The API and admin work either way. To build it, see the [frontend README](frontend/README.md#production-build-served-by-django).

See [docs/architecture.md](docs/architecture.md) for URL layout and ownership.

## Chat & Connect preview (FE2)

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173/chat-mock` for three incoming requests and a five-message thread. See [frontend setup and demo](frontend/README.md), [wireframes](docs/chat-connect-wireframes.md), and the [API contract proposal awaiting owner sign-off](docs/api-contract-chat.md).

## Environment variables

| Variable | Required on staging | Local default | Purpose |
|---|---|---|---|
| `SECRET_KEY` | Yes | dev value from `.env.example` | Django's cryptographic signing key. The app will not start without it. Use a unique value on staging and never commit it. |
| `DEBUG` | No (defaults to `False`) | `True` (from `.env.example`) | Turns debug mode on/off. Never set to `True` on staging. |
| `ALLOWED_HOSTS` | Yes | `127.0.0.1,localhost` | Comma-separated hostnames Django will serve (no `https://`). Staging: `acm-packreferrals-production.up.railway.app`. If it's missing, every request returns 400 Bad Request. |
| `CSRF_TRUSTED_ORIGINS` | Yes | unset (empty list) | Comma-separated origins trusted for form POSTs such as the admin login. Unlike `ALLOWED_HOSTS`, each value must include the scheme. Staging: `https://acm-packreferrals-production.up.railway.app`. If it's missing or wrong, admin login fails with 403 CSRF verification failed. |
| `FRONTEND_URL` | No | `http://localhost:3000` | Frontend origin for links in emails. |
| `EMAIL_BACKEND` | Yes (`anymail.backends.brevo.EmailBackend`) | unset (console) | How email is sent. Unset, email (including verification codes) is printed to the console. Staging uses Brevo's HTTPS API because Railway's plan blocks outbound SMTP (#34). |
| `BREVO_API_KEY` | Yes | unset | Brevo API key (Settings → SMTP & API → API Keys). Required when `EMAIL_BACKEND` is the Brevo backend; the app will not start without it. Never commit it. |
| `DEFAULT_FROM_EMAIL` | No | `Pack Referrals <packreferrals.acm@gmail.com>` | Sender for all email, as `Name <address>`; the name is what inboxes show. The address must be a sender verified in Brevo, or sends are rejected. |
| `SQLITE_PATH` | Yes (`/data/db.sqlite3`) | unset (uses `db.sqlite3` in the project root) | Where the SQLite database file lives. On staging it must point at the `/data` volume, or data is wiped on every redeploy (see [Database persistence](#database-persistence-showcase-day)). |
| `LOG_LEVEL` | No (defaults to `INFO`) | `INFO` | Level for the request log (see [Logging](#logging)). `WARNING` hides the per-request lines; CI sets this to keep test output readable. An invalid value stops the app from starting. |
| `NUM_PROXIES` | Yes (`2`) | unset | How many proxies sit in front of the app. Throttles use it to read the real client IP from `X-Forwarded-For`. Staging has two (a CDN node, then Railway's proxy), measured on 2026-10-24 (#28). Re-measure if the hosting setup changes. Unset, DRF uses the whole header, which a client can fill with fake values unless a proxy strips them, so the auth throttles could be bypassed. |
| `SENTRY_DSN` | Yes | unset (Sentry disabled) | Where errors are sent (see [Error tracking](#error-tracking)). Leave it unset locally and in CI; some tests raise exceptions on purpose. |
| `SENTRY_ENVIRONMENT` | Yes (`staging`) | unset | Environment name on Sentry events. If it's missing, Sentry labels them `production`. |
| `RAILPACK_PACKAGES` | Yes (`node@24`) | not used | Build-time only: extra tools Railway's builder installs. Railpack detects a Python app and doesn't install Node unless asked, so without this the frontend build fails with `npm: not found` (see [Deployment](#deployment-railway)). |

## Running tests and lint

```bash
pip install flake8
python manage.py test
flake8 .
```

Run both before opening a PR. CI runs the same commands.

## CI

GitHub Actions runs these checks on every pull request:

- **lint** (`.github/workflows/ci.yml`): `flake8`
- **test** (`.github/workflows/ci.yml`): `python manage.py test`
- **Frontend** (`.github/workflows/frontend.yml`): `npm run build`, the DOM tests and the Playwright tests, on Node 24. It runs on every PR, not only frontend ones, because backend changes (URLs, static settings) can break the deployed app too.

On pushes to `main`, lint and test always run; Frontend runs only when `frontend/` or its workflow changed. All checks must be green before merging. Results appear in the PR's **Checks** tab.

## Deployment (Railway)

Staging is hosted on [Railway](https://railway.app) and redeploys automatically when `main` is updated. One service runs both the API and the React app.

- **Builder:** Railpack. It installs Python and runs `pip install -r requirements.txt`, then runs the build command. `RAILPACK_PACKAGES=node@24` adds Node (see the table above).
- **Build command:** `cd frontend && npm ci && npm run build`, which writes the app to `frontend/dist/`
- **Start command:** `python manage.py collectstatic --noinput && python manage.py migrate && gunicorn pack_referrals.wsgi`
- **Static files:** `collectstatic` copies them into `staticfiles/`, and [WhiteNoise](https://whitenoise.readthedocs.io/) serves them, since Django doesn't serve static files itself when `DEBUG` is off. Without this, the Django admin is unstyled.
- **React app:** `STATICFILES_DIRS` includes `frontend/dist`, so `collectstatic` also picks up the built app, and WhiteNoise serves its files under `/static/assets/` (Vite's `base` is `/static/` for builds). Every other path except `/api/`, `/admin/` and `/static/` returns the app's `index.html` (`pack_referrals/views.py`, the last URL in `pack_referrals/urls.py`), and React Router shows the right page. Because the app and API share an origin, there's no CORS setup and no API URL to configure. If the build is missing, app pages return `503 Frontend not built` while the API keeps working; check the build logs for the Vite step.
- **Environment variables:** see the table above
- **Volume:** mounted at `/data`, which holds the SQLite database (see below)

The builder, build command and start command are set in Railway's dashboard (service **Settings**), not in this repo, so changes there aren't reviewed. Check them first if a deploy behaves unexpectedly: on 2026-10-25 a changed start command stopped migrations from running, and signup returned 500 until it was restored.

## Logging

`pack_referrals/middleware.py` logs one JSON line to stdout per request, which Railway shows in the service's logs. Each line has `method`, `path` (without the query string, so tokens or codes in the URL aren't logged), `status_code` and `duration_ms`:

```json
{"asctime": "2026-10-15 03:26:23,621", "levelname": "INFO", "name": "pack_referrals.middleware", "message": "GET /api/health/ 200 13.7ms", "method": "GET", "path": "/api/health/", "status_code": 200, "duration_ms": 13.7}
```

Static files served by WhiteNoise aren't logged. Under `runserver` you'll also see Django's own plain-text request lines; those don't appear on staging (gunicorn).

If sending a verification code fails (Brevo down, quota used up, bad key), `accounts.views` logs an `ERROR` line, `Sending a verification code failed`, with the traceback, in the same JSON format. Signup then returns `503` with a "try again" message. Login still returns its usual `200`, so it can't be used to find out which addresses are registered. Search the logs for that message if users report codes not arriving.

## Error tracking

When `SENTRY_DSN` is set, unhandled exceptions are sent to [Sentry](https://sentry.io) with the stack trace and request URL. Each event is tagged with the environment (`SENTRY_ENVIRONMENT`) and the release (the deployed commit, the same `commit_hash` as `/api/health/`). User details, IP addresses and cookies aren't sent (`send_default_pii` is off).

## Database persistence (showcase day)

**Problem:** SQLite stores everything in a single file. By default, that file lives on the container's local disk, which Railway wipes on every redeploy. Any seeded or demo data would be lost each time someone merges to `main`.

**Options considered:**

1. **Persistent volume.** Store the database file on a Railway volume that survives redeploys.
2. **Deploy freeze.** Keep local disk storage and stop redeploying during showcase week.

**Decision: Option 1 (Railway volume).** A volume is mounted at `/data`, and Django reads the database location from a `SQLITE_PATH` environment variable set to `/data/db.sqlite3`. Data persists across redeploys, so the team can keep shipping fixes up to showcase day without wiping demo data. We rejected the deploy freeze because it blocks last-minute bug fixes, and a single accidental merge would erase everything.

**Status: done.** `pack_referrals/settings.py` reads `SQLITE_PATH`, and staging sets it to `/data/db.sqlite3`. Verified on staging on 2026-10-08: after the fix (`542f3f2`) deployed, a test company named `probe-after-fix` was created. It was still listed at `/api/companies/` after the next two redeploys (`85b0d38` and `f2c33c9`).

**How to repeat the check:**

> **Note:** Steps 2 and 6 send `POST` and `DELETE` requests without logging in. That works only because the API is currently unauthenticated (`AllowAny`). Once `IsAuthenticated` is added to these endpoints, those requests will be rejected (401 or 403): send an auth token with them, or create and delete the test company in the Django admin instead. Always delete the test company afterward so no test data is left on staging.

```bash
STAGING=https://acm-packreferrals-production.up.railway.app
```

1. Note the deployed commit: `curl -s $STAGING/api/health/`. Write down `commit_hash`.
2. Create a test company and note the `id` in the response:

   ```bash
   curl -s -X POST $STAGING/api/companies/ \
     -H "Content-Type: application/json" \
     -d '{"name": "Persistence Check"}'
   ```

3. Trigger a real redeploy by merging any PR into `main`. A Railway restart doesn't count: the check is whether data survives a new container.
4. Run `curl -s $STAGING/api/health/` until `commit_hash` shows the new `main` commit. That confirms a new deploy is live.
5. Run `curl -s $STAGING/api/companies/`. "Persistence Check" should still be in the list. If it's missing, check that `SQLITE_PATH` is set on Railway and the volume is mounted at `/data`.
6. Clean up: `curl -s -X DELETE $STAGING/api/companies/<id>/`.

**Note:** Migrations run on every deploy against the volume's database. Test migrations locally before merging so a bad migration doesn't break staging data.

**Never run a seed command (such as `seed_demo_data`) on staging.** The database lives on the volume, so anything a seed writes stays there for good.

## Stack

- Django 5.2 + Django REST Framework
- React + Vite (frontend)
- SQLite
- Gunicorn (production server)
- GitHub Actions (CI) + flake8 (linting)
- Railway (hosting)

## Layout

- `pack_referrals/` — project settings, URLs, WSGI/ASGI
- `api/` — global `/api/health/` only (no domain models)
- `accounts/` — profiles, past roles, auth (`/api/accounts/…`)
- `companies/` — companies (`/api/companies/…`)
- `connections/` — connection requests, reports (`/api/connections/…`)
- `chat/` — conversations, messages (`/api/chat/…`)
- `frontend/` — React frontend (see [frontend/README.md](frontend/README.md))
- `manage.py` — Django CLI
