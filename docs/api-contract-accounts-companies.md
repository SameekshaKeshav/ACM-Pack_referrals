# API contract — profile, directory and companies

Owner: BE1 (Karthik). Companion to [`api-contract-chat.md`](api-contract-chat.md).

Everything here is in PRs #18 and #31. Every example below is a **real response
captured from a running server**, not written from memory.

## Conventions

- Every endpoint needs `Authorization: Bearer <access_token>`. Without one you
  get **401**, not an empty list.
- Writes send `Content-Type: application/json`.
- Dates are `YYYY-MM-DD`. An ongoing role has `end_date: null`.
- Ids are integers.
- Timestamps are UTC ISO-8601.
- **Identity always comes from the token.** Sending `user` in a body is ignored.

### Response shapes differ by endpoint

Two shapes exist in this API. Check which one you are calling.

| Endpoint | Shape |
|---|---|
| `GET /api/accounts/users/` | paged object: `{count, next, previous, results[]}` |
| `GET /api/companies/` | bare array |
| `GET /api/companies/<id>/`, `GET /api/accounts/me/` | single object |

Chat endpoints also return bare arrays. Aligning these is an open team
question — raise it if it costs you anything.

---

## What changed from the mock in `api/profile.js`

Five differences. Each will break silently if you keep the old assumption.

| Mock | Actual |
|---|---|
| `past_roles[].company: 'Google'` | an **object**: `{id, name, industry_tag, logo_url}` |
| `start_date: '2025-05'` | `'2025-05-01'` — full date |
| `end_date: ''` for an ongoing role | `null` |
| `id: 'role-1'` | integer `1` |
| `name` is editable | `name` is **read-only**; write `first_name` and `last_name` |

---

## Profile

### `GET /api/accounts/me/`

The signed-in user's own profile. There is no id in the URL, so there is no way
to request anyone else's.

```json
{
  "user_id": 1,
  "email": "jane@ncsu.edu",
  "name": "Jane Doe",
  "first_name": "Jane",
  "last_name": "Doe",
  "major": "Computer Science",
  "grad_year": 2028,
  "bio": "Junior, backend.",
  "current_role": "Co-op",
  "current_company": { "id": 2, "name": "Red Hat", "industry_tag": "", "logo_url": "" },
  "open_to_connect": true,
  "account_status": "active",
  "past_roles": [
    {
      "id": 1,
      "company": { "id": 1, "name": "Google", "industry_tag": "", "logo_url": "" },
      "role_title": "SWE Intern",
      "start_date": "2025-05-01",
      "end_date": "2025-08-01"
    }
  ]
}
```

`past_roles` is included so the profile page renders in **one request**, but it
is read-only here — write roles through `/api/accounts/past-roles/`.

### `PATCH /api/accounts/me/`

Partial update. `PUT` is refused with 405.

Writable: `first_name`, `last_name`, `major`, `grad_year`, `bio`,
`current_role`, `current_company_name`, `open_to_connect`.

Read-only and silently ignored if sent: `email`, `account_status`, `user_id`,
`name`, `past_roles`.

```json
{ "bio": "Junior, backend.", "current_company_name": "Red Hat", "current_role": "Co-op" }
```

A company name that is blank or only a legal suffix ("Inc.", "LLC") returns
**400**. `grad_year` must be between 2000 and 2100.

`current_company_name` is a **typed string, not an id**. It resolves to an
existing company when one matches (see deduplication below) and comes back as
an object. Send `""` to clear the current employer.

---

## Past roles

### `POST /api/accounts/past-roles/`

```json
{ "company_name": "Google", "role_title": "SWE Intern",
  "start_date": "2025-05-01", "end_date": "2025-08-01" }
```

Returns **201**:

```json
{
  "id": 1,
  "company": { "id": 1, "name": "Google", "industry_tag": "", "logo_url": "" },
  "role_title": "SWE Intern",
  "start_date": "2025-05-01",
  "end_date": "2025-08-01"
}
```

