# Pack Referrals — Backend Architecture

## Layering

| Layer | Location | Owner |
|-------|----------|--------|
| **HTTP (DRF views, URLs, serializers)** | Domain apps: `accounts`, `companies`, `connections`, `chat` | BE1–BE3 (+ PM on connections/chat overlap) |
| **Persistence (models, migrations, admin)** | `api` app (temporary shared module) | Whole backend; schema changes via PR review |
| **Project config** | `pack_referrals/` | PM / any dev |

Domain apps import models from `api.models` until the persistence layer moves (see below).

## URL map (v1 scaffold)

| Prefix | Resources |
|--------|-----------|
| `/api/health/` | Global health |
| `/api/accounts/` | `profiles/`, `past-roles/`, `health/` |
| `/api/companies/` | company CRUD, `health/` |
| `/api/connections/` | `connection-requests/`, `reports/`, `health/` |
| `/api/chat/` | `conversations/`, `messages/`, `health/` |

Frontend and API clients should use these prefixes. Legacy flat paths (`/api/profiles/`, etc.) are **removed** after the domain-app migration.

## Why `api` still exists

Django migrations and foreign keys are tied to the app label `api`. Renaming the app to `core` mid-sprint would require careful migration surgery (`RenameApp`, updating `Migration.dependencies`, and team-wide rebases).

**Decision (Sprint 0):**

1. **Now:** Treat `api` as the **shared persistence layer** (models + migrations + Django admin registrations). All REST surface area lives in domain apps.
2. **After schema stabilizes (target: end of Sprint 1 / early Sprint 2):** Rename `api` → `core` in a dedicated PR when:
   - No open migration conflicts on `main`
   - ERD in `docs/erd.md` matches production models
   - Team agrees on a freeze window (~1 day) for model changes

**Alternative (not chosen now):** Split models into each domain app immediately. Rejected for Sprint 0 because cross-app FKs (`Profile` ↔ `Company`, `ConnectionRequest` → `Conversation`) multiply migration ordering issues while the schema is still moving (e.g. `unverified` state, company dedupe).

## Serializer ownership

Serializers live next to views in each domain app (`accounts/serializers.py`, etc.) and reference `api.models`. When/if models move to `core` or per-app modules, serializers move with their views or import from `core.models`.

## Adding routes (team rule)

1. Implement views and URL patterns **inside your domain app** only.
2. Root `pack_referrals/urls.py` already includes each app; do **not** add resource routes there.
3. Schema changes: edit `api/models.py`, run `makemigrations`, update `docs/erd.md` in the same PR.

## Ownership (backend)

| Dev column | App | Typical endpoints |
|------------|-----|-------------------|
| BE1 — auth & profiles | `accounts` | verification, session, profiles, past roles |
| BE2 — connections & moderation | `connections` | connection-request state machine, reports, blocks |
| BE3 — chat | `chat` | conversations, messages, polling |
| Shared directory | `companies` | company CRUD, search (often BE1 + FE1) |
