#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(git rev-parse --show-toplevel)"
COMMANDS="$ROOT/contracts/verification.commands"
LOG_DIR="$ROOT/docs/evidence/local"
MODE="${1:-full}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOG_DIR/verify-${MODE}-${STAMP}.log"

case "$MODE" in
  contract) MODE_RANK=1 ;;
  quick) MODE_RANK=2 ;;
  full) MODE_RANK=3 ;;
  *) echo "usage: $0 [contract|quick|full]" >&2; exit 2 ;;
esac

[[ -f "$COMMANDS" ]] || { echo "missing $COMMANDS" >&2; exit 2; }
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG") 2>&1
printf 'repository=%s\nmode=%s\nstarted=%s\nhead=%s\n' \
  "$ROOT" "$MODE" "$(date -u --iso-8601=seconds)" "$(git -C "$ROOT" rev-parse HEAD)"

SECTION="contract"
while IFS= read -r line || [[ -n "$line" ]]; do
  if [[ "$line" =~ ^#[[:space:]]*scope:([a-z]+)[[:space:]]*$ ]]; then
    SECTION="${BASH_REMATCH[1]}"
    continue
  fi
  [[ -z "${line//[[:space:]]/}" ]] && continue
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  case "$SECTION" in
    contract) SECTION_RANK=1 ;;
    quick) SECTION_RANK=2 ;;
    full) SECTION_RANK=3 ;;
    *) echo "unknown verification scope: $SECTION" >&2; exit 2 ;;
  esac
  if (( SECTION_RANK <= MODE_RANK )); then
    printf '\n>>> [%s] %s\n' "$SECTION" "$line"
    bash -lc "cd \"$ROOT\" && $line"
  fi
done < "$COMMANDS"
printf '\ncompleted=%s\nlog=%s\n' "$(date -u --iso-8601=seconds)" "$LOG"
