# STAD 기반 다중 암종 재현 프로토콜
## BRCA / LUAD / CRC / STAD

- 문서 날짜: `2026-04-24` (최종 갱신: `2026-04-26`)
- 프로토콜 버전: `v2026.04.26-mc-r7`
- 적용 범위: `BRCA`, `LUAD`, `CRC`, `STAD` 통합 재실행

---

## 0) 현재 실행 상태 (2026-04-26)

`results/20260424_multicancer_stad_protocol_rerun/` 기준 상태:

- 초기 FE 스키마 감사(raw `features.parquet`)는 라벨 컬럼명 불일치로 차단됨.
- `label_standardization_config.yaml`로 라벨 계약을 고정함:
  - 1차 회귀 라벨 소스: `label_regression`
  - 표준 라벨: `sensitivity_score`
  - 변환: `identity`
  - 방향성: `higher_is_more_sensitive`
- STAD/BRCA/LUAD/CRC 라벨 조인 dry-run 통과:
  - left_only = 0, right_only = 0, 중복 키 = 0, 결측 = 0
- 4개 암종 모두 `features_with_label.parquet` 생성 완료:
  - `results/20260424_multicancer_stad_protocol_rerun/label_standardized/<cancer>/features_with_label.parquet`
- labeled schema audit 재실행 결과 4개 암종 모두 통과:
  - `step3_5_allowed = true`
  - `label_direction_status = CONFIRMED`
  - 결과 경로: `results/20260424_multicancer_stad_protocol_rerun/schema_audit_labeled/`
- Step 3.5 FS-A baseline 생성 및 산출물 감사(output audit) 4개 암종 모두 통과:
  - FS-A 출력: `results/20260424_multicancer_stad_protocol_rerun/step3_5_fs/fs_a_stad_baseline/<cancer>/features_slim.parquet`
  - FS-A 감사: `results/20260424_multicancer_stad_protocol_rerun/step3_5_fs/fs_a_stad_baseline/audit/`
- Step 3.6 scaffold metadata 생성 완료:
  - 공통: `results/20260424_multicancer_stad_protocol_rerun/step3_6_scaffold_metadata/drug_scaffold_map.parquet`
  - 암종별: `results/20260424_multicancer_stad_protocol_rerun/step3_6_scaffold_metadata/<cancer>/features_slim_with_scaffold.parquet`
  - scaffold 커버리지: `295/295` drugs
- Step 4-0 입력 QC 통과:
  - 결과: `results/20260424_multicancer_stad_protocol_rerun/step4_0_input_qc/`
  - `groupcv`, `scaffoldcv`, `unseen_drug` 포함 split 가능성 확인 완료
- Step 4 scaffold-enabled preflight 통과:
  - 설정: `step4_model_run_config_fs_a.yaml`
  - 검증: `step4_input_validation_summary.csv`, `step4_input_validation_summary.json`
  - 리포트: `step4_preflight_report.md`
  - 상태: `holdout/cv/groupcv/scaffoldcv/unseen_drug` 모두 4개 암종 feasible
- Step 4 feature-track-aware(2A/2B/2C) 보강 완료:
  - `2A_numeric`(기존): 4개 암종 `READY`
  - `2B_numeric_smiles` 입력 생성 완료: `results/20260424_multicancer_stad_protocol_rerun/step4_feature_tracks/built_inputs/2B_numeric_smiles/<cancer>/features_2b_numeric_smiles.parquet`
  - `2C_numeric_smiles_context` 입력 생성 완료: `results/20260424_multicancer_stad_protocol_rerun/step4_feature_tracks/built_inputs/2C_numeric_smiles_context/<cancer>/features_2c_numeric_smiles_context.parquet`
  - track-aware preflight 결과: 4개 암종 x 3 track 모두 `READY`, `BLOCKED = 0`
  - 관련 리포트: `results/20260424_multicancer_stad_protocol_rerun/step4_feature_tracks/built_inputs/feature_track_build_report.md`
- Step 4-1 ML audit(2026-04-25) 완료:
  - expected grid: `360`, completed: `320`, missing: `40`
  - 누락 분류: `optional ElasticNet 2B/2C baseline` (critical 아님)
  - leakage violation: `0`
  - profile 분포: `existing_result=248`, `light_resume=72`
  - feature cap(`variance_top_k`, `max_model_features=2000`) 적용 행: `72` (`light_resume` 전량)
  - CatBoost reference coverage: `4암종 x 3track x 5eval = 60/60` 통과
  - 감사 리포트: `results/20260424_multicancer_stad_protocol_rerun/step4_models/fs_a_stad_baseline/ml_step4_1/audit/`
