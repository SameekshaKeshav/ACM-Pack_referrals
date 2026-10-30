#!/usr/bin/env bash

set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".venv/bin/activate" ]]; then
    echo "Missing .venv. Create it and install requirements first." >&2
    exit 1
fi

source .venv/bin/activate
echo "Using virtual environment: ${VIRTUAL_ENV}"

HOST="127.0.0.1"
PORT_WAS_PROVIDED=0
if [[ -n "${PORT:-}" ]]; then
    PORT_WAS_PROVIDED=1
else
    PORT=8000
fi
BASE_URL="http://${HOST}:${PORT}"
SERVER_LOG="$(mktemp)"
RESPONSE_FILE="$(mktemp)"
PAYLOAD_FILE="$(mktemp)"
SERVER_PID=""

cleanup() {
    echo "Cleaning up temporary files and Django server..." >&2
    if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill -- -"$SERVER_PID" 2>/dev/null || true
        kill -KILL -- -"$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
    rm -f "$SERVER_LOG" "$RESPONSE_FILE" "$PAYLOAD_FILE"
}
trap cleanup EXIT

echo "[1/4] Running Django tests: python manage.py test connections"
python manage.py test connections

echo "[2/4] Applying migrations: python manage.py migrate --noinput"
python manage.py migrate --noinput

echo "[3/4] Resetting demo fixtures: python manage.py seed_demo_data"
python manage.py seed_demo_data >/dev/null

fixture_json=$(python manage.py shell --verbosity 0 -c '
import json
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()
sender = User.objects.get(username="postman_sender")
recipient = User.objects.get(username="postman_recipient")
print(json.dumps({
    "sender_id": sender.pk,
    "recipient_id": recipient.pk,
    "sender_token": str(AccessToken.for_user(sender)),
    "recipient_token": str(AccessToken.for_user(recipient)),
}))
' | tail -n 1)

read_fixture() {
    python - "$fixture_json" "$1" <<'PY'
import json
import sys

print(json.loads(sys.argv[1])[sys.argv[2]])
PY
}

SENDER_ID=$(read_fixture sender_id)
RECIPIENT_ID=$(read_fixture recipient_id)
SENDER_TOKEN=$(read_fixture sender_token)
RECIPIENT_TOKEN=$(read_fixture recipient_token)
echo "[4/4] Generated temporary JWTs for demo users ${SENDER_ID} and ${RECIPIENT_ID} (tokens hidden)"

if [[ "$PORT_WAS_PROVIDED" == 0 ]]; then
    echo "No PORT supplied; searching for an available port from 8000 through 8010..."
    for candidate_port in $(seq 8000 8010); do
        if python - "$candidate_port" <<'PY'
import socket
import sys

with socket.socket() as probe:
    try:
        probe.bind(("127.0.0.1", int(sys.argv[1])))
    except OSError:
        raise SystemExit(1)
PY
        then
            PORT="$candidate_port"
            echo "Selected available port ${PORT}."
            break
        fi
    done
fi

BASE_URL="http://${HOST}:${PORT}"
echo "Starting Django at ${BASE_URL}..."
if ! python - "$PORT" <<'PY'
import socket
import sys

with socket.socket() as probe:
    try:
        probe.bind(("127.0.0.1", int(sys.argv[1])))
    except OSError:
        raise SystemExit(1)
PY
then
    echo "Port ${PORT} is already in use. Choose another port with PORT=..." >&2
    exit 1
fi
setsid python manage.py runserver "${HOST}:${PORT}" --noreload >"$SERVER_LOG" 2>&1 &
SERVER_PID=$!
echo "Django started with process group ${SERVER_PID}; waiting for the health endpoint..."

for attempt in {1..20}; do
    if curl -fsS "${BASE_URL}/api/connections/health/" >/dev/null 2>&1; then
        echo "Django is ready: ${BASE_URL}/api/connections/health/"
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
    local endpoint="${!#}"
    printf '  HTTP request: %s (authentication redacted)\n' "$endpoint" >&2
    curl -sS "$@" -o "$output_file" -w "%{http_code}"
}

