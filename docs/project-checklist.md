# Project checklist

**This file replaces the technical tracker spreadsheet from Nov 4, 2026.** It is the single list of what is left before the showcase (week of Nov 16). Do not use the spreadsheet any more.

Last updated: Nov 4, 2026 by Sameeksha (PM).

## How to use this

1. Find your name below. Those are your tasks.
2. Finish them **as soon as you can**, in priority order. The dates are targets, not deadlines to wait for. Earlier is better, because the demo rehearsal in Week 10 needs everything merged.
3. **Tick the box in the same PR as the work** (`- [ ]` becomes `- [x]`). Do not open a separate PR just to tick a box. If a task needs no code (a decision, a recording), tick it in your next PR, or message Sameeksha.
4. If you are blocked, or a task is bigger than it looks, say so in the team chat the same day. Do not wait for the Thursday meeting.
5. If you think something is missing from this list, open a PR that adds it under the right name.

**Priorities**

- **MUST** is needed for the showcase.
- **SHOULD** is good to have, and gets done after the MUSTs.
- **CUT-FIRST** is the first thing dropped if we run out of time.

**Key dates**

| Date | What |
|---|---|
| Nov 8 | End of Week 9: code frozen except for critical bugs, demo dry-run |
| Nov 9 to 15 | Week 10: seeding real members, practice demo, rehearsal |
| Nov 16 | Showcase week |

