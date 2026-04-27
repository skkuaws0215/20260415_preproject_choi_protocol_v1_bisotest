# Step8 Neo4j Handoff (2026-04-27)

## 1) Scope

- 대상: `results/20260424_multicancer_stad_protocol_rerun/` 내 멀티암종 Step8 작업
- 기준: Step7 프로토콜 재선정 Top15 반영본

## 2) Required Inputs

- `results/20260424_multicancer_stad_protocol_rerun/restored_protocol_top30_ev_top15_admet_multiresponse/final_update/final_multiresponse_ev_admet_integrated_ranking.csv`
- `results/20260424_multicancer_stad_protocol_rerun/restored_protocol_top30_ev_top15_admet_multiresponse/final_update/final_multiresponse_three_tier_classification_top15.csv`
- `results/20260424_multicancer_stad_protocol_rerun/restored_protocol_top30_ev_top15_admet_multiresponse/final_update/step7_top30_to_top15_cutoff_reason_table.csv`
- `results/20260424_multicancer_stad_protocol_rerun/restored_protocol_top30_ev_top15_admet_multiresponse/final_update/cancer_approved_drug_mapping_table.csv`

## 3) Required Fields To Preserve In Neo4j

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

## 4) Step8 Execution Entry Points

- `run_step8_export_kg_json_multicancer.py`
- `run_step8_generate_kg_viewer_multicancer.py`
- `run_step8_neo4j_summary_multicancer.py`

## 5) Handoff Acceptance Checklist

- [ ] 입력 4종이 최신 타임스탬프로 로드됨
- [ ] cancer별 Top15 row count = 15 고정 확인
- [ ] Neo4j 적재 후 `recommendation_stage_code` 분포 집계 확인
- [ ] `selected_top15`/`cutoff_reason` 컬럼 손실 없음 확인
- [ ] 기존(백업) Top15와 diff 리포트 1장 첨부

## 6) Git Guardrail (Strict)

- 절대 원칙: **multi 범위 외 커밋/푸시 금지**
- 금지 경로 예시:
  - `20260416_new_pre_project_biso_Lung/`
  - `20260420_new_pre_project_biso_Colon/`
  - `20260421_new_pre_project_biso_STAD/`
- 허용 범위:
  - `results/20260424_multicancer_stad_protocol_rerun/` 및 관련 멀티암종 스크립트
- 병렬 에이전트 공통 규칙:
  - stage 전에 대상 파일 경로를 반드시 확인
  - non-multi 파일은 stage/commit/push 금지
