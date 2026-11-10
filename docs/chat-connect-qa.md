# Chat and Connect verification

The page distinguishes loading, empty results and errors for conversations, history and connection requests. Errors expose retry controls. Failed optimistic messages keep their text and display **Failed to send - tap to retry** on that bubble; retry reuses its text and reconciles the returned server ID.

## Incoming messages and accessibility

The selected conversation polls the existing history route with `?limit=100&after=<message ID>` every three seconds. A full batch advances the cursor until drained. Poll requests do not overlap; switching conversations, leaving the page or logging out aborts them. Hidden tabs pause polling; returning focus checks immediately. Failures preserve history and the draft, show Retry updates, and back off to a maximum of 30 seconds.

The incoming cursor is separate from POST acknowledgements, so sending a higher-ID message cannot skip an unseen earlier reply. Server echoes are deferred while an optimistic send is pending. This is polling, not a WebSocket connection. Only the selected thread receives automatic updates; refresh the conversation list to discover another newly created conversation.

A dedicated polite live region announces newly arriving messages from the other person, without replaying initial history or announcing own optimistic messages as incoming. Errors use alerts. Scrollable history is keyboard focusable; accepting a connection moves focus to its loaded composer. Incoming/outgoing tabs support arrows, Home and End. Pending bubbles retain full opacity for contrast. Long text and failure controls wrap within narrow layouts.

A failed POST whose response is lost after the backend commits remains an ambiguous failure: without backend idempotency keys, an explicit retry may create a duplicate on the server. The single-flight guard prevents overlapping attempts in this tab, not that network ambiguity.

## Run the checks

From `frontend` with the repository's supported Node version:

```bash
npm ci
npm run lint
npm run test:dom
npm run build
npx playwright install chromium
npm test
```

The additional `chat-connect-polish.spec.js` covers keyboard-only request → accept → send, incoming announcements, failed-send retry, loading/empty/error axe scans, and Chat/Connect at 375, 768 and 1440 pixels. Existing `a11y.spec.js` scans login, signup and enter-code as well as authenticated pages. New state scans fail on serious or critical axe violations. Existing scans keep their stricter zero-violations threshold. These fixtures exercise the real frontend with intercepted synthetic API responses; they do not prove staging integration or email delivery.

From the repository root, after installing Chromium:

```bash
bash scripts/capture-chat-connect.sh
```

This creates an isolated checkout of baseline `ef1ea41`, runs the same six responsive scenarios against it and the current checkout, and saves 12 before/after PNGs and commit references in `frontend/qa-evidence/responsive/`. No branch switching or changes to the user's checkout are required. The baseline screenshots are captures of actual baseline code, not reconstructed images. Inspect each pair: wrapping, horizontal overflow, visible focus, scrollable history, and a usable note/message input. The checks scroll the composer into view; they do not promise it stays fixed while scrolling the whole page.

## Verification recorded for this change

- Passed: 117 DOM tests, accessibility lint, production build, patch whitespace check.
- Discovered successfully: 35 Playwright tests, including nine new scenarios. Discovery is not execution.
- Pending: Playwright/axe execution, screenshot capture and visual review. Chromium could not launch in the preparation environment: its process singleton socket was denied (`Operation not permitted`).
- Pending: a human screen-reader check. A live-region assertion verifies markup and updates, not actual spoken output.
- Pending: two consecutive staging demo rehearsals and a locally saved backup recording; see [demo script](chat-connect-demo.md).

Do not tick the responsive or accessibility audit complete until the browser checks and the manual review have passed. Attach the actual results/screenshots to the PR. Do not reuse older branch test counts as evidence for this commit.
