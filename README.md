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

Environment variables are loaded from `.env` (see [`.env.example`](.env.example)). With `EMAIL_HOST` left empty, outbound email is printed to the console — fine for local auth spikes.

If migrations were reset on a branch (no production data yet), reset your local DB:

```bash
rm -f db.sqlite3
python manage.py migrate
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Global health: `/api/health/` (includes `commit_hash`, which is `null` locally). Django admin: `/admin/`.

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
| `FRONTEND_URL`, `EMAIL_*` | No | see `.env.example` | Frontend origin for links in emails, and SMTP settings. With `EMAIL_HOST` empty, email is printed to the console. |
| `SQLITE_PATH` | Yes (`/data/db.sqlite3`) | unset (uses `db.sqlite3` in the project root) | Where the SQLite database file lives. On staging it must point at the `/data` volume, or data is wiped on every redeploy (see [Database persistence](#database-persistence-showcase-day)). |

## Running tests and lint

```bash
pip install flake8
python manage.py test
flake8 .
```

Run both before opening a PR. CI runs the same commands.

## CI

GitHub Actions (`.github/workflows/ci.yml`) runs two checks on every pull request and on every push to `main`:

- **lint**: `flake8`
- **test**: `python manage.py test`

Both must be green before merging. Results appear in the PR's **Checks** tab.

## Deployment (Railway)

Staging is hosted on [Railway](https://railway.app) and redeploys automatically when `main` is updated.

- **Start command:** `python manage.py collectstatic --noinput && python manage.py migrate && gunicorn pack_referrals.wsgi`
- **Static files:** `collectstatic` copies them into `staticfiles/`, and [WhiteNoise](https://whitenoise.readthedocs.io/) serves them, since Django doesn't serve static files itself when `DEBUG` is off. Without this, the Django admin is unstyled.
- **Environment variables:** see the table above
- **Volume:** mounted at `/data` (intended for the SQLite database; see below)

## Database persistence (showcase day)

**Problem:** SQLite stores everything in a single file. By default, that file lives on the container's local disk, which Railway wipes on every redeploy. Any seeded or demo data would be lost each time someone merges to `main`.

**Options considered:**

1. **Persistent volume.** Store the database file on a Railway volume that survives redeploys.
2. **Deploy freeze.** Keep local disk storage and stop redeploying during showcase week.

**Decision: Option 1 (Railway volume).** A volume is mounted at `/data`, and Django reads the database location from a `SQLITE_PATH` environment variable set to `/data/db.sqlite3`. Data persists across redeploys, so the team can keep shipping fixes up to showcase day without wiping demo data. We rejected the deploy freeze because it blocks last-minute bug fixes, and a single accidental merge would erase everything.

**Status: done.** `pack_referrals/settings.py` reads `SQLITE_PATH`, and staging sets it to `/data/db.sqlite3`. Verified on staging on 2026-10-08: after the fix (`542f3f2`) deployed, a test company named `probe-after-fix` was created. It was still listed at `/api/companies/` after the next two redeploys (`85b0d38` and `f2c33c9`).

**How to repeat the check:**

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
