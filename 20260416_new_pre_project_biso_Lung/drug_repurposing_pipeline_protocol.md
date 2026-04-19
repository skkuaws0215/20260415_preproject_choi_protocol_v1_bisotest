# 약물 재창출(Drug Repurposing) 파이프라인 프로토콜
## 적응증 확장 재현 가이드

> 작성일: 2026-04-17
> 버전: v1.0
> 목적: BRCA v3.1 파이프라인을 타 질병에 동일하게 적용하여 약물 재창출 랭킹을 생성하는 재현 프로토콜
> 원칙: 프로토콜(코드) = 원본 그대로 사용 / 데이터 = 해당 질병의 실제 데이터만 사용

---

## 1. 적용 현황

| 단계 | 질병 | 유형 | 상태 | 비고 |
|:----:|------|:----:|:----:|------|
| 1 | 유방암 (BRCA) | 암종 | ✅ 완료 | 기준 파이프라인 |
| 2 | 폐암 (Lung) | 암종 | 🔄 진행 중 | 이 문서 기준 |
| 3 | 대장암 (Colorectal) | 암종 | 예정 | |
| 4 | IPF (특발성 폐섬유증) | 비암종 | 예정 | |
| 5 | RA (류마티스 관절염) | 비암종 | 예정 | |

---

## 2. 절대 규칙

```
1. curated_data/ → 읽기 전용. 수정/삭제 절대 금지.
2. curated_date/glue/ → 접근 자체 금지 (다른 팀원 영역).
3. 프로토콜(코드) = 팀4/팀장 원본 그대로 사용.
4. 데이터 = 해당 질병의 실제 데이터만 사용.
5. 팀4 가공 데이터(tmp_data/)를 실제 데이터로 혼동하지 않는다.
6. Proxy 데이터 사용 시 반드시 사용자 확인 요청.
7. 오류 발생 시 즉시 멈추고 보고. 자의적 해결 금지.
8. 불확실하면 모른다고 한다.
```

---

## 3. 전체 파이프라인 구조

```
Step 1. Raw 데이터 수집
Step 2. 데이터 전처리 (Raw → Parquet)
Step 3. Feature Engineering (Nextflow + AWS Batch)
    Step 3-1. prepare_fe_inputs
    Step 3-2. build_features
    Step 3-3. build_pair_features
    Step 3-4. upload_results
Step 3.5. Feature Selection → features_slim.parquet
Step 4. 모델 학습 (13개 모델 × 3입력셋 × 3평가방식)
Step 5. 앙상블 (Phase 3)
Step 6. Multi-objective Ranking + 외부 검증
Step 7. ADMET Gate
```

---

## 4. 질병별 데이터 비교표

### 4-1. Raw 데이터 현황

| 데이터 | BRCA | Lung | 비고 |
|--------|:----:|:----:|------|
| GDSC2 | ✅ | ✅ | 약물 감수성 (IC50) |
| DepMap CRISPR | ✅ | ✅ | 세포주 유전자 의존성 |
| LINCS L1000 | ✅ | ✅ | 약물 시그니처 |
| DrugBank | ✅ | ✅ | 약물 메타데이터 |
| ChEMBL | ✅ | ✅ | SMILES 매칭 |
| CPTAC | ❌ | ✅ | 외부 검증용 (Lung 추가) |
| ADMET | ✅ | ✅ | Step 7용 |

### 4-2. 전처리 결과 비교

| 항목 | BRCA | Lung | 비고 |
|------|:----:|:----:|------|
| 전체 cell line | 52 | 969 | GDSC2 기준 |
| 매칭 cell line | 52 (100%) | 578 (59.8%) | DepMap CRISPR과 매칭 |
| 미매칭 원인 | - | DepMap 데이터 부재 | 391개 미수행 |
| 약물 수 | 295 | 295 | 동일 |
| SMILES 커버리지 | 243/295 (82.4%) | 243/295 (82.4%) | 동일 |
| IC50 measurements | ~7,730 | 148,239 | Lung이 약 20배 |
| IC50 결측 | 0 | 0 | |
| 클래스 불균형 | 70.8:29.2 | 70.9:29.1 | 거의 동일 |