**Links:** [Staging](https://acm-packreferrals-production.up.railway.app/) · [API routes](api-routes.md) · [Security checklist](security-checklist.md) · [Wireframes](wireframes/) · [Ownership](ownership.md)

## Who is who

| Role | Person | GitHub |
|---|---|---|
| PM | Sameeksha | `SameekshaKeshav` |
| BE1: auth and data | Karthik | `KarthikPanicker2000` |
| BE2: moderation and safety | Thomas | `tlhart12` |
| BE3: infrastructure and QA | Danny | `danielbakalov` |
| FE1: profile and directory | Rawan | `rawanworks` |
| FE2: chat and connect | Sanjana | `sanjanashettybmsce` |

## Open pull requests

- [ ] **#39** (Thomas): report, block and interview experiences. Has a merge conflict with `main`. See Thomas's list.
- [ ] **#47** (Sanjana): company interview posts and accessibility. Needs a review. Its interview posts list only works once #39's routes are on `main`.

## Thomas (BE2: moderation and safety)

- [ ] **MUST · Nov 6** Resolve the merge conflict on #39 (`docs/security-checklist.md` only) and merge `main` into your branch.
- [ ] **MUST · Nov 6** Fix the review items on #39:
  - Reports require the reporter to be a participant in the message's conversation. A message the reporter cannot see must give the same "does not exist" response as one that is missing.
  - A blocked sender and a not-open recipient get the same error message, so a block is not revealed.
  - Add a per-user throttle on reports, reject reporting yourself, and ignore a duplicate report from the same reporter on the same target.
  - Allow interview experiences to be reported (they are anonymous, so moderators have no other way to act on them).
- [ ] **SHOULD · Nov 6** Offer to split the interview experiences out of #39 into their own PR, so they can merge on their own and unblock Sanjana's #47.
- [ ] **MUST · Nov 6** Block and unblock endpoints (`POST` and `DELETE /api/connections/users/<id>/block/`), as part of #39.
- [ ] **MUST · Nov 8** Add tests for these four cases:
  - A duplicate pending request returns 409.
  - A blocked user returns 403.
  - The 11th request in a day returns 429.
  - A suspended user's login returns 403.
- [ ] **MUST · Nov 8** Admin moderation: "mark reviewed" and "suspend user" actions on `Report`. A suspended user's login and verify return 403, and they are hidden from the directory and from new requests.
- [ ] **MUST · Nov 8** Fix the race where two simultaneous accepts both succeed (`select_for_update()` inside a transaction), and write a test. Confirm in the PR that it was tested and fixed.
- [ ] **SHOULD · Nov 13** Seed about 10 sample connection requests in different states (pending, accepted, declined) between seeded users, so a demo login has a non-empty inbox and at least one chat.
- [ ] **MUST · before Nov 16** Write `python manage.py fix_connection <id> <status>` to clear a stuck state, and test it against a deliberately broken case.
- [ ] **SHOULD** Close issues #22, #26 and #27 if the #39 changes already cover them. Otherwise fix them.
- [ ] **MUST · Nov 16 week** On call during the demo for report and block problems.

## Karthik (BE1: auth and data)

- [ ] **MUST · Nov 9** Referral accept and decline, backend. Today `/api/connections/referrals/` can only list and create, so incoming referral requests stay "pending" forever. Add `PATCH /api/connections/referrals/<id>/accept/` and `decline/`:
  - Only the recipient can answer. Anyone else gets 404, and the sender gets 403, the same as connection accept and decline.
  - Answering twice returns 409, and two simultaneous answers must not both succeed.
  - Add tests, and update `docs/api-routes.md` and `docs/security-checklist.md`.
  - Notification emails are **not** part of this. Do not build them.
  - Tell Sanjana as soon as it is on `main`, because her Accept and Decline UI depends on it.
- [ ] **MUST · Nov 8** Freeze the auth code, with zero open P0 or P1 auth bugs. Cover the token-expiry edge case for a demo that runs long.
- [ ] **SHOULD · Nov 6** Alumni follow-ups from the #45 review:
  - Rejecting an approved request should also suspend the matching profile, or the admin action description must say you have to suspend it too. An existing access token keeps working after a reject.
  - Document that rejecting a resubmission does not revoke an earlier approval.
  - Update the "registered emails can be discovered" gap in the security checklist to include approved alumni addresses.
  - Add the signup 201-versus-400 behavior for approved addresses to the Known gaps, as agreed.
- [ ] **MUST · Nov 13** Write `python manage.py seed_directory_data`: about 20 realistic companies with users of varied majors and grad years. Confirm by browsing the directory on staging.
- [ ] **SHOULD** Add a length limit to `Profile.bio` (issue #27).
- [ ] **MUST · before Nov 16** Run `reset_demo_data` once yourself, so you can run it if the presenter is busy.
- [ ] **MUST · Nov 16 week** On call during the demo to watch the login success rate in Sentry and the logs.

## Danny (BE3: infrastructure and QA)

- [ ] **MUST · Nov 6** Add accessibility checks to the frontend CI: `eslint-plugin-jsx-a11y` in lint, and `@axe-core/playwright` scans of the main pages.
- [ ] **SHOULD · Nov 6** Add a `get_authed_client(user)` test helper, and document how to run `python manage.py test` in a way that needs no extra setup. Confirm one teammate has run it successfully.
- [x] **MUST · Nov 8** Export a Postman (or Insomnia) collection covering every endpoint, each with a saved passing example. Today there are only two collections.
- [x] **MUST · Nov 8** Delete the older Sentry events on staging that contain emails or verification codes, and confirm in the #42 thread when it is done.
- [ ] **MUST · Nov 8** Create an admin login on staging for the person who will approve alumni requests (the admin page is `/admin/`), and tell Sameeksha who has it.
- [ ] **MUST · Nov 13** Re-run the write load test against the seeded data volume. Write the final decision on SQLite or Postgres for showcase day. The earlier write test passed on SQLite.
- [ ] **MUST** Do not raise `WEB_CONCURRENCY` above 1 unless a shared cache is configured first. Throttle counts are kept per worker, so every limit would multiply.
- [ ] **SHOULD** Plan for Brevo's 300 emails per day limit on showcase day. For example, check usage the day before, and keep demo accounts pre-verified or use `issue_demo_token`.
- [ ] **SHOULD** Fix the `manage.py check --deploy` warnings (HSTS and secure cookies) if there is time.
- [ ] **MUST · before Nov 16** Test a one-command rollback to the last known-good commit in under 2 minutes, at least once.
- [ ] **MUST · Nov 16 week** On call during the demo to watch the logs and error tracking.

## Rawan (FE1: profile and directory)

- [ ] **MUST · Nov 6** Fix the double-click bug on Add role and Remove role: add a busy flag that disables the buttons while a request is in flight, and treat a 404 on remove as success.
- [ ] **MUST · Nov 6** Add `verified_via` to `fromServer()` in `src/api/profile.js` (one line, item 3 in [alumni-access-frontend-handoff.md](alumni-access-frontend-handoff.md)). It fails silently if missing, because that function is an allowlist.
- [ ] **MUST · Nov 6** Wireframe styling PR for the profile page, matching `docs/wireframes/profile-directory-profile-view.png` and `profile-directory-profile-edit.png`:
  - Two-column layout, with the avatar, Edit button and toggle on the left.
  - An initials avatar in the circle (no photo upload, because the backend has no image field).
  - "Open to connect" as a toggle.
  - An About card, and job role rows with company, role and right-aligned dates.
  - The edit page in the wireframe's layout, with the Roles section.
  - Also use `value={form.grad_year ?? ''}` on the grad year input.
- [ ] **MUST · Nov 8** Empty, loading and error states for Profile and Directory. A save attempted while offline must show a specific error message, not a blank screen.
- [ ] **SHOULD · Nov 8** Responsive and cross-browser checks (Chrome, Safari, Firefox; 375, 768 and 1440 px) on Profile and Directory, with before and after screenshots and no horizontal scroll or overlap.
- [ ] **SHOULD · Nov 8** Accessibility pass on Profile, Directory and Company pages: no serious or critical axe violations, a keyboard-only walkthrough (edit profile, search, open a company), AA contrast, and a label on every input.
- [ ] **MUST · Nov 13** Walk through the seeded data on staging, and sign off a checklist that every seeded user shows correctly in search and filters.
- [ ] **MUST · before Nov 16** Record a backup screen recording of the profile and directory part of the demo, saved locally.
- [ ] **MUST · Nov 16 week** On call for Profile and Directory issues on the demo device and browser.

## Sanjana (FE2: chat and connect)

- [ ] **MUST · Nov 6** Get #47 reviewed and merged. Its interview posts list works only once #39's routes are on `main`, so coordinate with Thomas.
- [ ] **MUST · Nov 8** Empty, loading and error states for Chat and Connect. A failed message shows "Failed to send - tap to retry" on that message, and retry sends it again.
- [ ] **SHOULD · Nov 8** Responsive checks on Chat and Connect at 375, 768 and 1440 px, with the input still usable at every width, and before and after screenshots.
- [ ] **SHOULD · Nov 8** Accessibility pass on Chat, Connect and the auth screens: no serious or critical axe violations, a keyboard-only walkthrough (send a request, accept, send a message), and `aria-live` announcements for new messages and errors.
- [ ] **MUST · after Karthik's referral accept/decline is on `main`** Accept and Decline buttons on incoming referral requests, with the card updating to the new status.
- [ ] **SHOULD · after Sameeksha's company endpoint is on `main`** Referral form: offer only the companies on the selected connection's profile, instead of every company.
- [ ] **CUT-FIRST** Report and block UI, once #39 is merged.
- [ ] **MUST · Nov 13** Write a timed demo script under 3 minutes and reproduce it successfully twice in a row on staging.
- [ ] **MUST · before Nov 16** Record a backup screen recording of the chat and connect part of the demo, saved locally.
- [ ] **MUST · Nov 16 week** On call for Chat and Connect issues during the live run.

## Sameeksha (PM)

- [ ] **MUST · Nov 6** Make the scope-freeze decision and tell the team. In scope: alumni access (backend is merged, form is below), referral accept and decline (Karthik). Out of scope for the showcase: referral notification emails. Confirm or change this.
- [ ] **MUST · Nov 9** Alumni access, frontend. Build the request form on a new public route and a "Request alumni access" link on the signup page. See [alumni-access-frontend-handoff.md](alumni-access-frontend-handoff.md) for the contract. Add tests.
- [ ] **SHOULD · Nov 11** Company endpoint for the referral form: a way to get the current and past companies of a connection, so the form can offer only valid companies. The backend rejects any company that is not on the recipient's profile, with a 400.
- [ ] **MUST · Nov 8** Run the full demo dry-run, with zero P0 bugs in the connect-to-chat flow. Triage and assign only critical bugs.
- [ ] **MUST** Present demo readiness at Check-in #3.
- [ ] **MUST · Nov 8** Write the end-to-end test: signup, verify, send request, accept, send message, fetch message, in one test. Include the referral fields (company, role title, job link) and check that a non-connection gets 403.
- [ ] **SHOULD** Extend the Postman collection with the referral fields, and keep a bug log with priorities.
- [ ] **MUST · Nov 10** Write `python manage.py reset_demo_data` and `python manage.py issue_demo_token <email>` (prints a login token, and only runs when `ALLOW_DEMO_TOOLS=1`). Run the reset once and confirm it works.
- [ ] **MUST · Nov 13** Recruit 15 to 20 real ACM members to sign up on staging and fill out real profiles and company history. Start this week.
- [ ] **MUST · Nov 13** Organize the full team demo rehearsal.
- [ ] **MUST · before Nov 16** Record a backup screen recording of the full demo flow, saved offline.
- [ ] **SHOULD** Send the thank-you reply to Ms. Priest (NC State Alumni Engagement) if it has not gone out, and tell the team the alumni decision in writing.
- [ ] **SHOULD** Update the stale docs: `docs/mvp-scope.md` (profile and directory are no longer "on a mock"), `docs/recent-updates.md`, and the alumni line in `docs/design.md`.
- [ ] **MUST · Nov 16 week** Lead the showcase presentation.

## Done so far

| PR | What | Who |
|---|---|---|
| #36 | Directory filters | Sameeksha |
| #37 | Chat polling load test, React app served from Django on staging | Danny |
| #38 | Profile page wired to `/api/accounts/me/` | Rawan |
| #40 | Email through Brevo, with handling for a failed send | Danny |
| #41 | Connect button, request inbox, nav badge | Sameeksha |
| #42 | Sentry no longer receives request bodies or variables | Danny |
| #43 | Referral request UI for accepted connections | Sanjana |
| #44 | Write load test on SQLite | Danny |
| #45 | Alumni access requests, approved by hand in the admin | Karthik |
| #46 | Current role and company, add and remove past roles | Rawan |
