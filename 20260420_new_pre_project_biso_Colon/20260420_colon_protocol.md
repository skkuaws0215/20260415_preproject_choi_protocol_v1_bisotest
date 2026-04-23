# Colorectal (COAD+READ) pre-project protocol

- **질병:** 대장암 (Colorectal Cancer, COAD+READ)
- **옵션:** B (중간 확장)
- **작업 시작일:** 2026-04-20
- **최종 업데이트:** 2026-04-24
- **문서 버전:** v1.5

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

- **Step 6+ (외부 검증): ✅ 완료**

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

*문서명: `20260420_colon_protocol.md` (v1.5, 최종 업데이트 2026-04-24).*

---

## Step 6: 외부 검증 (5대 소스)

### 6-1. 약물 랭킹
- 스크립트: `scripts/step6_prepare_top_drugs.py`
- 앙상블 OOF 예측 → drug별 평균 → Top 30 추출
- 중복 제거: DRUG_NAME 기준 295→286 (9 duplicates)
- 출력: `results/colon_top30_drugs_ensemble.csv`

### 6-2. PRISM 검증
- 스크립트: `scripts/step6_2_prism_validation.py`
- 데이터: `curated_data/validation/prism/` (S3 → 로컬)
- 결과: 22/30 (73.3%) — Lung 67.4% 대비 우수

### 6-3. ClinicalTrials.gov 검증
- 스크립트: `scripts/step6_3_clinical_trials_validation.py`
- 데이터: `curated_data/validation/clinicaltrials/` (API v2 수집, 6,298 studies)
- 결과: 14/30 (46.7%), Phase II+ 85.7%

### 6-4. COSMIC 검증
- 스크립트: `scripts/step6_4_cosmic_validation.py`
- 데이터: `curated_data/validation/cosmic/*.tar`
- 결과: 10/30 (33.3%) — Cancer Gene Census 타겟 매칭

### 6-5. CPTAC 검증
- 스크립트: `scripts/step6_5_cptac_validation.py`
- 데이터: `curated_data/cbioportal/coad_cptac_2019/data_mrna_seq_v2_rsem.txt`
- 결과: 14/30 (46.7%), 매칭 타겟 100% 발현

### 6-6. GEO GSE39582 검증
- 스크립트: `scripts/step6_geo_validation.py`
- 데이터: `curated_data/geo/GSE39582/matrix/GSE39582_series_matrix.txt.gz`
- Probe-Gene 매핑: `curated_data/geo/GSE39582/GPL570_probe_to_gene.json` (GPL570 SOFT → 45,782 probes → 22,878 genes)
- 코호트: 585명 CRC 환자 (Marisa et al. 2013)
- 결과: 14/30 (46.7%)

### 6-7. 종합 스코어링
- 스크립트: `scripts/step6_6_comprehensive_scoring.py`
- 5대 소스 통합, 약물별 0~5 점수, 신뢰도 등급
- Very High (5/5): Temsirolimus, Camptothecin, Irinotecan, Topotecan
- 평균 검증 통과: 2.47/5
- 출력: `results/colon_comprehensive_drug_scores.csv`

---

## Step 7: ADMET Gate (초이 프로토콜)

### 7-1. ADMET 필터링
- 스크립트: `scripts/step7_1_admet_filtering.py`
- 방법: 초이 프로토콜 원본 방식
  - 22개 TDC ADMET assay (Toxicity/Absorption/Distribution/Metabolism/Excretion/Properties)
  - Morgan Fingerprint (radius=2, 2048 bits) + Tanimoto similarity ≥ 0.70
  - Safety Score: 기본 5.0 + assay별 가중치 기반 가감
  - 판정: PASS (≥6.0) / WARNING (≥4.0) / FAIL (<4.0)
- RDKit: Lipinski, PAINS, MW, LogP, TPSA, RotatableBonds
- 데이터: `curated_data/admet/tdc_admet_group/admet_group/` (22 폴더)
- 결과: PASS 5, WARNING 23, FAIL 2, Avg Safety 5.13

### 7-2. Top 15 선정
- 스크립트: `scripts/step7_2_select_top15.py`
- ADMET PASS + WARNING 중 예측 IC50 순 Top 15
- 카테고리 분류:
  - FDA_APPROVED_CRC: 2 (Topotecan, Irinotecan)
  - REPURPOSING_CANDIDATE: 3 (Temsirolimus, Rapamycin, AZD6482)
  - CLINICAL_TRIAL: 3
  - RESEARCH_PHASE: 7
