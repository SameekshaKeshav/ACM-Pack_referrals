# Week 7 referral frontend handoff

Follow-up: recipient Accept/Decline actions are described in [referral actions UI](referral-actions-ui.md). The original Week 7 scope below is historical.

Based on main `ab3c07f` (includes the referral backend, authentication, company/profile
integration and the connection inbox). This change adds frontend code and documentation;
it does not change models, migrations or backend endpoint behaviour.

## What to open

- `/referrals`: authenticated referral form, outgoing/incoming cards and pagination.
- `/chat/<conversation id>`: “Ask … for a referral” opens the form with that person selected.
- The main navigation also has a Referrals link.

Connection and referral requests remain separate. A connection acceptance creates the
conversation; the form offers the other people from the caller's visible conversations,
deduplicated by user ID. Current backend service creates these conversations only on an
accepted connection. The backend remains authoritative and refuses asks without an
accepted connection, after a block, or for an unavailable account. A URL parameter
cannot create a recipient option. An accepted connection missing its conversation would
need its backend data repaired before it appears in these choices.

## Contract and behaviour

- `POST /api/connections/referrals/`: numeric `recipient_id`, `role_title`,
  `message_text`; optional numeric `company_id`, `job_url`, `resume_url`.
- `GET /api/connections/referrals/?type=incoming|outgoing&limit=20&offset=N`:
  reads `{count, results}` and builds local page requests without following next links.
- `GET /api/chat/conversations/`: recipient choices.
- `GET /api/companies/`: optional company choices. The directory includes companies
  outside a recipient's profile; the backend rejects an ineligible choice and the form
  keeps the draft. Company-list failure still permits an ask without a company.
- The shared API client attaches Bearer auth, handles token refresh and session changes.
- Required nonblank role (255 code points), note (500 code points), http/https links
  (500 code points each). Unicode counting includes emoji as one code point.
- While sending, the form is disabled. Success clears role/note/links/company, retains
  the recipient, selects outgoing and reloads persisted cards. It does not claim email
  delivery.
- Errors keep the draft. Backend field/detail errors are shown. A 409 shows a duplicate
  explanation and disables resubmission until edited; no retry button is offered.
- Cards render user content as plain text. Only safe http/https URLs become links;
  external tabs use `noopener noreferrer`.
- There are no referral Accept/Decline buttons yet: these endpoints are Week 8 work.
- Company interview posts and formal accessibility audits remain Week 8 work.

## Checks performed here

- Vite production build passed.
- All 95 DOM tests passed, including nine new referral tests covering exact request/auth,
  pending submission, success card, duplicate conflict, field/network errors, Unicode,
  no connections, pagination/direction, safe links and recoverable load errors.
- A temporary local database and actual Django HTTP server were used with synthetic
  JWT accounts and the new frontend API module: accepted conversation lookup, create,
  outgoing list, recipient incoming list, duplicate 409 and unconnected 403 all passed.
  No real mail was sent and no shared database was used.
- Two new Playwright tests are included (create/reload and mobile conflict/layout).
  Chromium crashed at launch in this environment (SIGSEGV), so browser and visual
  verification are pending on a Mac or CI. No browser pass is claimed.

## Run and verify on your Mac

Use the existing clone on a clean `sanjana/referral-ui` branch based on current main.
Apply the included Git patch; do not copy a source folder over your clone.

Backend terminal:

```bash
cd ~/Projects/ACM-Pack_referrals
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

Keep the existing `.env` and local database. The current email settings use
`EMAIL_BACKEND`; local console mail is the default. Brevo credentials are private
backend configuration and are not in this package.

Frontend terminal:

```bash
cd ~/Projects/ACM-Pack_referrals/frontend
npm ci
npm run build
npm run test:dom
npx playwright install chromium
npm test
npm run dev
```

1. Sign in and open `/referrals`. With no accepted connections, sending is disabled.
2. With two active local accounts, send a connection request and accept it using the
   second account (a separate browser profile avoids shared localStorage sessions).
3. Open their chat and follow the referral link; confirm that person is selected.
4. Send a role and note, optionally a company from that person's profile and job/résumé
   links. Confirm the pending card appears in outgoing, and remains after refresh.
5. Sign in as the recipient and check Incoming; confirm the same ask appears.
6. Send the same role/company/person again: verify the duplicate explanation and retained
   draft. Try an unrelated company and verify the backend validation is shown.
7. Check keyboard navigation, pasted emoji at the note limit and the 390px layout.
8. Open `/referrals` logged out and confirm it redirects to login.

After checks and review, push `sanjana/referral-ui` and open a PR into the team's
agreed base (normally current main for this package). This package is local only;
no remote branch, PR or teammate message was created by preparing it.

## Browser test isolation follow-up

Mac verification reported build and all 95 DOM tests passing, but 8/16 browser tests
failing. The inherited chat browser fixtures did not intercept the new connection
inbox/header fetches. Those fixtures now return an empty connection queue instead of
letting synthetic JWT requests reach a live backend and potentially clear the session.

Playwright now starts its own Vite server on port 5174 with server reuse disabled.
This avoids running against a stale or different development frontend on 5173.
The referral test explicitly waits for the page heading and loaded recipient option.
The full browser suite must be rerun on Mac/CI; these changes do not establish a pass
for the previously missing referral form. If it still fails, inspect the generated
`frontend/test-results/**/error-context.md` and the failed test's current URL.

### Referral mock routing correction

The remaining referral browser failures occurred before the page heading appeared.
The referral fixture's `**/api/**` glob also matched Vite's `/src/api/*.js` module
requests, returning JSON in place of JavaScript. It now matches only URL paths that
start with `/api/`, leaving frontend module loads untouched. Rerun `npm test` on Mac
or CI to confirm the browser suite; browser execution remains unavailable here.