- Step 4-2 DL 7모델 full expansion(2026-04-25) 완료:
  - DL 계획/실행 범위: `4암종 x 3track x 7 DL models x 5 eval = 420`
  - DL 완료: `420/420`
  - 상태 표기: `DL full complete`
- Step 4-3 Graph 2모델 full expansion(2026-04-25) partial:
  - Graph 계획 범위: `4암종 x 3track x 2 graph models x 5 eval = 120`
  - Graph 완료: `95/120`
  - Graph 누락: `25` (LUAD only)
  - LUAD 누락 25개 resume 시도 결과: `0/25` 완료, `25/25` 미완료(재시도 없이 중단)
  - first blocked: `luad / 2A_numeric / GAT / holdout`
  - 신규 `error.log`: `0`, fatal traceback: `없음`
  - 운영 해석: 코드 예외보다는 LUAD 대용량 + GAT 계산 병목/hang 가능성이 높음
  - 필수 caveat: `Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations.`
- Step 4 통합 audit(2026-04-26) 완료:
  - 통합 리포트: `results/20260424_multicancer_stad_protocol_rerun/step4_models/fs_a_stad_baseline/integrated_step4_audit/integrated_step4_audit_report.md`
  - 모달리티 상태:
    - ML: `320/360` (`near-full`, ElasticNet 2B/2C optional missing 40)
    - DL: `420/420` (`full`)
    - Graph: `95/120` (`partial-full`)
  - strict leakage violation: `0`
  - Step5 readiness: `ready_with_caveat` → **Step5 ensemble 실행·감사·리뷰 완료(2026-04-26)**
- Step 5 앙상블 실행(동일 `ready_with_caveat` 전제) 완료:
  - 산출 루트: `results/20260424_multicancer_stad_protocol_rerun/step5_ensemble/`
  - 앙상블 메서드: `simple_mean`, `rank_mean`, `robust_weighted`
  - Step6 handoff 권고(리뷰 합의): 1차 `rank_mean`, 2차 `robust_weighted`, 백업 `simple_mean`
  - 예측 행: `1,505,658` / 메트릭 조합 행: `180` / combo 오류: `0`
  - 조인 키: `sample_id`, `canonical_drug_id`를 **문자열로 정규화** 후 병합(dtype 불일치 방지)
  - missing-aware: 누락 모달리티 조합 `10`개, LUAD graph-missing 플래그 조합 `10`개
  - 감사: `step5_ensemble/audit/` ( `step5_ensemble_report.md` 등)
  - 해석 보고: `step5_ensemble/review/step5_result_review_report.md`
  - 전역 mean 비교(감사 요약): `rank_mean` Spearman·NDCG@30이 상대적으로 우수, `robust_weighted`는 RMSE/MAE가 상대적으로 낮음(해석 시 평가축에 따라 1·2차 선택)
  - Step6 진입: 외부검증/ADMET 전 **내부 앙상블 후보**로서 결과 전달; LUAD Graph partial caveat는 Step6에도 유지

게이트 판단:
- Step 4·5 실행·감사는 완료되었고, 다음 단계는 **Step6 외부검증 정책·범위 확정(선행: Step5 shortlist·caveat 리뷰)**이다.
- 현재 권고 실행선: `ML(near-full) + DL(full) + Graph(partial)` + Step5 `rank_mean` 중심 통합 해석.
- 금지 범위 유지: 무승인 추가학습, 임의 재시도, 외부검증/ADMET 선실행 금지.

---

## 1) 목적

본 문서는 다음을 만족하는 단일 재현 프로토콜을 정의한다.
- STAD 파이프라인 구조를 기준 템플릿으로 재사용
- 데이터/외부검증 소스는 암종별 실제 소스로 치환
- 단일 모델 계열(`ML`, `DL`, `Graph`) 전체 실행
- 최종 약물 추천은 고정 3계열 앙상블(`ML + DL + Graph`) 사용

---

## 2) 공통 원칙