### 4-3. Cell Line 매칭 방법 (Lung 특이사항)

```python
# Name 정규화 규칙 (Lung에서 채택)
def normalize_name(name):
    return str(name).lower().replace('-', '').replace('/', '').replace(' ', '').replace('_', '')
```

| 방법 | 매칭률 | 채택 |
|------|:------:|:----:|
| 원본 (cell_line_name) | 50.5% | ❌ |
| Name 정규화 | 59.8% | ✅ |
| Sanger Model ID | 악화 | ❌ |

---

## 5. LINCS 처리 (질병별 세포주 교체)

### 5-1. 세포주 선택 기준

| | BRCA | Lung |
|--|------|------|
| 세포주 | MCF7 (단일) | 11개 폐암 세포주 |
| 선택 기준 | 유방암 대표 | primary_site = lung |
| 제외 | - | A549.311(서브클론), HCC515(normal) |

### 5-2. Lung 세포주 목록

| Cell ID | Subtype | Type |
|---------|---------|:----:|
| A549 | NSCLC carcinoma | tumor |
| CORL23 | NSCLC large cell | tumor |
| DV90 | NSCLC adenocarcinoma | tumor |
| H1299 | Carcinoma | tumor |
| HCC15 | NSCLC squamous | tumor |
| NCIH1694 | SCLC carcinoma | tumor |
| NCIH1836 | SCLC carcinoma | tumor |
| NCIH2073 | NSCLC adenocarcinoma | tumor |
| NCIH596 | NSCLC adenosquamous | tumor |
| SKLU1 | NSCLC adenocarcinoma | tumor |
| T3M10 | NSCLC large cell | tumor |

### 5-3. LINCS 추출 프로세스

```
1. cell_info.txt.gz → 폐암 세포주 식별 (primary_site 필터)
2. sig_info.txt.gz → trt_cp(compound treatment)만 필터링
3. gctx에서 시그니처 추출 (청크 단위, 5000개씩)
4. parquet 저장 (lincs_lung.parquet)
5. 약물 매칭 (3-stage: exact → aggressive norm → synonym)
6. 약물 단위 집계 (mean) → lincs_lung_drug_level.parquet
```

### 5-4. LINCS 시그니처 비교

| 항목 | BRCA (MCF7) | Lung (11 cells) |
|------|:-----------:|:---------------:|
| 전체 시그니처 | 63,367 | 50,468 |
| trt_cp 시그니처 | 29,312 | 25,265 |
| 유전자 수 | 12,328 | 12,328 |
| 파일 크기 | 7.6 GB | 1.8 GB |

### 5-5. 약물 매칭률 비교

| 매칭 방법 | BRCA | Lung |
|-----------|:----:|:----:|
| Simple match | 101 (34.2%) | 58 (19.7%) |
| Aggressive normalization | - | 92 (31.2%) |
| 최종 | 101 (34.2%) | 92 (31.2%) |

**Aggressive normalization 규칙:**
```python
# 하이픈, 특수문자, 공백 제거 후 비교
# 예: "SN-38" → "sn38" == "SN38"
# 예: "ABT-737" → "abt737" == "ABT737"
```

**미매칭 약물 처리:** build_pair_features에서 0.0 fill (제외하지 않음)

### 5-6. 대용량 처리 주의사항

| 항목 | 권장사항 |
|------|---------|
| gctx 압축 해제 | gunzip -k (원본 보존) |
| 메모리 부족 시 | 청크 단위 추출 (5,000개씩) |
| gc.collect() | 각 청크 후 실행 |
| 디스크 정리 | parquet 생성 확인 후 gctx/gz 삭제 |

