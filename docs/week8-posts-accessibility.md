# Week 8 — company interview posts and accessibility

## Scope and dependencies

Based on main `c95d932`, after the referral PR #43 and profile role PR #46.
This is frontend work: no backend models, migrations, permissions or moderation
endpoints are changed. Report/block UI is cut first as directed by the Week 8 plan.

The experiences UI follows BE2 PR #39, head `9123a41`, which is still open as of
this implementation. Main has no experiences endpoint yet. The UI shows a real
unavailable message and disables creation on 404/501; it never substitutes fixtures.
A merged UI alone does not establish that the feature works on staging.

## Company interview posts

Open `/company/<id>?tab=interviews`. The tab has:

- Loading, empty, unavailable and recoverable error states.
- Anonymous cards showing role, outcome, difficulty, process and month/year.
- A four-field required form, role max 255 and process max 5000 Unicode code points.
- Exact numeric difficulty 1–5; outcome `offer`, `rejected` or `no_response`.
- One submission in flight, explicit error messages and retained drafts on failures.
- A successful post appears in the list, and inputs reset only after acknowledgement.
- Own-post deletion through an inline confirmation. Other posts have no delete action.
- All member text renders as text. Response normalization whitelists public fields;
  author identity and exact timestamps are not displayed.
- Privacy guidance explains that moderators can identify authors, and asks writers
  to avoid personal/confidential information. This is anonymity from other members.
- Requests abort on unmount; the parent keys by company, so drafts and responses
  cannot carry into a different company. A fetch finishing after a mutation cannot
  restore a deleted post or drop a newly created one.

API contract (existing BE2 proposal, not a new frontend-defined route):

| Method | Path | Body / response |
|---|---|---|
| GET | `/api/companies/<id>/experiences/` | Array of public experience rows |
| POST | Same collection | `{role_title, outcome, difficulty, process_text}` → 201 row |
| DELETE | `/api/companies/<id>/experiences/<experience_id>/` | No body → 204 |

Public row: `id`, `role_title`, `outcome`, `difficulty`, `process_text`, `is_mine`,
`month`, `year`. Sender/author/company identity comes from auth and the URL, never
from the POST body. BE2 checks verified/active access and ownership; the five-post
per-day limit returns 429. UI controls are not security enforcement.

## The a11y tooling

1. `eslint-plugin-jsx-a11y` statically checks JSX with its recommended rules across
   `src`. React Router `to` is recognized as a link destination. Named scrollable
   regions may be focusable for keyboard scrolling; no recommended rule is disabled.
   ESLint 9 is pinned because the installed jsx-a11y release declares support through 9.
2. `@axe-core/playwright` runs actual browser page scans. Tests retain the full axe
   result as JSON attachments, and fail when any violation has impact `serious` or
   `critical`. Default axe rules run: no rule, page region or baseline is excluded.
   Moderate/minor issues remain visible in the attachments.
3. The existing Frontend workflow now runs JSX lint and includes the axe tests in
   `npm test`; test-result artifacts upload even after a failure.

```bash
cd frontend
npm ci
npm run lint:a11y
npm run build
npm run test:dom
npx playwright install chromium
npm run test:a11y
npm test
```

`test:a11y` is a focused run. `npm test` already includes it; running both is only
necessary when debugging accessibility separately from the rest of the suite.
Playwright owns its isolated Vite server on port 5174. Its API fixtures intercept
only `/api/` URL paths and never Vite's `/src/api/` JavaScript module requests.
No running Django, personal JWT or real email is needed for browser tests.

## Accessibility changes

- Skip-to-main links and keyboard-focusable main targets on authenticated/auth pages;
  profile loading/error/edit states now keep a main landmark and a page heading.
- Explicit code/email error associations (`aria-invalid`, `aria-describedby`).
- Company tabs retain valid panel targets and support arrow/Home/End navigation.
- Tab keyboard events live on the actual tab buttons; profile Add Role keyboard
  events live on the actual inputs. Dialog keyboard behaviour remains tested.
- Focusable named chat history for independent keyboard scrolling.
- Labelled legacy editable role inputs, meaningful empty-profile heading.
- More readable muted text, timestamps, statuses and composer help; pending/loading
  states preserve text contrast rather than fading text. Inline links are underlined.
- Visible select focus and a reduced-motion preference rule.
- Experience controls have labels/hints, status/error announcements, a deletion
  confirmation, and focus recovery after cancelling or completing deletion.

Automated browser coverage includes signup/login, enter-code and code error, populated
chat and failed send, referrals, directory, profile view/edit, company members,
Connect dialog, posts populated/empty/unavailable, delete confirmation, posting error,
and mobile posts/referrals. Keyboard assertions cover skip links and modal focus.

## Validation in this environment

- Clean dependency installation, production build and JSX a11y lint passed.
- All 110 DOM tests passed, including eight new experience tests and updated company
  tab coverage (existing profile-role tests are retained).
- Frontend API functions exercised through real HTTP against BE2 PR #39 in a detached
  backend checkout with temporary SQLite and synthetic JWT users: GET, POST, anonymous
  output for another user, own DELETE, other-user DELETE 403, max-length 400 and daily
  limit 429 passed. No mail or shared data was touched.
- A semantic-only precheck of nine rendered routes found no axe violations with
  color-contrast omitted because JSDOM has no layout. This is **not** the browser
  audit and does not satisfy the new Definition of Done.
- Browser launch fails here with SIGTRAP, before test assertions or axe scans run.
  All 32 browser tests are discoverable (16 existing, 3 posts, 13 accessibility).
  No full browser, visual or zero-serious/critical axe pass is claimed yet.

## Required review / manual acceptance

Keep the PR draft until Mac/CI browser tests pass, review is complete, and BE2's
endpoint dependency has a clear integration plan. New pages meet the added DoD only
when the browser axe report has no serious/critical violations, not merely because
this gate is present in code.

1. Run the command sequence above on Mac/CI. Inspect full axe attachments for failures.
2. With BE2 PR #39 available, exercise real list/create/delete from two active accounts.
   Main without it should show the unavailable state. Do not merge BE2 changes into
   this frontend patch or reset teammates' code just to manufacture a passing demo.
3. Keyboard-only: Tab to Skip, Enter into main; use company tab arrows/Home/End;
   fill the experience form, cancel/confirm own deletion, open/close Connect with
   Escape, check Tab trapping and returned focus.
4. Check 200% zoom, 390px viewport, long text and visible focus. Confirm readable
   status/error text. Do not enter private interview material in test posts.
5. Use VoiceOver/NVDA to check labels, region names and announcements; automated
   checks alone do not establish WCAG conformance. Record reviewer/date/results here.

Manual browser/assistive-technology review: pending.
Backend merge/staging verification: pending BE2 #39.

References: [Playwright accessibility testing](https://playwright.dev/docs/accessibility-testing),
[jsx-a11y](https://github.com/jsx-eslint/eslint-plugin-jsx-a11y),
[BE2 PR #39](https://github.com/SameekshaKeshav/ACM-Pack_referrals/pull/39).
