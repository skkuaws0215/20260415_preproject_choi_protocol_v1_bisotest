# 멀티암종 실행 보고서 (최신 통합본)

- 작성일시: `2026-04-26` (Step5 반영)
- 기준 실행 루트: `results/20260424_multicancer_stad_protocol_rerun/`
- 기준 문서(Step4): `results/20260424_multicancer_stad_protocol_rerun/step4_models/fs_a_stad_baseline/integrated_step4_audit/integrated_step4_audit_report.md`
- Step5 감사·리뷰: `step5_ensemble/audit/step5_ensemble_report.md`, `step5_ensemble/review/step5_result_review_report.md` (로컬 `results/` 트리)

## 1) Step 4 정식 범위

- ML 계획: `4암종 x 3track x 6모델 x 5eval = 360`
- DL 계획: `4암종 x 3track x 7모델 x 5eval = 420`
- Graph 계획: `4암종 x 3track x 2모델 x 5eval = 120`

## 2) 현재 확정 상태

### 2-1. ML
- planned = `360`
- completed = `320`
- missing = `40`
- 누락 분류 = `ElasticNet 2B/2C optional baseline missing`
- 상태 = `near-full`

### 2-2. DL
- planned = `420`
- completed = `420`
- missing = `0`
- 상태 = `full`

### 2-3. Graph
- planned = `120`
- completed = `95`
- missing = `25`
- 누락 범위 = `LUAD only`
- LUAD resume 결과 = `0/25` 완료, `25/25` 미완료
- first blocked = `luad / 2A_numeric / GAT / holdout`
- 신규 `error.log` = `0`
- fatal traceback = `없음`
- 상태 = `partial-full`

## 3) 운영 해석

- 통합 상태 정의:
  - `ML near-full`
  - `DL full`
  - `Graph partial-full`
- Graph LUAD 미완료는 코드 예외보다 계산 병목/hang 가능성이 높다.
  - 관찰 근거: CPU 98~99% 장시간 유지, metrics 95 고정(45분+), 신규 error/fatal traceback 없음
- 완료된 Graph `95` 결과는 유효하며 통합 분석에 사용 가능하다.

## 4) Step5 표시 규칙 (강제)

아래 문구를 Step5 산출물/보고서에 반드시 포함한다.

`Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations.`

추가 규칙:
- CatBoost 또는 특정 모델 고정 슬롯 금지
- 최종 ML/DL/Graph 후보는 all-model robust ranking 기반 선정
- Step5 진행은 통합 audit 결과를 근거로만 수행

## 5) Step5 준비도(실행 전)

- integrated readiness: `ready_with_caveat`
- strict leakage violation: `0`
- caveat: LUAD Graph 25 미완료를 해석/비교에서 명시해야 함

## 6) Step5 실행·감사 요약(2026-04-26)

- 상태: `ready_with_caveat` 전제하에 Step5 **실행·감사·결과 리뷰 완료**
- 앙상블 메서드: `simple_mean`, `rank_mean`, `robust_weighted`
- Step6 1·2·3차 권고(리뷰): 1차 `rank_mean` → 2차 `robust_weighted` → 3차 `simple_mean`
- 스케일: prediction rows `1,505,658` / metrics rows `180` / combo-level error `0`
- 누수: Step4/Step5 audit 기준 strict violation `0`
- 조인: `sample_id`·`canonical_drug_id` **string 정규화** 후 병합( dtype merge 오류 제거)
- missing-aware: 누락 모달리티 조합 `10`개, LUAD graph-missing 플래그 `10`개
- 강제 문구(유지): `Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations.`
- 전역 mean 메트릭(감사 `step5_ensemble_report.md`): `rank_mean`은 Spearman `0.4687`, NDCG@30 `0.3317` 등; `robust_weighted`는 RMSE `2.2504`, MAE `1.7069`로 오차 기준에서 유리 — **평가 목적에 맞게 1·2차 선택**
- 산출 위치(로컬): `.../step5_ensemble/results/`, `.../step5_ensemble/audit/`, `.../step5_ensemble/review/`

