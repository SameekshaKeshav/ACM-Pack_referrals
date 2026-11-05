#!/usr/bin/env bash
# Put staging back on an earlier (or later) commit, and time how long it takes.
#
#   scripts/rollback.sh <commit>             # e.g. scripts/rollback.sh c95d932
#   scripts/rollback.sh <commit> --dry-run   # do every check, deploy nothing
#   scripts/rollback.sh <commit> --rebuild   # build the commit again even if a rollback is possible
#   scripts/rollback.sh <commit> --yes       # don't ask before deploying
#   scripts/rollback.sh <commit> --force     # deploy even though the migration check failed
#
# Two ways to get there, picked automatically:
#   rollback  Railway reuses that deployment's existing build. Fast, but Railway
#             only allows it for recent deployments (on our plan, just the one
#             before the current one).
#   rebuild   `railway redeploy --commit`: builds the commit from source, like a
#             normal deploy. Works for any commit on GitHub, but takes as long as
#             a deploy.
#
# Rolling back code does not roll back the database: migrations stay applied.
# So the script refuses a commit that is missing migrations a newer deployment
# applied, unless you pass --force. See "Rolling back staging" in README.md.
#
# Needs the Railway CLI, logged in and linked to the staging service (check with
# `railway status`), plus git, curl and jq.
set -euo pipefail

cd "$(dirname "$0")/.."
STAGING_URL="${STAGING_URL:-https://acm-packreferrals-production.up.railway.app}"
POLL_SECONDS=3

usage() { sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

TARGET_ARG=""
DRY_RUN=0 REBUILD=0 YES=0 FORCE=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --rebuild) REBUILD=1 ;;
    --yes) YES=1 ;;
    --force) FORCE=1 ;;
    -h|--help) usage ;;
    -*) echo "Unknown option: $arg" >&2; usage ;;
    *) [[ -z "$TARGET_ARG" ]] || usage; TARGET_ARG="$arg" ;;
  esac
done
[[ -n "$TARGET_ARG" ]] || usage

for tool in railway git curl jq; do
  command -v "$tool" > /dev/null || { echo "Missing $tool." >&2; exit 1; }
done

SECONDS=0   # bash's built-in timer; the total time is measured from here

deployed_commit() {
  curl -fsS --max-time 5 "$STAGING_URL/api/health/" 2>/dev/null | jq -r '.commit_hash // empty' 2>/dev/null || true
}

# Migration files in a commit, one path per line, sorted for `comm`.
migration_files() {
  git ls-tree -r --name-only "$1" | grep -E '/migrations/[^/]+\.py$' | grep -v '/__init__\.py$' | LC_ALL=C sort || true
}

echo "Fetching origin so every deployed commit is known locally..."
git fetch --quiet origin

TARGET="$(git rev-parse --verify --quiet "$TARGET_ARG^{commit}")" || {
  echo "$TARGET_ARG is not a commit in this repository." >&2; exit 1; }
SHORT="${TARGET:0:7}"
if ! git merge-base --is-ancestor "$TARGET" origin/main; then
  echo "Warning: $SHORT is not on origin/main." >&2
fi

LIVE="$(deployed_commit)"
if [[ -z "$LIVE" ]]; then
  echo "Warning: $STAGING_URL/api/health/ did not answer, so the live commit is unknown." >&2
elif [[ "$LIVE" == "$TARGET" ]]; then
  echo "Staging is already on $SHORT. Nothing to do."
  exit 0
fi

# Newest first. Railway keeps every deployment in this list, including the
# ones it has since replaced (status REMOVED).
DEPLOYMENTS="$(railway deployment list --limit 100 --json)"

# --- Migration check ----------------------------------------------------------
# The database has every migration that any deployment since the target was
# last live has applied. If the target's code lacks one, it runs against tables
# it does not expect. Deployments before that point are skipped: the target
# was live after them, so their migrations were already compatible with it.
TARGET_LAST_LIVE="$(jq -r --arg c "$TARGET" \
  '[.[] | select(.meta.commitHash == $c and .status != "FAILED" and .status != "CRASHED")][0].createdAt // empty' \
  <<< "$DEPLOYMENTS")"
if [[ -n "$TARGET_LAST_LIVE" ]]; then
  CUTOFF="${TARGET_LAST_LIVE:0:19}"
else
  # Never deployed: compare with everything deployed after it was committed.
  CUTOFF="$(TZ=UTC git show -s --date=format-local:%Y-%m-%dT%H:%M:%S --format=%cd "$TARGET")"
fi
# Newest first, each commit once.
LATER_COMMITS="$(jq -r --arg cutoff "$CUTOFF" --arg c "$TARGET" \
  '[.[] | select(.createdAt[0:19] > $cutoff) | .meta.commitHash // empty | select(. != $c)]
   | reduce .[] as $h ([]; if index([$h]) then . else . + [$h] end) | .[]' <<< "$DEPLOYMENTS")"

