# MVP scope: MUST / CUT list

**Status:** DRAFT for Check-in #2. The team agrees it (or changes it) at the check-in, then this page is the reference.

**Showcase:** the week of Monday 11/16. The day within that week is not set yet, so plan for the earliest day (Monday 11/16) and treat the rest of that week as buffer, not build time.

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
| 1 | Sign up, verify, login | Done | Done (#30) | **Email set up but not yet confirmed** (#34): sends through Brevo; a real signup on staging still has to deliver a code |
| 2 | Profile view and edit | Done (`/api/accounts/me/`, #31) | **Still on a mock** (`api/profile.js`) | Not visible |
| 3 | Directory and company pages | Done (`/api/accounts/users/`, `/api/companies/?search=`, company detail, #18, #31) | **Not wired:** the directory shows placeholder cards and the company page is a stub | Not visible |
| 4 | Connection request, accept, decline | Done (#10, #16) | Components built; not retested end to end | Not visible |
| 5 | Chat (send, history, polling, unread) | Done (#21) | Done (#30) | Not visible |
| 6 | Referral request to a connection | Create, list and detail done (Wk 7); accept/decline and email are Wk 8 | Form and card are Wk 7 (FE2) | Not visible |
| 7 | Safety: suspended users hidden, blocked users cannot use chat | Hidden and chat checks done; **block and unblock endpoints not built** | Report/block UI not built | Not visible |
| 8 | Staging that works for the audience | Backend is up | **The frontend is not served from the staging URL yet** | Real email, persistent database, seeded demo data and a reset command |

The two biggest MUST gaps today are not features, they are wiring: items 2 and 3 are finished on the backend but the screens are still a mock (profile) and placeholders (directory, company page), and nothing is deployed for the audience to use.

## SHOULD (build if on track, cut without breaking the demo)

- Anonymous interview experiences on company pages (new this week: BE2 builds the API in Wk 7, FE2 the UI in Wk 8). It is the largest new piece of scope and is not part of the demo story above, so it is the first thing to cut if the Week 9 dry-run shows trouble.
- Accessibility checks in CI (`eslint-plugin-jsx-a11y` and axe scans) and the manual audits.
- Report button and moderation in the admin (the Report API is still open, issue #22).

## CUT, in this order, if we are behind

1. Directory filters beyond company search
2. Read receipts
3. Message pagination in the UI (the backend supports it)
4. Mobile polish
5. Firefox testing

## Known limits of referral requests (until Week 8)

- One pending ask per person, company and role (case ignored). Accept and decline are Week 8, and nothing leaves pending before then, so a second ask for the same role gets a 409 and stays blocked. The form should show the 409 message, not a retry button.
- The referral list is paged (`limit`/`offset`, like the directory). The conversation list is still unpaged (bounded by the user's own conversations).

## Decisions the team needs to make at Check-in #2

- Ask the committee lead which day in the week of 11/16 the showcase is.
- Agree this list, in particular that interview experiences are SHOULD and not MUST.
- Agree who owns the staging deploy of the frontend and by when (suggest: BE3, before the Week 9 dry-run).
- Email (decided): we send through Brevo's HTTPS API with `django-anymail`, since Railway's free plan blocks SMTP and Brevo needs no sending domain. The sender is `packreferrals.acm@gmail.com`. What's left for #34 is a real signup on staging.

## Testing plan

- `python manage.py test` runs the whole backend suite in CI on every PR.
- `npm run test:dom` and `npm test` run the frontend suites in CI.
- Week 8: one end-to-end test for signup, verify, connect, accept, chat and referral request.
- Week 9: a full dry-run of the demo story on staging, with a keyboard-only pass.
- Week 10: rehearsal with 15 or more real members' profiles on staging.