- 출력: `results/colon_final_top15.csv`, `results/colon_final_top15_summary.json`

### 22개 ADMET Assay 목록

| Category | Assay | Weight | Good Value |
|----------|-------|--------|------------|
| Toxicity | Ames Mutagenicity | -2.0 | 0 |
| Toxicity | DILI (Liver Injury) | -2.0 | 0 |
| Toxicity | hERG Cardiotoxicity | -1.5 | 0 |
| Toxicity | Acute Toxicity (LD50) | 1.0 | high |
| Absorption | Oral Bioavailability | 1.0 | 1 |
| Absorption | Caco-2 Permeability | 0.5 | high |
| Absorption | HIA (Intestinal) | 0.5 | 1 |
| Absorption | P-gp Inhibitor | -0.5 | 0 |
| Distribution | BBB Penetration | 0.5 | neutral |
| Distribution | Plasma Protein Binding | 0.3 | low |
| Distribution | Volume of Distribution | 0.3 | neutral |
| Metabolism | CYP2C9 Inhibitor | -0.5 | 0 |
| Metabolism | CYP2D6 Inhibitor | -0.5 | 0 |
| Metabolism | CYP3A4 Inhibitor | -0.5 | 0 |
| Metabolism | CYP2C9 Substrate | 0.2 | neutral |
| Metabolism | CYP2D6 Substrate | 0.2 | neutral |
| Metabolism | CYP3A4 Substrate | 0.2 | neutral |
| Excretion | Hepatocyte Clearance | 0.5 | neutral |
| Excretion | Microsome Clearance | 0.5 | neutral |
| Excretion | Half-Life | 0.5 | high |
| Properties | Lipophilicity (logD) | 0.3 | neutral |
| Properties | Aqueous Solubility | 0.5 | high |

---

## Step 7.5: AlphaFold 구조 검증

- 스크립트: `scripts/step7_5_alphafold_validation.py`
- 방법:
  1. Top 15 약물의 타겟 유전자 → UniProt ID 매핑 (수동 + API)
  2. AlphaFold DB API 에서 PDB 구조 다운로드
  3. pLDDT (B-factor) 분석 → 구조 신뢰도 확인
  4. Binding pocket 탐지 (BioPython NeighborSearch + scipy ConvexHull)
  5. 3Dmol.js 기반 3D 뷰어 HTML 생성 (포켓 gold stick 표시)
- 결과:
  - 16 타겟 → 14 UniProt 매핑 → 14/14 구조 다운로드
  - Avg pLDDT: 82.31, High confidence (≥70): 14/14
  - Binding pocket: 14/14 탐지 성공
  - 최대 포켓: MTOR 9 res / 192 ų, FLT3 9 res / 173 ų
- 출력: `results/alphafold_validation/`

---

## Step 7.6: COAD vs READ 분리 분석

