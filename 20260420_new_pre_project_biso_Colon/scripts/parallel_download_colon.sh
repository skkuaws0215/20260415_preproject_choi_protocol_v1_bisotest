#!/bin/bash
# Colon Raw 데이터 다운로드 (옵션 B 범위)
# 기반: Lung의 parallel_download.sh

set -e
BASE_DIR="/Users/skku_aws2_14/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest-1/20260420_new_pre_project_biso_Colon"
mkdir -p "$BASE_DIR/logs"
LOG_FILE="$BASE_DIR/logs/download_$(date +%Y%m%d_%H%M%S).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Colon Raw 다운로드 시작 ==="

# 1. GDSC
log "  - GDSC 다운로드"
aws s3 sync s3://say2-4team/Colon_raw/GDSC/ \
    "$BASE_DIR/curated_data/gdsc/" \
    --exclude "*" --include "GDSC2-dataset.csv" \
    --include "Cell_Lines_Details.xlsx" \
    --include "Compounds-annotation.csv" \
    2>&1 | tee -a "$LOG_FILE"

# 2. DepMap (원본 CSV만, 이미 만들어진 parquet 배제)
log "  - DepMap 다운로드 (원본 CSV만)"
aws s3 sync s3://say2-4team/Colon_raw/depmap/ \
    "$BASE_DIR/curated_data/depmap/" \
    --exclude "*" \
    --include "CRISPRGeneEffect.csv" \
    --include "CRISPRGeneDependency.csv" \
    --include "Model.csv" \
    --include "ModelCondition.csv" \
    2>&1 | tee -a "$LOG_FILE"
# 배제: depmap_crispr_long_20260408.parquet (가공본)

# 3. LINCS (GSE70138만)
log "  - LINCS 다운로드 (GSE70138)"
aws s3 sync s3://say2-4team/Colon_raw/LInc1000/GSE70138/ \
    "$BASE_DIR/curated_data/lincs/GSE70138/" \
    2>&1 | tee -a "$LOG_FILE"

# 4. DrugBank
log "  - DrugBank 다운로드"
aws s3 sync s3://say2-4team/Colon_raw/drugbank/ \
    "$BASE_DIR/curated_data/drugbank/" \
    2>&1 | tee -a "$LOG_FILE"

# 5. ChEMBL
log "  - ChEMBL 다운로드"
aws s3 sync s3://say2-4team/Colon_raw/chembl/ \
    "$BASE_DIR/curated_data/chembl/" \
    --exclude "*" \
    --include "chembl_36_chemreps.txt.gz" \
    --include "chembl_uniprot_mapping.txt" \
    --include "chembl_36_sqlite.tar.gz" \
    2>&1 | tee -a "$LOG_FILE"

# 6. ADMET
log "  - ADMET 다운로드"
aws s3 sync s3://say2-4team/Colon_raw/admet/ \
    "$BASE_DIR/curated_data/admet/" \
    2>&1 | tee -a "$LOG_FILE"

# 7. cBioPortal (2개 스터디만: CPTAC + TCGA-PanCan)
log "  - cBioPortal 다운로드 (coad_cptac_2019 + coadread_tcga_pan_can_atlas_2018)"
aws s3 sync s3://say2-4team/Colon_raw/cBioPortal/coad_cptac_2019/ \
    "$BASE_DIR/curated_data/cbioportal/coad_cptac_2019/" \
    2>&1 | tee -a "$LOG_FILE"
aws s3 sync s3://say2-4team/Colon_raw/cBioPortal/coadread_tcga_pan_can_atlas_2018/ \
    "$BASE_DIR/curated_data/cbioportal/coadread_tcga_pan_can_atlas_2018/" \
    2>&1 | tee -a "$LOG_FILE"

# 8. GEO (1차 외부검증: GSE39582만)
log "  - GEO 다운로드 (GSE39582, 1차 외부검증)"
aws s3 sync s3://say2-4team/Colon_raw/geo/GSE39582/ \
    "$BASE_DIR/curated_data/geo/GSE39582/" \
    2>&1 | tee -a "$LOG_FILE"

# 2차 외부검증 (일단 안 받음, 나중에 추가)
# aws s3 sync s3://say2-4team/Colon_raw/geo/GSE17536/ ...

# 9. COSMIC (Lung과 동일 방식으로 외부 수집 필요)
log "  - COSMIC: 외부 수집 필요 (별도 스크립트)"

# 10. PRISM (외부 수집 필요)
log "  - PRISM: 외부 수집 필요 (별도 스크립트)"

# 11. ClinicalTrials (외부 수집 필요)
log "  - ClinicalTrials: 외부 수집 필요 (별도 스크립트)"

log "=== 다운로드 완료 ==="

# 용량 확인
log "Disk usage:"
du -sh "$BASE_DIR/curated_data/"* 2>&1 | tee -a "$LOG_FILE"