- 단계 순서와 결과 패키징은 STAD 코드 골격을 기준으로 맞춘다.
- 입력 데이터는 암종별 raw/cohort/external validation 소스로 교체한다.
- 앙상블 전에 `ML`, `DL`, `Graph` 단일 모델 계열을 모두 실행한다.
- 최종 앙상블은 3계열(`ML`, `DL`, `Graph`) 구조를 유지한다.
- ML component는 고정 모델이 아니라 all eligible ML models의 robust ranking으로 선정한다.
- ML 후보군:
  - `CatBoost`, `XGBoost`, `LightGBM`, `RandomForest`, `ExtraTrees`, `ElasticNet`(where available)
- 누락된 optional baseline(ElasticNet 2B/2C)은 해당 실행선 ranking에서 제외하고, repair 후 재포함 가능하다.
- DL/Graph component는 계열 내 검증 성능과 일반화 지표 기반으로 선정한다.
- 실행 산출물은 버전 네이밍으로 완전 분리한다:
  - 재실행 폴더: `rerun_<YYYYMMDD>_<disease>_vNN`
  - 아카이브 태그: `<YYYYMMDD>_<disease>_vNN`

---

## 3) 암종 설정 표

| Cancer | 로컬 워크스페이스 기준 | Raw 데이터 계열 | 코호트 / 라벨 축 | 외부 검증 (Step 6) | 서브타입 축 (Step 7) | 출력 prefix |
|---|---|---|---|---|---|---|
| BRCA | `20260415_preproject_protocol_choi` (유방암 계열) | BRCA 전용 raw/mirror | BRCA 코호트 라벨(샘플-약물 반응) | PRISM, ClinicalTrials(BRCA), COSMIC(BRCA), CPTAC-BRCA, GEO(BRCA) | HR/HER2/ER-PR (가능 범위) | `brca_` |
| LUAD | `20260416_new_pre_project_biso_Lung` | 폐암 전용 raw | 프로젝트 정의 기준 LUAD/LUSC 범위 | PRISM, ClinicalTrials(Lung), COSMIC(Lung), CPTAC-Lung, GEO(Lung) | LUAD/LUSC 또는 흡연 관련 층화(가능 범위) | `lung_` |
| CRC | `20260420_new_pre_project_biso_Colon` | 대장암/CRC raw | COAD/READ 라벨 | PRISM(CRC), ClinicalTrials(CRC), COSMIC-CRC, CPTAC-CRC, GEO CRC 코호트 | COAD/READ, MSI (핵심) | `colon_` 또는 `crc_` |
| STAD | `20260421_new_pre_project_biso_STAD` | STAD raw | TCGA-STAD 라벨 | PRISM, ClinicalTrials(STAD), COSMIC(STAD), CPTAC-STAD, GEO(STAD) | MSI-H/MSS 및 사용 가능한 STAD subtype 메타데이터 | `stad_` |

참고:
- 특정 암종에서 소스가 없으면 missing으로 기록하고, 문서화된 fallback 규칙(15장)으로 진행한다.
- BRCA는 현재 BRCA 대응 프로젝트 계약(`choi` 계열)을 따른다.

---

## 3A) 라벨 표준화 규칙

BRCA/LUAD/CRC가 Step 3.5에 진입하기 전 반드시 확인해야 한다.

- 라벨 후보 컬럼 탐지:
  - `pIC50`, `pic50`, `IC50`, `ic50`, `AUC`, `auc`, `response_score`, `sensitivity_score`.
- 방향성은 자동 추정하지 않는다.
- 라벨 방향성 상태는 다음 중 하나로 기록한다:
  - `HIGHER_IS_MORE_SENSITIVE`,
  - `LOWER_IS_MORE_SENSITIVE`,
  - `NEEDS_CONFIRMATION`.
- 방향성이 `NEEDS_CONFIRMATION`이면 Step 3.5 진입을 차단한다.
- 라벨 단위/방향성 정합 규칙:
  - 필요 시 FS 전 단계에서 암종 공통 학습 타깃으로 변환(`label_normalized`)
  - 추적성을 위해 원본 라벨 컬럼은 반드시 보존
- 실행 단위 라벨 계약 파일 저장:
  - `results/.../schema_audit/label_standardization_contract.json`

---

## 3B) FE 필수 스키마 및 Fail-Fast 조건

아래 점검을 통과해야 Step 3.5 시작이 가능하다.

필수 컬럼:
- `sample_id`
- `canonical_drug_id`
- at least one label candidate column