---

## 6. Feature Engineering (Nextflow + AWS Batch)

### 6-1. FE 입력 파일

| 파일 | 용도 | BRCA | Lung |
|------|------|:----:|:----:|
| sample_features.parquet | DepMap CRISPR | 52 × 18,443 | 1,150 × 18,444 |
| labels.parquet | GDSC IC50 | ~7,730 × 4 | 148,239 × 4 |
| drug_features.parquet | Drug catalog + SMILES | 295 × 5 | 295 × 5 |
| lincs_*_drug_level.parquet | LINCS 약물 시그니처 | 101 × 12,329 | 92 × 12,329 |
| drug_target_mapping.parquet | 약물-타겟 매핑 | 485 × 2 | 485 × 2 (재사용) |

### 6-2. Nextflow config 수정사항 (질병별)

```groovy
// 질병별 변경 필요 항목
params {
    s3_base       = "s3://say2-4team/.../[질병명]"          // ← 변경
    run_id        = "YYYYMMDD_[질병]_fe_v1"                 // ← 변경
    lincs_drug_sig_uri = "${params.data_dir}/lincs_[질병]_drug_level.parquet"  // ← 변경
}

// 컬럼명 주의: drug_features.parquet의 SMILES 컬럼명
// canonical_smiles (build_features 요구) vs smiles (전처리 출력)
// → canonical_smiles로 통일 필요
```

### 6-3. AWS Batch 리소스 (재사용)

| 리소스 | 값 | 비고 |
|--------|-----|------|
| ECR | fe-v2-nextflow:v2-pip-awscli | 기존 이미지 재사용 |
| Compute Env | team4-fe-ce-cpu | ENABLED/VALID 확인 |
| Job Queue | team4-fe-queue-cpu | ENABLED/VALID 확인 |
| IAM | ecsTaskExecutionRole | 기존 재사용 |

### 6-4. 메모리 설정 (실험적 결과)

| Process | 초기 설정 | 최종 설정 | 비고 |
|---------|:---------:|:---------:|------|
| prepare_fe_inputs | 16 GB | 16 GB | |
| build_features | 16 GB | 128 GB | OOM 발생으로 증설 |
| build_pair_features | 32 GB | 128 GB | OOM 발생으로 증설 |
| upload_results | 4 GB | 4 GB | |

### 6-5. FE 결과 비교

| 항목 | BRCA | Lung |
|------|:----:|:----:|
| drug-cell pairs | 6,366 | 125,427 |
| features.parquet 컬럼 | 18,316 | 18,439 |
| pair_features.parquet 컬럼 | 2,073 | 2,075 |
| LINCS feature 5개 | ✅ | ✅ |
| 결측치 | 0 | 0 |
| 클래스 불균형 | 7:3 | 7:3 |

### 6-6. FE QC 체크리스트

```
[ ] features.parquet shape 확인 (컬럼 ~18,000+)
[ ] labels.parquet binary_label 분포 확인
[ ] pair_features.parquet LINCS 5개 컬럼 존재 확인
[ ] 전 파일 행 수 일치 확인
[ ] 결측치 0 확인
[ ] 클래스 불균형 5:1 이하 확인
```

---

## 7. Feature Selection → features_slim.parquet

### 7-1. Selection 순서 (TCGA 기준, BRCA와 동일)

```
1단계: Low Variance 제거
   - TCGA 기준 variance 계산
   - 임계값 미만 제거

2단계: High Correlation 정리
   - Pearson > 0.95 쌍에서 하나 제거
   - 기준: 전체 평균 상관이 높은 쪽 제거

3단계 (선택): Importance 기반 하위 컷
   - 모델 학습 후 과적합 심하면 적용
   - biology signal 보존 주의
```

### 7-2. Selection 대상별 처리

