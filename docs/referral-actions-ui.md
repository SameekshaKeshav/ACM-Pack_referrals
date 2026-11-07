# Referral Accept / Decline frontend

Based on main `c51bba7`. Depends on backend PR #57, head `4c8bf32`, which was still
open when this change was prepared. Prepare/review the UI now; merge and verify
its live flow after #57 reaches main. No backend files are included in this change.

## Behaviour

- Incoming pending referral cards offer Accept and Decline; outgoing and resolved
  cards do not. The backend still enforces recipient permissions.
- `PATCH /api/connections/referrals/<id>/accept/` or `decline/`, without a request
  body, uses the shared Bearer/refresh-aware API client.
- The full returned referral is validated: expected ID, accepted/declined status
  matching the requested action, and a valid resolved_at timestamp.
- Only a successful acknowledgement changes status. The card remains visible,
  buttons disappear, a polite live region announces the answer, and focus moves
  to the card's updated status.
- One action is in flight at a time per list; both buttons, list refresh and paging
  are disabled while saving. Changing direction/unmounting aborts the request;
  returning rereads the backend's persisted state.
- Failed requests retain the pending card with an announced error and allow a
  deliberate retry. No accepted status is fabricated after an error.
- 409/404 triggers a list refresh. A request answered in another tab shows its real
  status; a removed/blocked ask disappears. If an action route is not deployed,
  a still-visible pending card explains that availability may be the issue.
- Confirmed answers take precedence over stale list results for the mounted list.
- Referral acceptance creates no conversation and sends no notification email.
  It records an answer to an existing connection's ask.

## Verification

- Accessibility lint and production build passed.
- All 114 DOM tests passed (8 new action tests); checks cover both verbs, Bearer
  auth and empty PATCH body, double click, button visibility, status/focus/live
  announcement, permission/network errors, conflict recovery, unavailable routes,
  stale reads, malformed responses and unmount cancellation.
- Real HTTP/JWT checks against PR #57 in an isolated temporary database passed:
  accept, decline, resolved_at, persisted incoming/outgoing lists, sender403,
  outsider404 and second-answer409.
- Four new Playwright cases cover keyboard accept/decline and reload persistence,
  conflict recovery, and axe scans of pending, failed and resolved controls.
- Browser execution is pending on Mac/CI. Chromium crashes at launch here with
  SIGSEGV, before any assertion or axe scan. No browser/a11y pass is claimed.

## Run on Mac

Apply the included patch on a fresh frontend branch. Keep the existing .env and
local database. Main does not acquire the backend endpoints merely by applying
this frontend patch; get #57 merged and pull main before live integration testing.

```bash
cd frontend
npm ci
npm run lint
npm run build
npm run test:dom
npx playwright install chromium
npm test
```

Browser tests mock the API and do not require Django. Counts are based on current
main; if other PRs add tests, the totals may grow.

## Manual acceptance after backend merge

1. With two connected accounts, create two referral asks for different roles.
2. In the recipient's private/browser-profile session open Referrals → Incoming.
3. Accept one and decline the other. Cards show the new status and no action buttons.
4. Refresh both accounts. Sender Outgoing shows the same answers as recipient Incoming.
5. Keyboard-only: focus an action and press Enter; check the updated status receives
   focus. Check announcements with a screen reader; do not rely on colour alone.
6. With the same ask open in two browser sessions, answer it once and try the other
   session: it should refresh to the first answer rather than overwrite it.
7. Verify outgoing/resolved cards never show answer buttons.

Keep the PR dependent on #57 and require normal CI/review. Staging verification
and notification emails are separate from this frontend change.
