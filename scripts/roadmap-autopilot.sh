#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(git rev-parse --show-toplevel)"
if [[ -n "${CONTROL_REPO:-}" ]]; then
  CONTROL_REPO="$(realpath "$CONTROL_REPO")"
elif [[ -x "$ROOT/../portfolio-control/scripts/run-product-roadmap.sh" ]]; then
  CONTROL_REPO="$(realpath "$ROOT/../portfolio-control")"
elif [[ -x "$ROOT/../../../scripts/run-product-roadmap.sh" ]]; then
  CONTROL_REPO="$(realpath "$ROOT/../../..")"
else
  CONTROL_REPO="$(realpath -m "$ROOT/../portfolio-control")"
fi
[[ -x "$CONTROL_REPO/scripts/run-product-roadmap.sh" ]] || {
  echo "missing portfolio-control autopilot: $CONTROL_REPO/scripts/run-product-roadmap.sh" >&2
  exit 2
}
export PORTFOLIO_TARGET_PATH="${PORTFOLIO_TARGET_PATH:-$ROOT}"
# Grounded Growth target PRs are always human-reviewed. The control-plane runner
# enforces this manifest policy even if AUTOPILOT_MODE requests auto-merge.
exec "$CONTROL_REPO/scripts/run-product-roadmap.sh" gitg-self-host "$@"