| 구분 | 대상 | Selection 적용 |
|------|------|:--------------:|
| Gene (CRISPR) | ~18,435개 | ✅ Low var + High corr |
| Morgan FP | ~2,048개 | ✅ Low var + High corr |
| LINCS/Target/Pathway/Drug desc | ~25개 | ❌ 전부 유지 |

### 7-3. 질병별 Feature Selection 결과

#### BRCA (기준)

| 항목 | 원본 | Selection 후 | 제거율 |
|------|:----:|:------------:|:------:|
| Gene | 18,310 | 4,415 | 75.9% |
| Morgan FP | 2,048 | 1,094 | 46.6% |
| 기타 | 25 | 25 | 0% |
| **합계** | **20,383** | **5,534** | **72.8%** |

#### Lung (완료, 2026-04-17)

| 항목 | 원본 | Low Var 제거 | High Corr 제거 | 최종 | 제거율 |
|------|:----:|:------------:|:--------------:|:----:|:------:|
| Gene | 18,435 | 4,703 | 4,703 | **4,703** | 74.5% |
| Morgan FP | 2,048 | 1,039 | 1,032 | **1,032** | 49.6% |
| LINCS | 5 | - | - | **5** | 0% |
| Target | 10 | - | - | **10** | 0% |
| Drug desc | 9 | - | - | **9** | 0% |
| Drug other | 5 | - | - | **5** | 0% |
| **합계** | **20,512** | **-** | **-** | **5,764** | **71.9%** |

**비교:** Lung 제거율(71.9%) vs BRCA(72.8%) → 거의 동일하여 일관성 확인 ✅

### 7-4. 산출물

```
features_slim.parquet          → 모델 학습 입력 (수정본)
features.parquet               → 원본 보존 (수정 금지)
pair_features.parquet          → 원본 보존 (수정 금지)
feature_selection_log.json     → 단계별 제거 수 기록
```

---

## 8. 모델 학습 (Phase 2)

### 8-1. 입력셋 3종

| 입력셋 | 구성 | 설명 |
|--------|------|------|
| Phase 2A | numeric-only | features_slim 수치 피처만 |
| Phase 2B | numeric + SMILES | 2A + SMILES (ML: TF-IDF+SVD 64d, DL: char token) |
| Phase 2C | numeric + context + SMILES | 2B + strong context 5개 컬럼 |

### 8-2. 모델 구성 (15개)

| 유형 | 모델 | 비고 |
|:----:|------|------|
| ML | LightGBM | |
| ML | LightGBM DART | |
| ML | XGBoost | |
| ML | CatBoost | |
| ML | RandomForest | |
| ML | ExtraTrees | |
| DL | FlatMLP | |
| DL | ResidualMLP | |
| DL | FTTransformer | |
| DL | CrossAttention | |
| DL | TabNet | |
| DL | WideDeep | |
| DL | TabTransformer | early stop 적용 |
| Graph | GraphSAGE | drug-split 필수 |
| Graph | GAT | drug-split 필수 |

> **주의:** GraphSAGE, GAT는 반드시 drug-based split 적용. Random split 사용 시 약물 정보 누출로 성능 과대평가.

### 8-3. 평가 방식 3종

| 방식 | 설명 | 목적 |
|------|------|------|
| Holdout | train:test = 8:2 | 빠른 확인 |
| 5-Fold CV | 일반 KFold | 안정적 평가 |
| GroupCV | canonical_drug_id 기준 3-fold | unseen drug 일반화 |

### 8-4. 평가 지표

```
예측 성능: Spearman, Pearson, R², RMSE, MAE, Kendall's Tau
과적합: Train-Val Gap, Fold std
```

### 8-5. BRCA 결과 참고

| 순위 | 모델 | 입력셋 | GroupCV Spearman |
|:----:|------|:------:|:----------------:|
| 1 | CatBoost | 2A | 0.8624 |
| 2 | LightGBM | 2A | 0.8575 |
| 3 | ResidualMLP | 2C | 0.5493 |

