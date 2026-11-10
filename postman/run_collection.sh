#!/usr/bin/env bash
# Run the whole Postman collection against a throwaway local server.
#
#   postman/run_collection.sh                  # run every request and its tests
#   postman/run_collection.sh --save-examples  # ...and, if all pass, save each
#                                              # response as that request's example
#
# Uses a temporary SQLite file, so your db.sqlite3 is never touched, and starts
# its own runserver on $PORT (default 8765) with throttles raised so reruns do
# not hit 429s (the throttles themselves are covered by `manage.py test`).
# Needs Node for `npx`; newman is fetched on first use, nothing is installed globally.
# Local only: seed_demo_data refuses to run without DEBUG.
set -euo pipefail

cd "$(dirname "$0")/.."
COLLECTION=postman/pack-referrals.postman_collection.json
NEWMAN_VERSION=6.2.1
PORT="${PORT:-8765}"
SAVE_EXAMPLES=0
[[ "${1:-}" == "--save-examples" ]] && SAVE_EXAMPLES=1

PYTHON=python
[[ -x .venv/bin/python ]] && PYTHON=.venv/bin/python

WORK="$(mktemp -d)"
SERVER_PID=""
cleanup() {
  [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

# Set here rather than read from .env (load_dotenv never overrides these).
export SQLITE_PATH="$WORK/db.sqlite3"
export DEBUG=True
export EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
export SENTRY_DSN=""
export THROTTLE_CODE_REQUEST=1000/min
export THROTTLE_VERIFY_ATTEMPT=1000/min
export THROTTLE_ALUMNI_REQUEST=1000/min
export THROTTLE_MESSAGE_SEND=1000/min
export THROTTLE_REPORT_CREATE=1000/hour

echo "Migrating a throwaway database..."
"$PYTHON" manage.py migrate --noinput > /dev/null
"$PYTHON" manage.py seed_demo_data > "$WORK/seed.txt"

# seed_demo_data prints "name: value" lines; pass the ones the collection uses.
ENV_ARGS=(--env-var "base_url=http://127.0.0.1:$PORT")
for key in sender_token recipient_token outsider_token sender_id recipient_id outsider_id \
           company_id signup_email verify_email verify_code alumni_email; do
  value="$(sed -n "s/^$key: //p" "$WORK/seed.txt")"
  [[ -n "$value" ]] || { echo "seed_demo_data did not print $key" >&2; exit 1; }
  ENV_ARGS+=(--env-var "$key=$value")
done

"$PYTHON" manage.py runserver --noreload "127.0.0.1:$PORT" > "$WORK/server.log" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 40); do
  curl -sf "http://127.0.0.1:$PORT/api/health/" > /dev/null && break
  if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "runserver exited; its log:" >&2; cat "$WORK/server.log" >&2; exit 1
  fi
  sleep 0.5
done

status=0
npx --yes "newman@$NEWMAN_VERSION" run "$COLLECTION" "${ENV_ARGS[@]}" \
  --reporters cli,json --reporter-json-export "$WORK/report.json" || status=$?

if [[ $status -ne 0 ]]; then
  echo "newman failed (exit $status). Last lines of the server log:" >&2
  tail -n 40 "$WORK/server.log" >&2
  exit "$status"
fi

if [[ $SAVE_EXAMPLES -eq 1 ]]; then
  "$PYTHON" -I postman/save_examples.py "$COLLECTION" "$WORK/report.json"
fi
