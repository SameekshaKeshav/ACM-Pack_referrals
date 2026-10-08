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

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Global health: `/api/health/`. Django admin: `/admin/`.

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
| `FRONTEND_URL`, `EMAIL_*` | No | see `.env.example` | Frontend origin for links in emails, and SMTP settings. With `EMAIL_HOST` empty, email is printed to the console. |

CSRF trusted origins (the staging URL) are hardcoded in `pack_referrals/settings.py`, not read from environment variables. The database path is also hardcoded for now (see [Database persistence](#database-persistence-showcase-day)).

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

- **Start command:** `python manage.py migrate && gunicorn pack_referrals.wsgi`
- **Environment variables:** see the table above
- **Volume:** mounted at `/data` (intended for the SQLite database; see below)

## Database persistence (showcase day)

**Problem:** SQLite stores everything in a single file. By default, that file lives on the container's local disk, which Railway wipes on every redeploy. Any seeded or demo data would be lost each time someone merges to `main`.

**Options considered:**

1. **Persistent volume.** Store the database file on a Railway volume that survives redeploys.
2. **Deploy freeze.** Keep local disk storage and stop redeploying during showcase week.

**Decision: Option 1 (Railway volume).** A volume is mounted at `/data`, and the plan is for Django to read the database location from a `SQLITE_PATH` environment variable set to `/data/db.sqlite3`. Data will then persist across redeploys, so the team can keep shipping fixes up to showcase day without wiping demo data. We rejected the deploy freeze because it blocks last-minute bug fixes, and a single accidental merge would erase everything.

**Status: not done yet.** `pack_referrals/settings.py` still hardcodes the database to `db.sqlite3` in the project root and does not read `SQLITE_PATH`. Until it does, staging data is still wiped on every redeploy.

**Note:** Once this is in place, migrations will run on every deploy against the volume's database. Test migrations locally before merging so a bad migration doesn't break staging data.

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
