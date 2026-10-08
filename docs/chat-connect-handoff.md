# Sanjana's one-day Chat / Connect handoff

## Ready in this branch

- `/chat-mock`: React static component tree, three fake incoming requests and a fake five-message thread.
- Incoming Accept/Decline, read-only outgoing requests and selectable conversation list.
- Accept removes request #123 locally and logs `PATCH /api/connections/123/accept/`; neither action calls an API.
- Send Request makes `POST /api/connections/` with `{recipient_id,message_text}`, a runtime access token, a 500-character cap and live counter. It requires a real compatible endpoint to succeed outside browser tests.
- Wireframe SVG and layout notes in `docs/`; API proposal in `docs/api-contract-chat.md`, with actual pending approval states.
- Local run/demo instructions and meaningful browser tests in `frontend/`.

## Finish the external handoff

Published: [PR #7 - Add Chat/Connect UI and API contract proposal](https://github.com/SameekshaKeshav/ACM-Pack_referrals/pull/7), from `sanjana/chat-connect-ui` into `main`. The earlier publishing limitation is resolved; Sanjana applied the patch in an authenticated clone and published the branch/PR.

As of 2026-10-08, both [Frontend CI](https://github.com/SameekshaKeshav/ACM-Pack_referrals/actions/runs/37806242668) and [Tests CI](https://github.com/SameekshaKeshav/ACM-Pack_referrals/actions/runs/37806242462) passed for commit `ebd792623164fb36b07404cb5d0c96624af91440`. [PM review](https://github.com/SameekshaKeshav/ACM-Pack_referrals/pull/7#issuecomment-6064498871) recommends merging as **UI mock + proposed contract** when both workflows are green. Recheck the latest commit's CI before merging. This recommendation does not constitute API contract sign-off or successful backend integration.

Team-channel sharing is not confirmed yet. The remaining handoff and integration work is:

1. Share [PR #7](https://github.com/SameekshaKeshav/ACM-Pack_referrals/pull/7), `docs/wireframes/chat-connect.png`, and the wireframe notes in the actual team channel.
2. Thomas confirms/implements canonical connection routes: `POST /api/connections/`, `PATCH /api/connections/<id>/accept|decline/`, and lists with `?type=`. PM and the chat owner approve chat list/poll/read shapes, `sender_id`, and accept returning `conversation_id`. Add each real approval permalink/date to `docs/api-contract-chat.md`; approvals may be tracked as follow-up issues.
3. Sanjana records her FE2 approval and follows the repo's one-review-before-merge rule. Once BE2 is ready, integrate the approved Accept endpoint and the backend conversation-creation flow, and verify a real authenticated POST. A merge of this mock does not make it an integrated chat feature or a both-sides-signed-off contract.

## Suggested team post

Chat/Connect wireframes and frontend are published in [PR #7](https://github.com/SameekshaKeshav/ACM-Pack_referrals/pull/7) as a UI mock and proposed contract. `/chat-mock` shows 3 incoming requests, outgoing examples, the conversation sidebar, and a 5-message thread. Accept removes a card locally and logs the intended PATCH. Send Request posts `{recipient_id,message_text}` to `/api/connections/` and caps the note at 500 characters with a live counter.

Wireframes: `docs/chat-connect-wireframes.md`, `docs/wireframes/chat-connect.png`, and `docs/wireframes/chat-connect.svg`. Contract: `docs/api-contract-chat.md`. Demo: `cd frontend && npm ci && npm run dev`, then `http://localhost:5173/chat-mock`.

Thomas: please review/implement the canonical connection routes. PM's 2026-10-08 review confirms that main still exposes the nested CRUD route; live integration needs the proposed routes and compatible response shapes. Sameeksha: please review the chat shapes and decisions listed in the contract. The sign-off table is pending until we record your actual approvals.

## Scope

This catch-up implements FE2 weeks 2–5. It does not implement chat APIs, poll real threads, accept requests on the backend, create conversations, report/block, or send chat messages. Those later tasks depend on backend ownership and an approved contract.

## Verification

Latest local verification by Sanjana on 2026-10-08:

- `npm ci`: succeeded; audit reported 0 vulnerabilities after the React Router update to 7.18.4.
- `npm run build`: passed.
- `npm run test:dom`: all 5 React interaction tests passed, including typed/pasted 500/501 limits, Unicode count, local Accept/Decline, POST/auth payload, duplicate-click prevention, and failure/retry cases.
- `npm test`: all 7 Playwright Chromium tests passed on Sanjana's Mac, including the 375 x 812 mobile viewport check. The earlier execution-environment Chromium limitation no longer blocks browser verification.
- Existing `python manage.py test`: all 3 tests passed in the original handoff environment; this was not part of Sanjana's latest local frontend run.
- Wireframe PNG: rendered and visually inspected in the original handoff.

Remote verification: Frontend and Tests workflows passed for the published commit linked above. API test scenarios intercept/mock backend responses; they verify frontend behavior, not real backend persistence. A successful live POST and API contract approvals remain pending.
