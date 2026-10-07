# Chat & Connect frontend

React + Vite + React Router + Tailwind, NC State red/white theme. This scaffold is under `frontend/` because no FE1 scaffold was present in main or the published branches when inspected on 2026-10-07. Merge these feature components into FE1's scaffold if one exists elsewhere.

## Run locally

Requires Node 22.13+ (Node 24 recommended).

```bash
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173/chat-mock**. No Django or login is needed for the three incoming requests, two outgoing requests, sidebar, five-message thread, and local Accept/Decline demo. Reload or use Reset demo to restore fixtures. The other sidebar rows intentionally show an empty thread. Chat composer input is editable; chat Send is disabled and no chat endpoint is called.

## Demo (two minutes)

1. Open `/chat-mock`; verify three incoming cards and five bubbles in Avery's thread.
2. Open browser DevTools → Console. Click Accept on Maya: count changes 3 → 2, the card disappears, and console shows `PATCH /api/connections/123/accept/` with `{mock:true}`. No network request is made. Decline is also local.
3. Click Outgoing for read-only pending/accepted examples. Select sidebar rows, then Avery to return to the five messages.
4. Scroll to Send a request. Type or paste 500 ASCII characters: counter says `0 remaining`. Attempt a 501st: text stays at 500. Pasting 501 characters also truncates at 500. Unicode uses code-point counts to match Python `len()`.
5. For the actual POST flow, see below. The test suite intercepts HTTP and demonstrates 201/409/network failure without sending to real users.

## Live request POST

Run Django at `http://127.0.0.1:8000`; Vite proxies `/api`. Copy `.env.example` to `.env.local` only if overriding that target, then restart Vite. Open the API test panel and paste a valid **test account** JWT. It remains only in page memory. Enter a recipient test user's integer ID, write the note, click Send Request. Request is exactly:

```http
POST /api/connections/
Content-Type: application/json
Authorization: Bearer <access-token>

{"recipient_id":31,"message_text":"Hello!"}
```

The form expects `201 {"id":203,"status":"pending"}`; success adds the row to the outgoing list. Only valid success clears the note. It prevents duplicate clicks while sending and shows useful 400/401/403/404/409/429/501/server/network errors.

**Backend dependency:** current main does not implement this shape/path, and `thomas/main` has a 501 stub. A real successful POST cannot be claimed until BE2's endpoint and auth are implemented. Do not change the URL to main's nested raw CRUD route to work around this. The frontend HTTP wiring is implemented and covered by browser tests with intercepted responses.

## Verification

```bash
npm run build
npx playwright install chromium
npm test
```

Playwright starts Vite automatically on port 5173; it can reuse an existing local Vite server. Tests cover exact fixture counts, local PATCH logging without a real PATCH, outgoing/sidebar navigation, 500/501 typing/paste and emoji lengths, exact POST/auth body, single in-flight submission, success, error recovery, token absence, and mobile layout.

Wireframes: [`../docs/chat-connect-wireframes.md`](../docs/chat-connect-wireframes.md). API proposal and approval table: [`../docs/api-contract-chat.md`](../docs/api-contract-chat.md). Acceptance walkthrough: [`../docs/chat-connect-handoff.md`](../docs/chat-connect-handoff.md).
