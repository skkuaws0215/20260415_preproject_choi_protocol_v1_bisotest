# Colorectal (COAD+READ) pre-project protocol

- **질병:** 대장암 (Colorectal Cancer, COAD+READ)
- **옵션:** B (중간 확장)
- **작업 시작일:** 2026-04-20
- **최종 업데이트:** 2026-04-22
- **문서 버전:** v1.4

## 경로 (수정 반영)

- **로컬**

```
/Users/skku_aws2_14/20260415_preproject_choi_protocol_v1_bisotest/
  20260415_preproject_choi_protocol_v1_bisotest/
  20260415_preproject_choi_protocol_v1_bisotest-1/
  20260420_new_pre_project_biso_Colon
```

한 줄:  
`/Users/skku_aws2_14/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest-1/20260420_new_pre_project_biso_Colon`

- **S3 원본 (읽기 전용):** `s3://say2-4team/Colon_raw/`
- **S3 작업 폴더:** `s3://say2-4team/20260408_new_pre_project_biso/20260420_new_pre_project_biso_Colon/`
- **GitHub:** `skkuaws0215/20260415_preproject_choi_protocol_v1_bisotest` — 저장소 내 `20260420_new_pre_project_biso_Colon/`

## 데이터 소스

| 소스 | 위치 / 비고 |
|------|-------------|
| GDSC2 | `Colon_raw/GDSC/GDSC2-dataset.csv` (품질 우선) |
| DepMap | `Colon_raw/depmap/CRISPRGeneEffect.csv` — wide → long **직접 변환** |
| LINCS | `curated_data/lincs/GSE92742/` 사용 (Lung 선례 일관) — `Colon_raw/LInc1000/GSE70138/` 보유하나 미사용 |
| DrugBank | `Colon_raw/drugbank/` |
| ChEMBL | `Colon_raw/chembl/` |
| 루트 Parquet 4개 | `Colon_raw/` 루트의 집약 parquet — **입력에서 배제** (원시만 사용) |

## 외부 검증

### 1차

| 검증 | 데이터 |
|------|--------|
| CPTAC-CRC | `Colon_raw/cBioPortal/coad_cptac_2019/` |
| GEO | `Colon_raw/geo/GSE39582/` |
| COSMIC-CRC | 별도 수집 — Lung의 `curated_data/validation/cosmic` 방식 준용 |
| PRISM | CRC cell — 별도 수집 |
| ClinicalTrials | CRC — 별도 수집 |

### 2차 (추가 예정)

| 항목 | 비고 |
|------|------|
| GSE17536 | `Colon_raw/geo/GSE17536/` |
| GSE17538 | **Colon_raw GEO 목록에 없음** — S3 보강 또는 대체 GSE 검토 |
| GSE17537 | Colon_raw에 **존재** (17538과 혼동 주의) |

## Subtype 태깅

- **Stratified 평가:** COAD vs READ, MSI
- **메타데이터 저장만:** RAS, BRAF, BRAF V600E (세부)
- **이번 라운드 미사용:** HER2, CMS, sidedness
- **추가 카테고리 발견:** MACR (Mucinous Adenocarcinoma, 10.3%) — `primary_site` 필드에 그대로 보존, Step 6 평가 단계에서 처리 방침 결정 예정

## 메타데이터 (cBioPortal 최소 활용)

- **`coadread_tcga_pan_can_atlas_2018`:** site / MSI / RAS / BRAF 태깅용 (최소 연동)

## Baseline에서 제외 (미사용)

- msigdb, string, opentargets, gtex

## Lung 대비 프로토콜 차이

1. **전처리 신규:** Lung은 기존 `curated_data/` 활용 가정 — Colon은 전처리 단계부터 구축.
2. **LINCS:** Colon과 Lung 모두 **GSE92742** 사용 (Colon 초기 계획 GSE70138에서 변경, sig_id prefix 검증으로 Lung 방식 따름). 자세한 경과는 `differences.md` 참조.
3. **Subtype + stratified 평가** 신규.
4. **외부 검증:** GSE39582 추가 — Lung은 CPTAC 중심.
5. **`Colon_raw/` 루트 parquet 4개 배제** — 원시 파이프라인만 사용.

## 로컬 디렉터리 스켈레톤 (참고)

`curated_data/`, `data/`, `scripts/`, `logs/`, `reports/`, `results/`  
`curated_data/{gdsc,depmap,lincs,drugbank,chembl,admet,cbioportal,geo,validation,processed}`  
`curated_data/validation/{cosmic,prism,clinicaltrials}`

- **대시보드:** `dashboard/` (Streamlit, Colon 파이프라인 전체 현황 시각화)
  - 실행: `streamlit run dashboard/app.py`
  - 상세: `dashboard/README.md` 및 `dashboard/TODO.md`