필수 무결성 점검:
- no missing input file (`features.parquet`) per cancer
- duplicate rows on (`sample_id`, `canonical_drug_id`) must be zero
- feature columns are identifiable (numeric feature candidates available)
- global and per-feature missing rate report is available
- unique sample/drug counts are sufficient for Step 4 evaluation design
- STAD vs target common feature ratio is reported

Fail-fast 조건 (Step 3.5 차단):
- missing `features.parquet`
- missing mandatory columns
- unresolved label direction (`NEEDS_CONFIRMATION`)
- no usable numeric feature columns
- duplicate key rows remain unresolved
- GroupCV infeasible due to insufficient unique drugs

필수 감사 산출물:
- `fe_schema_audit_summary.csv`
- `fe_schema_audit_summary.json`
- `stad_schema_audit.json`, `brca_schema_audit.json`, `luad_schema_audit.json`, `crc_schema_audit.json`
- `protocol_deviation_log.md`

---

## 3C) FS-B 누수(Leakage) 방지 SOP

FS-B(지도형/개선형 FS)는 누수 방지 조건을 만족할 때만 허용한다.

원칙:
- FS-A (STAD baseline): unsupervised filters only (variance/correlation), same thresholds across cancers.
- FS-B (improved): supervised signals allowed, but only inside training folds.

누수 방지 규칙:
- Never run supervised feature ranking on full dataset before GroupCV split.
- For each CV fold:
  - fit feature selector on training fold only,
  - apply selected feature list to validation fold,
  - aggregate fold-level performance.
- Keep fold-wise selected feature logs for reproducibility.
- Compare FS-B against FS-A using the same split protocol and seed policy.

필수 FS-B 산출물:
- `selected_features.csv`
- `dropped_features.csv`
- `fs_summary.json`
- `fs_config.yaml`
- fold-level feature selection logs (per model/eval mode where applicable)

---

## 4) Step 0-1 데이터 매핑 규칙

- 코드 진입점은 암종 워크스페이스를 유지하고 데이터 root만 치환한다.
- 실행 전 암종별 매핑을 확정한다:
  - raw S3/local source path,
  - curated mirror path,
  - required cohort files,
  - required LINCS source mode.
- Step 2 전 필수 확인:
  - required raw directories exist,
  - required cohort label file exists,
  - no writes to read-only raw mirrors.
- 실행 단위 매핑 매니페스트 저장:
  - `reports/step0_1_mapping_manifest.json`

---

## 5) Step 2 전처리 / 조인 규칙

본 단계는 조용한 불일치(silent mismatch) 위험이 가장 높은 구간이다.

- 키 정규화는 반드시 일관되게 수행:
  - sample id,
  - cell line id/name,
  - drug id (`canonical_drug_id`),
  - gene symbol mapping where needed.
- 암종별 relabel 로직은 허용하되 반드시 명시:
  - Example: STAD depmap relabeling (`labels sample_id` vs depmap naming mismatch).
- Step 2 필수 QC 산출물:
  - integrated qc report,
  - join mismatch report,
  - relabel/remap report if remapping is performed.
- 중단 조건:
  - major join collapse,
  - unresolved key mapping,
  - unexpectedly high unmatched label rate.

---

## 6) Step 3 피처 엔지니어링(FE)

- FE는 암종별 전처리 완료 테이블만 사용한다.
- 재실행 간 비교 가능하도록 FE 설정을 고정한다.
- 필수 산출물:
  - feature matrix parquet,
  - pair feature parquet,
  - FE manifest report.
- AWS Batch/Nextflow를 쓰는 경우 work dir 및 컨테이너/프로파일 설정을 로그에 고정 기록한다.

---

## 7) Step 3.5 Feature Selection

- 입력은 동일 실행 라인의 Step 3 FE 산출물을 사용한다.
- 본 runline에서는 라벨 표준화 이후 `features_with_label.parquet`를 사용한다.
- threshold(저분산/고상관)는 버전과 함께 명시한다.
- 필수 산출물:
  - `features_slim.parquet`,
  - selection log JSON,
  - selected columns metadata.
- 본 단계는 반복 개선이 발생하는 구간이다:
  - 기존 버전 산출물을 보존한 상태에서 threshold를 조정해 재실행한다.
- 권장 이중 트랙:
  - FS-A: STAD 기준선 필터 스택(재현성 기준)
  - FS-B: fold-safe 누수 방지 조건 하의 개선형 지도 FS
