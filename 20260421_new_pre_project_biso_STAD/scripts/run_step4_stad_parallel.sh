#!/usr/bin/env bash
# Alias: run_step4_stad.sh now defaults to parallel lanes (STEP4_PARALLEL=1).
# This wrapper keeps the old name and forces parallel explicitly.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export STEP4_PARALLEL="${STEP4_PARALLEL:-1}"
exec "$SCRIPT_DIR/run_step4_stad.sh"