## 실행 상태 (2026-04-21 기준)

- **Step 2 (전처리) 완료** ✅
  - 7개 data/ 산출물 생성 완료
  - 통합 QC ALL PASSED (이슈 0건)
- **Step 3 (Feature Engineering) 완료** ✅
  - Nextflow on AWS Batch (run_id: `20260420_colon_fe_v2`)
  - 소요 시간: 7분 20초
  - 결과: 35 cells × 295 drugs = 9,692 pairs, 17,925 features
- **Step 3.5 (Feature Selection) 완료** ✅
  - `scripts/feature_selection.py` 독립 스크립트 (Lung 로직 100% 재현)
  - 결과: 19,998 → 5,662 features (71.7% 감축)
- **Step 4: ✅ ML/DL/Graph 전체 완료 (Drug Split + Scaffold Split, 2026-04-22)**
- **Step 4.5 (Feature Selection, 옵션): ✅ 완료 (FSimp Top 1000 결과 반영)**
- **Step 5: ✅ 앙상블 완료 (2026-04-22)**
  
### Step 5 앙상블 상세

#### 최종 선정: Tier1_2B_fsimp (GraphSAGE + CatBoost Weighted Average)

| 항목 | 값 |
|------|-----|
| **구성** | GraphSAGE FSimp 2B (w=0.8) + CatBoost FSimp 2B (w=0.2) |
| **Spearman** | **0.6010** |
| **Pearson** | 0.6417 |
| **Kendall** | 0.4268 |
| **RMSE** | 2.0890 |
| **MAE** | 1.6021 |
| **R²** | 0.4111 |

#### 선정 근거

1. **모든 지표에서 단일 모델 대비 일관된 개선** (Spearman/Pearson/RMSE/MAE/R² 5개 지표 전부)
2. **과반수 샘플(53.8%)에서 단일 GraphSAGE 보다 정확**
3. **모델 다양성 확보**: GraphSAGE ↔ CatBoost 예측 상관 0.67 (33% 독립적)
   - GNN (그래프 구조 학습) + Gradient Boosting (테이블 기반 학습) = 서로 다르게 학습, 다르게 틀림
4. DL (ResidualMLP) 은 가중치 0.0 으로 최적화에서 자동 탈락 — 기여 없음

#### 성능 진행

```
Baseline:  CatBoost 2B         0.4881
  ↓ FS (+20.2%)
FSimp:     GraphSAGE FSimp 2B  0.5914
  ↓ 앙상블 (+1.6%)
Ensemble:  Graph0.8+ML0.2      0.6010  (총 +23.1%)
```

#### 다중 지표 비교

| 지표 | GraphSAGE 단독 | 앙상블 | Δ |
|------|---------------|--------|---|
| Spearman | 0.5914 | **0.6010** | +0.0096 |
| RMSE | 2.1034 | **2.0890** | -0.0144 |
| MAE | 1.6211 | **1.6021** | -0.0190 |
| R² | 0.4030 | **0.4111** | +0.0081 |

- **Step 6+ (외부 검증): 대기**

## Step 4.5 Feature Selection (옵션)

### 트리거 조건

Step 4 완료 후 다음 중 하나 이상 해당 시 실행:
- Overfitting Ratio > 50%
- Graph Scaffold Drop > 15%
- Val Spearman 이 기대치 대비 현저히 낮음

### Colon 결과 요약

| 구분 | Drug Split | Scaffold Split | Overfit |
|------|------------|----------------|---------|
| ML | +0.0037 (소폭 개선) | -0.0030 (변화 없음) |  |
| DL | -0.0393 (악화) | +0.0094 (소폭 개선) |  |
| Graph | +0.1352 (대폭 개선) | +0.1101 (대폭 개선) |  |
| 전체 |  |  | 69.0% → 71.3% (미해결) |

상세 보고서: `COLON_STEP4_5_FS_EXPERIMENT_20260422.md`

## Step 3 Feature Engineering 결과

### 산출물 (S3 + 로컬)
- S3: `s3://say2-4team/20260408_new_pre_project_biso/20260420_new_pre_project_biso_Colon/fe_output/20260420_colon_fe_v2/`
- 로컬: `fe_qc/20260420_colon_fe_v2/`
- 주요 파일: `features/features.parquet`, `features/labels.parquet`, `pair_features/pair_features_newfe_v2.parquet`

### 데이터 규모
| 항목 | 값 |
|------|-----|
| Cell lines | 35 (COAD/READ, DepMap CRISPR 매칭) |
| Drugs | 295 |
| Drug-cell pairs | 9,692 |
| features.parquet 컬럼 | 17,925 |
| pair_features 컬럼 | 2,075 |
| LINCS features | 5개 (cosine, pearson, spearman, top50, top100) |
| 결측치 | 0 |
| 클래스 불균형 | 2.33:1 (label_binary 0:6784, 1:2908) |

