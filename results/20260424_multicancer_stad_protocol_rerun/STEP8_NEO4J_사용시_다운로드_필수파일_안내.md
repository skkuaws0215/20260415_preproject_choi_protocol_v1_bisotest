# Step8 Neo4j 사용 시 다운로드 필수 파일 안내

## 목적

- 이 문서는 Step8(Neo4j/KG 적재) 담당자가 멀티암종 rerun 결과에서 반드시 받아야 하는 입력 파일을 빠르게 식별하기 위한 안내서입니다.

## 기준 루트

- `results/20260424_multicancer_stad_protocol_rerun/`

## 1) 필수 다운로드 파일 (Required)

아래 4개는 Step8 수행 전에 반드시 다운로드/확보합니다.

1. `restored_protocol_top30_ev_top15_admet_multiresponse/final_update/final_multiresponse_ev_admet_integrated_ranking.csv`
2. `restored_protocol_top30_ev_top15_admet_multiresponse/final_update/final_multiresponse_three_tier_classification_top15.csv`
3. `restored_protocol_top30_ev_top15_admet_multiresponse/final_update/step7_top30_to_top15_cutoff_reason_table.csv`
4. `restored_protocol_top30_ev_top15_admet_multiresponse/final_update/cancer_approved_drug_mapping_table.csv`

## 2) 권장 다운로드 파일 (Recommended)

추적/검증용으로 함께 받는 것을 권장합니다.

1. `restored_protocol_top30_ev_top15_admet_multiresponse/final_update/final_multiresponse_three_tier_summary_by_cancer.csv`
2. `restored_protocol_top30_ev_top15_admet_multiresponse/final_update/step7_top30_to_top15_cutoff_reason_summary.csv`
3. `restored_protocol_top30_ev_top15_admet_multiresponse/final_update/final_multiresponse_ev_admet_integrated_ranking.pre_protocol_backup.csv`
4. `restored_protocol_top30_ev_top15_admet_multiresponse/step6_ev_selected_top15_multiresponse.pre_protocol_backup.csv`

## 3) Step8 실행 진입점 스크립트

- `run_step8_export_kg_json_multicancer.py`
- `run_step8_generate_kg_viewer_multicancer.py`
- `run_step8_neo4j_summary_multicancer.py`

## 4) Neo4j 적재 시 보존 권장 컬럼

- `cancer`
- `canonical_drug_id`
- `drug_name`
- `final_rank_by_cancer`
- `ev_composite_0_10`
- `admet_status_22assay`
- `fda_approved_cancer_based`
- `n_clinicaltrials_studies_total`
- `recommendation_stage_code`
- `recommendation_stage_label_ko`
- `selected_top15`
- `cutoff_reason`

## 5) 작업 제약 (중요)

- 멀티암종 범위 외 파일은 커밋/푸시 금지
- 본 안내서 기준 파일은 `results/20260424_multicancer_stad_protocol_rerun/` 범위에서만 취급
