#!/bin/bash

BASE_DIR="/Users/skku_aws2_14/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest/20260416_new_pre_project_biso_Lung"

echo "=== 다운로드 진행 상황 ==="
echo ""

for dir in gdsc admet cptac depmap drugbank validation chembl lincs; do
    target_dir="$BASE_DIR/curated_data/$dir"
    if [ -d "$target_dir" ]; then
        file_count=$(find "$target_dir" -type f 2>/dev/null | wc -l | tr -d ' ')
        total_size=$(du -sh "$target_dir" 2>/dev/null | cut -f1)
        echo "[$dir] 파일: $file_count개, 크기: $total_size"
    else
        echo "[$dir] 대기 중..."
    fi
done

echo ""
echo "=== 최근 로그 (마지막 10줄) ==="
tail -10 "$BASE_DIR/logs/download_log.txt" 2>/dev/null || echo "로그 파일 생성 대기 중..."