## Step 3.5 Feature Selection 결과

### 산출물
- `fe_qc/20260420_colon_fe_v2/features_slim.parquet` — 모델 학습 입력
- `fe_qc/20260420_colon_fe_v2/feature_selection_log.json` — 단계별 로그
- `fe_qc/20260420_colon_fe_v2/feature_categories.json`
- `fe_qc/20260420_colon_fe_v2/final_columns.json`

### Selection 로직 (Lung 100% 재현)
| 단계 | 기준 | 대상 | Before → After | 제거 |
|------|------|------|:---:|:---:|
| 1 | variance > 0.01 | gene (CRISPR) | 17,919 → 4,637 | 13,282 |
| 2 | Pearson \|r\| > 0.95 | gene (CRISPR) | 4,637 → 4,564 | 73 |
| 3 | variance > 0.01 | morgan FP | 2,048 → 1,075 | 973 |
| 4 | Pearson \|r\| > 0.95 | morgan FP | 1,075 → 1,067 | 8 |
| - | keep_all | lincs/target/drug_desc/drug_other | 29 → 29 | 0 |
| **총** | | | **19,998 → 5,662** | **14,336** |

## 주요 이슈 및 해결 (2026-04-21)

### 1. DepMap CRISPR이 파일명(`_colon`)과 달리 Colon 필터 안 됨
- 증상: FE v1 결과에 489 cells (전 암종 혼재) 발견
- 원인: `depmap_crispr_long_colon.parquet`이 실제로는 1,150 cells (전체)
- 해결: `labels.parquet`의 35 cells 기준으로 재필터링 후 S3 재업로드

### 2. GDSC2-dataset.parquet 스키마 불일치
- 증상: `cell_line_name`, `ln_IC50` 컬럼 찾을 수 없음 (대문자만 있음)
- 원인: Colon 로컬은 원본 대문자 스키마, Lung S3는 소문자로 rename된 버전
- 해결: Lung S3 버전으로 교체 후 Colon 35 cells 필터링

### 3. Cell line naming 불일치 (핵심 발견)
- 증상: GDSC2의 46개 Colon cells 중 DepMap 매칭은 15개뿐 (32.6%)
- 원인: 표기법 차이 (`HCT116` vs `HCT-116`, `LOVO` vs `LoVo`, `SW 620` vs `SW620` 등)
- 해결: Lung 방식 정규화 (lower + 하이픈/공백/슬래시 제거) → 35개로 증가 (76.1%)

### 4. Nextflow 실행 환경 (Cursor 샌드박스 프록시)
- 증상: `curl 403`, `UnknownFormatConversionException`, 풀링 실패
- 원인: Cursor Agent 샌드박스가 동적 프록시 경유 (127.0.0.1:53116)
- 해결: macOS Terminal.app에서 직접 실행 → 정상 7분 20초 완료

### 5. Feature Selection 스크립트 부재
- 증상: Lung에 FS 결과물(`features_slim.parquet`)만 있고 스크립트 없음 (ad-hoc 실행)
- 해결: Lung 산출물(`feature_selection_log.json`, `final_columns.json`) 역추적 + `scripts/feature_selection.py` 신규 작성

---

*문서명: `20260420_colon_protocol.md` (v1.4, 최종 업데이트 2026-04-22).*

---

## 📝 변경 이력

- **v1.4 (2026-04-22)**:
  - Step 5 앙상블 상세 분석 반영
  - 최종 선정 모델: GraphSAGE(0.8) + CatBoost(0.2) = 0.6010
  - 다중 지표 (Spearman/Pearson/Kendall/RMSE/MAE/R²) 비교 추가
  - 선정 근거 4가지 명시

- **v1.3 (2026-04-22)**:
  - Step 5 앙상블 완료 반영 (Best 0.6010)
  - Step 4.5 → Step 5 진행 경과 기록

- **v1.2 (2026-04-22)**:
  - Step 4.5 Feature Selection (옵션) 섹션 추가
  - FSimp Top 1000 결과 요약 반영 (ML/DL/Graph, Drug/Scaffold)
  - 상세 보고서 링크 추가 (`COLON_STEP4_5_FS_EXPERIMENT_20260422.md`)

- **v1.1 (2026-04-22)**:
  - Step 4 상태 업데이트 (ML/DL/Graph 전체 완료)
  - 지표 #21 (Scaffold Split) Colon 달성 반영
  - 대시보드 (Streamlit) 경로/실행법 추가
  - 상세: `COLON_ADVANCED_VALIDATION_PLAN.md v1.3` 참조

- **v1.0 (2026-04-21)**:
  - 초기 버전 (Colon 프로젝트 컨텍스트, 경로, Step 2-3 반영)