Note the asymmetry: you **send a string** (`company_name`) and **receive an
object** (`company`). The backend resolves the name so the directory does not
fill with near-duplicate employers.

Omit `end_date` for an ongoing role.

### `PATCH` / `DELETE /api/accounts/past-roles/<id>/`

Only the owner. Someone else's role returns **404**, not 403 — the API does not
confirm that a role you cannot touch exists.

### Errors

```json
{ "company_name": ["This field may not be blank."] }
{ "end_date": ["End date cannot be before the start date."] }
```

---

## Companies

### Deduplication — read this before building the UI

Companies are never created directly. They appear when someone adds a role at
one, and the name is matched on a normalized key: lowercased, whitespace
collapsed, punctuation dropped, a trailing `inc`/`llc`/`ltd`/`corp`/`co`
removed.

```
"Google"  "  google  "  "Google Inc."  "GOOGLE, LLC"  "google corp"   → one company
"Google Cloud"                                                        → a different one
```

**The first spelling anyone types becomes the display name.** If the first
person to add the company types `"google inc."`, that is what everyone sees on
the company page. Tell me if the UI needs tidier names — we could prefer the
shortest spelling, or let an admin set a canonical one.

### `GET /api/companies/?search=goog`

Bare array. Case-insensitive, matches anywhere in the name, and also matches
the normalized key — so `"Google Inc."` finds the company stored as `"Google"`.

```json
[ { "id": 1, "name": "Google", "industry_tag": "", "logo_url": "" } ]
```

No matches is `[]` with status **200**, never a 404. A blank or
whitespace-only `search` is ignored and returns everything. Not paginated.

### `GET /api/companies/<id>/`

```json
{
  "id": 1,
  "name": "Google",
  "industry_tag": "",
  "logo_url": "",
  "affiliated_users": [
    { "user_id": 1, "name": "Jane Doe", "major": "Computer Science",
      "grad_year": 2028, "role_title": "SWE Intern",
      "start_date": "2025-05-01", "end_date": "2025-08-01", "is_current": false },
    { "user_id": 2, "name": "Bob Lee", "major": "Statistics",
      "grad_year": 2027, "role_title": "Data Analyst",
      "start_date": "2024-06-01", "end_date": null, "is_current": false }
  ]
}
```

`is_current: true` means this is the person's **current** employer. Those rows
take `role_title` from the profile and have `null` dates. Someone who is both a
current employee and has a past role here appears **once**, as current.

Only verified members appear. Unverified and suspended accounts are hidden.

Companies are read-only over the API: `POST` and `DELETE` return **405**.

---

## People directory

### `GET /api/accounts/users/`

Paged. Filters are optional and combine with AND.

| Parameter | Behaviour |
|---|---|
| `major` | substring, case-insensitive (`?major=computer` matches "Computer Science") |
| `grad_year` | exact |
| `company_id` | current employer **or** any past role there |
| `limit` | default 20, capped at 100 |
| `offset` | standard offset paging |

```
GET /api/accounts/users/?major=statistics&grad_year=2027&limit=20
```

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    { "user_id": 2, "name": "Bob Lee", "major": "Statistics", "grad_year": 2027,
      "current_role": "", "current_company": null, "open_to_connect": true }
  ]
}
```

Only `account_status == "active"` members are listed.

A directory row carries no `bio` and no contact details — it is enough to
decide whether to send a connection request, which is the one action it leads
to. Use `GET /api/companies/<id>/` for the company view of the same people.

### Errors

A non-numeric or negative filter is a **400**, not a silently unfiltered list:

```json
{ "grad_year": "Must be a whole number." }
```

---

## Things to tell me about rather than work around

- If you need a field that is not here, ask — do not infer it from a model.
- If the two response shapes cost you anything, say so and I will align mine.
- If the "first spelling wins" display name looks wrong in the UI, that is a
  real design question and worth settling before the showcase.
