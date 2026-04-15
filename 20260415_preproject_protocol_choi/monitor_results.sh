#!/bin/bash

RESULTS_DIR="results"
CHECK_INTERVAL=180  # 3분마다 체크

echo "=== 결과 모니터링 시작 ==="
echo "체크 간격: ${CHECK_INTERVAL}초"
echo ""

# 초기 파일 목록
INITIAL_FILES=$(ls -1 "$RESULTS_DIR"/*.json 2>/dev/null | sort)
INITIAL_COUNT=$(echo "$INITIAL_FILES" | grep -c "^" || echo 0)

echo "초기 결과 파일: ${INITIAL_COUNT}개"
echo "$INITIAL_FILES"
echo ""

# 기대하는 파일 목록
ML_FILES=(
    "choi_numeric_ml_v1_holdout.json"
    "choi_numeric_ml_v1_5foldcv.json"
    "choi_numeric_ml_v1_groupcv.json"
    "choi_numeric_smiles_ml_v1_holdout.json"
    "choi_numeric_smiles_ml_v1_5foldcv.json"
    "choi_numeric_smiles_ml_v1_groupcv.json"
    "choi_numeric_context_smiles_ml_v1_holdout.json"
    "choi_numeric_context_smiles_ml_v1_5foldcv.json"
    "choi_numeric_context_smiles_ml_v1_groupcv.json"
)

DL_FILES=(
    "choi_numeric_dl_v1_holdout.json"
    "choi_numeric_dl_v1_5foldcv.json"
    "choi_numeric_dl_v1_groupcv.json"
    "choi_numeric_smiles_dl_v1_holdout.json"
    "choi_numeric_smiles_dl_v1_5foldcv.json"
    "choi_numeric_smiles_dl_v1_groupcv.json"
    "choi_numeric_context_smiles_dl_v1_holdout.json"
    "choi_numeric_context_smiles_dl_v1_5foldcv.json"
    "choi_numeric_context_smiles_dl_v1_groupcv.json"
)

while true; do
    sleep $CHECK_INTERVAL
    
    CURRENT_FILES=$(ls -1 "$RESULTS_DIR"/*.json 2>/dev/null | sort)
    CURRENT_COUNT=$(echo "$CURRENT_FILES" | grep -c "^" || echo 0)
    
    if [ "$CURRENT_COUNT" -gt "$INITIAL_COUNT" ]; then
        NEW_FILES=$(comm -13 <(echo "$INITIAL_FILES") <(echo "$CURRENT_FILES"))
        NEW_COUNT=$((CURRENT_COUNT - INITIAL_COUNT))
        
        echo "=========================================="
        echo "$(date '+%Y-%m-%d %H:%M:%S')"
        echo "새로운 결과 파일 감지: ${NEW_COUNT}개"
        echo "$NEW_FILES"
        echo ""
        
        # ML 파일 체크
        ML_COMPLETE=0
        ML_TOTAL=${#ML_FILES[@]}
        for file in "${ML_FILES[@]}"; do
            if [ -f "$RESULTS_DIR/$file" ]; then
                ML_COMPLETE=$((ML_COMPLETE + 1))
            fi
        done
        
        # DL 파일 체크
        DL_COMPLETE=0
        DL_TOTAL=${#DL_FILES[@]}
        for file in "${DL_FILES[@]}"; do
            if [ -f "$RESULTS_DIR/$file" ]; then
                DL_COMPLETE=$((DL_COMPLETE + 1))
            fi
        done
        
        echo "ML 진행률: ${ML_COMPLETE}/${ML_TOTAL}"
        echo "DL 진행률: ${DL_COMPLETE}/${DL_TOTAL}"
        echo ""
        
        # ML 완료 체크
        if [ "$ML_COMPLETE" -eq "$ML_TOTAL" ] && [ "$INITIAL_COUNT" -lt "$ML_TOTAL" ]; then
            echo "🎉 ML 학습 완료!"
            echo "TRIGGER: ML_COMPLETE"
            echo ""
        fi
        
        # DL 완료 체크
        if [ "$DL_COMPLETE" -eq "$DL_TOTAL" ]; then
            echo "🎉 DL 학습 완료!"
            echo "TRIGGER: DL_COMPLETE"
            echo ""
        fi
        
        # 전체 완료 체크
        if [ "$ML_COMPLETE" -eq "$ML_TOTAL" ] && [ "$DL_COMPLETE" -eq "$DL_TOTAL" ]; then
            echo "🎉🎉 전체 학습 완료!"
            echo "TRIGGER: ALL_COMPLETE"
            break
        fi
        
        INITIAL_FILES="$CURRENT_FILES"
        INITIAL_COUNT="$CURRENT_COUNT"
    else
        echo "[$(date '+%H:%M:%S')] 체크 중... (현재: ${CURRENT_COUNT}개 파일)"
    fi
done

echo ""
echo "=== 모니터링 종료 ==="