---

## 9. 앙상블 (Phase 3)

### 9-1. 앙상블 조합

| 조합 | 구성 | 비고 |
|------|------|------|
| FRC (프로토콜) | FlatMLP + ResidualMLP + CrossAttention | 프로토콜 기본 |
| DL Top3 | GroupCV 상위 DL 3개 | |
| ML Top3 | GroupCV 상위 ML 3개 | |
| ML+DL 혼합 | 전체 상위 3개 | BRCA 최고 성능 |

### 9-2. 앙상블 방식

| 방식 | 설명 |
|------|------|
| Simple Average | 단순 평균 |
| Weighted Average | GroupCV Spearman 비례 가중치 |

### 9-3. 총 실험 수

```
4조합 × 2방식 × 3입력셋 = 24개 앙상블 실험
```

### 9-4. 앙상블 평가 지표

```
Spearman, Ensemble Gain, Diversity, Error Overlap, Consensus Score
```

### 9-5. BRCA 결과

| 순위 | 조합 | 입력셋 | 방식 | Spearman |
|:----:|------|:------:|------|:--------:|
| 1 | ML+DL 혼합 (RF+ResidualMLP+TabNet) | 2A | Weighted | **0.5521** |
| 2 | ResidualMLP 단일 | 2C | - | 0.5493 |
| 3 | FRC | 2C | Simple | 0.5452 |

**BRCA 핵심 발견:**
- 프로토콜 조합 Gain 전부 음수, 커스텀만 양수
- Phase 2A에서 앙상블 효과 최대
- SMILES/Context는 DL 단일에만 효과적, 앙상블에서는 diversity 감소
- Diversity vs Error Overlap 상관: -0.997

### 9-6. Lung 결과 (2026-04-19)

**양수 Gain 조합 (4/24):**

| 순위 | 조합 | 입력셋 | 방식 | Spearman | Best Single | Gain |
|:----:|------|:------:|------|:--------:|:-----------:|:----:|
| 1 | ML+DL 혼합 (CatBoost+ResidualMLP+TabNet) | 2A | Weighted | 0.4797 | 0.4765 | **+0.0033** |
| 2 | ML+DL 혼합 (CatBoost+ResidualMLP+TabNet) | 2A | Simple | 0.4790 | 0.4765 | +0.0025 |
| 3 | DL Top3 (ResidualMLP+TabTransformer+TabNet) | 2C | Weighted | 0.4290 | 0.4277 | +0.0013 |
| 4 | DL Top3 (ResidualMLP+TabTransformer+TabNet) | 2C | Simple | 0.4290 | 0.4277 | +0.0012 |

**최종 추천:** Phase 2C **CatBoost 단일 모델** (Spearman: 0.5030)

**Lung 핵심 발견:**
- **앙상블 제한적 효과**: 24개 중 4개만 양수 Gain (17%)
- **CatBoost 압도적 우위**: 대부분 앙상블보다 단일 모델 우수
- 최대 Gain: +0.0033 (0.7% 향상) - 복잡도 대비 미미
- Diversity vs Gain 상관: -0.2562 (p=0.2268) - 낮은 상관
- Error Overlap 높음 (0.6~0.8) - 모델 간 유사한 오류 패턴
- **결론**: 단일 모델(CatBoost) 사용 권장

### 9-7. BRCA vs Lung 앙상블 비교

| 지표 | BRCA | Lung | 차이점 |
|------|------|------|--------|
| **최고 단일 모델** | ResidualMLP (0.5493) | CatBoost (0.5030) | Lung은 ML 모델 우위 |
| **최고 앙상블** | 혼합 Weighted (0.5521) | 혼합 Weighted (0.4797) | BRCA가 0.07 더 높음 |
| **최대 Gain** | +0.0028 | +0.0033 | 유사 (둘 다 미미) |
| **양수 Gain 비율** | TBD | 4/24 (17%) | Lung은 대부분 실패 |
| **Diversity 효과** | 음수 상관 (-0.997) | 음수 상관 (-0.26) | 둘 다 높은 다양성≠높은 성능 |
| **최종 추천** | ResidualMLP 단일 | CatBoost 단일 | **둘 다 단일 모델 권장** |

