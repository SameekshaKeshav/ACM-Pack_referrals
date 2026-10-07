# Sanjana's one-day Chat / Connect handoff

## Ready in this branch

- `/chat-mock`: React static component tree, three fake incoming requests and a fake five-message thread.
- Incoming Accept/Decline, read-only outgoing requests and selectable conversation list.
- Accept removes request #123 locally and logs `PATCH /api/connections/123/accept/`; neither action calls an API.
- Send Request makes `POST /api/connections/` with `{recipient_id,message_text}`, a runtime access token, a 500-character cap and live counter. It requires a real compatible endpoint to succeed outside browser tests.
- Wireframe SVG and layout notes in `docs/`; API proposal in `docs/api-contract-chat.md`, with actual pending approval states.
- Local run/demo instructions and meaningful browser tests in `frontend/`.

## Finish the external handoff

1. Post the SVG/wireframe doc and the review-branch/PR link in the actual team channel. The channel was not identified in the attachments, so no team-channel post has been made from this workspace.
2. Thomas reviews connection paths/shapes and implements the non-stub POST endpoint. Sameeksha reviews chat shapes, ownership, block/text and pagination decisions. Add each real approval permalink/date to the contract table.
3. Sanjana reviews and records her FE2 approval, demos locally, and follows the repo's one-review-before-merge rule. A prepared proposal is not a both-sides-signed-off contract.

## Suggested team post

Chat/Connect wireframes and frontend are ready for review in the feature branch. `/chat-mock` shows 3 incoming requests, outgoing examples, the conversation sidebar, and a 5-message thread. Accept removes a card locally and logs the intended PATCH. Send Request posts `{recipient_id,message_text}` to `/api/connections/` and caps the note at 500 characters with a live counter.

Wireframes: `docs/chat-connect-wireframes.md` and `docs/wireframes/chat-connect.svg`. Contract: `docs/api-contract-chat.md`. Demo: `cd frontend && npm ci && npm run dev`, then `http://localhost:5173/chat-mock`.

Thomas: please review the connection contract and canonical `/api/connections/` route; current main still uses the nested CRUD route and your branch has the stub. Sameeksha: please review the chat shapes and decisions listed in the contract. The sign-off table is pending until we record your actual approvals.

## Scope

This catch-up implements FE2 weeks 2–5. It does not implement chat APIs, poll real threads, accept requests on the backend, create conversations, report/block, or send chat messages. Those later tasks depend on backend ownership and an approved contract.
