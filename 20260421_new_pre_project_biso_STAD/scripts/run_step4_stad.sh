#!/usr/bin/env bash
set -euo pipefail

# STAD Step 4 runner (safe mode)
# - creates isolated run-id outputs under data/<run_id>/
# - does NOT overwrite prior run unless --force passed to sub-steps
# - Default: STEP4_PARALLEL=1 → CPU lane (ML→Graph) || GPU lane (DL, MPS when available).
#   Set STEP4_PARALLEL=0 for strict sequential ML→DL→Graph on one process order.

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

RUN_ID="${RUN_ID:-step4_stad_inputs_$(date +%Y%m%d_%H%M%S)}"
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "$LOG_DIR"
PYTHON_BIN="${PYTHON_BIN:-python3}"
EVAL_MODES="${EVAL_MODES:-holdout,cv5,groupcv,scaffoldcv}"
STEP4_PARALLEL="${STEP4_PARALLEL:-1}"

echo "[STAD Step4] PROJECT_ROOT=$PROJECT_ROOT"
echo "[STAD Step4] RUN_ID=$RUN_ID"
RESULT_TAG="${RESULT_TAG:-20260421_stad_step4_v1}"
echo "[STAD Step4] RESULT_TAG=$RESULT_TAG"
echo "[STAD Step4] EVAL_MODES=$EVAL_MODES"
echo "[STAD Step4] STEP4_PARALLEL=$STEP4_PARALLEL"
echo "[STAD Step4] PYTHON_BIN=$PYTHON_BIN"

echo "[STAD Step4] Prepare Phase 2A inputs..."
"$PYTHON_BIN" scripts/prepare_phase2a_data_stad.py --run-id "$RUN_ID" \
  2>&1 | tee "${LOG_DIR}/stad_step4_prepare_phase2a_${RUN_ID}.log"

echo "[STAD Step4] Prepare Phase 2B/2C inputs..."
"$PYTHON_BIN" scripts/prepare_phase2bc_data_stad.py --run-id "$RUN_ID" \
  2>&1 | tee "${LOG_DIR}/stad_step4_prepare_phase2bc_${RUN_ID}.log"

echo "[STAD Step4] Input preparation complete."

CPU_LOG="${LOG_DIR}/stad_step4_cpu_lane_${RUN_ID}.log"
DL_LOG="${LOG_DIR}/stad_step4_dl_lane_${RUN_ID}.log"

if [[ "${STEP4_PARALLEL}" == "1" ]]; then
  echo "[STAD Step4] Training: parallel lanes — CPU (ML→Graph) + GPU/MPS (DL)."
  echo "[STAD Step4]   CPU lane log: $CPU_LOG"
  echo "[STAD Step4]   DL  lane log: $DL_LOG"
  (
    set -euo pipefail
    cd "$PROJECT_ROOT"
    "$PYTHON_BIN" scripts/run_ml_all_stad.py \
      --run-id "$RUN_ID" \
      --result-tag "$RESULT_TAG" \
      --eval-modes "$EVAL_MODES" \
      2>&1 | tee "$CPU_LOG"

    FORCE_CPU=1 "$PYTHON_BIN" scripts/run_graph_all_stad.py \
      --run-id "$RUN_ID" \
      --result-tag "$RESULT_TAG" \
      --eval-modes "$EVAL_MODES" \
      2>&1 | tee -a "$CPU_LOG"
  ) &
  CPU_PID=$!

  (
    set -euo pipefail
    cd "$PROJECT_ROOT"
    FORCE_CPU=0 "$PYTHON_BIN" scripts/run_dl_all_stad.py \
      --run-id "$RUN_ID" \
      --result-tag "$RESULT_TAG" \
      --eval-modes "$EVAL_MODES" \
      2>&1 | tee "$DL_LOG"
  ) &
  DL_PID=$!

  wait "${CPU_PID}"
  wait "${DL_PID}"
  echo "[STAD Step4] ML + Graph (CPU) and DL (GPU lane) complete."
else
  echo "[STAD Step4] Training: sequential ML → DL → Graph (STEP4_PARALLEL=0)."
  echo "[STAD Step4] Run ML experiments..."
  "$PYTHON_BIN" scripts/run_ml_all_stad.py \
    --run-id "$RUN_ID" \
    --result-tag "$RESULT_TAG" \
    --eval-modes "$EVAL_MODES" \
    2>&1 | tee "${LOG_DIR}/stad_step4_ml_${RUN_ID}.log"

  echo "[STAD Step4] Run DL experiments..."
  "$PYTHON_BIN" scripts/run_dl_all_stad.py \
    --run-id "$RUN_ID" \
    --result-tag "$RESULT_TAG" \
    --eval-modes "$EVAL_MODES" \
    2>&1 | tee "${LOG_DIR}/stad_step4_dl_${RUN_ID}.log"

  echo "[STAD Step4] Run Graph experiments..."
  "$PYTHON_BIN" scripts/run_graph_all_stad.py \
    --run-id "$RUN_ID" \
    --result-tag "$RESULT_TAG" \
    --eval-modes "$EVAL_MODES" \
    2>&1 | tee "${LOG_DIR}/stad_step4_graph_${RUN_ID}.log"

  echo "[STAD Step4] Sequential ML/DL/Graph done."
fi

echo "[STAD Step4] Step4 training (ML/DL/Graph) finished."

echo "[STAD Step4] Building metric review tables (all models × phases × eval modes)..."
"$PYTHON_BIN" scripts/summarize_step4_metrics_stad.py \
  --result-tag "$RESULT_TAG" \
  2>&1 | tee "${LOG_DIR}/stad_step4_metrics_review_${RUN_ID}.log"

echo "[STAD Step4] Step5 gate table (cv5 / groupcv / scaffoldcv val Spearman + train−val gap per model)..."
"$PYTHON_BIN" scripts/report_step5_gate_eval_spearman_table_stad.py \
  --project-root "$PROJECT_ROOT" \
  --result-tag "$RESULT_TAG" \
  2>&1 | tee "${LOG_DIR}/stad_step5_gate_eval_table_${RUN_ID}.log"

echo ""
echo "================================================================================"
echo "[STAD Step4] STOP — Review metrics before Step 5 ensemble."
echo "  • CSV (full table): reports/step4_metrics_review_${RESULT_TAG}.csv"
echo "  • Step5 gate (fixed): results/${RESULT_TAG}/step5_gate_eval_spearman_table.csv"
echo "  • Markdown preview: reports/step4_metrics_review_${RESULT_TAG}.md"
echo "  Adjust configs / re-run training if needed. When ready for ensemble + finalize:"
echo "    RUN_ID=${RUN_ID} RESULT_TAG=${RESULT_TAG} bash scripts/run_step5_ensemble_stad.sh"
echo "  Optional: set SKIP_ENSEMBLE=0 to chain Step 5 at the end of this script (same RUN_ID/RESULT_TAG)."
echo "================================================================================"
echo ""

if [[ "${SKIP_ENSEMBLE:-1}" != "1" ]]; then
  echo "[STAD Step4] SKIP_ENSEMBLE!=1 — running Step 5 ensemble + finalize immediately..."
  RUN_ID="$RUN_ID" RESULT_TAG="$RESULT_TAG" "$PROJECT_ROOT/scripts/run_step5_ensemble_stad.sh" \
    2>&1 | tee "${LOG_DIR}/stad_step5_bundle_${RUN_ID}.log"
else
  echo "[STAD Step4] SKIP_ENSEMBLE=1 — ensemble not run. Use run_step5_ensemble_stad.sh after review."
fi
