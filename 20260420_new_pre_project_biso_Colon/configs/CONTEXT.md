# Colon 파이프라인 Context

## 프로젝트 개요
- 질병: 대장암 (Colorectal Cancer, COAD+READ)
- 파이프라인 기반: BRCA (myprotocol) + Lung 확장
- 옵션: B (중간 확장)
- 작업 시작일: 2026-04-20

## 경로
- 로컬 베이스: /Users/skku_aws2_14/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest-1/20260420_new_pre_project_biso_Colon
- S3 원본 (읽기전용): s3://say2-4team/Colon_raw/
- S3 작업폴더: s3://say2-4team/20260408_new_pre_project_biso/20260420_new_pre_project_biso_Colon/
- GitHub: skkuaws0215/20260415_preproject_choi_protocol_v1_bisotest (폴더: 20260420_new_pre_project_biso_Colon)

## 참조 원본 위치
- Lung 소스: /Users/skku_aws2_14/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest-1/20260416_new_pre_project_biso_Lung
- BRCA 소스: /Users/skku_aws2_14/20260408_pre_project_biso_myprotocol/20260408_pre_project_biso_myprotocol

## 절대 규칙 (위반 시 즉시 중단)
1. curated_data/ 읽기 전용 (수정/삭제 금지)
2. Colon_raw/ 루트 4개 parquet 배제:
   - drug_features_catalog.parquet
   - drug_target_mapping.parquet
   - gdsc_ic50.parquet
   - lincs_drug_signature_normalized.parquet
3. Colon_raw/ 하위 사용 범위:
   - 사용: gdsc, depmap, lincs(GSE92742 + GSE70138 보유), drugbank, chembl, admet, cBioPortal, geo(GSE39582만)
   - 미사용: gtex, msigdb, opentargets, string (baseline 우선)