## 7) 권고(업데이트)

- Step6 전: `step5_external_validation_candidate_shortlist.csv`와 LUAD Graph caveat를 우선 리뷰
- 단기: Step5 `rank_mean` 중심으로 내부 후보·비교; Graph partial(95/120) 전제 유지
- 중기: LUAD Graph 누락 25는 AWS Batch 또는 경량 GAT·별도 repair(무승인 재시도는 프로토콜 금지 범주와 별도 승인 필요)
- 장기: Graph full은 로컬 단일 환경 대신 서버/AWS 병렬 실행 권고

## 8) Step7 최신 업데이트 (2026-04-27)

- 적용 규칙(프로토콜 정렬):
  - `1단계`: `ADMET PASS` AND (`fda_approved_cancer_based == True` OR `n_clinicaltrials_studies_total >= 3`)
  - `2단계`: `ADMET PASS` AND 1단계 미해당
  - `3단계`: `ADMET WARNING`
- Top30 선반정 후 Top15 재선정 반영:
  - BRCA: `2` 교체
  - CRC: `4` 교체
  - LUAD: `4` 교체
  - STAD: `2` 교체
- 핵심 산출물:
  - `results/20260424_multicancer_stad_protocol_rerun/restored_protocol_top30_ev_top15_admet_multiresponse/final_update/final_multiresponse_ev_admet_integrated_ranking.csv`
  - `results/20260424_multicancer_stad_protocol_rerun/restored_protocol_top30_ev_top15_admet_multiresponse/final_update/final_multiresponse_three_tier_classification_top15.csv`
  - `results/20260424_multicancer_stad_protocol_rerun/restored_protocol_top30_ev_top15_admet_multiresponse/final_update/step7_top30_to_top15_cutoff_reason_table.csv`
- 대시보드 반영:
  - `results/20260424_multicancer_stad_protocol_rerun/dashboard_extracts/multi_cancer_real_dashboard.html`
  - `약물추천` 탭에 `3단계 표` + `Top30→Top15 컷오프 근거표` 표시

## 9) Step8(Neo4j) 핸드오프 패키지 + 작업 제약

### 9-1. 다른 팀원에게 전달할 최소 패키지

- `Top15 최종 입력`:
  - `.../final_update/final_multiresponse_ev_admet_integrated_ranking.csv`
- `3단계 라벨 입력`:
  - `.../final_update/final_multiresponse_three_tier_classification_top15.csv`
- `컷오프 추적 입력`:
  - `.../final_update/step7_top30_to_top15_cutoff_reason_table.csv`
- `암종 승인 매핑 입력`:
  - `.../final_update/cancer_approved_drug_mapping_table.csv`
- `Step8 스크립트 진입점`:
  - `run_step8_export_kg_json_multicancer.py`
  - `run_step8_generate_kg_viewer_multicancer.py`
  - `run_step8_neo4j_summary_multicancer.py`

### 9-2. 전달 시 필수 메모(운영)

- Step8 팀은 **반드시 Step7 최신 Top15(프로토콜 재선정본)**을 기준으로 KG를 생성해야 한다.
- `fda_approved_cancer_based`, `admet_status_22assay`, `recommendation_stage_code`, `selected_top15`, `cutoff_reason` 컬럼은 Neo4j property로 유지 권고.
- 이전 Top15 백업은 비교용이며, 운영 기준 입력은 최신 파일 1종으로 고정한다.

### 9-3. Git 작업 제약(중요)

- 본 저장소에서 **multi 범위 외 변경은 커밋/푸시 금지**.
- 특히 아래 경로는 이번 작업 범위에서 제외:
  - `20260416_new_pre_project_biso_Lung/`
  - `20260420_new_pre_project_biso_Colon/`
  - `20260421_new_pre_project_biso_STAD/`
  - 기타 `multi` 실행 루트(`results/20260424_multicancer_stad_protocol_rerun/`) 외 실험성 파일
- 병렬 에이전트 사용 시에도 동일 제약 적용:
  - `multi 관련 파일만 stage`
  - `non-multi 파일은 stage/commit/push 금지`
