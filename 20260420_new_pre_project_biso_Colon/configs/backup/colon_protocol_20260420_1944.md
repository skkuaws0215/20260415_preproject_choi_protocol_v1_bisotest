# Colorectal (COAD+READ) pre-project protocol

- **질병:** 대장암 (Colorectal Cancer, COAD+READ)
- **옵션:** B (중간 확장)
- **작업 시작일:** 2026-04-20

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
| LINCS | `Colon_raw/LInc1000/GSE70138/` **만** 사용 — **GSE92742 미사용** (Lung 대비 차이 문서화) |
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
- **메타데이터 저장만:** RAS, BRAF
- **이번 라운드 미사용:** HER2, CMS, sidedness

## 메타데이터 (cBioPortal 최소 활용)

- **`coadread_tcga_pan_can_atlas_2018`:** site / MSI / RAS / BRAF 태깅용 (최소 연동)

## Baseline에서 제외 (미사용)

- msigdb, string, opentargets, gtex

## Lung 대비 프로토콜 차이

1. **전처리 신규:** Lung은 기존 `curated_data/` 활용 가정 — Colon은 전처리 단계부터 구축.
2. **LINCS:** Colon은 **GSE70138만** — Lung은 **GSE92742** 중심.
3. **Subtype + stratified 평가** 신규.
4. **외부 검증:** GSE39582 추가 — Lung은 CPTAC 중심.
5. **`Colon_raw/` 루트 parquet 4개 배제** — 원시 파이프라인만 사용.

## 로컬 디렉터리 스켈레톤 (참고)

`curated_data/`, `data/`, `scripts/`, `logs/`, `reports/`, `results/`  
`curated_data/{gdsc,depmap,lincs,drugbank,chembl,admet,cbioportal,geo,validation,processed}`  
`curated_data/validation/{cosmic,prism,clinicaltrials}`

---

*문서명: `20260420_colon_protocol.md` (작성일 기준).*
