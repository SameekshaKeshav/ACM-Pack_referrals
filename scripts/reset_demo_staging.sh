#!/usr/bin/env bash
# Reset the showcase demo accounts on staging, from your laptop (no interactive railway ssh).
#
# Run from the repo root:   bash scripts/reset_demo_staging.sh
# Needs: Railway CLI logged in and linked to the service (`railway status`).
#
# Steps: wake staging -> check Python + DB in the container -> dry run -> ask you -> reset.
# Nothing on staging changes until you type "y" at the prompt.

set -euo pipefail

URL=https://acm-packreferrals-production.up.railway.app/api/health/

echo "== 0. Railway link (expect: ACM Pack Referrals / ACM-Pack_referrals / production)"
railway status
echo

echo "== 1. Wake staging (app sleeping is on; the first request may 502, so retry)"
awake=0
for i in {1..20}; do
  if curl -sf --max-time 15 "$URL"; then echo; echo "Staging is awake"; awake=1; break; fi
  echo "Not answering yet ($i/20), retrying in 5s..."; sleep 5
done
if [[ $awake -ne 1 ]]; then echo "Staging never answered. Check \`railway logs\`." >&2; exit 1; fi
echo

echo "== 2. Check Python and the database inside the container (read-only)"
railway ssh -- sh -c 'set -e; echo "python: $(command -v python)"; python -c "import sys, django; print(\"venv:  \", sys.prefix, \"| django\", django.get_version())"; if [ -f "$SQLITE_PATH" ]; then echo "db:     $SQLITE_PATH exists"; else echo "db:     MISSING ($SQLITE_PATH)"; exit 1; fi; python manage.py check' < /dev/null
# If "python:" prints nothing, replace `python` below with /app/.venv/bin/python.
echo

echo "== 3. Dry run (changes nothing)"
railway ssh -- sh -c 'ALLOW_DEMO_TOOLS=1 python manage.py reset_demo_data --dry-run' < /dev/null
echo
echo "Check the list above. Any \"(N with a real member)\" rows involve a real ACM member and will be deleted too."
# railway ssh is given < /dev/null above so it cannot swallow what you type here.
read -r -p "Reset the demo accounts on staging now? [y/N] " answer || answer=""
if [[ "$answer" != "y" ]]; then echo "Cancelled. Nothing was changed."; exit 0; fi
echo

echo "== 4. Reset"
railway ssh -- sh -c 'ALLOW_DEMO_TOOLS=1 python manage.py reset_demo_data --yes' < /dev/null
echo
echo "Done. Optional presenter logins (paste the printed line into the browser dev console):"
echo "  railway ssh -- sh -c 'ALLOW_DEMO_TOOLS=1 python manage.py issue_demo_token skeshav2@ncsu.edu'   # set A"
echo "  railway ssh -- sh -c 'ALLOW_DEMO_TOOLS=1 python manage.py issue_demo_token dbbakalo@ncsu.edu'   # set B"

# --- Separate: keep staging awake during the showcase (run in its own terminal, Ctrl+C to stop) ---
# caffeinate -i zsh -c 'URL=https://acm-packreferrals-production.up.railway.app/api/health/; while true; do code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 "$URL"); echo "$(date +%H:%M:%S) $code"; sleep 180; done'