4. 복사된 스크립트: 원본 로직 유지, BASE_DIR/경로/로그 문구만 수정
5. 오류 발생 시 즉시 멈추고 보고 (자의적 해결 금지)
6. 불확실하면 모른다고 하고 확인 요청
7. Proxy 데이터 사용 시 사용자 확인 필요
8. eseo 폴더 (s3://say2-4team/20260409_eseo/) 사용 금지 (타 팀원 소유)

## LINCS 세포주 정책 (확정)
포함 13개:
  CL34, HCT116, HT115, HT29, LOVO, MDST8,
  NCIH508, RKO, SNU1040, SNUC5, SW480, SW620, SW948

제외:
  HELA, HELA.311 (자궁경부암 DepMap ECAD 확정)
  HT29.311 (Cas9 서브클론, Lung 정책 일관)
  NCIH716 (trt_cp 시그니처 0개)

알려진 제한:
  HT29 편향 77.1% (14,513/18,823) → 현 단계 보정 없음
  사후 모니터링: FE 영향도 + 외부검증 HT29 bias 감시

## Subtype 태깅 정책
- 평가 stratification 사용: COAD/READ, MSI
- 메타데이터 저장만: RAS, BRAF
- 후순위 (이번 미사용): HER2, CMS, sidedness

## 외부 검증 (옵션 B) + Survival 포함

### 배경
- Lung은 CPTAC 사용했으나 Survival 검증이 누락된 상태
- Lung은 향후 재실험 계획 (NSCLC-only + Survival 추가)
- Colon은 처음부터 Survival 포함해서 표준 구축

### 1차 검증 (현재 파이프라인)
1. CPTAC-CRC (coad_cptac_2019)
   - Method A: IC50 proxy (타겟 유전자 발현)
   - Method B: Survival binary (p < 0.05 기준)  [NEW - Lung에 누락]
   - Method C: P@K
2. GSE39582
   - Method A: 발현 기반 validation
   - Method B: Survival 연관성  [NEW - GSE39582는 생존 데이터 포함]
3. COSMIC-CRC
   - 드라이버 유전자 매칭 (약물 타겟 vs CRC 드라이버)
4. PRISM (CRC cell lines)
   - IC50 실측 검증
5. ClinicalTrials (CRC)
   - 임상시험 근거

### 2차 검증 (나중에 추가)
- GSE17536 (survival 포함)
- GSE17538 (survival 포함)

### Survival 검증 구현 (Method B)
- CPTAC/GEO clinical 테이블 로드
- 약물 타겟 유전자 발현 high vs low 분류
- Kaplan-Meier + log-rank test
- p < 0.05 기준 통과 판정
- Colon의 Top 약물 검증 지표 중 하나

## 메타데이터 소스
- cBioPortal 최소 활용: coadread_tcga_pan_can_atlas_2018 (MSI/RAS/BRAF 태깅용)

## Lung 대비 프로토콜 차이점
1. 전처리 단계 신규 추가 (Lung은 curated_date/ 기존 활용)
2. LINCS: GSE92742 사용 (Lung 선례 따름, GSE70138 보유하나 미사용)
3. Subtype 태깅 및 stratified 평가 신규 추가
4. 외부 검증에 GSE39582 추가 (Lung은 CPTAC만)
5. Colon_raw/ 루트 4개 parquet 배제 (원본만 사용)
6. LINCS 세포주 사전 검증으로 HELA 오분류 + NCIH716 무효 + .311 제외

## 진행 상태
- [x] Step 1: Raw 데이터 다운로드
- [x] Step 2-0: 환경 구축
- [x] Step 2-1: Raw → Parquet
- [x] Step 2-2: ChEMBL SQLite
- [x] Step 2-3: DepMap wide→long
- [x] Step 2-4: Colon 세포주 필터링 + labels
- [x] Step 2-5: Drug catalog + Bridge
- [x] Step 2-6: LINCS gctx → parquet
- [x] Step 2-7: LINCS 약물 단위 집계
- [x] Step 2-8: Subtype 태깅
- [x] Step 2-9: drug_target_mapping 복사
- [x] Step 2-10: 통합 QC

## Step 2 실행 결과 (2026-04-20 완료)

### 주요 산출물
- `data/labels.parquet`: (12,538, 4) — GDSC COREAD, 46 cells × 295 drugs, 100% 매칭
- `data/drug_features.parquet`: (295, 5) — Lung과 100% 일치 (Q1-C 방법론 검증)
- `data/drug_target_mapping.parquet`: (485, 2) — 295 drugs 100% 커버, 235 unique targets
- `data/lincs_colon.parquet`: (18,823, 12,336) — GSE92742 only, Colon 13 cells
- `data/lincs_colon_drug_level.parquet`: (91, 12,329) — 매칭률 30.85% (Lung 31.19%와 일관)
- `data/colon_subtype_metadata.parquet`: (594, 11) — TCGA COADREAD 태깅
- `curated_data/processed/depmap/depmap_crispr_long_colon.parquet`: (20.4M, 3)

### LINCS 데이터 소스 최종 결정
- 초기 계획: GSE70138만 사용
- 문제 발견: GSE70138 단독으로는 Colon 13 중 HT29만 포함 (다른 12 cells 0개)
- 대안 검토: GSE92742 추가 또는 GSE92742 only
- Lung 방식 검증: Lung lincs_lung.parquet의 sig_id prefix 모두 GSE92742 계열 (CPC, HOG, PCLB, DOS 등)
- 최종 결정: GSE92742 only (Lung 선례 일관)
- GSE70138: curated_data/lincs/GSE70138/에 보유하나 미사용 (삭제 안 함, 규칙 1 준수)
- 결과: 18,823 signatures (Colon 13 cells 모두 커버), HT29 편향 77.1%

### 환자 메타데이터 통계 (TCGA COADREAD, N=594)
- primary_site: COAD 378 (63.6%), READ 155 (26.1%), MACR 61 (10.3%)
- msi_status: MSS 468 (78.8%), MSI-H 89 (15.0%), NaN 37 (6.2%)
- RAS mutation: 246 (41.4%)
- BRAF mutation: 62 (10.4%)
- BRAF V600E: 48 (8.1%)

### 추가 카테고리: MACR
- MACR = Mucinous Adenocarcinoma of Colon and Rectum (점액성 선암)
- 초기 "COAD/READ" 이분법에 포함 안 됨
- primary_site 필드에 'MACR'로 그대로 보존
- Step 6 평가 단계에서 처리 방침 결정 예정

### 신규 Colon 전용 스크립트 (5개)
- scripts/filter_colon_cell_lines.py (342 lines) — GDSC COREAD 필터 + 매칭
- scripts/bridge_drug_features.py (203 lines) — catalog 6col → features 5col 전환
- scripts/extract_lincs_gctx.py (334 lines) — GSE92742 cmapPy 파싱, 청크 처리
- scripts/colon_subtype_tagging.py (323 lines) — TCGA subtype 태깅
- scripts/step2_qc.py (343 lines) — Step 2 통합 QC

### 통합 QC 결과 (Step 2-10)
- ALL QC CHECKS PASSED
- 이슈 0건
- 파일 존재/스키마/Drug ID 일관성/Cell ID 일관성 모두 통과
- Step 3 FE 입력 호환성 검증 완료
