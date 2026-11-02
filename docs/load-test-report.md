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
| `database is locked` errors | Document if seen | None on staging (read-only). None locally with writes, up to 100 messages/s across 4 workers (see [Write test](#write-test-local-multiple-workers)) | **PASS** (local) |

p95 is under 500ms, so no issue was filed. The read path has plenty of headroom: Django spent about 5ms per poll, and the single gunicorn worker was busy about 8% of the time. The staging run sent no writes, so a second, local test sent messages while the same 50 clients polled. It found no `database is locked` errors, even with 4 workers writing at 100 messages/s.

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

## Write test (local, multiple workers)

- **Run:** 2026-11-01, on a laptop (10 cores), `main` at `ab3c07f`
- **Script:** the same [`loadtests/locustfile.py`](../loadtests/locustfile.py), with `LOADTEST_SENDER_TOKEN` set so senders run alongside the pollers

### Why local instead of staging

Staging runs one gunicorn sync worker, which handles one request at a time over one database connection. `database is locked` needs two connections to overlap: one holds the write lock, and the other waits past Django's 5-second timeout. With one worker that can't happen, so a write test on staging would pass whatever the load. It would also leave test messages in staging's database permanently. A local server can run several workers, which is what would cause the error if anyone raised `WEB_CONCURRENCY`.

### Setup

| | |
|---|---|
| Server | `gunicorn -w <1 or 4> pack_referrals.wsgi` on `127.0.0.1`, `DEBUG=false`, settings from `loadtests/loadtest_settings.py` (the real settings, plus 500 tracebacks printed to the console) |
| Database | A fresh SQLite file per scenario, in the default rollback-journal mode (`PRAGMA journal_mode` = `delete`). Nothing in the settings changes this, so staging should be in the same mode, but staging's database file wasn't checked. |
| Accounts | `python -m loadtests.setup_local` creates a reader and a writer and a conversation between them. Pollers use the reader's token, senders the writer's. |
| Clients | 50 pollers as in the staging test (one poll every 3s), plus 1–25 senders, each posting a message every 0.25–3s |
| Throttle | `THROTTLE_MESSAGE_SEND=1000000/min`, so the 30/min limit doesn't cap the senders |
| Duration | 3 minutes per scenario |

Before the runs, holding an exclusive lock on the database from another process for 7 seconds made a send return 500 after 5.2s, with `database is locked` in the server log. So the setup reports the error when it happens.

### Results

0 failed requests and 0 `database is locked` errors in every scenario. Client times include no network (Locust and gunicorn on the same machine), so compare them with each other, not with staging. Server times are `duration_ms` from the request log.

| Scenario | Workers | Messages/s | Requests | Failures | Poll p95 (client) | Send p95 (client) | Send p50 / p95 / max (server) |
|----------|---------|------------|----------|----------|-------------------|-------------------|-------------------------------|
| 1 sender every 3s (the follow-up proposed below) | 1 | 0.3 | 3,089 | 0 | 59ms | 44ms | 3.9 / 5.9 / 6.5ms |
| 1 sender every 3s | 4 | 0.3 | 3,089 | 0 | 30ms | 31ms | 8.0 / 12.9 / 17.1ms |
| 10 senders every 1s | 4 | 10 | 4,820 | 0 | 46ms | 39ms | 7.3 / 24.2 / 62.8ms |
| 25 senders every 0.25s | 4 | 100 | 20,860 | 0 | 67ms | 60ms | 5.5 / 15.3 / 89.0ms |
| 25 senders every 0.25s | 1 | 100 | 20,835 | 0 | 130ms | 76ms | 1.9 / 3.9 / 25.0ms |

The 100 messages/s runs wrote about 17,900 messages each. The database holds about 50 more than Locust counted, because sends still in progress when Locust stopped finished on the server.

### Interpretation

- **Writes did contend, and SQLite handled it.** At 100 messages/s, a send took 1.9ms inside Django with 1 worker and 5.5ms with 4. The difference is time spent waiting for another worker's write lock. The longest send took 89ms, far below the 5-second timeout where `database is locked` would be raised.
- **One worker never sees the error, but it queues.** With 1 worker at 100 messages/s, every request waits its turn, so poll p95 doubled (67ms → 130ms) even though Django's own time stayed lowest.
- **Real use is far below this.** 100 messages/s is many times what a student app will see. Under the default throttle, one user can send at most 0.5 messages/s.

### Limitations of the write test

- **Laptop disk, not Railway's volume.** A write's lock is held until the data is synced to disk, and the laptop's SSD is fast. Railway's volume may be slower, which would make writes hold the lock longer. The largest wait seen was about 55 times shorter than the timeout, which leaves a lot of room, but it wasn't measured on Railway.
- **Only one kind of write.** Senders only posted messages. Other writes (mark as read, connection requests, profile edits) weren't tested, but they are also short single statements or small transactions.
- **Throttle disabled.** The throttle was raised so the senders could reach these rates. Throttle counts are kept in each worker's memory (no `CACHES` setting), so with 4 workers the real limit would be about 4 times the configured one.

## Limitations

- **Read-only on staging.** The staging test only sent GETs, and SQLite lets many readers work at once, so it could not surface `database is locked`. See the [write test](#write-test-local-multiple-workers) for writes.
- **Empty conversation.** Every response was `[]` (2 bytes), so no messages were serialized. This is close to the cheapest possible poll.
- **One user.** All clients shared one token and conversation. The server runs the same queries for each request and caches nothing per user, so the load per request is realistic, but per-user effects aren't covered.
- **Synchronized clients.** See the bursts above.
- **Server-side sample.** The `duration_ms` figures come from the last 7 seconds of the run. Locust's results were steady throughout, so they are likely representative.

## Follow-ups

- **Write test.** Done locally instead of on staging (see [Write test](#write-test-local-multiple-workers)). A staging run with one sender would pass by construction while staging has one worker.
- **Throttles with more workers.** If `WEB_CONCURRENCY` is ever raised, the message and auth throttles need a shared cache (for example `DatabaseCache`). Otherwise each worker counts separately and the limits multiply.
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

### Write test (local)

From the repository root, with the root and `loadtests/` requirements installed:

```bash
export SQLITE_PATH=/tmp/loadtest.sqlite3 DJANGO_SETTINGS_MODULE=loadtests.loadtest_settings
export DEBUG=false THROTTLE_MESSAGE_SEND=1000000/min
eval "$(python -m loadtests.setup_local)"   # migrates and sets the three LOADTEST_* variables

gunicorn -w 4 -b 127.0.0.1:8765 pack_referrals.wsgi > server.log 2>&1 &

LOADTEST_SENDERS=25 LOADTEST_SEND_INTERVAL=0.25 \
  locust -f loadtests/locustfile.py --headless -u 75 -r 10 -t 3m \
  --host http://127.0.0.1:8765 --csv loadtests/results/local

grep -c 'database is locked' server.log
```

`-u` is the total number of clients: `LOADTEST_SENDERS` of them send and the rest poll. Use a new `SQLITE_PATH` file per run. To compare journal modes, set `SQLITE_JOURNAL_MODE=wal` before running `setup_local`.
