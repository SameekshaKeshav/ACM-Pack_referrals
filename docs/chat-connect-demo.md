# Chat and Connect demo — target 2 minutes 40 seconds

## Prepare before starting the timer

Use the team's actual staging URL and two explicitly designated demo accounts, A and B, in separate browser profiles. Confirm login codes work through the configured email method, both accounts have profiles, and a company/member search can find B. Start without an existing A–B request/connection. Arrange any additional incoming request with another disposable demo account before rehearsal. Never display access tokens, real inbox contents or authentication codes in the recording.

Confirm the deployed frontend includes this change and that connection/chat endpoints respond. Do not use `/chat-mock` for this integrated demonstration. A mock-backed browser test is useful evidence of UI behavior but cannot substitute for either staging run.

## Timed sequence

| Time | Action | Say |
| --- | --- | --- |
| 0:00–0:20 | Show A signed in; open Directory and B's company. | “This connects NC State members through their companies. I built the frontend flow for connection requests and chat.” |
| 0:20–0:45 | Choose B, open Connect, type a brief note and send. Show Request sent. | “A short note accompanies the request. The frontend validates its length, shows sending feedback, and keeps the note if there is an error.” |
| 0:45–1:05 | Switch to B; open Messages and refresh requests if necessary. Accept A. | “The recipient can accept or decline. Accepting opens the conversation returned by the backend.” |
| 1:05–1:35 | Send a message as B; switch to A and open that conversation. Reply as A. | “Messages appear immediately while sending and reconcile with the saved response. An open conversation checks for incoming replies every three seconds.” |
| 1:35–1:55 | Show the incoming reply on B; refresh the page and show history. | “Conversation history comes from the backend in chronological order and survives a page reload.” |
| 1:55–2:20 | Briefly show keyboard focus on the composer; show prepared narrow-width screenshot. | “The controls work by keyboard, new replies have screen-reader announcements, and the input is checked at phone, tablet and desktop widths.” Say the width-check claim only after those checks actually pass. |
| 2:20–2:40 | Return to the conversation and finish. | “Errors keep the draft or the failed message so the user can retry. The backend handles identity, connection permissions and persistence.” |

A controlled failed-send demonstration is optional and should replace another segment to stay under three minutes. Rehearse it before using it: an offline message should remain visible with **Failed to send - tap to retry**; reconnect and retry. Do not deliberately disrupt shared staging or promise exactly-once delivery after an ambiguous network failure.

## Rehearsal record — complete with actual observations

Reset only designated disposable demo records using the team's approved reset method, or use a fresh pair of test accounts. Do not delete shared records to repeat the flow.

| Run | Staging URL / deployed commit | Date and duration | Request, accept, reply and reload result | Outcome |
| --- | --- | --- | --- | --- |
| 1 | Pending | Pending | Pending | Not run |
| 2, immediately after run 1 | Pending | Pending | Pending | Not run |

Tick the requirement only when both runs succeed consecutively in under three minutes. Record any blockers and rerun both after a material fix.

## Local backup recording on Mac

After successful staging rehearsal, use **Shift–Command–5 → Record Selected Portion**. Frame the app rather than the whole desktop; keep notifications out of frame. Record the Chat/Connect sequence above, then stop from the menu bar and save as `Pack-Referrals-Chat-Connect-backup.mov` in a known local folder, for example `~/Movies/Pack-Referrals/`. Open the saved file and check playback, readable text and the complete flow. This recording is still pending; this document does not certify that a video exists.
