# Chat / Connect API contract

Status: **proposed for review; not signed off**. Prepared for Sanjana Shetty (FE2), Thomas Hart (BE2), and Sameeksha Keshav (PM). Date: 2026-10-07.

## Evidence and route decision

Inspected [main at 110e11a](https://github.com/SameekshaKeshav/ACM-Pack_referrals/tree/110e11a3eca2bcc470b0a6e828fc2bea75b5dec5), [Thomas's branch at 705d3f7](https://github.com/SameekshaKeshav/ACM-Pack_referrals/tree/705d3f7348651c6497d0fb4effb57c5515f0690e), the attached onboarding guide (pages 19–21, 29–30), and the attached tracker (FE2 weeks 2–5).

The current main router exposes `/api/connections/connection-requests/`, and serializers still expose model fields. Thomas's branch adds `/api/connections/` and `/api/connections/<id>/accept/` as 501 stubs. This proposal uses the task's **`/api/connections/`** for connection requests and the main router's **`/api/chat/`** prefix for chat. These are explicit future contracts, not claims about implemented backend behavior. FE must not silently fall back to the nested endpoint: it has different validation and request fields.

BE2 must implement/confirm the canonical connection paths before live integration. PM must confirm the chat response shapes and owner. Models currently live in the domain apps, superseding the guide's old shared `api.models` instructions. No backend models, migrations, or routing are changed by this frontend PR.

## Common rules

- Every endpoint requires `Authorization: Bearer <access_token>`. JSON writes use `Content-Type: application/json`; IDs are positive JSON integers; API timestamps are UTC ISO-8601 strings.
- The authenticated user supplies sender/reporter identity. Client input must never control it.
- Missing/expired JWT returns 401. Participant/recipient/block restrictions are enforced on the server.
- For this first version, lists return JSON arrays. Chat history is bounded by `limit`; connections and conversation lists are unpaginated initially. Switching to `{results,next,...}` requires a coordinated contract change.
- Validation errors may use DRF field arrays (`{"message_text":["Maximum 500 characters."]}`); general errors use `{"detail":"..."}`. FE maps HTTP status to user-facing text and treats messages as plain text.
- Message length uses Unicode code points, matching Python `len()`, rather than UTF-16 code units. Trim only to check emptiness; preserve intentional whitespace in valid messages.
- Decline is silent and permanent. A sender-facing list must never reveal a decline status. Proposed rule: omit declined outgoing rows; block re-requests server-side with a generic 403. PM/BE2 must approve this decision.
- Soft-block proposal: retain stored history but hide conversations from both users and reject sends. This resolves the guide's hard-delete/soft-block mismatch only after PM approval.

## Connection endpoints — BE2

### Create

`POST /api/connections/`

Request:

```json
{"recipient_id":31,"message_text":"Hi! Could we talk about your internship?"}
```

Success **201** (minimum stable shape consumed by FE):

```json
{"id":203,"status":"pending"}
```

`message_text`: nonblank, 1–500 Unicode code points. Enforce the limit on the server too. Reject self-requests (400), unknown recipient (404), closed/blocked/unavailable recipient or permanently disallowed pair (403), duplicate pending request in either direction or existing connection (409), and the eleventh request in a rolling 24 hours (429). Send no `sender` or `status` fields from FE. Exact duplicate/accepted-pair policy needs BE2 confirmation.

### Incoming / outgoing

`GET /api/connections/?type=incoming` → **200**:

```json
[{"id":123,"sender":{"id":21,"name":"Maya Patel","company":"IBM"},"message_text":"Could we connect?","status":"pending","created_at":"2026-10-07T14:00:00Z"}]
```

Incoming queue contains only pending requests to the authenticated user. `GET /api/connections/?type=outgoing` → **200**:

```json
[{"id":201,"recipient":{"id":31,"name":"Priya Shah","company":"Microsoft"},"message_text":"Could we connect?","status":"pending","created_at":"2026-10-07T14:00:00Z"}]
```

Outgoing may contain pending/accepted rows; see the silent-decline rule above. `company` is a nullable display string. Invalid/missing `type` → 400 (proposal). Empty list → `[]`.

### Resolve

`PATCH /api/connections/123/accept/`, no request body → **200**:

```json
{"id":123,"status":"accepted","conversation_id":5}
```

`PATCH /api/connections/123/decline/`, no request body → **200**:

```json
{"id":123,"status":"declined"}
```

Only recipient may resolve (403 otherwise); unknown ID → 404; already resolved → 409. Accept must atomically create exactly one conversation with the two participants. The recipient may see the declined response; the sender may not. Race/idempotency policy needs PM/BE2 confirmation.

## Chat endpoints — PM / proposed chat owner

### Conversation list

`GET /api/chat/conversations/` → **200**:

```json
[{"id":5,"other_user":{"id":41,"name":"Avery Chen","company":"Red Hat"},"last_message":{"id":5,"sender_id":41,"body_text":"Happy to help!","created_at":"2026-10-07T14:34:00Z"},"updated_at":"2026-10-07T14:34:00Z","unread_count":1}]
```

Only the caller's unblocked conversations; order by `updated_at` descending then `id` descending. `last_message` is null for a new conversation, and `updated_at` then equals its creation time. Unread count counts only unread messages from the other user. Empty list → `[]`.

### Fetch history / older history / poll

`GET /api/chat/conversations/5/messages/?limit=50` → **200**:

```json
[{"id":5,"conversation_id":5,"sender_id":41,"body_text":"Happy to help!","created_at":"2026-10-07T14:34:00Z","read_status":false}]
```

- Default `limit=50`, integer range 1–100. Without cursors return the most recent `limit` messages, sorted oldest first by `(created_at,id)`.
- Older history: `?before=2026-10-07T14%3A34%3A00Z&before_id=5&limit=50`. Use exclusive `(created_at,id)` cursor so equal timestamps do not skip records. `before_id` is an extension to the tracker that needs PM approval. Both fields are required together.
- Poll: `?after=5&limit=50`, integer ID cursor, only IDs greater than `after`, ascending by ID. If a poll returns `limit` messages, immediately request the next batch until caught up; otherwise poll again after ~3 seconds. No new messages → `[]`.
- Do not combine `before` and `after`. Invalid cursors/limits → 400. Unknown conversation → 404; existing conversation without participation → 403; blocked conversation → 403. List scoping must not expose another user's conversation.
- FE deduplicates by message ID and displays chronological order. All times from API are real ISO timestamps; the mock's short display times are fixtures only.

### Send message

`POST /api/chat/messages/`

```json
{"conversation_id":5,"body_text":"Thanks for your help!"}
```

Success **201**:

```json
{"id":6,"conversation_id":5,"sender_id":7,"body_text":"Thanks for your help!","created_at":"2026-10-07T14:35:00Z","read_status":false}
```

Nonblank `body_text`, ≤2000 Unicode code points; sender derived from JWT; nonparticipant/blocked → 403; missing conversation → 404; invalid body → 400. This proposal chooses `conversation_id`/`sender_id` over main's raw model field names `conversation`/`sender`, requiring an explicit serializer change by the chat owner.

### Mark read

`POST /api/chat/conversations/5/read/`, no body → **200**:

```json
{"conversation_id":5,"updated_count":3}
```

Only unread messages sent by the other participant are updated; repeat call → `updated_count:0`. Same participation/block checks as history. Read receipts remain optional UI polish; unread counts can consume this endpoint independently.

### Text / polling decision

React renders `body_text` as plain text; never use `dangerouslySetInnerHTML`. The guide proposes storing HTML-escaped text. PM must choose one canonical representation before wiring: proposed API returns original plain text and backend stores plain text, avoiding double escaping; if storage escaping is retained, the API must normalize back to plain text. `<script>` and other markup must render inertly. This PR does not implement backend sanitization.

After integration, poll the active thread every ~3 seconds and sidebar every 15 seconds; cancel timers on navigation/unmount, pause when hidden, and prevent overlapping requests. These are next-week integration tasks, not implemented in `/chat-mock`.

## Final component contract

| Component | Props | Responsibility |
| --- | --- | --- |
| `ChatMockPage` | none | Own queue, selected thread, mock reset, in-memory API test token; host fixtures and POST form |
| `RequestQueue` | `requests`, `direction`, `onAccept(id)`, `onDecline(id)` | Render incoming/outgoing cards or empty state |
| `ConnectionRequestCard` | `request`, `direction`, callbacks | Identity/note/status; incoming actions only |
| `ConversationListItem` | `conversation`, `selected`, `onSelect(id)` | Selectable sidebar row with preview/unread badge |
| `ChatWindow` | `conversation`, `messages`, `currentUser` | Thread plus local composer; Send disabled until chat integration |
| `MessageBubble` | `message`, `isOwn`, `senderName` | Plain-text bubble, alignment, accessible sender and display time |
| `SendRequestForm` | `accessToken`, `onCreated(request)` | 500-character note, live counter, single in-flight POST, errors/success |
| `Avatar` | `name`, `small` | Decorative initials |

Mock view models contain formatted times and sidebar preview strings. Future adapters must map API `last_message` objects and timestamps to these view models. Auth integration will replace the demo's API test token panel with the shared auth provider; no token is stored in localStorage or source code.

## Review decisions and signatures

| Decision | Reviewer | Status |
| --- | --- | --- |
| Canonical connection paths, note emptiness, duplicate/accepted pair handling, silent decline | Thomas / BE2 | Pending |
| Chat shapes, bare arrays, cursor tie-breaker, read endpoint, polling | Sameeksha / PM | Pending |
| Soft block, body text representation, chat ownership | Sameeksha + Thomas | Pending |
| Client components and 500-character behavior | Sanjana / FE2 | Implementation prepared; personal sign-off pending |

| Signatory | Approval of this exact revision (commit/link) | Date |
| --- | --- | --- |
| Sanjana Shetty / FE2 | Pending | — |
| Thomas Hart / BE2 | Pending | — |
| Sameeksha Keshav / PM | Pending | — |

Reviewers should record approval on the PR and add their approval permalink and date here. Keep the document marked proposed until all relevant owners approve; do not substitute prepared code or passing mock tests for backend agreement.