**공통 패턴:**
- 앙상블 효과 제한적 (Gain < 0.01)
- 단일 최고 모델이 앙상블과 비슷하거나 우수
- 높은 Diversity가 성능 보장하지 않음
- Phase 2A에서 앙상블 효과가 가장 큼
- 복잡도 증가 대비 성능 향상 미미

**차이점:**
- BRCA: DL 모델(ResidualMLP) 최고
- Lung: ML 모델(CatBoost) 최고
- Lung은 앙상블 실패율이 더 높음 (83% vs TBD)

---

## 10. 외부 검증 (Step 6)

### 10-1. 질병별 외부 검증 데이터

| | BRCA | Lung | 역할 |
|--|------|------|------|
| 주 검증 (환자 코호트) | METABRIC | CPTAC-LUAD/LUSC | 독립 환자 코호트, Survival 검증 |
| 변이 기반 검증 | - | COSMIC | 약물 타겟 ↔ 폐암 드라이버 유전자 일치 확인 |
| 약물 반응 검증 | - | PRISM | 대규모 세포주 약물 감수성 |
| 임상 근거 검증 | - | ClinicalTrials | 추천 약물의 폐암 임상시험 현황 |

### 10-2. BRCA vs Lung 검증 체계 비교

```
BRCA: 단일 검증
  └── METABRIC (Method A + B + C)

Lung: 다층 검증 (4개 소스)
  ├── CPTAC-LUAD/LUSC  → 독립 환자 코호트 (Survival, 발현, 단백질)
  ├── COSMIC           → 드라이버 유전자 기반 약물-질병 연관성
  ├── PRISM            → 세포주 약물 감수성 실측 (재창출 후보 커버리지)
  └── ClinicalTrials   → 임상시험 근거 (실제 임상 진행 여부)
```

### 10-3. COSMIC 활용 방법

```
1. 파이프라인 추천 약물의 타겟 유전자 추출
   (drug_target_mapping.parquet 참조)

2. COSMIC에서 해당 유전자의 폐암 변이 빈도 조회
   - LUAD/LUSC별 변이 빈도 (mutation frequency)
   - 드라이버 vs 패신저 분류

3. 검증 기준
   - 추천 약물 타겟이 COSMIC 폐암 드라이버 유전자와 일치 → 강한 근거
   - 변이 빈도 상위 20% 이내 → 임상적 유의성 높음
   - 일치하지 않음 → 약물 재창출 근거 약함 (단, 우회 경로 가능)

4. 소스 경로
   curated_data/validation/cosmic/
```

### 10-4. 각 검증 소스별 확인 항목

| 소스 | 확인 항목 | 판정 기준 |
|------|----------|----------|
| CPTAC | 타겟 유전자 발현 → 생존 연관성 | Survival p < 0.05 |
| COSMIC | 타겟 유전자 변이 빈도 | 폐암 드라이버 Top 20% |
| PRISM | 추천 약물 IC50 실측 | IC50 < median |
| ClinicalTrials | 폐암 임상시험 존재 여부 | Phase II 이상 |

### 10-5. 검증 방법 (BRCA 기준, Lung 확장 적용)

```
Method A: IC50 proxy 검증 (CPTAC 발현 기반)
Method B: Survival binary 검증 (CPTAC 생존 데이터)
Method C: P@K 검증
Method D: 드라이버 유전자 일치 검증 (COSMIC) ← Lung 신규
Method E: 세포주 약물 반응 검증 (PRISM) ← Lung 신규
```

---

