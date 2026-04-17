#!/bin/bash

# 작업 디렉토리 설정
BASE_DIR="/Users/skku_aws2_14/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest/20260416_new_pre_project_biso_Lung"
LOG_FILE="$BASE_DIR/logs/download_log.txt"

# 로그 함수
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== 병렬 다운로드 시작 ==="

# AWS S3 병렬 다운로드 설정
log "AWS CLI 병렬 다운로드 설정 중..."
aws configure set default.s3.max_concurrent_requests 20
aws configure set default.s3.multipart_threshold 64MB
aws configure set default.s3.multipart_chunksize 16MB
log "✓ AWS CLI 설정 완료"

# 그룹 1 (소용량) - 백그라운드
log "그룹 1 (소용량) 다운로드 시작..."

log "  - GDSC 다운로드 시작"
aws s3 sync s3://say2-4team/Lung_raw/GDSC/ \
  "$BASE_DIR/curated_data/gdsc/" \
  2>&1 | tee -a "$LOG_FILE" &
PID_GDSC=$!

log "  - ADMET 다운로드 시작"
aws s3 sync s3://say2-4team/Lung_raw/admet/ \
  "$BASE_DIR/curated_data/admet/" \
  2>&1 | tee -a "$LOG_FILE" &
PID_ADMET=$!

log "  - CPTAC 다운로드 시작"
aws s3 sync s3://say2-4team/Lung_raw/CPTAC/ \
  "$BASE_DIR/curated_data/cptac/" \
  2>&1 | tee -a "$LOG_FILE" &
PID_CPTAC=$!

# 그룹 2 (중간용량) - 백그라운드
log "그룹 2 (중간용량) 다운로드 시작..."

log "  - DepMap 다운로드 시작"
aws s3 sync s3://say2-4team/Lung_raw/depmap/ \
  "$BASE_DIR/curated_data/depmap/" \
  2>&1 | tee -a "$LOG_FILE" &
PID_DEPMAP=$!

log "  - DrugBank 다운로드 시작"
aws s3 sync s3://say2-4team/Lung_raw/drugbank/ \
  "$BASE_DIR/curated_data/drugbank/" \
  2>&1 | tee -a "$LOG_FILE" &
PID_DRUGBANK=$!

log "  - Additional Sources 다운로드 시작"
aws s3 sync "s3://say2-4team/Lung_raw/additional_sources/" \
  "$BASE_DIR/curated_data/validation/" \
  2>&1 | tee -a "$LOG_FILE" &
PID_ADDL=$!

# 그룹 3 (대용량) - 백그라운드
log "그룹 3 (대용량) 다운로드 시작..."

log "  - ChEMBL 다운로드 시작"
aws s3 sync s3://say2-4team/Lung_raw/chembl/ \
  "$BASE_DIR/curated_data/chembl/" \
  2>&1 | tee -a "$LOG_FILE" &
PID_CHEMBL=$!

log "  - LInc1000(세포주) 다운로드 시작"
aws s3 sync "s3://say2-4team/Lung_raw/LInc1000(세포주)/" \
  "$BASE_DIR/curated_data/lincs/LInc1000_cell_lines/" \
  2>&1 | tee -a "$LOG_FILE" &
PID_LINC1000=$!

log "  - LINCS 다운로드 시작"
aws s3 sync s3://say2-4team/Lung_raw/lincs/ \
  "$BASE_DIR/curated_data/lincs/lincs_main/" \
  2>&1 | tee -a "$LOG_FILE" &
PID_LINCS=$!

# 모든 백그라운드 작업 완료 대기
log "모든 다운로드 작업 실행 중... 완료 대기"
wait $PID_GDSC $PID_ADMET $PID_CPTAC $PID_DEPMAP $PID_DRUGBANK $PID_ADDL $PID_CHEMBL $PID_LINC1000 $PID_LINCS

log "=== 전체 다운로드 완료 ==="

# 다운로드 검증
log "다운로드 검증 시작..."

echo "" >> "$LOG_FILE"
log "=== 다운로드 검증 결과 ==="

for dir in gdsc admet cptac depmap drugbank validation chembl lincs; do
    target_dir="$BASE_DIR/curated_data/$dir"
    if [ -d "$target_dir" ]; then
        file_count=$(find "$target_dir" -type f | wc -l | tr -d ' ')
        total_size=$(du -sh "$target_dir" | cut -f1)
        zero_files=$(find "$target_dir" -type f -size 0 | wc -l | tr -d ' ')

        log "[$dir]"
        log "  파일 수: $file_count"
        log "  전체 크기: $total_size"
        log "  0-byte 파일: $zero_files"

        if [ "$zero_files" -gt 0 ]; then
            log "  ⚠️  WARNING: 0-byte 파일 발견!"
            find "$target_dir" -type f -size 0 >> "$LOG_FILE"
        else
            log "  ✓ OK"
        fi
        log ""
    else
        log "[$dir] ✗ 디렉토리 없음"
    fi
done

log "=== 검증 완료 ==="
log "상세 로그: $LOG_FILE"
