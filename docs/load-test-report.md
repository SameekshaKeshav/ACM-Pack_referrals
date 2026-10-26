# Pack Referrals — Chat Polling Load Test

Load test of the chat polling endpoint on staging: 50 clients polling `GET /api/chat/conversations/<id>/messages/` every 3 seconds for 5 minutes.

- **Run:** 2026-10-26 00:31–00:36 UTC (2026-10-25 20:31–20:36 EDT)
- **Staging:** https://acm-packreferrals-production.up.railway.app/, `main` at `dd2949a`
- **Script:** [`loadtests/locustfile.py`](../loadtests/locustfile.py)

## Summary

| Check | Target | Result | Status |
|-------|--------|--------|--------|
| Poll p95 response time | ≤ 500ms | 290ms | **PASS** |
| Failed requests | 0 | 0 of 5,026 | **PASS** |
| Errors in Sentry during the run | None | None | **PASS** |
| `database is locked` errors | Document if seen | None, but this test only read (see [Limitations](#limitations)) | **NOT TESTED** |

p95 is under 500ms, so no issue was filed. The read path has plenty of headroom: Django spent about 5ms per poll, and the single gunicorn worker was busy about 8% of the time. Because the test sent no writes, it says nothing about SQLite's concurrent-write limits. Whether to run a write test before showcase is an open question for the PM.

## Setup

| | |
|---|---|
| Tool | Locust 2.47.0 (`loadtests/requirements.txt`), run headless from a laptop |
| Clients | 50, started 10 per second |
| Pacing | `constant_pacing(3)`: each client starts a request every 3s, about 16.7 requests/s in total |
| Duration | 5 minutes |
| Requests | Each client loads the history once (`history`), then polls with `?after=<last id>` (`poll`) |
| Server | 1 gunicorn sync worker (`WEB_CONCURRENCY` unset; one `Booting worker` line per startup in Railway's logs) |
| Database | SQLite on the `/data` volume |
| Test data | Conversation 1, between two test accounts made for this test (account B is user 2, a `+loadtest` alias). All 50 clients used account A's token. The conversation had no messages. |

Command:

```bash
LOADTEST_TOKEN=<access token> LOADTEST_CONVERSATION_ID=1 \
  locust -f loadtests/locustfile.py --headless -u 50 -r 10 -t 5m \
  --host https://acm-packreferrals-production.up.railway.app \
  --csv loadtests/results/staging --html loadtests/results/staging.html
```

## Results

### Client side (Locust)

From `staging_stats.csv`. Locust rounds percentiles to about 10ms.

| Request | Count | Failures | p50 | p95 | p99 | Max | Avg size |
|---------|-------|----------|-----|-----|-----|-----|----------|
| `poll` | 4,976 | 0 | 180ms | **290ms** | 400ms | 627ms | 2 bytes |
| `history` | 50 | 0 | 220ms | 330ms | 360ms | 363ms | 2 bytes |

Throughput averaged 16.6 polls/s. It ran higher (up to 24 requests/s) only during the first ~15 seconds, while clients were starting and loading history, then stayed at 16–17 requests/s. The cumulative p95 stayed between 260 and 340ms while all 50 clients were running, with no upward trend: it was 280ms at the halfway point and 290ms at the end.

**Baseline:** a 15-second run with 1 client gave a poll p50 of 130ms and p95 of 180ms (5 requests). At 50 clients, p50 rose by about 50ms and p95 by about 110ms.

### Server side (Railway request log)

`duration_ms` from `pack_referrals.middleware` for 105 consecutive polls at 00:36:11–00:36:17 UTC. This is the time spent inside Django, not counting time waiting for a free worker.

| Min | Median | Mean | p95 | Max |
|-----|--------|------|-----|-----|
| 2.95ms | 4.6ms | 5.0ms | 8.2ms | 9.6ms |

## Interpretation

- **Most of the latency is outside Django.** About 5ms of a ~180ms poll is Django; the rest is the network between the test laptop and Railway, Railway's proxy, and waiting for the worker.
- **Requests arrived in bursts, and the worker queued them.** Clients started in groups of 10 per second and `constant_pacing` kept each group in step, so in the logged sample each second brought a burst of 10–20 polls within 80–170ms, then nothing until the next second. The log timestamps in each burst are spaced about one request's duration apart, so the single worker handled them one after another, and the last poll in a large burst waited up to about 150ms. This probably explains most of the rise from the 1-client baseline. Real users aren't synchronized, so this test was harsher than real traffic in this respect.
- **The worker had large headroom.** At 16.6 requests/s × 5ms, the worker was busy about 8% of the time. Don't read this as a capacity figure: waiting times grow sharply well before 100%, and real polls return messages, which costs more than an empty list.

## Limitations

- **Read-only.** The test only sent GETs, and SQLite lets many readers work at once. `database is locked` happens when a writer holds the lock and other connections wait past the timeout, so this test could not surface it. It does not show that SQLite is fine for chat.
- **Empty conversation.** Every response was `[]` (2 bytes), so no messages were serialized. This is close to the cheapest possible poll.
- **One user.** All clients shared one token and conversation. The server runs the same queries for each request and caches nothing per user, so the load per request is realistic, but per-user effects aren't covered.
- **Synchronized clients.** See the bursts above.
- **Server-side sample.** The `duration_ms` figures come from the last 7 seconds of the run. Locust's results were steady throughout, so they are likely representative.

## Follow-ups

- **Write test (PM decision).** A second run in which account B sends a message every few seconds (under the `message_send` throttle, 30/minute by default) would make polls return data and test SQLite under concurrent reads and writes. It would leave about 100 test messages in conversation 1 on staging permanently.
- **Gunicorn log severity.** Gunicorn writes its own log lines to stderr, which Railway labels `severity: error` (for example `Booting worker`). They aren't errors.
- **Start command.** Before this test, staging's start command had been changed so `migrate` no longer ran on deploy. Migration `accounts.0003_verificationcode_attempts` was missing, and signup returned 500 (`no column named attempts`). The start command has been restored and signup works. The start command only lives in Railway's dashboard; keeping it in the repo (Railway config file) would put changes through review.

## How to rerun

1. Install Locust: `pip install -r loadtests/requirements.txt` (not the root `requirements.txt`, which Railway installs).
2. Get an access token for a participant in a test conversation: `POST /api/accounts/auth/login/`, then `POST /api/accounts/auth/verify/` with the code. Until real email is set up on staging (#34), the code is printed in Railway's logs. Save only the `access` value; it lasts 24 hours.
3. To create a new test conversation, a second account sends `POST /api/connections/` to the first, and the recipient accepts with `PATCH /api/connections/<id>/accept/`. The response includes `conversation_id`.
4. Check the token and conversation with a single poll, which should return `200` and a list: `GET /api/chat/conversations/<id>/messages/?after=0`.
5. Tell the team, then run the command above. Exit code `1` means poll p95 was over 500ms.
6. Check Sentry and Railway's logs for the run's time window. Railway shows UTC.

Results go to `loadtests/results/`, which is gitignored.
