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

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). API routes are under `/api/` (health check: `/api/health/`). Django admin is at `/admin/`.

## Stack

- Django 5.2 + Django REST Framework
- SQLite (default Django database)

## Layout

- `pack_referrals/` — project settings, URLs, WSGI/ASGI
- `api/` — app (models, views, serializers, URLs)
- `manage.py` — Django CLI
