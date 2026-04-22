# Colon 고급 검증 계획 (Advanced Validation Plan)

> **작성일**: 2026-04-21
> **최종 수정**: 2026-04-22 (v1.3)
> **대상**: Colon Drug Repurposing Pipeline
> **범위**: 프로토콜 v2.4 미진행 지표 확장 + 분자 수준 검증
> **상태**:
>   - **Task 1 (Scaffold Split)**: ✅ 완료 (2026-04-22)
>   - **Task 2 (AlphaFold + Docking)**: 위치 확정 (**Step 7.5 검증 + Step 8 KG 적재, D-3 구조**), 계획만 문서화, 구현은 **Colon Step 4~7 완료 후**

---

## 📋 개요

프로토콜 v2.3 Section 13의 **32개 지표 체크리스트** 중 Lung/BRCA에서 미진행된 지표를 Colon에서 시도. 추가로 약물-타겟 결합을 **분자 수준에서 검증**하는 파이프라인 확장.

### 미진행 지표 현황 (프로토콜 v2.3 Section 13)

| # | 지표 | 카테고리 | Lung 상태 | Colon 계획 |
|:-:|------|---------|:---:|:---:|
| 21 | Scaffold split | 일반화 | ❌ | **🔄 Task 1 (ML 완료 직후 실행)** |
| 22 | Multi-seed stability | 일반화 | ❌ | ⏸️ 향후 |
| 23 | Cross-dataset | 일반화 | ❌ | ⏸️ Step 6에서 PRISM 부분 |
| 30 | MAP | 약물 랭킹 | ❌ | ⏸️ 향후 |
| 31 | AUC-ROC | 약물 랭킹 | ❌ | ⏸️ 향후 |

