# 멀티암종 실행 보고서 (최신 통합본)

- 작성일시: `2026-04-26`
- 기준 실행 루트: `results/20260424_multicancer_stad_protocol_rerun/`
- 기준 문서: `results/20260424_multicancer_stad_protocol_rerun/step4_models/fs_a_stad_baseline/integrated_step4_audit/integrated_step4_audit_report.md`

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

## 5) Step5 준비도

- integrated readiness: `ready_with_caveat`
- strict leakage violation: `0`
- caveat: LUAD Graph 25 미완료를 해석/비교에서 명시해야 함

## 6) 권고

- 단기: `ML + DL + Graph partial(95/120)` 기준으로 audit/통합 비교 진행
- 중기: LUAD Graph missing 25는 AWS Batch 또는 경량 GAT 설정으로 별도 repair
- 장기: Graph full은 로컬 단일 환경 대신 서버/AWS 병렬 실행으로 이전