- 본 실행선 최신 상태:
  - FS-A 완료 + output audit 통과
  - Step 3.6 scaffold metadata(`canonical_smiles`, `scaffold_smiles`, `scaffold_id`) 생성 완료
  - scaffold 관련 컬럼은 split metadata 전용으로 사용하며 모델 feature matrix에서는 제외

Step 3 -> Step 3.5 즉시 진입 가능 체크리스트(5항):
- [ ] Step 3 산출물 파일이 존재하고(`features.parquet` 또는 runline 기준 `features_with_label.parquet`) 읽기 가능하다.
- [ ] 필수 키/라벨 컬럼(`sample_id`, `canonical_drug_id`, `sensitivity_score` 또는 표준화 대상)이 존재한다.
- [ ] (`sample_id`, `canonical_drug_id`) 중복 키가 0건이다.
- [ ] 타깃 결측률이 0이고, FS 입력으로 사용할 numeric feature 후보가 존재한다.
- [ ] 최신 schema audit에서 fail-fast 사유가 해소되어 `step3_5_allowed = true`다.

---

## 8) Step 4 모델 실행

- 단일 모델 계열을 모두 실행:
  - ML all candidates,
  - DL all candidates,
  - Graph candidates.
- 평가 모드는 정책에 맞게 고정:
  - `holdout`, `cv`, `groupcv`, `scaffoldcv`, `unseen_drug`
- Step 4 실행 전 preflight 필수:
  - `validate_step4_inputs.py`에서 4개 암종 split feasible 여부 확인
  - `scaffold_id` 존재/결측률/고유 scaffold 수/폴드 분배 가능성 점검
  - `canonical_smiles`, `scaffold_smiles`, `scaffold_id`는 모델 입력 피처에서 제외(누수 방지)
- Step 4 입력은 feature track 단위로 운영:
  - `2A_numeric`: FS-A 기반 기본 입력
  - `2B_numeric_smiles`: 2A + `drug_chem_features` 증분 입력
  - `2C_numeric_smiles_context`: 2B + target/LINCS/pathway context 증분 입력
- track 공통 규칙:
  - raw SMILES string은 모델 feature로 사용 금지
  - `scaffold_id`는 split metadata 전용
  - label 계열 및 meta/split 컬럼은 모델 feature matrix에서 제외
- 암종별 실행 버전 태그 하위로 결과를 저장한다.
- 필수 산출물:
  - family-level JSON metrics,
  - OOF prediction bundles (for `groupcv`),
  - run metadata JSON.

---

## 9) Step 5 앙상블 선정 규칙

최종 추천은 3계열(`ML + DL + Graph`) 앙상블에서 산출한다.

- ML component:
  - CatBoost는 초기 reference ML candidate로 추적한다.
  - 최종 ML 후보는 all eligible ML models에서 robust ranking으로 선정한다.
  - 암종별/트랙별로 best ML model이 달라질 수 있다.
- DL component:
  - phase별 일반화 성능(`groupcv`, `scaffoldcv`, `unseen_drug`)과 안정성 지표로 선정
- Graph component:
  - 동일한 일반화/안정성 기준으로 선정
  - LUAD는 Graph partial 상태를 강제 caveat로 표시

실행·보고에 포함할 앙상블 메서드(본 러닝라인):
- `simple_mean`, `rank_mean`, `robust_weighted` (grid-search blend는 본 러닝라인 Step5 범위 밖)
- Step6 1차 전달 후보(리뷰 기준): `rank_mean` (안정성·일반화 축과의 정합)

필수 산출물:
- ensemble predictions/metrics, component weights, modality coverage, audit CSV/JSON, `step5_ensemble_run_config.json` (조인 키 정규화 기록 포함)

데이터 병합 규칙(Step5):
- 예측 병합 전 `sample_id`·`canonical_drug_id`는 반드시 동일한 문자열 규칙(`str` + strip)으로 정규화한다.

추천 선택 정책:
- choose the protocol-approved blend variant,
- ML 후보 선정 시 `groupcv/scaffoldcv/unseen_drug` 중심 robust ranking 적용
- overfit penalty 반영:
  - `spearman_gap > 0.3` warning, `> 0.5` severe
  - `fold_std > 0.05` warning, `> 0.1` severe