TARGET_MIGRATIONS="$(migration_files "$TARGET")"
PROBLEMS=""
for commit in $LATER_COMMITS; do
  if ! git cat-file -e "$commit^{commit}" 2>/dev/null; then
    PROBLEMS+="  ${commit:0:7} was deployed but is not in this repository, so it cannot be checked."$'\n'
    continue
  fi
  missing="$(LC_ALL=C comm -23 <(migration_files "$commit") <(printf '%s\n' "$TARGET_MIGRATIONS"))"
  while IFS= read -r file; do
    [[ -z "$file" || "$PROBLEMS" == *"  $file ("* ]] && continue   # listed once, newest first
    PROBLEMS+="  $file (deployed with ${commit:0:7})"$'\n'
  done <<< "$missing"
done

# --- Pick rollback or rebuild ---------------------------------------------------
METHOD=rebuild
DEPLOYMENT_ID="$(jq -r --arg c "$TARGET" \
  '[.[] | select(.meta.commitHash == $c and .status != "FAILED" and .status != "CRASHED")][0].id // empty' \
  <<< "$DEPLOYMENTS")"
if [[ -n "$DEPLOYMENT_ID" && $REBUILD -eq 0 ]]; then
  # $id is a GraphQL variable (passed with --raw-var), not a shell one.
  # shellcheck disable=SC2016
  CAN_ROLLBACK="$(railway api --compact --raw-var "id=$DEPLOYMENT_ID" \
    'query($id: String!) { deployment(id: $id) { canRollback } }' | jq -r '.data.deployment.canRollback')"
  [[ "$CAN_ROLLBACK" == "true" ]] && METHOD=rollback
fi

echo
echo "Live on staging: ${LIVE:-unknown}"
echo "Target:          $TARGET  $(git show -s --format=%s "$TARGET")"
if [[ $METHOD == rollback ]]; then
  echo "Method:          rollback to deployment $DEPLOYMENT_ID (reuses its build)"
elif [[ $REBUILD -eq 1 ]]; then
  echo "Method:          rebuild from source (--rebuild)"
elif [[ -n "$DEPLOYMENT_ID" ]]; then
  echo "Method:          rebuild from source (Railway no longer allows a rollback to that deployment)"
else
  echo "Method:          rebuild from source (this commit has no earlier deployment to roll back to)"
fi

if [[ -n "$PROBLEMS" ]]; then
  echo
  echo "Migration check FAILED. These migrations may be applied on staging but are missing from $SHORT:"
  printf '%s' "$PROBLEMS"
  echo "Rolling back code does not undo them, so $SHORT's code could fail against the newer tables."
  if [[ $FORCE -eq 0 ]]; then
    echo "Pick a commit that has these migrations, or fix forward instead. --force skips this check."
    exit 1
  fi
  echo "--force given, continuing anyway."
else
  echo "Migration check: OK, no migrations applied since $SHORT was live are missing from it."
fi

if [[ $DRY_RUN -eq 1 ]]; then
  echo
  echo "Dry run: nothing was deployed. (${SECONDS}s)"
  exit 0
fi

if [[ $YES -eq 0 ]]; then
  [[ -t 0 ]] || { echo "Not a terminal, so cannot ask. Pass --yes to deploy." >&2; exit 1; }
  read -r -p "Deploy $SHORT to staging now? [y/N] " answer
  [[ "$answer" == [yY] ]] || { echo "Cancelled."; exit 1; }
fi

if [[ $METHOD == rollback ]]; then
  # shellcheck disable=SC2016
  railway api --compact --raw-var "id=$DEPLOYMENT_ID" \
    'mutation($id: String!) { deploymentRollback(id: $id) }' > /dev/null
  TIMEOUT="${TIMEOUT:-300}"
else
  railway redeploy --commit "$TARGET" --yes > /dev/null
  TIMEOUT="${TIMEOUT:-900}"   # a full build
fi
echo "Started the $METHOD at ${SECONDS}s. Waiting for /api/health/ to report $SHORT..."

DEADLINE=$((SECONDS + TIMEOUT))
LAST_REPORT=$SECONDS
current=""
while (( SECONDS < DEADLINE )); do
  current="$(deployed_commit)"
  if [[ "$current" == "$TARGET" ]]; then
    echo
    echo "Staging is on $SHORT. Total time: ${SECONDS}s."
    echo "The next merge to main deploys over this. Hold merges until the fix is ready."
    [[ -n "$LIVE" ]] && echo "To undo this: scripts/rollback.sh ${LIVE:0:7}"
    exit 0
  fi
  if (( SECONDS - LAST_REPORT >= 30 )); then
    echo "  ${SECONDS}s: staging reports ${current:-(no answer)}"
    LAST_REPORT=$SECONDS
  fi
  sleep "$POLL_SECONDS"
done

echo "Gave up after ${TIMEOUT}s: staging still reports ${current:-no answer}." >&2
echo "Check \`railway deployment list\` and \`railway logs --build\` / \`railway logs\`." >&2
exit 1
