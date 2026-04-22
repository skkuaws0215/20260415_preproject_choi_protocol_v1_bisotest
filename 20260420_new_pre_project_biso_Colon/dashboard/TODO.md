# Dashboard TODO (Technical Debt & Future Work)

이 문서는 대시보드 MVP 완성 후 **통합 재진행 시점에 반영할 작업**을 기록합니다.

> **사용자 방침 (2026-04-22)**: 나중에 전체 암종(Lung/Colon/STAD)에서 동일 프로토콜로 다시 1번 재진행 예정.
> 그 시점에 아래 TODO 통합 반영.

---

## 🔧 Phase 1 파서 관련

### 1. Holdout 파서 지원 추가
- **현 상태**: `fold_results` 필드 없는 Holdout JSON 스킵됨 (파서 0개 처리)
- **영향**: 30개 Holdout 실험 누락 (ML 3 + DL 3 파일 × 모델별)
- **해결 방안**: `parse_model_result()` 에 Holdout 분기 추가
  - `fold_results` 없으면 `train`, `test`, `gap` 필드 직접 파싱
  - `val_spearman_mean` 대신 `test_spearman` 사용
  - `n_folds = 1` 로 처리
- **파일**: `dashboard/parsers/step4_modeling_parser.py`

### 2. 5-Fold CV 실험 개수 이상 확인
- **관찰**: 5-Fold CV 39 experiments 파싱됨 (기대값 45 = 15 × 3)
- **추정**: 6개 실험 빠짐 (어느 모델/Phase인지 미확인)
- **액션**: 통합 재진행 시 파일별 모델 구성 확인
- **파일**: `dashboard/parsers/step4_modeling_parser.py`

### 3. 암종 prefix 일반화
- **현 상태**: `colon_*` 파일명 패턴에 하드코딩됨 (`FILENAME_RE`)
- **해결 방안**: disease prefix 를 인자화 → `lung_*`, `colon_*`, `stad_*` 모두 지원
- **파일**: `dashboard/parsers/step4_modeling_parser.py`

---

## 📊 Phase 2-6 파서 확장

### 4. Step 2 QC 리포트 파서
- **대상 파일**: `reports/step2_1_qc_report.txt`, `step2_4_matching_report.json` ... (8개)
- **모듈**: `dashboard/parsers/step2_qc_parser.py` (신규)

### 5. Step 3 Feature Engineering 파서
- **대상**: `fe_qc/20260420_colon_fe_v1/`, `fe_qc/20260420_colon_fe_v2/`
- **모듈**: `dashboard/parsers/step3_fe_parser.py` (신규)

### 6. Step 5 앙상블 결과 파서
- **Lung 참고**: `phase3_ensemble_analysis.py` 산출물 구조
- **모듈**: `dashboard/parsers/step5_ensemble_parser.py` (신규)

### 7. Step 6 외부 검증 결과 파서
- **Lung 참고**: `step6_1_map_drug_names.py`, `step6_2_prism_validation.py`, `step6_3_clinical_trials_validation.py` 산출물
- **모듈**: `dashboard/parsers/step6_validation_parser.py` (신규)

---

## 🎨 Phase 2 UI 확장

### 8. Lung vs Colon vs STAD 비교 탭
- **현 상태**: placeholder (Tab 7)
- **해결 방안**: 각 암종에서 동일 파서로 DataFrame 생성 → 비교 뷰
- **전제**: 위 #3 (prefix 일반화) 선행 필요

### 9. 실시간 진행 상황 탭
- **아이디어**: 현재 실행 중인 스크립트 (PID, 로그 tail) 을 대시보드에서 모니터링
- **우선순위**: 낮음

---

## 🏗️ 아키텍처 개선

### 10. 파서 결과 캐싱
- **현 상태**: 대시보드 열 때마다 JSON 재파싱
- **해결 방안**: `st.cache_data` 데코레이터 추가
- **효과**: 첫 로드 후 즉시 반응

### 11. 통합 엔트리 포인트
- **현 상태**: 각 Step 파서 독립 실행
- **해결 방안**: `dashboard/parsers/__init__.py` 에 `load_all_steps()` 함수 추가

---

## 📝 기록된 환경 특성 (Cursor/Shell)

### heredoc 안 됨
- **현상**: `cat > file.py << 'EOF' ... EOF` 가 현재 셸에서 실패
- **대응**: **모든 파일 생성은 Cursor에게 위임** (Python 직접 쓰기 방식)
- **이전 사고**: 2026-04-22 대용량 파일 커밋 사고 (세션 요약 참조)

### import 경로 요구사항
- **테스트 실행**: `PYTHONPATH=. python3 -m dashboard.parsers.xxx`
- **Streamlit 실행**: `PYTHONPATH` 불필요 (자동 처리)

---

_Last updated: 2026-04-22_
