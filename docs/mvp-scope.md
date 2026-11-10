# MVP scope: MUST / CUT list

**Status:** Updated Nov 10, 2026 (code freeze was Nov 8). The table below shows where each row stands today. Open work and owners are in [project-checklist.md](project-checklist.md).

**Showcase:** the week of Monday 11/16. Plan for the earliest day (Monday 11/16) and treat the rest of that week as buffer, not build time. The team rehearsal is Friday 11/13.

**Definition of Done for every row:** merged to `main`, CI green, visible on staging.

## The demo story

One flow the audience can follow in about five minutes:

1. A new user signs up with an @ncsu.edu address, enters the emailed code and lands signed in.
2. They fill in their profile (major, graduation year, past roles).
3. They search the directory or a company page and find an alum.
4. They send a connection request; the alum accepts; they chat.
5. Once connected, they send a specific referral request (company, role, job link, why they fit), and the alum gets an email about it.

## MUST (the demo does not work without these)

| # | What | Backend | Frontend | Staging |
|---|------|---------|----------|---------|
| 1 | Sign up, verify, login | Done | Done (#30) | Done (#34): codes arrive through Brevo |
| 2 | Profile view and edit | Done (`/api/accounts/me/`, #31) | Done: wired to the API, current role and past roles, wireframe styling (#38, #46, #60, #61) | On staging |
| 3 | Directory and company pages | Done (`/api/accounts/users/`, `/api/companies/?search=`, company detail, #18, #31) | Done: directory with filters (#36) and company page (`Directory.jsx`, `Company.jsx`). Interview posts on the company page are in review (#47) | On staging |
| 4 | Connection request, accept, decline | Done (#10, #16) | Done: Connect button, request inbox and nav badge (#41), chat and connect polish (#64) | On staging |
| 5 | Chat (send, history, polling, unread) | Done (#21) | Done (#30, #64) | On staging |
| 6 | Referral request to a connection | Create, list and detail done. Accept and decline are in review (#57). The notification email is out of scope for the showcase | Form and card done (#43). Accept and Decline buttons are in review (#58) | On staging, except accept and decline until #57 and #58 merge |
| 7 | Safety: suspended users hidden, blocked users cannot use chat | Done (#39): hidden and chat checks, block and unblock endpoints, block check on connection requests, report endpoint. Admin actions to mark a report reviewed and suspend a user are in review (#62) | Report and block UI is cut (the API and admin are the safety path for the demo) | On staging |
| 8 | Staging that works for the audience | Backend is up, email through Brevo (#40), one-command rollback (#51) | The React app is served from the staging URL (#37) | Seeded demo data and a reset command (`reset_demo_data`, `issue_demo_token`) are in review (#55) |

What is left is merging the open pull requests (#47, #55, #57, #58, #62), putting real members' profiles on staging, and rehearsing. No new features are planned.

## SHOULD (build if on track, cut without breaking the demo)

- Anonymous interview experiences on company pages. The API is on `main` (#39); the UI is in review (#47). It is not part of the demo story above, so it is the first thing to cut if the dry-run shows trouble.
- Accessibility checks in CI (`eslint-plugin-jsx-a11y` and axe scans) and the manual audits.
- Moderation in the admin (the Report API is create-only: `POST /api/reports/`; reports are read and actioned in the admin). The Report and Block buttons in the UI are cut.

## CUT, in this order, if we are behind

1. Directory filters beyond company search
2. Read receipts
3. Message pagination in the UI (the backend supports it)
4. Mobile polish
5. Firefox testing

## Known limits of referral requests

- One pending ask per person, company and role (case ignored). Until accept and decline (#57) are on `main`, nothing leaves pending, so a second ask for the same role gets a 409 and stays blocked. The form shows the 409 message, not a retry button.
- The referral form offers every company. A company endpoint that limited it to the connection's own companies was cut (Nov 10); the backend rejects a company that is not on the recipient's profile with a 400.
- The referral list is paged (`limit`/`offset`, like the directory). The conversation list is still unpaged (bounded by the user's own conversations).

## Decisions

- Interview experiences are SHOULD, not MUST. Referral notification emails and the company endpoint for the referral form are out of scope for the showcase.
- Staging deploy of the frontend: BE3 (done, #37).
- Email (decided): we send through Brevo's HTTPS API with `django-anymail`, since Railway's free plan blocks SMTP and Brevo needs no sending domain. The sender is `packreferrals.acm@gmail.com`. Confirmed on staging on 2026-10-28.

## Testing plan

- `python manage.py test` runs the whole backend suite in CI on every PR.
- `npm run test:dom` and `npm test` run the frontend suites in CI.
- One end-to-end test for signup, verify, connect, accept, chat and referral request (#53, in review).
- `postman/run_collection.sh` runs every endpoint against a throwaway database (see `postman/README.md`).
- A full dry-run of the demo story on staging, with a keyboard-only pass.
- Week 10: rehearsal on Friday 11/13 with 15 or more real members' profiles on staging.
