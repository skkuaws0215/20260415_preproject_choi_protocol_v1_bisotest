# Colon 파이프라인 — 프로젝트 컨텍스트 (CONTEXT)

이 문서는 Cursor·에이전트가 작업 시 참조하는 **단일 진실 소스**입니다. 사용자가 제공한 규칙·경로·단계를 반영합니다.

---

## 작업 개요

- **질병:** 대장암 (Colorectal Cancer, **COAD+READ**)
- **목표:** 약물 재창출(drug repurposing) 파이프라인 구축
- **관계:** 유방암(BRCA)·폐암(Lung) 파이프라인을 대장암으로 확장하는 작업
- **기반 프로토콜:** 저장소 루트의 `drug_repurposing_pipeline_protocol.md` **v2.3**
- **옵션:** **B** (중간 확장)

---

## 경로

| 구분 | 경로 |
|------|------|
| **로컬 베이스 (Colon 프로젝트)** | `/Users/skku_aws2_14/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest-1/20260420_new_pre_project_biso_Colon` |
| **Git 워크스페이스 루트** | `/Users/skku_aws2_14/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest-1` |
| **S3 원본 (읽기 전용)** | `s3://say2-4team/Colon_raw/` |
| **S3 작업 폴더** | `s3://say2-4team/20260408_new_pre_project_biso/20260420_new_pre_project_biso_Colon/` |
| **GitHub** | `skkuaws0215/20260415_preproject_choi_protocol_v1_bisotest` — 저장소 내 폴더 `20260420_new_pre_project_biso_Colon/` |

---

## 참조 Lung 파이프라인 (코드 재사용 기준)

- **경로:** `/Users/skku_aws2_14/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest-1/20260416_new_pre_project_biso_Lung`
- **원칙:** 프로토콜(코드)은 **Lung 원본을 그대로 재사용**하고, **데이터만 대장암(Colon)에 맞게 교체**
- **Step 2 전처리 관련 스크립트 (대표):**
  - `scripts/convert_raw_to_parquet.py` — Raw → Parquet
  - `scripts/extract_chembl_from_sqlite.py` — ChEMBL SQLite 추출
  - `scripts/aggregate_lincs_to_drug_level.py` — LINCS 약물 단위 집계
  - `scripts/main.nf` — Step 3 FE 내 `prepare_fe_inputs` 등 (Nextflow)

---

## 절대 규칙 (위반 시 즉시 중단)

1. **`curated_data/`** — **읽기 전용.** 수정·삭제 금지.
2. **`s3://say2-4team/Colon_raw/`** — 원본, **직접 수정 금지.**
3. **`Colon_raw/` 루트 4개 parquet 배제** (입력에 사용하지 않음):
   - `drug_features_catalog.parquet`
   - `drug_target_mapping.parquet`
   - `gdsc_ic50.parquet`
   - `lincs_drug_signature_normalized.parquet`
4. **`Colon_raw/` 하위 12개 폴더 중 사용 범위**
   - **사용:** `gdsc`, `depmap`, `lincs` (**GSE70138만**), `drugbank`, `chembl`, `admet`, `cBioPortal`, `geo` (**GSE39582만**)
   - **미사용 (baseline 우선):** `gtex`, `msigdb`, `opentargets`, `string`
5. **Proxy 데이터** — 사용이 필요하면 **즉시 멈추고 사용자에게 확인 요청.**
6. **오류** — 발생 시 **즉시 멈추고 보고.** 임의로 우회 해결하지 않음.
7. **불확실** — 모른다고 말하고 사용자에게 질문.

---

## Subtype 태깅 (대장암 특화)

- **Stratified 평가에 사용:** COAD / READ, MSI
- **메타데이터 저장만 (평가 stratify 안 함):** RAS, BRAF
- **이번 라운드 미사용:** HER2, CMS, sidedness

---

## 외부 검증 (옵션 B)

- **1차:** CPTAC-CRC + GSE39582 + COSMIC-CRC + PRISM(CRC) + ClinicalTrials(CRC)
- **2차 (추후):** GSE17536, GSE17538

---

## Lung 대비 Colon 차이 (요약)

