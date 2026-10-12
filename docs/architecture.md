# Pack Referrals — Backend Architecture

## Layering

| Layer | Location | Owner |
|-------|----------|--------|
| **Models, migrations, admin** | Domain apps: `accounts`, `companies`, `connections`, `chat` | BE1–BE3 (see ownership table) |
| **HTTP (DRF views, URLs, serializers)** | Same domain apps | Same |
| **Global API health** | `api` app (no models) | PM / any dev |
| **Project config** | `pack_referrals/` | PM / any dev |

Each backend dev runs `makemigrations` only inside their app(s), which avoids conflicting `api.0003_*` migrations on parallel branches.

## Model ownership

| App | Models |
|-----|--------|
| `accounts` | `Profile`, `PastRole` |
| `companies` | `Company` |
| `connections` | `ConnectionRequest`, `Report` |
| `chat` | `Conversation`, `ConversationParticipant`, `Message` |

Cross-app foreign keys use string references (e.g. `Report.reported_message` → `"chat.Message"`, `Profile.current_company` → `"companies.Company"`).

## URL map (v1)

| Prefix | Resources |
|--------|-----------|
| `/api/health/` | Global health |
| `/api/accounts/` | `profiles/`, `past-roles/`, `health/` |
| `/api/companies/` | company CRUD, `health/` |
| `/api/connections/` | `connection-requests/`, `reports/`, `health/` |
| `/api/chat/` | `conversations/`, `messages/`, `health/` |

Tell frontend before wiring clients: paths are prefixed (e.g. `/api/accounts/profiles/`, not `/api/profiles/`).

## Schema changes (team rule)

1. Edit **your app’s** `models.py` only.
2. Run `python manage.py makemigrations <your_app>` and commit that app’s migration folder.
3. Update `docs/erd.md` in the same PR.
4. Implement views/serializers in the same app; do not add resource routes to root `urls.py`.

## Resetting local DB after migration squash

While there is no production/seed data, squashing app migrations is done by deleting old `api` migrations and re-running per-app migrations. After pulling such a change:

```bash
rm -f db.sqlite3
python manage.py migrate
```

Once real seed data exists, use normal migration operations instead of deleting history.

## Ownership (backend)

| Dev column | App | Typical work |
|------------|-----|--------------|
| BE1 — auth & profiles | `accounts` (+ `companies` for directory) | verification, profiles, past roles |
| BE2 — connections & moderation | `connections` | connection-request state machine, reports, blocks |
| BE3 — chat | `chat` | conversations, messages, polling |
