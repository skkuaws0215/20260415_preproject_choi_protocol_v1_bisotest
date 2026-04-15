#!/bin/bash

echo "ML 완료 모니터링 시작..."
echo "체크 간격: 30초"
echo ""

while true; do
    # Phase 2C JSON 파일 확인
    if ls results/choi_numeric_context_smiles_ml_v1_*.json >/dev/null 2>&1; then
        COUNT=$(ls results/choi_numeric_context_smiles_ml_v1_*.json 2>/dev/null | wc -l)
        if [ "$COUNT" -eq 3 ]; then
            echo ""
            echo "=========================================="
            echo "$(date '+%Y-%m-%d %H:%M:%S')"
            echo "🎉 ML 전체 완료! (Phase 2A/2B/2C)"
            echo "=========================================="
            echo ""
            echo "ML 결과 비교표 생성 중..."
            python3 analyze_ml_all_phases.py
            echo ""
            echo "완료!"
            break
        fi
    fi
    
    # 현재 진행 상황
    OOF_COUNT=$(ls results/choi_numeric_context_smiles_ml_v1_oof/*.npy 2>/dev/null | wc -l || echo 0)
    echo "[$(date '+%H:%M:%S')] Phase 2C OOF: $OOF_COUNT/6 완료..."
    
    sleep 30
done