**이 문서에서 다룰 것**:
- **Task 1**: Scaffold split (지표 #21) — **구현 완료, ML 완료 직후 실행**
- **Task 2**: AlphaFold + Docking 기반 약물-타겟 결합 검증 + Neo4j KG 통합 — **Step 7.5 신설 + Step 8 통합 (D-3 구조)**, Colon Step 4~7 완료 후 구현

---

## 🎯 Task 1: Scaffold Split (지표 #21) ✅ 구현 완료, 실행 대기

### 실행 상태

- **작성일**: 2026-04-21 (오늘)
- **실행 예정**: Step 4 ML 학습 (Phase 2C까지) 완료 직후
- **현재**: ML Phase 2B/2C 진행 중, 완료 후 바로 실행
- **결정**: **옵션 B (전체 구현, 3 Phase × 6 ML 모델)**

### 1-1. 개념

#### GroupCV (현재) vs Scaffold Split (추가)

| 분할 방식 | groups 기준 | 난이도 | 업계 평균 Spearman |
|----------|------------|:---:|:---:|
| GroupCV (현재) | `canonical_drug_id` | 🟡 보통 | 0.3~0.5 |
| **Scaffold split** | **Murcko scaffold** | 🔴 **더 엄격** | **0.25~0.35 예상** |

#### Murcko Scaffold란?
- 분자의 **핵심 고리 골격** (ring system + linker)
- 예: 파클리탁셀, 도세탁셀, 카바지탁셀 → 모두 동일한 **taxane scaffold**
- GroupCV에서는 이들이 다른 drug_id라 train/val 분리되지만,
- Scaffold split에서는 **한쪽 fold에만 몰아넣음** → 더 엄격

#### 왜 더 엄격한가?
```
예시:
  Drug split (GroupCV)의 Fold 1
    train: 파클리탁셀, 비노렐빈, ...
    val:   도세탁셀, 에토포사이드, ...
    → 모델이 "taxane 구조" 기억해서 도세탁셀 잘 예측
    → 과대평가 위험

  Scaffold split의 Fold 1
    train: 비노렐빈, 에토포사이드 (다른 scaffold)
    val:   파클리탁셀, 도세탁셀, 카바지탁셀 (동일 taxane scaffold)
    → 모델이 taxane을 처음 보는 상태에서 예측
    → 진짜 일반화 능력 측정
```

### 1-2. 구현 상태 ✅

**두 스크립트 모두 작성 완료** (2026-04-21, Claude 작성). 경로:

```
scripts/
  ├─ compute_scaffolds.py         (192 lines) ✅ 작성 완료
  └─ run_ml_scaffold_all.py       (216 lines) ✅ 작성 완료
```

#### `compute_scaffolds.py` 역할

**입력**:
- `data/drug_features.parquet` (canonical_smiles 포함)
- `fe_qc/20260420_colon_fe_v2/features/labels.parquet`

**출력**:
- `data/scaffold_groups.npy` (9692,) — pair별 scaffold integer ID
- `data/scaffold_mapping.json` — {drug_id: scaffold_smiles, scaffold_to_id}
- `data/scaffold_stats.json` — 통계 요약

**주요 기능**:
- RDKit `MurckoScaffold.MurckoScaffoldSmiles` 사용
- 결측/파싱 실패 SMILES 별도 처리 (`NO_SMILES`, `INVALID_SMILES`, `EMPTY_SCAFFOLD`)
- 상위 10개 scaffold 출력
- **3-fold 불균형 자동 체크** (단일 scaffold가 fold의 50% 초과 시 경고)

**핵심 로직**:
```python
from rdkit.Chem.Scaffolds import MurckoScaffold

def extract_scaffold(smiles):
    if pd.isna(smiles) or smiles == '':
        return 'NO_SMILES'
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return 'INVALID_SMILES'
    scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
    return scaffold if scaffold else 'EMPTY_SCAFFOLD'
```

#### `run_ml_scaffold_all.py` 역할

**입력**:
- `data/X_numeric.npy`, `X_numeric_smiles.npy`, `X_numeric_context_smiles.npy`
- `data/y_train.npy`
- `data/scaffold_groups.npy` (compute_scaffolds.py에서 생성)

**출력**:
- `results/colon_numeric_ml_v1_scaffoldcv.json`
- `results/colon_numeric_smiles_ml_v1_scaffoldcv.json`
- `results/colon_numeric_context_smiles_ml_v1_scaffoldcv.json`
- `results/colon_numeric_ml_v1_scaffold_oof/*.npy` (6 파일)
- `results/colon_numeric_smiles_ml_v1_scaffold_oof/*.npy` (6 파일)
- `results/colon_numeric_context_smiles_ml_v1_scaffold_oof/*.npy` (6 파일)

**주요 기능**:
- 기존 `run_ml_all.py`의 `train_evaluate_ml` 함수 import해서 재사용
- `groups` 파라미터만 `canonical_drug_id` → `scaffold_id`로 교체
- `GroupKFold(n_splits=3)` 그대로 사용 (그룹 기준만 변경)
- **실행 후 자동으로 Drug split vs Scaffold split 비교 리포트 출력**
- 각 모델의 Drop (Spearman 하락) 3단계 판정: 🟢 독립적 / 🟡 중간 / 🔴 심각

**핵심 로직**:
```python
from run_ml_all import train_evaluate_ml  # 기존 함수 재사용

scaffold_groups = np.load('data/scaffold_groups.npy')

for model_name, model_class in models.items():
    results = train_evaluate_ml(
        X, y, scaffold_groups,           # ← groups만 scaffold로 교체
        model_name, model_class,
        eval_mode='groupcv',              # GroupKFold 그대로 사용
        output_stem=f"{output_stem}_scaffold",
        oof_dir=oof_dir
    )
```

### 1-3. 실행 계획 ✅ 옵션 B 결정

#### 채택된 옵션: **옵션 B (완전 구현, Phase 2A/2B/2C × 6 ML)**

- **실행 시점**: Step 4 ML 학습 완료 직후 (Phase 2C JSON 생성 확인 후)
- **소요**: 실행 30~40분
- **결과**: 3개 JSON, 18 실험 (6 모델 × 3 Phase × GroupKFold 3-fold)
- **추가 지표**: #21 완전 달성 (ML 범위 내)

#### 실행 명령 (순서대로)

```bash
cd 20260420_new_pre_project_biso_Colon
pwd  # 확인

# 1단계: Scaffold 추출 (2~3분)
python3 scripts/compute_scaffolds.py

# 2단계: Scaffold split ML 실행 (30~40분)
python3 scripts/run_ml_scaffold_all.py 2>&1 | tee logs/colon_ml_scaffold.log
```

#### 왜 옵션 B를 선택했나?

| 옵션 | 범위 | 소요 | 가치 |
|------|------|:---:|------|
| A (최소) | Phase 2A × 6 ML | ~15분 | 개념 증명만 |
| **B (선택)** | **3 Phase × 6 ML** | **~40분** | **#21 완전 달성, Phase별 비교** |
| C (최대) | 3 Phase × 15 모델 | 2~3시간 | DL 스크립트 수정 필요, 복잡도 증가 |

옵션 B가 가장 균형 있음:
- 지표 #21 완전 충족
- Phase 2A vs 2B vs 2C 에서 scaffold 의존도 비교 가능
- 구현 복잡도 낮음 (ML만 대상)
- 시간 부담 적음

#### DL/Graph는 하지 않는 이유

- DL 스크립트 (`run_dl_all.py` 436 lines)의 scaffold split 적용은 **복잡도 높음**
- epochs=50, TabTransformer/CrossAttention 등 Attention 모델 포함
- DL 범위는 **향후 확장** 영역으로 보관
- ML만으로도 scaffold 의존도 측정 가능 (LightGBM/CatBoost가 주력 모델이므로)

### 1-4. 예상 결과 해석

#### 업계 벤치마크 기반 예상

| 측정 | Colon 현재 (drug split) | Scaffold split 예상 |
|------|:---:|:---:|
| LightGBM Phase 2A GroupCV | 0.4859 | **0.30~0.38** |
| CatBoost Phase 2A GroupCV | 0.4851 | 0.30~0.38 |
| 평균 | 0.4580 | 0.25~0.35 |

#### 해석 기준

```
Drug split → Scaffold split 하락 정도

🟢 하락 < 0.05 (0.48 → 0.43+)
   → 모델이 scaffold 독립적으로 일반화 가능
   → 진짜 새로운 chemotype도 예측 능력 있음
   → drug repurposing 관점에서 매우 긍정적

🟡 하락 0.05~0.15 (0.48 → 0.33~0.43)
   → 일부 scaffold 의존성 있음
   → 업계 평균 수준
   → 같은 계열 약물끼리는 잘 예측, 새 계열은 약함

🔴 하락 > 0.15 (0.48 → 0.33 이하)
   → scaffold 암기 심함
   → 모델이 "유사 구조 있으면 예측, 없으면 실패"
   → 새로운 chemotype 제안 시 신뢰 어려움
```

### 1-5. 실행 후 확인 사항

#### 자동 출력되는 비교 리포트 예시

`run_ml_scaffold_all.py`는 실행 마지막에 자동으로 다음을 출력:

```
Drug Split vs Scaffold Split 비교 (기존 GroupCV vs 신규 ScaffoldCV)

[Phase 2A]
  Model               | Drug Sp | Scaffold Sp | Drop  | Drop %
  ------------------------------------------------------------------
  LightGBM            | 0.4859  | 0.35xx      | +0.13 | +27%   🟡 중간 의존
  CatBoost            | 0.4851  | 0.32xx      | +0.16 | +33%   🔴 scaffold 의존 심함
  LightGBM_DART       | 0.4829  | 0.34xx      | +0.14 | +29%   🟡 중간 의존
  RandomForest        | 0.4524  | 0.38xx      | +0.07 | +15%   🟡 중간 의존
  XGBoost             | 0.4321  | 0.30xx      | +0.13 | +30%   🟡 중간 의존
  ExtraTrees          | 0.4093  | 0.28xx      | +0.13 | +32%   🟡 중간 의존

[Phase 2B], [Phase 2C] ... (같은 형식)
```

#### 후속 작업

1. **결과 해석**: Drop 분포 보고 Colon 모델의 chemotype 일반화 능력 평가
2. **프로토콜 업데이트**: `drug_repurposing_pipeline_protocol.md` Section 13 지표 #21 달성 기록
3. **문서 업데이트**: `COLON_STEP4_EXECUTION_GUIDE.md`의 32개 지표 맵에 #21 추가 (28/32 → 29/32)
4. **Git 커밋**: Task 1 완료 + 결과 파일들

### ✅ Task 1 실행 결과 (2026-04-22)

#### 1. 핵심 성과
- **지표 #21 (Scaffold Split)**: Lung ❌ → **Colon ✅ 최초 달성** 🎯
- **Scaffold Split 최고 성능**: LightGBM Phase 2B = **0.4041 ± 0.1169**
- **Drug Split 최고 성능 (비교)**: CatBoost Phase 2B = 0.4881 ± 0.0539
- **Lung 최고 대비**: -0.0149 (Lung 0.5030 vs Colon 0.4881)

#### 2. 실험 규모
- 총 30 JSON files, 129 experiments
  - Drug Split (GroupCV 3-fold): 45 experiments
  - Scaffold Split (ScaffoldCV 3-fold): 45 experiments
  - 5-Fold CV: 39 experiments (참고용, leakage 의심)

#### 3. 주요 발견 (Next Step 과제)

**3.1. Graph 모델의 Scaffold Drop 큼**
- GAT Phase 2A: -33.4%
- GAT Phase 2C: -32.5%
- GraphSAGE Phase 2C: -29.5%
- 원인 가설: KNN edge (k=7) 가 scaffold 경계 넘음 → 정보 누출
- **액션**: k=4 등 낮은 값으로 Graph 재실험 검토 (Step 4.5)

**3.2. ML/DL 모델 69% Overfitting (89/129)**
- Train Spearman: 0.94~1.0 vs Val Spearman: 0.3~0.5
- Gap: 0.5~0.6 (threshold 0.15 초과)
- 원인 가설: Feature 5,657 vs Sample 9,692 → overparametrized
- **액션**: FS 공격적 축소 (5,657 → 1,000), Regularization 강화 (Step 4.5)

**3.3. 5-Fold CV Leakage 확인**
- CatBoost Phase 2C = 0.8955 ± 0.0097 (std 매우 작음)
- Drug Split (CatBoost 2B = 0.4881 ± 0.0539) 대비 약 +0.4 높음
- 원인: 약물 정보가 train/val 양쪽에 → leakage
- **액션**: 5-Fold CV 결과는 "참고용" 으로 명확 표기, 주요 지표는 Drug/Scaffold Split 만

**3.4. 51% Unstable (66/129, std ≥ 0.05)**
- 원인 가설: 3-fold 분할로 fold 간 분산 큼
- **액션**: Repeated GroupKFold 또는 5-fold GroupKFold 검토

#### 4. 대시보드 구축 완료
- Streamlit 기반 인터랙티브 대시보드 완성
- 경로: `dashboard/app.py`
- 실행: `streamlit run dashboard/app.py`
- 구성:
  - Tab 1: Overview (파이프라인 전체)
  - Tab 4: Step 4 Modeling (메인)
    - Section 1: Summary (6 지표 카드)
    - Section 2: 인터랙티브 필터
    - Section 3: 전체 Ranking Table (CSV 다운로드)
    - Section 4: 4개 시각화 (Bar/Heatmap/Box/**Overfit Scatter**)
    - Section 5: 드릴다운 (Fold별 상세)
  - Tab 2, 3, 5, 6, 7: placeholder (향후 확장)
- 미완료 작업: `dashboard/TODO.md` 참조 (Holdout 파서, prefix 일반화 등)

#### 5. 관련 커밋 (2026-04-22)
- `f45cb27` feat(colon): Add pipeline dashboard MVP (Streamlit)
- `eb918c8` chore(colon): Add phase2_utils.py (copied from Lung)
- `e97dc37` feat(colon): Add Step 4 Modeling tab — full implementation (Phase 3)

GitHub: https://github.com/skkuaws0215/20260415_preproject_choi_protocol_v1_bisotest

---

## 🧬 Task 2: AlphaFold + Docking 검증 (Step 7.5 + Step 8 통합, D-3 구조)

### 2-0. 파이프라인 위치 확정 (v1.2)

**채택 구조**: **옵션 D-3 (Step 7.5 검증 + Step 8 KG 통합)**

#### 업데이트된 프로토콜 구조 (향후 v2.5 반영 예정)

```
Step 4. 모델 학습 (15 모델)
Step 5. 앙상블
Step 6. 외부 검증 (PRISM, COSMIC, CPTAC, CT)
Step 7. ADMET Gate → Top 15 통과
  ↓
Step 7.5. ⭐ AlphaFold + Docking (NEW, Task 2-A)
  ├─ 7.5-1. 타겟 추출 (Top 15 약물의 주요 타겟)
  ├─ 7.5-2. UniProt 서열 수집
  ├─ 7.5-3. 구조 예측 (PDB 없으면 AlphaFold)
  ├─ 7.5-4. Binding site 식별
  ├─ 7.5-5. Docking (AutoDock Vina)
  └─ 7.5-6. 친화도 → 최종 랭킹 multi-objective 통합
Step 8. Neo4j KG 적재
  ├─ 기존 노드/엣지 (약물-타겟-질병-경로)
  └─ ⭐ Docking 결과를 drug-target edge의 속성으로 추가 (NEW, Task 2-B)
       - binding_affinity_kcal_mol
       - binding_site
       - pdb_structure_source (experimental / alphafold)
       - docking_confidence
Step 9. LLM 연동
  └─ ⭐ Docking 정보 기반 질의 가능 (NEW)
       예: "약물 X의 타겟 Y와의 결합 친화도는?"
```

### 2-0-1. 왜 D-3 구조인가?

#### "한 번 실행, 두 번 활용" 원칙

**Step 7.5의 역할 (검증)**:
- Top 15 약물 의사결정에 직접 기여
- 낮은 친화도 약물 탈락 기준 (단, 보수적 적용)
- Multi-objective ranking 강화

**Step 8의 역할 (자원)**:
- Docking 결과를 Knowledge Graph 속성으로 영속화
- LLM 질의 시 활용 (Step 9)
- 향후 다른 질병 분석 시 cross-reference

**두 역할의 시너지**:
- 검증 결과를 **일회성으로 소비**하지 않음
- 저장된 docking 데이터가 **장기적 자산**으로 축적
- 논문 작성 시 "전체 파이프라인" 완결성

#### 업계 표준 준수

- 드러그 디스커버리 표준: **ADMET → Docking** (안전성 먼저, 분자 검증 후속)
- Top 15 수준이면 docking 계산 부담 현실적 (45건 내외)

### 2-1. 개념 (기존 내용 유지)

#### 목적
- **Step 4~7 파이프라인** (IC50 예측): 통계적 연관성 기반
- **Task 2 추가 검증**: 물리적/구조적 약물-타겟 결합 확인
- 두 증거가 일치하면 **임상 타당성 강화**
- **Step 8 통합**으로 Knowledge Graph의 depth 강화

#### 전체 흐름 (D-3 구조)

```
Step 7 완료 → Colon Top 15 약물 확정 (ADMET 통과)
    ↓
[Step 7.5-1] 각 약물의 타겟 유전자 확인
    ↓ drug_target_mapping.parquet
[Step 7.5-2] 타겟 단백질의 UniProt ID → 서열 확보
    ↓
[Step 7.5-3] 구조 준비
┌─────────────────────────────────────┐
│ A. 기존 PDB 구조 있음  → 그대로 사용 │
│ B. 구조 없음           → AlphaFold 예측 │
└─────────────────────────────────────┘
    ↓
[Step 7.5-4] Binding site 식별
    ├─ 알려진 site (문헌)
    └─ 자동 탐지 (pocket detection)
    ↓
[Step 7.5-5] Docking
AutoDock Vina / Glide 등으로 약물 docking
    ↓
Binding affinity (kcal/mol) 계산
    ↓
[Step 7.5-6] 분석 + Multi-objective ranking 통합
- 강한 결합 (< -8 kcal/mol): 강한 후보
- 중간 결합 (-6 ~ -8): 보통 후보
- 약한 결합 (> -6): 재고
    ↓
IC50 예측 + ADMET + Docking 친화도 → 최종 랭킹
    ↓
─────────────── Step 8 ───────────────
    ↓
[Step 8 통합] Neo4j KG에 docking 결과 적재
- drug 노드와 target 노드를 연결하는 edge에 속성 추가
- LLM이 질의 가능한 형태로 영속화
```

### 2-2. 필요 리소스

#### 단백질 구조 예측
- **AlphaFold3** (2024 출시)
  - DeepMind API 또는 Google Colab
  - 비상업적 무료
  - Colab 한계 있음
- **AlphaFold2** (기존)
  - 로컬 GPU 필요 (NVIDIA)
  - **M4 Apple Silicon 불가**
- **ColabFold** (대안)
  - Google Colab에서 AlphaFold2 간소화 버전
  - 무료 GPU 활용
  - 실행 가능

#### 도킹 소프트웨어
- **AutoDock Vina** (오픈소스, 권장)
  - 무료, 크로스 플랫폼
  - Python wrapper 있음
- **Glide** (Schrödinger)
  - 상용, 라이선스 필요
- **OpenMM + Rosetta**
  - 오픈소스, 학습 곡선 있음

#### 추천 조합
```
AlphaFold3 (DeepMind API 또는 Colab)
  + AutoDock Vina (오픈소스)
  + PyMOL (시각화)
```

### 2-3. 구현 계획

#### Step 1: 타겟 단백질 서열 수집

```python
# Top 15 약물의 타겟 유전자 추출
top15 = pd.read_parquet('results/colon_top15_drugs.parquet')
drug_targets = pd.read_parquet('data/drug_target_mapping.parquet')

top15_targets = drug_targets.merge(top15, on='canonical_drug_id')
unique_genes = top15_targets['target_gene'].unique()
# 예상: 약 20~40개 unique gene

# UniProt ID 조회 (API 또는 manual)
for gene in unique_genes:
    # UniProt API로 서열 가져오기
    sequence = fetch_uniprot_sequence(gene)
```

#### Step 2: 구조 예측 (AlphaFold)

```python
# 각 gene 서열에 대해 AlphaFold 실행
# 방법 1: AlphaFold3 API
# 방법 2: ColabFold (무료)
# 방법 3: 로컬 AlphaFold2 (GPU 있을 때)

# 결과: PDB 파일 (3D 구조)
```

#### Step 3: Docking

```python
from vina import Vina  # AutoDock Vina Python wrapper

v = Vina(sf_name='vina')
v.set_receptor('target.pdbqt')  # 예측된 단백질 구조
v.set_ligand_from_file('drug.pdbqt')  # 약물 SMILES → 3D conformer

# Binding site 정의 (pocket detection 또는 알려진 site)
v.compute_vina_maps(center=[x, y, z], box_size=[20, 20, 20])

# Docking 실행
v.dock(exhaustiveness=32, n_poses=10)
energy = v.energies()[0][0]  # 가장 강한 결합 에너지
```

#### Step 4: 통합 분석

```python
# IC50 예측 + Docking 친화도 결합
final_ranking = pd.DataFrame({
    'drug_name': ...,
    'predicted_ic50': ...,           # Step 4에서
    'binding_affinity_kcal_mol': ...,  # Task 2에서
    'prism_hit_rate': ...,            # Step 6에서
    'clinical_trials': ...,
})

# Multi-objective score
final_ranking['composite_score'] = (
    -0.3 * final_ranking['predicted_ic50'] +  # 낮을수록 좋음
    -0.3 * final_ranking['binding_affinity_kcal_mol'] +  # 낮을수록 좋음 (강한 결합)
    0.2 * final_ranking['prism_hit_rate'] +
    0.2 * final_ranking['clinical_trials_norm']
)
```

#### Step 5: Neo4j KG 통합 (Step 8) ⭐ v1.2 추가

```python
from neo4j import GraphDatabase

# Step 7.5에서 계산된 docking 결과를 Step 8 Neo4j에 속성으로 저장
driver = GraphDatabase.driver(neo4j_uri, auth=(user, password))

with driver.session() as session:
    for _, row in docking_results.iterrows():
        # drug - target 관계에 docking 속성 추가
        query = """
        MATCH (d:Drug {canonical_drug_id: $drug_id})
        MATCH (t:Target {gene_symbol: $target_gene})
        MERGE (d)-[r:TARGETS]->(t)
        SET r.binding_affinity_kcal_mol = $affinity,
            r.binding_site = $site,
            r.pdb_structure_source = $pdb_source,
            r.docking_confidence = $confidence,
            r.docking_date = $today,
            r.docking_tool = $tool
        """
        session.run(query,
            drug_id=row['canonical_drug_id'],
            target_gene=row['target_gene'],
            affinity=row['binding_affinity_kcal_mol'],
            site=row['binding_site'],
            pdb_source=row['pdb_source'],  # 'experimental' or 'alphafold'
            confidence=row['pLDDT'],  # AlphaFold 신뢰도 (있으면)
            today=datetime.now().date(),
            tool='AutoDock Vina')
```

**이 통합의 가치**:
- Step 9 LLM이 "약물 X가 타겟 Y와 얼마나 강하게 결합하나?" 질의 가능
- 다른 질병 파이프라인에서 **재사용** (cross-disease reference)
- 향후 신규 약물 추가 시 **기존 docking 결과와 비교** 가능

### 2-4. 예상 소요

| 작업 | 소요 |
|------|:---:|
| AlphaFold 환경 학습 | 1주 |
| ColabFold 파이프라인 구축 | 3~5일 |
| AutoDock Vina 학습 + 스크립트 | 5~7일 |
| Colon Top 15 타겟 구조 예측 | 2~3일 |
| Docking 실행 + 분석 | 3~5일 |
| 통합 분석 + 문서화 | 2~3일 |
| **합계** | **약 4~6주** |

### 2-5. 예상 가치

#### 논문 기여도
- **Drug repurposing in silico validation**의 완결성
- 통계적 연관성 + 구조적 근거 동시 제시
- Top 저널 투고 가능 수준

#### 실제 활용
- Colon 파이프라인 검증 후 다른 질병에도 적용 가능
- AlphaFold3 최신 기술 활용 사례

### 2-6. 일정

- **전제**: Step 7 (ADMET Gate) 완료, Top 15 약물 확정
- **시점**: Step 4~7 완료 후 (2026년 5~6월 예상)
- **소요**: 4~6주 (Step 7.5 구현 4~5주 + Step 8 통합 3~5일)

### 2-7. 프로토콜 v2.5 반영 제안 (v1.2 신규) ⭐

**구현 완료 후** 팀4 원본 프로토콜을 v2.4 → **v2.5**로 공식 업데이트 제안:

#### v2.5에서 수정할 섹션

**Section 3 (전체 파이프라인 구조)**:
```
기존:
Step 7. ADMET Gate

→ 변경:
Step 7. ADMET Gate
Step 7.5. AlphaFold + Docking 검증 (v2.5 신규)
```

**Section 11 이후 신설 — Section 11.5**:
- 새로운 섹션: "11.5. AlphaFold + Docking 검증 (Step 7.5)"
- 11.5-1. 개요
- 11.5-2. 구현 방법
- 11.5-3. 필요 리소스 (AlphaFold, Vina)
- 11.5-4. 결과 해석 기준 (-8, -6 kcal/mol 임계값)
- 11.5-5. Multi-objective ranking 통합

**Section 12 (Neo4j KG)**:
- 기존 노드/엣지 설명 유지
- **추가**: drug-target edge의 속성에 docking 결과 포함
- 예시 쿼리: "친화도 -8 이하 약물 검색"

**Section 12-A (LLM 연동)**:
- **추가**: Docking 속성 기반 질의 예시
  - "약물 X의 모든 타겟에 대한 binding affinity 보여줘"
  - "친화도 상위 5개 약물-타겟 페어는?"

**Section 17 (변경 이력)**:
- v2.5 엔트리 추가: "AlphaFold + Docking 공식 도입 (Step 7.5 신설), Step 8 docking 속성 통합, Section 12-A LLM 질의 확장"

#### 소급 적용 (Lung)

- Lung도 Step 7까지 완료 상태
- **Lung Top 15 약물에 대해 Step 7.5 소급 적용 가능**
- 이를 통해 Lung-Colon 비교 시 docking 친화도 비교 추가

**소급 적용 순서 권장**:
1. Colon에서 Step 7.5 파이프라인 검증
2. Colon 결과로 파이프라인 안정화
3. Lung에 소급 적용
4. 두 질병 비교 리포트 작성

### 2-8. 체크리스트 (Task 2, D-3 구조 반영)

#### Step 7.5 구현 (Task 2-A)
- [ ] 사전: Step 7 완료, Top 15 약물 확정
- [ ] AlphaFold3 또는 ColabFold 환경 구축
- [ ] Top 15 약물의 타겟 유전자 추출 (drug_target_mapping.parquet)
- [ ] 각 타겟의 UniProt 서열 수집 (API 또는 수동)
- [ ] 단백질 구조 예측
  - [ ] PDB 존재 확인 (experimental)
  - [ ] 없으면 AlphaFold 예측
- [ ] AutoDock Vina 환경 구축
- [ ] 약물 3D conformer 생성 (RDKit)
- [ ] Binding site 탐지 또는 문헌 기반 정의
- [ ] Docking 실행 (Top 15 × 평균 2~3 타겟 ≈ 30~45건)
- [ ] Binding affinity 집계 (kcal/mol)
- [ ] IC50 + ADMET + Docking 통합 Multi-objective ranking

#### Step 8 KG 통합 (Task 2-B)
- [ ] Neo4j 스키마 확장: drug-target edge에 docking 속성 추가
- [ ] `ingest_docking_results.py` 작성
- [ ] 기존 Neo4j 인스턴스에 docking 결과 적재
- [ ] Cypher 쿼리 검증 (샘플 질의 통과)
- [ ] Section 12 문서 업데이트

#### Step 9 LLM 연동 (Task 2-C)
- [ ] Ollama prompt 템플릿 업데이트 (docking 정보 포함)
- [ ] 예시 질의 테스트 ("친화도 -8 이하 약물은?")
- [ ] Section 12-A 문서 업데이트

#### 프로토콜 v2.5 공식 반영 (Task 2-D)
- [ ] 구현 완료 + Colon 검증 통과 확인
- [ ] `drug_repurposing_pipeline_protocol.md` v2.4 → v2.5 업데이트
  - [ ] Section 3: Step 7.5 추가
  - [ ] Section 11.5 신설
  - [ ] Section 12: docking 속성 추가
  - [ ] Section 12-A: LLM 질의 확장
  - [ ] Section 17: v2.5 이력
- [ ] Lung 소급 적용 계획 수립
- [ ] Git 커밋: "feat(protocol): v2.5 - Add AlphaFold + Docking (Step 7.5) + KG integration"

---

## 📊 진행 상태 추적

### 체크리스트

#### Task 1: Scaffold Split

**구현 단계**:
- [x] ~~사전: Step 5 앙상블 완료~~ ← 결정 변경: Step 4 ML 완료 직후 실행
- [x] `compute_scaffolds.py` 구현 (2026-04-21, 192 lines)
- [x] `run_ml_scaffold_all.py` 구현 (2026-04-21, 216 lines, 옵션 B 채택)
- [x] `COLON_ADVANCED_VALIDATION_PLAN.md` 문서화

**실행 단계** (대기):
- [ ] Step 4 ML 학습 완료 대기 (Phase 2C JSON 생성 확인)
- [ ] Scaffold 스크립트 2개를 `scripts/` 폴더에 배치
- [ ] `python3 scripts/compute_scaffolds.py` 실행
- [ ] `scaffold_groups.npy` 생성 확인 (unique scaffolds 수, 분포)
- [ ] 3-fold 불균형 경고 확인
- [ ] `python3 scripts/run_ml_scaffold_all.py` 실행
- [ ] 자동 비교 리포트 확인 (Drop 분포)
- [ ] 해석: scaffold 의존성 평가 (🟢/🟡/🔴)

**후속 업데이트**:
- [ ] 프로토콜 `drug_repurposing_pipeline_protocol.md` Section 13 #21 상태 업데이트
- [ ] `COLON_STEP4_EXECUTION_GUIDE.md`의 32개 지표 맵 갱신 (29/32)
- [ ] Git 커밋: "feat(colon): Add Scaffold Split validation (Task 1)"

#### Task 2: AlphaFold + Docking (Step 7.5 + Step 8, D-3 구조)
→ 상세 체크리스트는 **Section 2-8** 참조

**요약**:
- [ ] **Task 2-A**: Step 7.5 구현 (Colon Top 15 기준)
- [ ] **Task 2-B**: Step 8 Neo4j KG 통합
- [ ] **Task 2-C**: Step 9 LLM 연동 확장
- [ ] **Task 2-D**: 프로토콜 v2.4 → v2.5 공식 반영
- [ ] Lung 소급 적용 (선택)

---

## 🎯 이 문서의 위치

### 현재 위치
```
20260420_new_pre_project_biso_Colon/
  ├─ COLON_STEP4_EXECUTION_GUIDE.md     (Step 4 실행 가이드, 2026-04-21)
  └─ COLON_ADVANCED_VALIDATION_PLAN.md  (이 문서, Step 5.5/7.5 확장 계획)
```

### 향후 통합 옵션
- **옵션 A**: Step 5/7 완료 후 `COLON_STEP4_EXECUTION_GUIDE.md`의 "다음 단계" 섹션에 통합
- **옵션 B**: 별도 문서 유지, 다른 질병 (IPF, RA) 적용 시 재사용
- **옵션 C**: 프로토콜 v2.4로 승격 (Lung 이후 추가된 확장 단계로 공식화)

**결정은 Task 1 실행 후** (2026년 4월 말 ~ 5월 초 예상).

---

## 📚 참고 자료

### Scaffold Split
- [RDKit Murcko Scaffolds 문서](https://www.rdkit.org/docs/source/rdkit.Chem.Scaffolds.MurckoScaffold.html)
- Bemis & Murcko (1996) "The Properties of Known Drugs. 1. Molecular Frameworks"
- [DeepChem Scaffold Splitter](https://deepchem.readthedocs.io/en/latest/api_reference/splits.html#scaffold-splitter)

### AlphaFold
- [AlphaFold3 (DeepMind)](https://deepmind.google/technologies/alphafold/)
- [AlphaFold2 Github](https://github.com/google-deepmind/alphafold)
- [ColabFold](https://github.com/sokrypton/ColabFold)

### Docking
- [AutoDock Vina](https://vina.scripps.edu/)
- [Vina Python API](https://autodock-vina.readthedocs.io/en/latest/docking_python.html)
- [OpenBabel (ligand preparation)](https://openbabel.org/)

---

## 📝 변경 이력

| 날짜 | 버전 | 변경 | 작성자 |
|------|:---:|------|:---:|
| **2026-04-22** | **v1.3** | **Task 1 (Scaffold Split) 실행 완료 반영. 지표 #21 (Scaffold Split) Colon 최초 달성 기록. Task 1 실행 결과 서브섹션 신설 (핵심 성과 / 실험 규모 / 주요 발견 / 대시보드 / 커밋). 주요 발견 4가지 및 각 액션 아이템 명시 (Step 4.5 로 연결). 대시보드 (Streamlit MVP) 구축 결과 반영.** | **Claude + 사용자** |
| 2026-04-21 | v1.0 | 초안 작성 (Task 1 + Task 2) | Claude + 사용자 |
| 2026-04-21 | v1.1 | Task 1 구현 완료 반영, 실행 시점 변경 (Step 5 후 → Step 4 ML 후), 옵션 B 채택, 체크리스트 업데이트 | Claude + 사용자 |
| **2026-04-21** | **v1.2** | **Task 2 위치 확정 = D-3 구조 (Step 7.5 검증 + Step 8 KG 적재)**. Section 2-0 신설 (위치 결정 근거), Section 2-3-5 신설 (Neo4j 통합 코드), Section 2-7 신설 (프로토콜 v2.5 반영 제안), Section 2-8 상세 체크리스트 추가. 구현은 Colon Step 4~7 완료 후. | **Claude + 사용자** |
