#!/usr/bin/env bash
set -euo pipefail
# Run from any directory within the repository. Uses synthetic API fixtures, never real JWTs or people.
repo=$(git rev-parse --show-toplevel)
base=${1:-ef1ea41}
evidence="$repo/frontend/qa-evidence/responsive"
mkdir -p "$evidence"
evidence=$(cd "$evidence" && pwd)
temp_root=$(mktemp -d "${TMPDIR:-/tmp}/pack-chat-qa.XXXXXX")
baseline="$temp_root/baseline"
cleanup() {
  git -C "$repo" worktree remove --force "$baseline" 2>/dev/null || true
  rmdir "$temp_root" 2>/dev/null || true
}
trap cleanup EXIT
# A detached worktree keeps the user's checkout and current branch untouched.
git -C "$repo" worktree add --detach "$baseline" "$base"
mkdir -p "$baseline/frontend/tests/fixtures"
cp "$repo/frontend/tests/chat-connect-polish.spec.js" "$baseline/frontend/tests/"
cp "$repo/frontend/tests/fixtures/chat-connect.js" "$baseline/frontend/tests/fixtures/"
(
  cd "$baseline/frontend"
  npm ci
)
(
  cd "$baseline/frontend"
  SCREENSHOT_PHASE=before EVIDENCE_DIR="$evidence" npm test -- tests/chat-connect-polish.spec.js --grep 'responsive capture' --workers=1
)
(
  cd "$repo/frontend"
  SCREENSHOT_PHASE=after EVIDENCE_DIR="$evidence" npm test -- tests/chat-connect-polish.spec.js --grep 'responsive capture' --workers=1
)
printf 'Before/after screenshots: %s\n' "$evidence"
printf 'Baseline: %s\nCurrent: %s\n' "$(git -C "$repo" rev-parse "$base")" "$(git -C "$repo" rev-parse HEAD)" > "$evidence/commits.txt"
