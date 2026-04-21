# STAD 재현 프로토콜 (로컬 실행 기준)

본 문서는 위암(TCGA-STAD) 파이프라인을 Step 0부터 재현할 때의 실행 순서를 정리합니다.  
원칙은 다음과 같습니다.

- 코드: Colon/Lung 선행 구현 재사용
- 데이터: STAD 실제 데이터만 사용
- raw mirror: `curated_data/`는 읽기 전용

## 0. 사전 준비

- 작업 경로: `20260421_new_pre_project_biso_STAD`
- Python: 3.10 (`conda` env `drug4` 권장)
- AWS CLI 인증
- 참조 프로토콜: `/Users/skku_aws2_14/Downloads/drug_repurposing_pipeline_protocol (2).md` (업데이트 중)

## 1. Raw 수집/동기화

### 1-1. 팀 S3 raw mirror 동기화

```bash
cd 20260421_new_pre_project_biso_STAD
./scripts/parallel_download_stad.sh
```

주요 소스:
- `s3://say2-4team/Stad_raw/gdsc/`
- `s3://say2-4team/Stad_raw/depmap/`
- `s3://say2-4team/Stad_raw/cbioportal/stad_tcga_pan_can_atlas_2018/`
- `s3://say2-4team/Stad_raw/geo/{GSE62254,GSE15459,GSE84437}/`
- `s3://say2-4team/Stad_raw/additional_sources/cosmic_stad/`
- `s3://say2-4team/Stad_raw/cptac_stad/pdc_manifests/`

### 1-2. LINCS GSE92742 정렬

`lincs_source.json` 기준 표준은 `GSE92742`입니다.  
`Stad_raw/LInc1000`에 `GSE92742`가 아직 없고 Colon 쪽에 이미 있으면, 로컬 심볼릭 링크로 맞춥니다.

```bash
./scripts/link_lincs_gse92742_from_colon.sh
```

## 2. 전처리 (Step 2)

```bash
./scripts/run_step2_stad.sh
```

생성되는 주요 산출물:
- `curated_data/processed/gdsc/*.parquet`
- `curated_data/processed/depmap/*.parquet`
- `curated_data/processed/chembl/*.parquet`
- `curated_data/processed/drugbank/*.parquet`
- `data/labels.parquet`
- `data/drug_features.parquet`
- `data/drug_target_mapping.parquet`
- `data/lincs_stad.parquet`
- `data/lincs_stad_drug_level.parquet`
- `data/lincs_stad_drug_level_with_crispr_prefix.parquet`
- `reports/step2_integrated_qc_report.json`

## 3. LINCS cell_id 재검증 (GSE92742 only)

후보 리스트를 GSE92742 실데이터(`cell_info`, `sig_info`) 기준으로 재작성합니다.

```bash
python3 scripts/rebuild_stad_lincs_cell_ids_gse92742.py --project-root .
```

필수 산출물:
- `configs/stad_lincs_cell_ids.json` (usable cell만)
- `reports/lincs/stad_lincs_cell_id_review.csv`
- `reports/lincs/stad_lincs_cell_id_qc.json`
- `logs/rebuild_stad_lincs_cell_ids_*.log`

## 4. 외부검증 (Step 6)

Step 6 실행 전, 학습 산출 Top30 CSV 3종이 필요합니다.

- `results/stad_top30_phase2b_catboost_with_names.csv`
- `results/stad_top30_phase2c_catboost_with_names.csv`
- `results/stad_top30_unified_2b_and_2c_with_names.csv`

실행:

```bash
SYNC_S3=1 ./scripts/run_step6_stad.sh
```

## 5. 알려진 제한 사항 (현재 확정)

- `GSE92742` 기준 LINCS usable STAD cell은 `AGS`만 확인됨
- `trt_cp` signature count: `AGS = 362`
- 따라서 downstream 해석/보고에서 다음 문구를 명시:
  - "LINCS evidence in STAD is AGS-only under GSE92742; coverage limitation applies."

## 6. 운영 체크리스트

- [ ] `curated_data/` raw 파일을 수정/삭제하지 않았는가
- [ ] Step 2 QC 리포트가 생성되었는가
- [ ] LINCS cell_id QC 리포트가 최신인가
- [ ] Step 6 입력 Top30 CSV 3종이 준비되었는가
- [ ] 보고서에 LINCS AGS-only limitation이 반영되었는가