## 11. ADMET Gate (Step 7)

### 11-1. 필터링 3단계

```
Tier 1 Hard Fail → 즉시 탈락
- hERG > 0.7
- PAINS > 0
- Lipinski 위반 > 2

Tier 2 Soft Flag → 검토 후 판단
- hERG 0.5~0.7
- DILI, Ames, CYP3A4, PPB, Caco2

Tier 3 Context → 항암제 특성상 완화
- F(oral), t_half, Carcinogenicity
```

### 11-2. BRCA 최종 결과

```
Top 30 → Top 15 → ADMET 7개 PASS
Repurposing 1위: Ibrutinib (Safety 111.9)
```

---

## 12. 경로 정보 템플릿

### 로컬

```
/Users/[user]/[project_root]/
└── [date]_new_pre_project_biso_[Disease]/
    ├── curated_data/          ← Raw 데이터 (읽기 전용)
    │   ├── gdsc/
    │   ├── depmap/
    │   ├── lincs/
    │   ├── drugbank/
    │   ├── chembl/
    │   ├── cptac/             ← 외부 검증용
    │   ├── admet/             ← Step 7용
    │   ├── validation/        ← 외부 검증용
    │   └── processed/         ← 전처리 결과
    ├── data/                  ← FE 입력/S3 업로드 대상
    ├── scripts/
    ├── logs/
    └── reports/
```

### S3

```
s3://say2-4team/[base_path]/[date]_new_pre_project_biso_[Disease]/
├── data/                    ← FE 입력 파일
├── fe_output/               ← FE 결과
│   └── [run_id]/
│       ├── features/
│       ├── pair_features/
│       └── reports/
└── work/                    ← Nextflow 작업 디렉토리
```

### 참조 스크립트 (코드만 참조, 데이터 사용 금지)

```
/Users/[user]/[brca_protocol_path]/nextflow/scripts/
├── build_drug_catalog.py
├── prepare_fe_inputs.py
├── build_features_v8_20260406.py
└── build_pair_features_newfe_v2.py
```

---

## 13. 새 질병 추가 시 체크리스트

```
[ ] Raw 데이터 수집 (GDSC, DepMap, LINCS, DrugBank, ChEMBL)
[ ] 외부 검증 데이터 수집 (METABRIC 대체)
[ ] Cell line 매칭 방법 결정 (정규화 규칙)
[ ] LINCS 세포주 선택 (해당 질병 세포주 목록)
[ ] LINCS gctx → parquet 추출
[ ] 약물 매칭 (3-stage)
[ ] 약물 단위 집계 (mean)
[ ] Drug catalog 생성 (SMILES 매칭)
[ ] FE 입력 파일 준비 (4~5개)
[ ] S3 업로드
[ ] Nextflow config 수정 (경로, run_id, LINCS 파일명)
[ ] Nextflow AWS Batch 실행
[ ] FE QC
[ ] Feature Selection → features_slim.parquet
[ ] choi_protocol 경로/컬럼 매핑 수정
[ ] 모델 학습 (13개 × 3입력셋 × 3평가)
[ ] 앙상블 (24개 실험)
[ ] 외부 검증
[ ] ADMET Gate
[ ] 질병간 비교 분석 (앙상블 최적 조합 비교)
```

---

## 14. 기반 프로토콜 및 레퍼런스

### 14-1. 내부 프로토콜 계보