assert_status() {
    local expected="$1"
    local actual="$2"
    local description="$3"

    if [[ "$actual" != "$expected" ]]; then
        echo "FAIL: ${description}: expected ${expected}, got ${actual}" >&2
        cat "$RESPONSE_FILE" >&2
        exit 1
    fi
    echo "PASS: ${description} (${actual})"
}

reset_fixtures() {
    echo "  Resetting demo database state..." >&2
    python manage.py seed_demo_data >/dev/null
}

django_setup() {
    echo "  Creating the scenario-specific database state..." >&2
    python manage.py shell --verbosity 0 -c "$1"
}

echo
echo "=== Basic request creation and list responses ==="
status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"recipient_id\":${RECIPIENT_ID},\"message_text\":\"Hello\"}" \
    "${BASE_URL}/api/connections/")
assert_status 201 "$status" "create request"
connection_id=$(python - "$RESPONSE_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as response:
    print(json.load(response)["id"])
PY
)

status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"recipient_id\":${RECIPIENT_ID},\"message_text\":\"Hello\"}" \
    "${BASE_URL}/api/connections/")
assert_status 409 "$status" "duplicate pending request"

status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${RECIPIENT_TOKEN}" \
    "${BASE_URL}/api/connections/?type=incoming")
assert_status 200 "$status" "incoming request list"
python - "$RESPONSE_FILE" "$SENDER_ID" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as response:
    item = json.load(response)[0]

assert item["sender"] == {
    "id": int(sys.argv[2]),
    "name": "Sender User",
    "company": "Acme",
}
assert set(item) == {"id", "sender", "message_text", "status", "created_at"}
PY
echo "PASS: incoming response shape"

status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    "${BASE_URL}/api/connections/?type=outgoing")
assert_status 200 "$status" "outgoing request list"
python - "$RESPONSE_FILE" "$RECIPIENT_ID" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as response:
    item = json.load(response)[0]

assert item["recipient"] == {
    "id": int(sys.argv[2]),
    "name": "postman_recipient",
    "company": "Acme",
}
PY
echo "PASS: outgoing response shape"

status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    "${BASE_URL}/api/connections/connection-requests")
assert_status 404 "$status" "connection-requests endpoint is not exposed"

status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"recipient_id\":${SENDER_ID},\"message_text\":\"Hello\"}" \
    "${BASE_URL}/api/connections/")
assert_status 400 "$status" "request to self"

status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d '{"recipient_id":999999,"message_text":"Hello"}' \
    "${BASE_URL}/api/connections/")
assert_status 404 "$status" "unknown recipient"

echo
echo "=== Conflict handling ==="
reset_fixtures
django_setup "from connections.models import ConnectionRequest; ConnectionRequest.objects.create(sender_id=${RECIPIENT_ID}, recipient_id=${SENDER_ID}, status='pending')"
status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"recipient_id\":${RECIPIENT_ID},\"message_text\":\"Hello\"}" \
    "${BASE_URL}/api/connections/")
assert_status 409 "$status" "pending request in reverse direction"

reset_fixtures
django_setup "from connections.models import ConnectionRequest; ConnectionRequest.objects.create(sender_id=${SENDER_ID}, recipient_id=${RECIPIENT_ID}, status='accepted')"
status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"recipient_id\":${RECIPIENT_ID},\"message_text\":\"Hello\"}" \
    "${BASE_URL}/api/connections/")
assert_status 409 "$status" "existing accepted connection"

echo
echo "=== Declined, closed, and suspended recipient behavior ==="
reset_fixtures
django_setup "from connections.models import ConnectionRequest; ConnectionRequest.objects.create(sender_id=${SENDER_ID}, recipient_id=${RECIPIENT_ID}, status='declined')"
status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"recipient_id\":${RECIPIENT_ID},\"message_text\":\"Hello\"}" \
    "${BASE_URL}/api/connections/")
assert_status 403 "$status" "declined connection pair"
status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    "${BASE_URL}/api/connections/?type=outgoing")
assert_status 200 "$status" "outgoing list after declined request"
[[ "$(cat "$RESPONSE_FILE")" == "[]" ]] || { echo "FAIL: declined request was listed" >&2; exit 1; }
echo "PASS: declined request hidden from outgoing list"

