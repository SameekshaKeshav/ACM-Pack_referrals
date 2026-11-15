# Pack Referrals

ACM NC State project: a verified NC State alumni/student network for browsing company affiliations and requesting referrals.

**Staging:** https://acm-packreferrals-production.up.railway.app/

**What is left to do:** see [docs/project-checklist.md](docs/project-checklist.md). It replaces the tracker spreadsheet.

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
| `ALLOW_DEMO_TOOLS` | No (leave unset) | unset | Switches on `reset_demo_data` and `issue_demo_token` (see [Demo accounts](#demo-accounts-for-the-showcase)). Only the value `1` works. Set it for one command, not as a permanent Railway variable. |

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

### Rolling back staging

If a merge breaks staging, put it back on the last commit that worked:

```bash
scripts/rollback.sh <commit> --dry-run   # checks only, deploys nothing
scripts/rollback.sh <commit>             # asks, deploys, prints how long it took
```

You need the Railway CLI, logged in and linked to the service (`railway status` shows it), plus `jq`. The last commit that worked is usually the one before the bad merge: `git log --oneline --first-parent origin/main`, or `railway deployment list`, which shows the commit of each deployment.

The script picks one of two methods:

- **Rollback** reuses that deployment's existing build, so it takes about as long as a restart. Railway only allows it for recent deployments. On our plan that is just the one before the current one (checked on 2026-11-04).
- **Rebuild** (`railway redeploy --commit`) builds the commit from source, like a normal deploy. It works for any commit, but takes as long as a deploy. Pass `--rebuild` to use it even when a rollback is possible.

Measured on staging on 2026-11-05, going between `44c859e` and `c95d932`, with the script's totals (checks plus deploy, without time at the prompt):

| Method | Total |
|---|---|
| Rollback | **29 s** and **17 s** (Railway timed the three rollbacks at 17, 21 and 11 s) |
| Rebuild | **81 s** (2 s of checks, 79 s to build and go live) |

Both are under the 2-minute target, but a rebuild's time depends on the build, so allow for more if dependencies have changed.

Things a rollback does not do:

- **It does not undo migrations.** They stay applied on the `/data` database, and older code may fail against newer tables. The script refuses a commit that is missing a migration that a later deployment applied, and lists the files. `--force` skips the check. Use it only if you've read the migration and know the old code copes. Otherwise fix forward.
- **It does not stop the next deploy.** Railway deploys every merge to `main`, which replaces the rollback. Tell the team to hold merges until the fix is merged.

To undo a rollback, run the script again with the newer commit. It prints that command when it finishes.

**After a rollback, `/api/health/` shows `"commit_hash": null`** (seen on 2026-11-05, even when rolling back to the original deployment of a commit). A rebuild of the same commit reported it again. Both health and Sentry's release tag read `RAILWAY_GIT_COMMIT_SHA`, which a deployment created by a Railway rollback apparently doesn't set, so Sentry events have no release until the next normal deploy. To see which commit is live, use `railway deployment list`. The script checks there too, and only uses `/api/health/` to check the app is answering.

### Demo accounts for the showcase

Eight accounts let the presenter run the demo from a known start. There are **two demo sets**, so the two judge panels each get a fresh demo without a reset in between: use set A for the first panel and set B for the second. Each set is three of the team's own `@ncsu.edu` accounts:

| | Presenter (signs in) | Alum the presenter already chats with | Alum waiting in the presenter's inbox |
|---|---|---|---|
| **Set A** | `skeshav2@ncsu.edu` | `sshett24@ncsu.edu` (Red Hat) | `rtelgoha@ncsu.edu` (Google) |
| **Set B** | `dbbakalo@ncsu.edu` | `kmpanick@ncsu.edu` (Red Hat) | `tlhart@ncsu.edu` (Google) |

Both sets share two fictional members: `demo.jordan@ncsu.edu` (open to connect, so each presenter can send a fresh request live) and `demo.lee@ncsu.edu` (not open to connect). They do not receive mail.

**These six accounts become demo accounts.** A reset overwrites their name, major, graduation year, bio and company with the demo profile, and removes their connection requests, conversations, referrals, reports, blocks and past roles. Do not use them for anything real until `reset_demo_data --remove` has been run after the showcase. A reset refuses to touch an account that is a staff or superuser account. The dry run does **not** check for this (only the real run does, and it changes nothing when it refuses), so check the staff accounts yourself first: see "Running it on staging" below.

Two commands manage them. Both do nothing unless `ALLOW_DEMO_TOOLS=1` is set for that command.

```bash
# See what a reset would delete. Changes nothing.
ALLOW_DEMO_TOOLS=1 python manage.py reset_demo_data --dry-run

# Put the demo accounts back to the start (asks first; --yes skips the question).
ALLOW_DEMO_TOOLS=1 python manage.py reset_demo_data

# A login for a presenter (skeshav2@ncsu.edu for set A, dbbakalo@ncsu.edu for set B),
# without waiting for an emailed code.
ALLOW_DEMO_TOOLS=1 python manage.py issue_demo_token skeshav2@ncsu.edu

# After the showcase: delete the demo accounts entirely.
ALLOW_DEMO_TOOLS=1 python manage.py reset_demo_data --remove
```

**The starting state, for each set:** the presenter already chats with the Red Hat alum (3 messages, 1 unread) and can ask that alum for a referral. The Google alum's connection request is waiting in the presenter's inbox to accept. Jordan is open to connect but not yet connected, so the presenter can send a new request live. Lee is not open to connect. All eight appear in the directory. Playing one set does not change the other.

**What it touches:** only these eight accounts and their requests, conversations, referrals, reports, blocks and past roles. No other member's profile or data is changed, and the command prints the counts first. A conversation or request between a demo account and a real member is removed too (counted separately as "with a real member"), because it cannot exist without the demo account.

**`issue_demo_token`** only works for the eight demo addresses, never for any other member. It prints one line to paste into the browser's developer console: it saves the login where the app looks for it and opens `/chat`. The access token lasts about a day and the refresh token printed with it up to 7 days (`ACCESS_TOKEN_LIFETIME_HOURS`, `REFRESH_TOKEN_LIFETIME_DAYS`). It refuses a staff or superuser account, and so does `reset_demo_data`, including `--remove`. Anyone with shell access on the server can sign in as any of the eight, so treat the login like a password.

**Running it on staging:** the database is on the Railway volume, so the command has to run inside the service, from a shell opened with `railway ssh`. `railway run` does not work: it runs on your laptop, where `/data` does not exist. Danny runs it, because the Railway project is in his workspace. Anyone else needs to be invited to the project and to add an SSH key (`railway ssh keys`). Staging is the Railway environment called `production`.

```bash
# On your laptop. Staging sleeps when idle, and railway ssh cannot wake it: it fails with
# "Railway TUI not currently available" or "agent path is temporarily unavailable".
curl -s https://acm-packreferrals-production.up.railway.app/api/health/
railway ssh --environment production --service ACM-Pack_referrals

# Now on the server (the prompt looks like root@...:/app#, not your laptop's).
pwd                                   # /app
echo $RAILWAY_ENVIRONMENT_NAME        # production

# The SSH shell does not have the app's PATH, so `python` is "command not found" until you
# copy it from the running app (process 1). This reads only PATH, not the other variables.
export PATH="$(tr '\0' '\n' < /proc/1/environ | sed -n 's/^PATH=//p')"

# Check Django uses the volume. If this is not under /data, stop: the commands would run
# against an empty database in the container.
python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['NAME'])"

# Staff accounts. None of them may have one of the eight demo addresses.
python manage.py shell -c "from django.contrib.auth import get_user_model as G; print(list(G().objects.filter(is_staff=True).values_list('username', 'email')))"

ALLOW_DEMO_TOOLS=1 python manage.py reset_demo_data --dry-run
ALLOW_DEMO_TOOLS=1 python manage.py reset_demo_data      # read the counts, then answer y
exit
```

Use the interactive shell rather than `railway ssh -- <command>`: the reset asks before changing anything and refuses without a terminal. Set `ALLOW_DEMO_TOOLS=1` only in front of the command, as above, never in the service's Variables in Railway's dashboard, where it would apply to the running app.

**Shortcut from your laptop:** `bash scripts/reset_demo_staging.sh` wakes staging, runs the dry run, asks `[y/N]`, then resets. It needs the Railway CLI logged in and linked (`railway status`). It does not list the staff accounts first, so run the staff check above before the first use. A reset still refuses to touch a staff account, and then changes nothing.

## Logging

`pack_referrals/middleware.py` logs one JSON line to stdout per request, which Railway shows in the service's logs. Each line has `method`, `path` (without the query string, so tokens or codes in the URL aren't logged), `status_code` and `duration_ms`:

```json
{"asctime": "2026-10-15 03:26:23,621", "levelname": "INFO", "name": "pack_referrals.middleware", "message": "GET /api/health/ 200 13.7ms", "method": "GET", "path": "/api/health/", "status_code": 200, "duration_ms": 13.7}
```

Static files served by WhiteNoise aren't logged. Under `runserver` you'll also see Django's own plain-text request lines; those don't appear on staging (gunicorn).

If sending a verification code fails (Brevo down, quota used up, bad key), `accounts.views` logs an `ERROR` line, `Sending a verification code failed`, with the traceback, in the same JSON format. Signup then returns `503` with a "try again" message. Login still returns its usual `200`, so it can't be used to find out which addresses are registered. Search the logs for that message if users report codes not arriving.

## Error tracking

When `SENTRY_DSN` is set, unhandled exceptions are sent to [Sentry](https://sentry.io) with the stack trace and request URL. Each event is tagged with the environment (`SENTRY_ENVIRONMENT`) and the release (the deployed commit, the same `commit_hash` as `/api/health/`). User details, IP addresses and cookies aren't sent (`send_default_pii` is off). Request bodies and the values of variables in the stack trace aren't sent either, because they can contain emails, verification codes and chat messages. Sentry sends both by default, so `settings.py` turns them off explicitly. You get the file, function and line of each frame, but to see the data involved, reproduce the error locally.

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

**Never run a seed command (such as `seed_demo_data`) on staging.** The database lives on the volume, so anything a seed writes stays there for good. The one exception is `reset_demo_data`, which is built for staging: it only touches the eight [demo accounts](#demo-accounts-for-the-showcase), shows what it will delete first, and refuses to run unless `ALLOW_DEMO_TOOLS=1` is set.

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