- leakage violation(약물/스캐폴드 overlap) 발생 모델은 제외
- export top drug list with stable schema for Step 6/7.
- Step5 산출/보고서에는 아래 문구를 반드시 포함:
  - `Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations.`
- 모델 고정 슬롯(CatBoost 고정 등)은 금지하며, 최종 ML/DL/Graph 후보는 all-model robust ranking 결과를 따른다.

---

## 10) Step 6 외부 검증

- 암종과 일치하는 외부 근거 소스만 사용한다.
- 각 소스는 다음 정보를 산출해야 한다:
  - per-drug evidence score,
  - coverage stats,
  - missing-data flags.
- 외부 근거를 통합하여 단일 종합 결과 산출물을 만든다.
- 일부 소스가 비어도 15장 fallback 정책으로 가중 통합하고 사유를 기록한다.

---

## 11) Step 7 ADMET / AlphaFold / 서브타입 필터

- 입력: Step 5 추천 후보 + Step 6 근거 컨텍스트
- 수행 내용:
  - ADMET filtering/scoring,
  - structural support (AlphaFold or equivalent),
  - subtype-aware interpretation.
- 필수 산출물:
  - final top candidate table,
  - stage/priority summary,
  - subtype context report.

---

## 12) Step 8 KG / Neo4j

- 암종별 KG JSON을 생성한다.
- 로컬 인터랙티브 HTML 뷰어를 생성한다.
- 선택적으로 Neo4j 적재를 수행한다(환경변수 자격증명만 사용, 비밀정보 커밋 금지).
- 필수 산출물:
  - KG JSON,
  - viewer HTML,
  - Neo4j load summary (`applied` or `skipped` with reason).

---

## 13) Step 9 LLM 설명 생성 (Local / AWS)

- 구조화 산출물을 기반으로 약물별 설명을 생성한다.
- 지원 모드:
  - local LLM runtime,
  - cloud/AWS mode (if configured).
- 모델 런타임이 없을 때:
  - produce dry-run/placeholder schema output,
  - keep pipeline continuity for dashboard and QA.

---

## 14) 산출물 체크리스트

암종별 실행 단위(`\<YYYYMMDD>_<disease>_vNN`) 기준:

- Step 0-1 mapping manifest exists.
- Step 2 integrated QC and join diagnostics exist.
- Step 3 FE outputs exist.
- Step 3.5 `features_slim.parquet` exists.
- Step 3.6 `features_slim_with_scaffold.parquet` 및 `drug_scaffold_map.parquet` exists.
- Step 4 feature track 입력(`2B`, `2C`) built parquet 및 build report exists.
- Step 4-0 input QC 및 Step 4 preflight 결과 exists.
- Step 4 ML/DL/Graph result JSON and OOF artifacts exist.
- Step 5 ensemble summary exists (다중 메서드 + audit; 1차 `rank_mean` 권고).
- Step 6 comprehensive external validation exists.
- Step 7 final candidate report exists.
- Step 8 KG JSON/HTML and Neo4j summary exist.
- Step 9 explanations JSON/report exists.
- 아카이브 완료 경로:
  - `rerun_<date>_<disease>_vNN/results_archive/<date>_<disease>_vNN/`

---

## 15) 실패 대응(Fallback) 규칙

- 데이터 매핑 불일치(Step 0-2):
  - 실행 중단 후 키 정규화 수정. 결과가 게시되지 않았다면 동일 버전 재실행, 게시됐으면 버전 증가.
- FE 실패:
  - 상위 입력/스키마를 검증하고 타 암종 프록시 데이터로 우회하지 않는다.
- OOF 산출물 누락:
  - Step 5 전에 해당 모델 계열을 재실행한다.
- 외부 소스 미가용:
  - 남은 소스로 가중 fallback 통합하고 요약에 기록한다.
- LLM 런타임 미가용:
  - dry mode로 실행하고 결정론적 구조 산출물을 유지한다.
- 암종별 수동 패치 발생:
  - `reports/change_note_<date>_<disease>_vNN.md`에 반드시 기록한다.

---

## 실행 네이밍 규칙 (운영)

- 재실행 워크스페이스 생성:
  - `./run_all_reruns.sh --date-prefix <YYYYMMDD> --auto-version`
- 최신 버전 아카이브:
  - `./archive_run.sh --date-prefix <YYYYMMDD> --auto-version`

이 규칙은 동일 날짜 반복 실행에서도 산출물 충돌 없이 재현성을 보장한다.