reset_fixtures
django_setup "from accounts.models import Profile; Profile.objects.filter(user_id=${RECIPIENT_ID}).update(open_to_connect=False)"
status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"recipient_id\":${RECIPIENT_ID},\"message_text\":\"Hello\"}" \
    "${BASE_URL}/api/connections/")
assert_status 403 "$status" "closed recipient"

reset_fixtures
django_setup "from accounts.models import Profile; Profile.objects.filter(user_id=${RECIPIENT_ID}).update(account_status='suspended')"
status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"recipient_id\":${RECIPIENT_ID},\"message_text\":\"Hello\"}" \
    "${BASE_URL}/api/connections/")
assert_status 403 "$status" "suspended recipient"

echo
echo "=== Message validation and preservation ==="
reset_fixtures
printf '{"recipient_id":%s,"message_text":"  Hello  "}' "$RECIPIENT_ID" >"$PAYLOAD_FILE"
status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    -H "Content-Type: application/json" \
    --data-binary "@${PAYLOAD_FILE}" \
    "${BASE_URL}/api/connections/")
assert_status 201 "$status" "preserve intentional whitespace"
whitespace_id=$(python - "$RESPONSE_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as response:
    print(json.load(response)["id"])
PY
)
django_setup "from connections.models import ConnectionRequest; assert ConnectionRequest.objects.get(pk=${whitespace_id}).message_text == '  Hello  '"
echo "PASS: message whitespace preserved"

reset_fixtures
for invalid_id in 0 -1 1; do
    if [[ "$invalid_id" == 1 ]]; then
        invalid_json='true'
    else
        invalid_json="$invalid_id"
    fi
    status=$(request "$RESPONSE_FILE" \
        -H "Authorization: Bearer ${SENDER_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"recipient_id\":${invalid_json},\"message_text\":\"Hello\"}" \
        "${BASE_URL}/api/connections/")
    assert_status 400 "$status" "invalid recipient_id ${invalid_json}"
done

echo
echo "=== Daily request limit and unauthenticated access ==="
reset_fixtures
other_id=$(django_setup '
from accounts.models import Profile
from django.contrib.auth import get_user_model
from companies.models import Company
from connections.models import ConnectionRequest
User = get_user_model()
other, _ = User.objects.get_or_create(username="postman_other_recipient")
other.set_password("OtherPass123!")
other.save()
Profile.objects.update_or_create(user=other, defaults={"current_company": Company.objects.get(name="Acme"), "open_to_connect": True, "account_status": "active"})
ConnectionRequest.objects.filter(sender_id=1).delete()
print(other.pk)
' | tail -n 1)
django_setup "from connections.models import ConnectionRequest; from django.utils import timezone; from datetime import timedelta; ConnectionRequest.objects.bulk_create([ConnectionRequest(sender_id=${SENDER_ID}, recipient_id=${RECIPIENT_ID}, message_text='Hello', created_at=timezone.now() - timedelta(hours=1)) for _ in range(10)])"
status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"recipient_id\":${other_id},\"message_text\":\"Hello\"}" \
    "${BASE_URL}/api/connections/")
assert_status 429 "$status" "daily request limit"

reset_fixtures
long_message=$(printf 'x%.0s' {1..501})
printf '{"recipient_id":%s,"message_text":"%s"}' "$RECIPIENT_ID" "$long_message" >"$PAYLOAD_FILE"
status=$(request "$RESPONSE_FILE" \
    -H "Authorization: Bearer ${SENDER_TOKEN}" \
    -H "Content-Type: application/json" \
    --data-binary "@${PAYLOAD_FILE}" \
    "${BASE_URL}/api/connections/")
assert_status 400 "$status" "message longer than 500 characters"

status=$(request "$RESPONSE_FILE" \
    "${BASE_URL}/api/connections/?type=outgoing")
if [[ "$status" != 401 && "$status" != 403 ]]; then
    echo "FAIL: unauthenticated access: expected 401 or 403, got ${status}" >&2
    cat "$RESPONSE_FILE" >&2
    exit 1
fi
echo "PASS: unauthenticated access rejected (${status})"

echo "All connection endpoint checks completed successfully."