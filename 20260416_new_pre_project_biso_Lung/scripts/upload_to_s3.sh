#!/bin/bash

# 작업 디렉토리 설정
BASE_DIR="/Users/skku_aws2_14/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest/20260416_new_pre_project_biso_Lung"
LOG_FILE="$BASE_DIR/logs/upload_log.txt"
S3_TARGET="s3://say2-4team/20260408_new_pre_project_biso/20260416_new_pre_project_biso_Lung/"

# 로그 함수
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== S3 업로드 시작 ==="
log "Source: $BASE_DIR/curated_data/"
log "Target: ${S3_TARGET}curated_data/"

# AWS S3 병렬 업로드 설정 (이미 설정되어 있지만 확인)
aws configure set default.s3.max_concurrent_requests 20
aws configure set default.s3.multipart_threshold 64MB
aws configure set default.s3.multipart_chunksize 16MB

# 업로드 시작
log "curated_data/ 전체 업로드 중..."
aws s3 sync "$BASE_DIR/curated_data/" "${S3_TARGET}curated_data/" \
    --storage-class INTELLIGENT_TIERING \
    2>&1 | tee -a "$LOG_FILE"

if [ $? -eq 0 ]; then
    log "✓ 업로드 완료"
else
    log "✗ 업로드 실패"
    exit 1
fi

# 업로드 검증
log "업로드 검증 중..."
log ""
log "=== S3 업로드 검증 ==="

# 로컬 파일 수
LOCAL_COUNT=$(find "$BASE_DIR/curated_data/" -type f | wc -l | tr -d ' ')
log "로컬 파일 수: $LOCAL_COUNT"

# S3 파일 수
S3_COUNT=$(aws s3 ls "${S3_TARGET}curated_data/" --recursive | wc -l | tr -d ' ')
log "S3 파일 수: $S3_COUNT"

if [ "$LOCAL_COUNT" -eq "$S3_COUNT" ]; then
    log "✓ 파일 수 일치: $LOCAL_COUNT == $S3_COUNT"
    log "✓ 업로드 검증 통과"
else
    log "⚠️  WARNING: 파일 수 불일치: 로컬=$LOCAL_COUNT, S3=$S3_COUNT"
fi

# 디렉토리별 파일 수
log ""
log "=== 디렉토리별 S3 업로드 확인 ==="
for dir in gdsc admet cptac depmap drugbank validation chembl lincs; do
    s3_file_count=$(aws s3 ls "${S3_TARGET}curated_data/$dir/" --recursive 2>/dev/null | wc -l | tr -d ' ')
    log "[$dir] S3 파일 수: $s3_file_count"
done

log ""
log "=== 업로드 완료 ==="
log "S3 경로: ${S3_TARGET}curated_data/"
