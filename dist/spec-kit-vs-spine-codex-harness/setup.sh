#!/usr/bin/env bash
# One-time setup: checks prerequisites, creates the two trees the harness needs, installs their
# dependencies, and puts the measurement's constitution in place. Safe to re-run.
#   source .env && ./setup.sh
set -euo pipefail
cd "$(dirname "$0")"
: "${SPINE_REPO:?SPINE_REPO is not set — copy env.example to .env, fill it in, then: source .env}"
WORK_DIR=${WORK_DIR:-/tmp/speckit-bench}
RESULTS_DIR=${RESULTS_DIR:-$PWD/results}
TARGET_SHA=${TARGET_SHA:-bd16dbb7}
TARGET_DIR=${TARGET_DIR:-$WORK_DIR/target}
SPINE_REF=${SPINE_REF:-v3.52.0}
SPINE_CODE_DIR=${SPINE_CODE_DIR:-$WORK_DIR/spine-code}
CODEX_AUTH=${CODEX_AUTH:-api-key}
CODEX_LOGIN_HOME=${CODEX_LOGIN_HOME:-$WORK_DIR/codex-app-login}
ok=1
say() { printf '%-28s %s\n' "$1" "$2"; }

echo "== prerequisites"
for c in git uv python3; do
  if command -v "$c" >/dev/null; then say "$c" "$("$c" --version 2>&1 | head -1)"; else say "$c" "MISSING (required)"; ok=0; fi
done
if command -v claude >/dev/null; then say "claude (Claude Code)" "$(claude --version 2>&1 | head -1)"; else say "claude (Claude Code)" "not found — needed only for Claude runs"; fi
if command -v codex >/dev/null; then say "codex (Codex CLI)" "$(codex --version 2>&1 | head -1)"; else say "codex (Codex CLI)" "not found — needed only for OpenAI runs"; fi
if [ "$CODEX_AUTH" = app ] && ! command -v codex >/dev/null; then ok=0; fi
[ -n "${ANTHROPIC_API_KEY:-}" ] && say "ANTHROPIC_API_KEY" "set" || say "ANTHROPIC_API_KEY" "not set — needed only for Claude runs"
[ -n "${OPENAI_API_KEY:-}" ] && say "OPENAI_API_KEY" "set" || say "OPENAI_API_KEY" "not set — needed only for OpenAI runs"
if [ "$CODEX_AUTH" = app ]; then
  if CODEX_HOME="$CODEX_LOGIN_HOME" codex login status >/dev/null 2>&1; then
    say "Codex sign-in (app)" "signed in at $CODEX_LOGIN_HOME"
  else
    say "Codex sign-in (app)" "NOT signed in — run: mkdir -p $CODEX_LOGIN_HOME && CODEX_HOME=$CODEX_LOGIN_HOME codex login"; ok=0
  fi
  if [ "${SPINE_BACKEND:-api}" = codex ]; then
    say "Spine backend" "Codex subscription adapter (no API key)"
  else
    [ -n "${OPENAI_API_KEY:-}" ] || say "" "spec-kit only: Spine + PKG needs OPENAI_API_KEY — use --arms speckit"
  fi
fi
case "$(cd "$(dirname "$WORK_DIR")" 2>/dev/null && pwd -P)/" in
  "$(cd ~ && pwd -P)"/*) say "WORK_DIR" "UNDER \$HOME — spec-kit's writes are denied there; use e.g. /tmp/speckit-bench"; ok=0;;
  *) say "WORK_DIR" "$WORK_DIR";;
esac
git -C "$SPINE_REPO" rev-parse --git-dir >/dev/null 2>&1 || { say "SPINE_REPO" "not a git checkout: $SPINE_REPO"; ok=0; }
[ "$ok" = 1 ] || { echo "fix the items above and re-run"; exit 1; }

echo "== trees"
git -C "$SPINE_REPO" fetch -q --tags origin || true
git -C "$SPINE_REPO" rev-parse --verify "${TARGET_SHA}^{commit}" >/dev/null
git -C "$SPINE_REPO" rev-parse --verify "${SPINE_REF}^{commit}" >/dev/null
mkdir -p "$WORK_DIR" "$RESULTS_DIR"
if [ ! -d "$TARGET_DIR" ]; then git -C "$SPINE_REPO" worktree add -q --detach "$TARGET_DIR" "$TARGET_SHA"; fi
if [ "$(git -C "$TARGET_DIR" rev-parse HEAD)" != "$(git -C "$SPINE_REPO" rev-parse "${TARGET_SHA}^{commit}")" ]; then
  echo "Target tree has the wrong commit. Choose fresh WORK_DIR and RESULTS_DIR."; exit 1
fi
say "target (what both tools change)" "$TARGET_DIR @ $(git -C "$TARGET_DIR" rev-parse --short HEAD)"
if [ ! -d "$SPINE_CODE_DIR" ]; then git -C "$SPINE_REPO" worktree add -q --detach "$SPINE_CODE_DIR" "$SPINE_REF"; fi
if [ "$(git -C "$SPINE_CODE_DIR" rev-parse HEAD)" != "$(git -C "$SPINE_REPO" rev-parse "${SPINE_REF}^{commit}")" ]; then
  echo "Spine tree has the wrong commit. Choose fresh WORK_DIR and RESULTS_DIR."; exit 1
fi
say "Spine code (version measured)" "$SPINE_CODE_DIR @ $SPINE_REF ($(git -C "$SPINE_CODE_DIR" rev-parse --short HEAD))"

echo "== dependencies (uv sync; a few minutes the first time)"
(cd "$SPINE_CODE_DIR" && uv sync --frozen -q --extra dev --extra mcp)
(cd "$TARGET_DIR" && uv sync --frozen -q --extra dev)
say "venvs" "ready"

echo "== constitution"
cp constitution.md "$RESULTS_DIR/constitution.md"
say "constitution.md" "the one every measured spec-kit run used → $RESULTS_DIR/constitution.md"

echo "== ready. Next: follow QUICKSTART.md for tests and a model-specific dry run"
