"""Load test: 50 clients polling one conversation's messages every 3 seconds.

Needs LOADTEST_TOKEN (JWT access token of a conversation participant) and
LOADTEST_CONVERSATION_ID. See docs/load-test-report.md for how to run it.

Setting LOADTEST_SENDER_TOKEN (the other participant's token) adds senders that
post a message to the same conversation every LOADTEST_SEND_INTERVAL seconds
(default 3). LOADTEST_SENDERS of the -u clients are senders (default 1); the
rest poll.
"""
import os

from locust import HttpUser, constant_pacing, events, task

TOKEN = os.environ["LOADTEST_TOKEN"]
CONVERSATION_ID = int(os.environ["LOADTEST_CONVERSATION_ID"])
PATH = f"/api/chat/conversations/{CONVERSATION_ID}/messages/"
SENDER_TOKEN = os.environ.get("LOADTEST_SENDER_TOKEN")
P95_LIMIT_MS = 500


class PollingClient(HttpUser):
    # Start a poll every 3s. constant(3) would wait 3s after each response
    # instead, so slow responses would quietly lower the request rate.
    wait_time = constant_pacing(3)

    def on_start(self):
        self.client.headers["Authorization"] = f"Bearer {TOKEN}"
        self.last_id = 0
        self._fetch(PATH, name="history")  # opening the thread

    @task
    def poll(self):
        self._fetch(f"{PATH}?after={self.last_id}", name="poll")

    def _fetch(self, url, name):
        with self.client.get(url, name=name, catch_response=True) as resp:
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}")
                return
            messages = resp.json()
            if messages:
                self.last_id = messages[-1]["id"]


class SendingClient(HttpUser):
    # Without a sender token this class is skipped, so the read-only run is unchanged.
    abstract = not SENDER_TOKEN
    fixed_count = int(os.environ.get("LOADTEST_SENDERS", "1"))
    wait_time = constant_pacing(float(os.environ.get("LOADTEST_SEND_INTERVAL", "3")))

    def on_start(self):
        self.client.headers["Authorization"] = f"Bearer {SENDER_TOKEN}"
        self.sent = 0

    @task
    def send(self):
        self.sent += 1
        body = {"conversation_id": CONVERSATION_ID, "body_text": f"load test message {self.sent}"}
        with self.client.post(
            "/api/chat/messages/", json=body, name="send", catch_response=True
        ) as resp:
            if resp.status_code != 201:
                resp.failure(f"HTTP {resp.status_code}")


@events.quitting.add_listener
def fail_if_slow(environment, **kwargs):
    p95 = environment.stats.get("poll", "GET").get_response_time_percentile(0.95)
    if p95 > P95_LIMIT_MS:
        environment.process_exit_code = 1
