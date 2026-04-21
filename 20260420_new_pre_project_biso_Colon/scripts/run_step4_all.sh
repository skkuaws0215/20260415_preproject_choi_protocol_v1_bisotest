#!/bin/bash
# Colon Step 4 전체 자동 순차 실행 스크립트
# 
# 실행 순서:
#   1. DL drug split (2시간)
#   2. Graph drug split (1시간)
#   3. compute_scaffolds (3분)
#   4. ML scaffold (40분)
#   5. DL scaffold (2시간)
#   6. Graph scaffold (1시간)
# 
# 총 소요: 약 6~7시간

set -e

LOG_DIR="logs"
mkdir -p $LOG_DIR

ts() {
    date '+%Y-%m-%d %H:%M:%S'
}

check_memory() {
    python3 -c "
import psutil
m = psutil.virtual_memory()
avail_gb = m.available / 1024**3
print(f'Available: {avail_gb:.2f} GB, Used: {m.percent:.1f}%')
if avail_gb < 2.0:
    print('⚠️  Memory below 2GB! Waiting 60s before continuing...')
    import time
    time.sleep(60)
"
}

echo "=========================================="
echo "Step 4 전체 자동 실행 시작"
echo "시작: $(ts)"
echo "=========================================="
echo ""

# 사전 체크: ML drug split 완료됐는지
echo "[사전 체크] ML drug split 완료 확인..."
required_files=(
    "results/colon_numeric_ml_v1_holdout.json"
    "results/colon_numeric_ml_v1_5foldcv.json"
    "results/colon_numeric_ml_v1_groupcv.json"
    "results/colon_numeric_smiles_ml_v1_holdout.json"
    "results/colon_numeric_smiles_ml_v1_5foldcv.json"
    "results/colon_numeric_smiles_ml_v1_groupcv.json"
    "results/colon_numeric_context_smiles_ml_v1_holdout.json"
    "results/colon_numeric_context_smiles_ml_v1_5foldcv.json"
    "results/colon_numeric_context_smiles_ml_v1_groupcv.json"
)

missing=0
for f in "${required_files[@]}"; do
    if [ ! -f "$f" ]; then
        echo "  ❌ Missing: $f"
        missing=$((missing+1))
    fi
done

if [ $missing -gt 0 ]; then
    echo ""
    echo "❌ ML drug split이 아직 완료되지 않았습니다 ($missing개 파일 누락)."
    echo "   ML 완료 후 다시 실행해주세요."
    exit 1
fi

echo "✅ ML drug split 완료 확인 ($(ts))"
echo ""

# 1단계: DL drug split
echo "=========================================="
echo "[1/6] DL drug split 시작 ($(ts))"
echo "예상 소요: 1.5~2시간"
echo "=========================================="
check_memory
python3 scripts/run_dl_all.py 2>&1 | tee $LOG_DIR/colon_dl_all.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "❌ DL drug split 실패 ($(ts))"
    exit 1
fi
echo "✅ DL drug split 완료 ($(ts))"
echo ""
sleep 10

# 2단계: Graph drug split
echo "=========================================="
echo "[2/6] Graph drug split 시작 ($(ts))"
echo "예상 소요: 50분~1시간"
echo "=========================================="
check_memory
python3 scripts/run_graph_all.py 2>&1 | tee $LOG_DIR/colon_graph_all.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "❌ Graph drug split 실패 ($(ts))"
    exit 1
fi
echo "✅ Graph drug split 완료 ($(ts))"
echo ""
sleep 10

# 3단계: Scaffold 추출
echo "=========================================="
echo "[3/6] Scaffold 추출 시작 ($(ts))"
echo "예상 소요: 2~3분"
echo "=========================================="
check_memory
python3 scripts/compute_scaffolds.py 2>&1 | tee $LOG_DIR/compute_scaffolds.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "❌ Scaffold 추출 실패 ($(ts))"
    exit 1
fi

if [ ! -f "data/scaffold_groups.npy" ]; then
    echo "❌ scaffold_groups.npy 생성 안 됨"
    exit 1
fi

echo "✅ Scaffold 추출 완료 ($(ts))"
echo ""

# 4단계: ML scaffold split
echo "=========================================="
echo "[4/6] ML scaffold split 시작 ($(ts))"
echo "예상 소요: 40분"
echo "=========================================="
check_memory
python3 scripts/run_ml_scaffold_all.py 2>&1 | tee $LOG_DIR/colon_ml_scaffold.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "❌ ML scaffold 실패 ($(ts))"
    exit 1
fi
echo "✅ ML scaffold 완료 ($(ts))"
echo ""
sleep 10

# 5단계: DL scaffold split
echo "=========================================="
echo "[5/6] DL scaffold split 시작 ($(ts))"
echo "예상 소요: 1.5~2시간"
echo "=========================================="
check_memory
python3 scripts/run_dl_scaffold_all.py 2>&1 | tee $LOG_DIR/colon_dl_scaffold.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "❌ DL scaffold 실패 ($(ts))"
    exit 1
fi
echo "✅ DL scaffold 완료 ($(ts))"
echo ""
sleep 10

# 6단계: Graph scaffold split
echo "=========================================="
echo "[6/6] Graph scaffold split 시작 ($(ts))"
echo "예상 소요: 50분~1시간"
echo "=========================================="
check_memory
python3 scripts/run_graph_scaffold_all.py 2>&1 | tee $LOG_DIR/colon_graph_scaffold.log

if [ ${PIPESTATUS[0]} -ne 0 ]; then
    echo "❌ Graph scaffold 실패 ($(ts))"
    exit 1
fi
echo "✅ Graph scaffold 완료 ($(ts))"
echo ""

# 전체 완료
echo "=========================================="
echo "🎉 Step 4 전체 완료!"
echo "종료: $(ts)"
echo "=========================================="

echo ""
echo "=== 생성된 주요 결과 ==="
echo ""
echo "[Drug Split]"
ls -la results/colon_*_ml_v1_*.json 2>/dev/null | wc -l | xargs echo "ML JSON 파일 수:"
ls -la results/colon_*_dl_v1_*.json 2>/dev/null | wc -l | xargs echo "DL JSON 파일 수:"
ls -la results/colon_*_graph_v1_groupcv.json 2>/dev/null | wc -l | xargs echo "Graph JSON 파일 수:"

echo ""
echo "[Scaffold Split]"
ls -la results/colon_*_ml_v1_scaffoldcv.json 2>/dev/null | wc -l | xargs echo "ML scaffold JSON 수:"
ls -la results/colon_*_dl_v1_scaffoldcv.json 2>/dev/null | wc -l | xargs echo "DL scaffold JSON 수:"
ls -la results/colon_*_graph_v1_scaffoldcv.json 2>/dev/null | wc -l | xargs echo "Graph scaffold JSON 수:"

echo ""
echo "내일 아침 확인해주세요!"
