#!/usr/bin/env bash
set -euo pipefail

# Step 5 only: OOF ensemble + finalize — run after reviewing reports/step4_metrics_review_<RESULT_TAG>.csv
#
# Required env:
#   RUN_ID       — same as Step 4 training
#   RESULT_TAG   — same as Step 4 training
#
# Optional:
#   PYTHON_BIN   — default python3
#   EXTRA_ENSEMBLE_ARGS — extra args passed to run_ensemble_catboost_dl_graph_stad.py (quoted string)

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
RUN_ID="${RUN_ID:?Set RUN_ID (same as Step 4)}"
RESULT_TAG="${RESULT_TAG:?Set RESULT_TAG (same as Step 4)}"
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "$LOG_DIR"

STAMP="${RUN_ID}"
echo "[STAD Step5] PROJECT_ROOT=$PROJECT_ROOT"
echo "[STAD Step5] RUN_ID=$RUN_ID RESULT_TAG=$RESULT_TAG"

CSV_REVIEW="${PROJECT_ROOT}/reports/step4_metrics_review_${RESULT_TAG}.csv"
if [[ ! -f "${CSV_REVIEW}" ]]; then
  echo "[STAD Step5][WARN] Missing review table: ${CSV_REVIEW}" >&2
  echo "[STAD Step5][WARN] Generate first: python3 scripts/summarize_step4_metrics_stad.py --result-tag ${RESULT_TAG}" >&2
fi

EVAL_MODE="${EVAL_MODE:-groupcv}"

"$PYTHON_BIN" scripts/run_ensemble_catboost_dl_graph_stad.py \
  --run-id "$RUN_ID" \
  --result-tag "$RESULT_TAG" \
  --eval-mode "$EVAL_MODE" \
  2>&1 | tee "${LOG_DIR}/stad_step5_ensemble_${STAMP}.log"

"$PYTHON_BIN" scripts/finalize_step5_stad.py \
  --project-root "$PROJECT_ROOT" \
  --result-tag "$RESULT_TAG" \
  --eval-mode "$EVAL_MODE" \
  2>&1 | tee "${LOG_DIR}/stad_step5_finalize_${STAMP}.log"

echo "[STAD Step5] Done. Ensemble JSON: results/${RESULT_TAG}/ensemble_catboost_dl_graph_${EVAL_MODE}.json"
