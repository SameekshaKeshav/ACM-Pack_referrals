#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".venv/bin/activate" ]]; then
    echo "Missing .venv. Create it and install requirements first." >&2
    exit 1
fi

source .venv/bin/activate

HOST="127.0.0.1"
PORT="${PORT:-8000}"
BASE_URL="http://${HOST}:${PORT}"
SERVER_LOG="$(mktemp)"
SERVER_PID=""

cleanup() {
    if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    rm -f "$SERVER_LOG"
}
trap cleanup EXIT

echo "Running Django tests..."
python manage.py test connections

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Resetting Postman fixtures..."
python manage.py seed_demo_data

echo "Starting Django at ${BASE_URL}..."
python manage.py runserver "${HOST}:${PORT}" --noreload >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!

for attempt in {1..20}; do
    if curl -fsS "${BASE_URL}/api/connections/health/" >/dev/null 2>&1; then
        break
    fi
    if [[ "$attempt" == 20 ]]; then
        echo "Django did not become ready. Server log:" >&2
        cat "$SERVER_LOG" >&2
        exit 1
    fi
    sleep 0.25
done

request() {
    local output_file="$1"
    shift
    curl -sS "$@" -o "$output_file" -w "%{http_code}"
}

assert_status() {
    local expected="$1"
    local actual="$2"
    local description="$3"
    local body_file="$4"

    if [[ "$actual" != "$expected" ]]; then
        echo "FAIL: ${description}: expected ${expected}, got ${actual}" >&2
        cat "$body_file" >&2
        exit 1
    fi
    echo "PASS: ${description} (${actual})"
}

response_file="$(mktemp)"
trap 'rm -f "$response_file"; cleanup' EXIT

status=$(request "$response_file" \
    -u postman_sender:SenderPass123! \
    -H "Content-Type: application/json" \
    -d '{"recipient":2,"message_text":"Hello"}' \
    "${BASE_URL}/api/connections/")
assert_status "201" "$status" "create connection request" "$response_file"
connection_id=$(python - "$response_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as response:
    print(json.load(response)["id"])
PY
)

status=$(request "$response_file" \
    -u postman_sender:SenderPass123! \
    -H "Content-Type: application/json" \
    -d '{"recipient":2,"message_text":"Hello"}' \
    "${BASE_URL}/api/connections/")
assert_status "409" "$status" "reject duplicate connection request" "$response_file"

status=$(request "$response_file" \
    -u postman_recipient:RecipientPass123! \
    "${BASE_URL}/api/connections/?type=incoming")
assert_status "200" "$status" "list incoming connection requests" "$response_file"
python - "$response_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as response:
    request = json.load(response)[0]

assert request["sender"] == {"name": "Sender User", "company": "Acme"}
assert set(request) == {"id", "sender", "message_text", "status", "created_at"}
PY
echo "PASS: incoming response shape"

status=$(request "$response_file" \
    -u postman_recipient:RecipientPass123! \
    -X PATCH \
    "${BASE_URL}/api/connections/${connection_id}/accept/")
assert_status "501" "$status" "accept endpoint remains the documented stub" "$response_file"

echo "Connection endpoint demo completed successfully."