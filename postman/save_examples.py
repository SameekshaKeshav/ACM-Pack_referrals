"""Save the responses from a newman run as each request's example.

    python postman/save_examples.py <collection.json> <newman-report.json>

The report comes from ``newman run ... --reporters json --reporter-json-export``;
``postman/run_collection.sh --save-examples`` does both steps. Every request's
``response`` list is replaced with the one response it got in that run, so the
examples are real output, never hand-written.

It refuses to write anything if any test failed or any request did not run, so
a saved example is always a passing one. Tokens are redacted: the example keeps
the request as written (``{{sender_token}}``), not as sent, and any JWT in a
response body is replaced.
"""

import copy
import json
import re
import sys

JWT_RE = re.compile(r"eyJ[\w-]+\.[\w-]+\.[\w-]+")
REDACTED = "<redacted JWT>"
# Long non-JSON bodies (the OpenAPI schema, the Swagger page) are cut to this many
# characters, so the collection stays readable and does not change every time
# any route's docs do.
MAX_TEXT_BODY = 1500


def requests_in(items):
    for item in items:
        if "item" in item:
            yield from requests_in(item["item"])
        else:
            yield item


def body_text(response):
    stream = response.get("stream") or {}
    return bytes(stream.get("data") or []).decode("utf-8", errors="replace")


def content_type(response):
    for header in response.get("header", []):
        if header["key"].lower() == "content-type":
            return header["value"]
    return ""


def example_body(response):
    text = body_text(response)
    if "json" in content_type(response) and text:
        try:
            text = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
        except ValueError:
            pass
    elif len(text) > MAX_TEXT_BODY:
        text = (f"{text[:MAX_TEXT_BODY]}\n\n... (cut by save_examples.py; "
                f"{len(text)} characters in full)")
    return JWT_RE.sub(REDACTED, text)


def preview_language(response):
    kind = content_type(response)
    if "json" in kind:
        return "json"
    if "html" in kind:
        return "html"
    return "text"


def main(collection_path, report_path):
    with open(collection_path) as f:
        collection = json.load(f)
    with open(report_path) as f:
        run = json.load(f)["run"]

    if run.get("failures"):
        names = sorted({failure["source"]["name"] for failure in run["failures"]})
        sys.exit("Not saving: tests failed in " + "; ".join(names))

    # The last execution of each request wins (each runs once in a full run).
    executions = {e["item"]["id"]: e for e in run["executions"] if e.get("response")}

    items = list(requests_in(collection["item"]))
    missing = [item["name"] for item in items if item["id"] not in executions]
    if missing:
        sys.exit("Not saving: these requests did not run: " + "; ".join(missing))

    for item in items:
        response = executions[item["id"]]["response"]
        original = copy.deepcopy(item["request"])
        original.pop("description", None)
        item["response"] = [{
            "name": f'{response["code"]} {response["status"]}',
            "originalRequest": original,
            "status": response["status"],
            "code": response["code"],
            "_postman_previewlanguage": preview_language(response),
            # Only the content type: Date, Server and the rest change every run.
            "header": [{"key": "Content-Type", "value": content_type(response)}],
            "cookie": [],
            "body": example_body(response),
        }]

    with open(collection_path, "w") as f:
        json.dump(collection, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Saved {len(items)} examples to {collection_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