- 스크립트: `scripts/step7_6_coad_read_analysis.py`
- 방법:
  - TCGA coadread_tcga_pan_can_atlas_2018 mRNA (592 samples)
  - subtype metadata (COAD 378, READ 155) 로 환자 분류
  - Top 15 타겟 유전자의 COAD vs READ 발현 비교 (Welch t-test)
  - 효과 크기 (Cohen's d) + 약물별 추천
- 결과:
  - 9/16 타겟 유전자 분석 완료
  - 유의 차이: JAK2 (COAD_higher, p=0.008)
  - Lestaurtinib: COAD_preferred (JAK2 억제제)
  - 나머지 6개 약물: Both (COAD/READ 모두 적용 가능)
  - 8개 약물: Unknown (타겟 발현 데이터 없음)
- 출력: `results/colon_coad_read_analysis.json`, `results/colon_coad_read_drug_recommendations.csv`

---

## Step 8: Neo4j Knowledge Graph

- 스크립트: `scripts/step8_neo4j_load.py`, `scripts/step8_generate_kg_viewer.py`
- 인프라:
  - Neo4j Aura: `neo4j+s://108928fe.databases.neo4j.io` (biso-kg, AuraDB Free)
  - PostgreSQL: `colon_drugdb` (로컬, 4 테이블)
- 적재 내용:
  - Disease 노드: Colorectal Cancer (COAD+READ) — 기존 BRCA, Lung 에 추가
  - CellLine: 35개 → Disease 연결
  - Drug → Disease: PREDICTED_FOR 21, TREATS 13 (Top 15)
  - Target → Disease: ASSOCIATED_WITH 44
  - AlphaFold 속성: pLDDT, pocket_size, pocket_volume
  - COAD/READ 추천: 관계 속성에 반영
- Cross-Disease 연결:
  - 3개 질병 간 공유 약물: Vinorelbine, Rapamycin, Topotecan 등
  - Lung Target ASSOCIATED_WITH: 14 추가
- 인터랙티브 뷰어: `results/knowledge_graph_viewer.html` (순수 Canvas JS, force-directed)
- 그래프 현황: 30,589 nodes, 113,615+ relationships

---

## Step 9: LLM 약물 재창출 근거 생성

- 스크립트: `scripts/step9_llm_explanation.py`
- LLM: Ollama llama3.1 (4.9GB, 로컬)
- 방법:
  1. Top 15 약물 각각에 대해 전체 파이프라인 근거 수집
  2. 프롬프트 구성: 예측 모델 + 5대 검증 + ADMET + AlphaFold + COAD/READ + 카테고리
  3. Ollama 로 한국어 Explanation 생성 (약물당 ~40초, 총 ~11분)
- 포함 근거:
  - 예측 IC50 + 앙상블 성능
  - 외부 검증 5개 소스 통과 여부
  - ADMET 22 assay Safety Score + verdict
  - AlphaFold pLDDT + binding pocket
  - COAD vs READ 적합성
  - 카테고리 (FDA_APPROVED_CRC / REPURPOSING / CLINICAL_TRIAL / RESEARCH)
- 출력: `results/colon_drug_explanations.json`, `results/colon_drug_explanations_report.md`

---

## 재현 실험 체크리스트

### 환경

| 항목 | 버전/설정 |
|------|----------|
| Python | 3.12.7 |
| RDKit | ✅ (Lipinski, PAINS, Morgan FP, 3D) |
| BioPython | ✅ (PDB 파싱, NeighborSearch) |
| scipy | ✅ (ConvexHull) |
| neo4j driver | 6.1.0 |
| Ollama | 0.21.0 + llama3.1:latest |
| Neo4j Aura | biso-kg (AuraDB Free) |
| PostgreSQL | 16 (brew) |
| Streamlit | 대시보드 |

### 실행 순서

```
# Step 6: 외부 검증
python3 scripts/step6_prepare_top_drugs.py
python3 scripts/step6_2_prism_validation.py
python3 scripts/step6_3_clinical_trials_validation.py
python3 scripts/step6_4_cosmic_validation.py
python3 scripts/step6_5_cptac_validation.py
python3 scripts/step6_geo_validation.py
python3 scripts/step6_6_comprehensive_scoring.py

# Step 7: ADMET
python3 scripts/step7_1_admet_filtering.py
python3 scripts/step7_2_select_top15.py

# Step 7.5: AlphaFold
python3 scripts/step7_5_alphafold_validation.py

# Step 7.6: COAD/READ
python3 scripts/step7_6_coad_read_analysis.py

# Step 8: Neo4j
python3 scripts/step8_neo4j_load.py
python3 scripts/step8_generate_kg_viewer.py

# Step 9: LLM
python3 scripts/step9_llm_explanation.py

# 대시보드
streamlit run dashboard/app.py
```

### 필수 데이터 (curated_data/)

```
curated_data/
├── admet/tdc_admet_group/admet_group/  (22 assay 폴더)
├── validation/prism/                    (PRISM dose-response)
├── validation/clinicaltrials/           (ClinicalTrials API 결과)
├── validation/cosmic/                   (COSMIC tar 파일)
├── cbioportal/coad_cptac_2019/          (CPTAC mRNA + clinical)
├── cbioportal/coadread_tcga_pan_can_atlas_2018/  (TCGA mRNA 592명)
├── geo/GSE39582/                        (GEO matrix + GPL570 annotation)
└── gdsc/Cell_Lines_Details.xlsx         (GDSC cell line 정보)
```

## 📝 변경 이력

- **v1.5 (2026-04-24)**:
  - Step 6: 5대 외부 검증 완료 (PRISM, CT, COSMIC, CPTAC, GEO)
  - Step 7: ADMET Gate (초이 22 assay + Tanimoto) + Top 15 선정
  - Step 7.5: AlphaFold 구조 검증 + binding pocket 탐지
  - Step 7.6: COAD vs READ 분리 분석 (TCGA 531명)
  - Step 8: Neo4j Knowledge Graph 적재 + 인터랙티브 뷰어
  - Step 9: LLM 약물 재창출 근거 생성 (Ollama llama3.1)
  - 대시보드: 10탭 (Step 1~9 + Comparison)
  - Pipeline Step 1~9 100% 완료

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