| 문서 | 날짜 | 내용 | 관계 |
|------|------|------|------|
| Team4_Experiment_Protocol_v2_3 | 2026-03 | 팀4 원본 실험 프로토콜 | 최초 기반 |
| protocol_guide_v1 (biso) | 2026-04-08 | 팀4 기반 재현 가이드, 15개 모델, FE+학습+ADMET | v1 |
| protocol_guide_v2 | 2026-04-10 | 7-Hurdle System 추가, MultiModalFusionNet | v2 |
| protocol_guide_v3 | 2026-04-14 | 15개 모델 재학습, Feature Selection(20,389→5,534), 6단계 확장 평가 | v3 |
| protocol_guide_v3.1 | 2026-04-14 | Multi-objective scoring, 치료제 분리, ADMET Tanimoto v1, CatBoost 단독 채택 | v3.1 |
| PROTOCOL_CHOI_통합실행가이드 | 2026-04-15 | 팀장 프로토콜 기반 학습 파이프라인, 3입력셋(2A/2B/2C), 13모델×3평가, 앙상블 Phase 3 | choi_protocol |
| lung_preprocessing_protocol | 2026-04-16 | 폐암 전처리 프로토콜, LINCS 11세포주, Cell line 정규화 | Lung 전처리 |
| **본 문서** | **2026-04-17** | **적응증 확장 재현 가이드, BRCA→Lung 비교, 재현 체크리스트** | **통합** |

### 14-2. 핵심 참조 관계

```
Team4_Experiment_Protocol_v2_3 (팀4 원본)
    ↓
protocol_guide_v1~v3.1 (BRCA 파이프라인 진화)
    ↓
PROTOCOL_CHOI_통합실행가이드 (팀장 프로토콜 + 커스터마이징)
    ↓
본 문서 (적응증 확장 재현 가이드)
```

### 14-3. GitHub 저장소

| 저장소 | 용도 |
|--------|------|
| skkuaws0215/20260408_pre_project_biso_myprotocol | BRCA 파이프라인 (v1~v3.1), 대시보드 |
| skkuaws0215/20260415_preproject_choi_protocol_v1_bisotest | choi_protocol 학습 파이프라인, Lung 확장 |

### 14-4. BRCA 앙상블 선정 과정 (v3 → v3.1)

```
15개 모델 학습
    ↓
앙상블 통과 12개 (Sp≥0.713 AND RMSE≤1.385)
    ↓
앙상블 B: 4개 (CatBoost + DART + FlatMLP + CrossAttn)
    ↓
앙상블 A: 3개 (CatBoost + DART + FlatMLP, CrossAttn 중복 제거)
    ↓
CatBoost 단독과 비교 → METABRIC Top 15 overlap 80%, Sp 0.994
    ↓
CatBoost 단독 채택 (v3.1)
```

### 14-5. choi_protocol 앙상블 결과 (Phase 3)

```
24개 앙상블 실험 (4조합 × 2방식 × 3입력셋)
    ↓
프로토콜 조합 Gain: 전부 음수
커스텀 조합 Gain: 6개 양수
    ↓
최고: ML+DL 혼합 (RF+ResidualMLP+TabNet) 2A Weighted → Sp 0.5521
단일 최고: ResidualMLP 2C → Sp 0.5493
    ↓
최종: 앙상블 + 단일 교차 검증 방식 채택
```

### 14-6. S3 데이터 경로

| 경로 | 용도 | 접근 |
|------|------|:----:|
| s3://say2-4team/curated_date/ | 전처리 완료 원본 데이터 | 읽기 전용 |
| s3://say2-4team/curated_date/glue/ | 다른 팀원 영역 | 접근 금지 |
| s3://say2-4team/Lung_raw/ | 폐암 Raw 데이터 (35.5GB) | 읽기 전용 |
| s3://say2-4team/20260408_new_pre_project_biso/.../BRCA/ | BRCA 업무폴더 | 읽기/쓰기 |
| s3://say2-4team/20260408_new_pre_project_biso/.../Lung/ | Lung 업무폴더 | 읽기/쓰기 |

---

## 15. 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|:----:|----------|
| 2026-04-19 | v1.1 | Lung Phase 2+3 완료, 앙상블 분석 추가, BRCA vs Lung 비교 추가 |
| 2026-04-17 | v1.0 | 초안 작성 (BRCA 완료, Lung FE 완료 기준) |