1. 전처리 단계를 **신규**로 구축 (Lung은 기존 `curated_data/` 활용 가정이었음).
2. **LINCS:** Colon은 **GSE70138만** — Lung의 GSE92742 중심과 구분.
3. **Subtype 태깅** 및 stratified 평가 정책 적용.
4. **외부 검증:** GSE39582 등 Colon 프로토콜 반영.
5. **`Colon_raw/` 루트 parquet 4개 배제** — 원시 파이프라인만 사용.

---

## 파이프라인 단계 (참고)

1. **Step 1:** 환경 설정 + Raw 데이터 수집 (`scripts/parallel_download_colon.sh` 등)
2. **Step 2:** 데이터 전처리 (Raw → Parquet; Lung 스크립트 적응 복사)
3. **Step 3:** FE (Nextflow)
4. **Step 3.5:** Feature Selection
5. **Step 4:** 모델 학습
6. **Step 5:** 앙상블
7. **Step 6:** 외부 검증
8. **Step 7:** ADMET
9. **Step 8:** Neo4j 적재

---

## 현재 진행 상태 (2026-04-22)

- **완료 Step**: 1, 2, 3, 3.5, 4, 4.5(옵션), 5
- **다음 Step**: 6 (외부 검증)

### 핵심 성과

- **최종 앙상블**: GraphSAGE FSimp(w=0.8) + CatBoost FSimp(w=0.2) = **0.6010** (Drug Split Spearman)
- **핵심 발견**: Feature Selection (5657→1000) 이 Graph 모델에 가장 효과적 (+29.9%)
- **앙상블 구성**: GNN + Gradient Boosting 조합, 예측 상관 0.67 (충분한 diversity)
- **Overfit 현황**: 69% (FS 로 미해결, Hyperparameter tuning 별도 필요)

### 주요 산출물

- 대시보드: `dashboard/app.py` (Streamlit, 5/7 탭 구현)
- 실험 보고서: `COLON_STEP4_5_FS_EXPERIMENT_20260422.md`
- 앙상블 결과: `results/ensemble_20260422/ensemble_results.json`
- 프로토콜: `20260420_colon_protocol.md` (v1.4)

---

## 코딩·운영 선호 (에이전트용)

- Python **3.10**, conda 환경 **`drug4`**
- **`pathlib`** 우선, **f-string** 우선
- Parquet: **pandas / pyarrow**
- 파일 I/O는 **타임스탬프 로그**, 로그는 **`logs/`** 하위
- 자격 증명 **하드코딩 금지**
- Lung에서 가져온 코드에는 **출처 경로 주석** 권장

---

## Step 1 완료 확인 메모 (검증용 체크리스트)

다음은 Raw 동기화 후 점검에 쓸 **참고 목록**이다 (파일 목록은 시점에 따라 변할 수 있음).

- `curated_data/gdsc/GDSC2-dataset.csv`
- `curated_data/depmap/CRISPRGeneEffect.csv`, `Model.csv` (및 스크립트가 요구하는 기타 DepMap 원본)
- `curated_data/lincs/GSE70138/` — GSE70138 동기화 결과
- `curated_data/drugbank/`
- `curated_data/chembl/chembl_36_chemreps.txt.gz` (및 ChEMBL 관련 동기화 파일)
- `curated_data/cbioportal/coad_cptac_2019/`
- `curated_data/cbioportal/coadread_tcga_pan_can_atlas_2018/`
- `curated_data/geo/GSE39582/`

---

## 문서 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-20 | 사용자 제공 컨텍스트·규칙을 반영하여 초안 작성 |

---

## 대시보드 (Dashboard)

- **경로:** `dashboard/`
- **기술 스택:** Streamlit + Plotly + Pandas
- **실행:** `cd <프로젝트 루트> && streamlit run dashboard/app.py`
- **구조:**
  - `dashboard/app.py` — 메인 Streamlit 앱 (탭 7개)
  - `dashboard/parsers/` — Step별 결과 파서
  - `dashboard/views/` — 각 탭 뷰 구현
  - `dashboard/utils/` — 상수, 스타일
- **참고:** `lung_pipeline_dashboard.html` (Lung 대시보드, 정적 HTML)
- **미완료 작업:** `dashboard/TODO.md` 참조 (통합 재진행 시 반영)
