# Pack Referrals

ACM NC State project: a verified NC State alumni/student network for browsing company affiliations and requesting referrals.

## Local setup

Requires Python 3.11+.

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

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

## Stack

- Django 5.2 + Django REST Framework
- SQLite (default Django database)

## Layout

- `pack_referrals/` — project settings, URLs, WSGI/ASGI
- `api/` — global `/api/health/` only (no domain models)
- `accounts/` — profiles, past roles, auth (`/api/accounts/…`)
- `companies/` — companies (`/api/companies/…`)
- `connections/` — connection requests, reports (`/api/connections/…`)
- `chat/` — conversations, messages (`/api/chat/…`)
- `manage.py` — Django CLI
