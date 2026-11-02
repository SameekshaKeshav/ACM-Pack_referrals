# Alumni access: what it needs from the frontend

For **Rawan (FE1)** and **Sanjana (FE2)**. Owner: BE1 (Karthik). Companion to
[`api-contract-accounts-companies.md`](api-contract-accounts-companies.md),
which holds the full request/response contract.

NC State has no alumni-verification API — Alumni Engagement confirmed the
directory ended with their CRM change. So signup stays `@ncsu.edu` only and
alumni get in by **manual admin approval**.

> **Pending Sameeksha's confirmation.** This was raised as must-have vs cut for
> the Thursday meeting. Don't build against it until she has signed off; scope
> could still change.

**The endpoint is unreachable until someone builds a form.** Nothing below is
assigned yet.

## 1. The request form — a new public route

```js
import { publicRequest } from '../api/client';

await publicRequest('/api/accounts/alumni-access-requests/', {
  method: 'POST',
  body: { email, full_name, unity_id, grad_year, major, linkedin_url, note },
});
```

`publicRequest` is already exported and omits `Authorization`, which is correct
here: an alum has no account yet. The route belongs **outside** `RequireAuth` in
`src/App.jsx`, next to `/signup` and `/login`.

| Field | Required | Notes |
|---|---|---|
| `email` | yes | Any domain — that is the point |
| `full_name` | yes | Max 150 |
| `unity_id` | yes | Letters then digits, starts with a letter (`jdoe`, `jdoe2`). Case-insensitive; the backend lowercases it |
| `grad_year` | yes | Four digits |
| `major` | yes | Max 255 |
| `linkedin_url` | no | Must be a valid URL if sent |
| `note` | no | **Max 500 characters** — please enforce client-side too |

**Include a hidden input named `confirm_email`, left empty.** It is a spam trap:
a submission that fills it is silently discarded. Hide it from users, do not
prefill it, keep it out of the tab order.

### Three things that will look like bugs but are deliberate

- **Success is `202`, not `201`**, with
  `{ "detail": "Thanks - your request is with the team..." }`. `send()` treats
  202 as ok and returns the body, so show `data.detail`.
- **The same 202 comes back whether the request was stored, was a duplicate, or
  tripped the trap.** Otherwise the endpoint tells a stranger who has already
  applied. There is no way to distinguish them, by design — so no "you have
  already applied" message.
- **Field errors are a normal `400`** with per-field messages, and
  `ApiError.data` carries them, so they can be mapped onto inputs rather than
  using the flattened `error.message`.

Throttled at **3 per 15 minutes per client**, returning `429`. `errorText()`
already renders *"Too many attempts. Please wait before trying again."*

## 2. The entry point on `/signup` — most likely to get missed

An alum who has not been approved, or who does not know this exists, will type a
personal address into signup and get:

```json
{ "email": ["Email must be an @ncsu.edu address."] }
```

That is currently a dead end, and the form is unreachable without a link.
`src/pages/Auth.jsx` needs a *"Not a current student? Request alumni access"*
link near the email field, and ideally that 400 should surface it inline rather
than only showing the raw message.

**`Auth.jsx` has no clear owner** — `git log` shows it last touched by Codex, and
it sits in neither FE column of the tracker. One of you needs to claim it.
Sanjana is the likelier fit, being adjacent to the auth integration in #30.

## 3. After approval, nothing new

Approval grants **eligibility, not an account**. An approved alum then goes
through the existing flow unchanged: `/signup` → emailed code → `/enter-code` →
verify. No new auth screens, and no change to those request bodies. Their
`account_status` is `unverified` until they verify, exactly like a student.

## 4. One line in `profile.js` — Rawan

`GET /api/accounts/me/` gains one read-only field:

| Field | Values |
|---|---|
| `verified_via` | `"ncsu_email"` or `"admin_approval"` |

`fromServer()` in `src/api/profile.js` is an explicit allowlist, so the field is
**silently dropped** unless it is added:

```js
verified_via: data.verified_via ?? 'ncsu_email',
```

Read-only — do not add it to `WRITABLE_FIELDS`. Badging admin-approved alumni in
`ProfileView.jsx` is optional; the data is there either way.

**`account_status` has not changed** — still only `unverified` / `active` /
`suspended`. No fourth value was added, so any existing status check keeps
working.

## What does not exist, so don't build it

- **No endpoint to read, list or check the status of a request.** No status page,
  no polling, no "pending" screen. Approval is communicated out of band.
- **No email** is sent on submission, approval or rejection. If the form implies
  "we will email you", that is a promise nothing currently keeps — worth raising
  with Sameeksha.
- **No way to edit or withdraw** a submitted request.

## Confirming it reaches the backend

```bash
curl -i -X POST http://localhost:8000/api/accounts/alumni-access-requests/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"alum@gmail.com","full_name":"Jo Alum","unity_id":"jalum","grad_year":2019,"major":"Computer Science"}'
```

Expect `202` and the `detail` string, then check the row at
`/admin/accounts/alumniaccessrequest/`. A fourth post inside 15 minutes returns
`429` — that is the throttle, not a bug.

---

If any of the three deliberate-weirdness items makes the UX awkward, say so. The
backend can change; working around it in the UI is worse.
