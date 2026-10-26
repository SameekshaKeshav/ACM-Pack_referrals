"""Load test: 50 clients polling one conversation's messages every 3 seconds.

Needs LOADTEST_TOKEN (JWT access token of a conversation participant) and
LOADTEST_CONVERSATION_ID. See docs/load-test-report.md for how to run it.
"""
import os

from locust import HttpUser, constant_pacing, events, task

TOKEN = os.environ["LOADTEST_TOKEN"]
PATH = f"/api/chat/conversations/{os.environ['LOADTEST_CONVERSATION_ID']}/messages/"
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


@events.quitting.add_listener
def fail_if_slow(environment, **kwargs):
    p95 = environment.stats.get("poll", "GET").get_response_time_percentile(0.95)
    if p95 > P95_LIMIT_MS:
        environment.process_exit_code = 1
