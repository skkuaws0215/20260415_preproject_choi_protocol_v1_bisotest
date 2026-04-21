# Colon Step 4 실행 가이드

> **작성일**: 2026-04-21  
> **최종 수정**: 2026-04-21 (v1.1: Scaffold Split 전면 반영)  
> **대상**: Colon Pipeline Step 4 (모델 학습)  
> **전제**: Step 3 FE + Step 3.5 FS 완료 상태 (`fe_qc/20260420_colon_fe_v2/features_slim.parquet` 존재)
> **프로토콜**: v2.4 (Scaffold Split 공식 도입)

---

## 📋 개요

### 이번 Step 4에서 할 일

**모델 15개 (프로토콜 v2.4 Section 8-2 준수):**
- ML 6개: LightGBM, LightGBM DART, XGBoost, CatBoost, RandomForest, ExtraTrees
- DL 7개: FlatMLP, ResidualMLP, FTTransformer, CrossAttention, TabNet, WideDeep, TabTransformer
- Graph 2개: GraphSAGE, GAT

**실험 개수 (v1.1 업데이트):**

1. Phase 2A 학습 입력 생성 (`X_numeric.npy`, `y_train.npy`)
2. Phase 2B/2C 학습 입력 생성 (`X_numeric_smiles.npy`, `X_numeric_context_smiles.npy`, `smiles_token_ids.npy`, `context_codes.npy`)

**[Drug Split] 기존 프로토콜 v2.3**:
3. ML 6개 × 3 평가 (holdout+5foldcv+groupcv) × 3 Phase = **54 실험**
4. DL 7개 × 3 평가 × 3 Phase = **63 실험**
5. Graph 2개 × GroupCV × 3 Phase = **6 실험** (v1.0 대비 증가: 2A만 → 2A/2B/2C)

**Drug split 합계: 123 실험**

**[Scaffold Split] 프로토콜 v2.4 신규 (Lung 미진행 #21 달성)**:
6. ML 6개 × ScaffoldCV × 3 Phase = **18 실험**
7. DL 7개 × ScaffoldCV × 3 Phase = **21 실험**
8. Graph 2개 × ScaffoldCV × 3 Phase = **6 실험**

**Scaffold split 합계: 45 실험**

**총 168 실험** (Drug 123 + Scaffold 45)

> ⚠️ **32개 지표 커버리지 주의**: 프로토콜 v2.4 Section 13에 명시된 **32개 지표 체크리스트** 중 Step 4 학습 단독으로 계산되는 것은 일부에 불과함. 앙상블 지표는 Step 5, 약물 랭킹 지표는 Step 6에서 계산. 상세는 아래 "📊 32개 지표 커버리지 맵" 섹션 참조.
>
> **v1.1 변경점**: Scaffold split 추가로 Lung 대비 **지표 #21 달성** (일반화 2/6 → 3/6). 전체 커버리지 목표: 25/32 (Lung) → 28/32 (Colon).

### Lung 대비 Colon의 주요 변경점

| 항목 | Lung | Colon | 이유 |
|------|:---:|:---:|------|
| 샘플 수 | 125,427 | 9,692 | 데이터 규모 차이 (약 13배) |
| DL epochs | 30 | 50 | 샘플 적어 충분히 학습 필요 |
| TabTransformer early stop | `val_sp < 0.57` 시 중단 | 제거 | BRCA 기준이라 Colon과 무관 |
| GraphSAGE k (KNN) | 10 | 7 | 샘플 수 대비 비율 조정 |
| Graph device | CPU 강제 | MPS 우선 시도 | Colon 작아서 MPS 가능 |
| output_stem | `lung_*`, `choi_*` | `colon_*` | 질병별 식별 |

---

## 🗂️ 파일 배치

### 복사할 파일 (작업 디렉토리 → Colon 프로젝트)

```
/home/claude/colon_step4/
├── prepare_phase2a_data.py         → Colon/scripts/
├── prepare_phase2bc_data.py        → Colon/scripts/  (덮어쓰기)
├── run_ml_all.py                   → Colon/scripts/  (덮어쓰기)
├── run_dl_all.py                   → Colon/scripts/  (덮어쓰기)
├── run_graph_sage_mps.py           → Colon/scripts/  (덮어쓰기)
└── gat_modification_guide.py       → (Cursor에서 보고 수정용)
```

### 유지되는 기존 Colon 구조

```
20260420_new_pre_project_biso_Colon/
├── scripts/
│   ├── [기존 Step 2 스크립트들]
│   ├── feature_selection.py
│   ├── phase2_utils.py             (Lung에서 복사됨, 수정 불필요)
│   ├── data_validation.py          (Lung에서 복사됨, 수정 불필요)
│   ├── prepare_phase2a_data.py     ⬅ 새로 추가
│   ├── prepare_phase2bc_data.py    ⬅ Colon용으로 덮어쓰기
│   ├── run_ml_all.py               ⬅ Colon용으로 덮어쓰기
│   ├── run_dl_all.py               ⬅ Colon용으로 덮어쓰기
│   ├── run_graph_sage_mps.py       ⬅ Colon용으로 덮어쓰기
│   └── run_graph_gat_mps.py        ⬅ 수동 수정 (가이드 참조)
├── fe_qc/20260420_colon_fe_v2/
│   ├── features_slim.parquet        (입력)
│   └── features/labels.parquet      (입력)
├── data/                            ⬅ 새로 생성됨
│   ├── X_numeric.npy               (생성됨)
│   ├── y_train.npy                 (생성됨)
│   ├── X_numeric_smiles.npy        (생성됨)
│   ├── X_numeric_context_smiles.npy (생성됨)
│   ├── smiles_token_ids.npy        (생성됨)
│   ├── context_codes.npy           (생성됨)
│   ├── context_vocab.json          (생성됨)
│   └── drug_features.parquet        (사전 준비 필요 ⚠️)
└── results/                         ⬅ 새로 생성됨 (학습 결과)
```

---

## 🚨 사전 체크리스트 (실행 전 필수)

### 체크 1: `drug_features.parquet` 위치 확인

Phase 2B/2C는 `data/drug_features.parquet`의 `canonical_smiles` 컬럼을 사용함.

```bash
cd 20260420_new_pre_project_biso_Colon

# 후보 위치 확인
ls -la data/drug_features.parquet 2>/dev/null && echo "OK: data/"
ls -la fe_qc/20260420_colon_fe_v2/drug_features.parquet 2>/dev/null && echo "FOUND: fe_qc/"
find . -name "drug_features.parquet" -not -path "*/node_modules/*" 2>/dev/null
```

파일이 없으면:
- Step 3 FE 산출물에서 복사
- 또는 S3에서 다운로드:
  ```bash
  aws s3 cp s3://say2-4team/20260408_new_pre_project_biso/20260420_new_pre_project_biso_Colon/data/drug_features.parquet data/
  ```

### 체크 2: `canonical_smiles` 컬럼 존재 확인

```bash
python3 -c "
import pandas as pd
df = pd.read_parquet('data/drug_features.parquet')
print('Columns:', list(df.columns))
print('Shape:', df.shape)
if 'canonical_smiles' in df.columns:
    coverage = df['canonical_smiles'].notna().sum() / len(df) * 100
    print(f'canonical_smiles coverage: {coverage:.1f}%')
else:
    print('⚠️ canonical_smiles 컬럼 없음')
"
```

### 체크 3: 필수 패키지

```bash
python3 -c "
import lightgbm, xgboost, catboost, sklearn
import torch
print('torch:', torch.__version__)
print('MPS available:', torch.backends.mps.is_available())
try:
    import torch_geometric
    print('PyG:', torch_geometric.__version__)
except ImportError:
    print('⚠️ PyTorch Geometric 미설치 (Graph 모델 실행 전 필요)')
try:
    from rdkit import Chem
    print('RDKit: OK')
except ImportError:
    print('⚠️ RDKit 미설치 (Phase 2B/2C 실행 전 필요)')
"
```

패키지 설치 (필요시):
```bash
pip install lightgbm xgboost catboost scikit-learn
pip install torch torch_geometric
pip install rdkit-pypi
```

---

## 🚀 실행 순서

### Step 0: 파일 배치

Cursor/터미널에서:

```bash
cd 20260420_new_pre_project_biso_Colon

# Claude가 생성한 파일을 scripts/로 복사
# (사용자님이 /mnt/user-data/outputs/에서 로컬로 받은 후)
cp ~/Downloads/prepare_phase2a_data.py scripts/
cp ~/Downloads/prepare_phase2bc_data.py scripts/
cp ~/Downloads/run_ml_all.py scripts/
cp ~/Downloads/run_dl_all.py scripts/
cp ~/Downloads/run_graph_sage_mps.py scripts/

# 확인
ls -la scripts/*.py | grep -E "prepare_phase|run_ml|run_dl|run_graph"
```

### Step 1: Phase 2A 입력 생성 (~1분)

```bash
cd 20260420_new_pre_project_biso_Colon
python scripts/prepare_phase2a_data.py
```

**기대 출력**:
```
X_numeric shape: (9692, ~5660)
y_train shape: (9692,)
✓ Saved: data/X_numeric.npy (~220 MB)
✓ Saved: data/y_train.npy (~38 KB)
```

**검증**:
```bash
ls -la data/X_numeric.npy data/y_train.npy
python3 -c "import numpy as np; print(np.load('data/X_numeric.npy').shape, np.load('data/y_train.npy').shape)"
```

### Step 2: Phase 2B/2C 입력 생성 (~5-10분)

```bash
python scripts/prepare_phase2bc_data.py
```

**기대 출력**:
```
X_numeric:             (9692, ~5660)
X_numeric_smiles:      (9692, ~5724)   (+64)
X_numeric_context_smiles: (9692, ~5788) (+128)
SMILES 커버리지: ~82%
```

**검증**:
```bash
ls -la data/*.npy
```

### Step 3: ML 모델 학습 (~30분~2시간, CPU 기반)

**실행 전 `run_graph_gat_mps.py` 수동 수정** (Step 5에서 필요):

```bash
# GAT 수정 (gat_modification_guide.py 참조)
cd scripts/
cp run_graph_gat_mps.py run_graph_gat_mps.py.lung_bak

# 자동 치환 (lung → colon)
sed -i '' 's/lung_numeric_graph/colon_numeric_graph/g' run_graph_gat_mps.py

# 수동 편집 필요한 곳 (에디터에서):
#   1. device = 'cpu' → MPS 자동 선택
#   2. build_knn_graph(X, k=10) → k=7
#   3. base_dir = Path(__file__).parent → Path(__file__).parent.parent
#   4. features_path = base_dir / "features_slim.parquet" 
#        → base_dir / "fe_qc" / "20260420_colon_fe_v2" / "features_slim.parquet"

cd ..
```

**ML 실행**:

```bash
# 전체 ML (Phase 2A, 2B, 2C 순차, 모든 모델/평가)
python scripts/run_ml_all.py 2>&1 | tee logs/colon_ml_all.log
```

**예상 소요**:
- Phase 2A: ~10분 (6 모델 × 3 평가 = 18 실험)
- Phase 2B: ~12분
- Phase 2C: ~15분
- **합계: ~40분~1시간** (CatBoost가 가장 느림)

**결과 파일**:
```
results/
├── colon_numeric_ml_v1_holdout.json
├── colon_numeric_ml_v1_5foldcv.json
├── colon_numeric_ml_v1_groupcv.json
├── colon_numeric_ml_v1_oof/
│   ├── LightGBM.npy
│   ├── LightGBM_DART.npy
│   ├── XGBoost.npy
│   ├── CatBoost.npy
│   ├── RandomForest.npy
│   └── ExtraTrees.npy
├── colon_numeric_smiles_ml_v1_*.json
├── colon_numeric_smiles_ml_v1_oof/
├── colon_numeric_context_smiles_ml_v1_*.json
└── colon_numeric_context_smiles_ml_v1_oof/
```

### Step 4: DL 모델 학습 (~1-3시간, MPS 기반)

```bash
python scripts/run_dl_all.py 2>&1 | tee logs/colon_dl_all.log
```

**예상 소요**:
- Phase 2A: ~30분 (7 모델 × 3 평가 = 21 실험, epochs=50)
- Phase 2B: ~35분
- Phase 2C: ~40분
- **합계: ~1.5~2시간**

**주의**:
- MPS 사용 중 Activity Monitor로 GPU 사용률 확인
- OOM 발생 시 batch_size 조정 필요 (현재 128)

### Step 5: Graph 모델 학습 (~20-40분)

```bash
# GraphSAGE
python scripts/run_graph_sage_mps.py 2>&1 | tee logs/colon_graph_sage.log

# GAT
python scripts/run_graph_gat_mps.py 2>&1 | tee logs/colon_graph_gat.log
```

결과는 `results/colon_numeric_graph_v1_oof/`와 `results/colon_numeric_graph_v1_groupcv.json`에 저장됨.

### Step 6: 결과 요약 및 앙상블 (선택, ~10분)

```bash
# 결과 통합 테이블
python scripts/generate_all_phases_summary.py
python scripts/phase2_comprehensive_metrics_analysis.py

# 앙상블 24조합
python scripts/phase3_ensemble_analysis.py
```

---

## 🧬 Scaffold Split 실행 (프로토콜 v2.4 신규)

### 개요

Drug split이 완료된 후 실행. Murcko scaffold 기준으로 GroupKFold 재분할하여 **unseen chemotype** 일반화 평가.

### 전제 조건

모든 drug split 학습 완료:
- `colon_numeric_context_smiles_ml_v1_*.json` (3개)
- `colon_numeric_context_smiles_dl_v1_*.json` (3개)
- `colon_numeric_context_smiles_graph_v1_groupcv.json` (1개)

### 실행 순서

#### 1단계: Scaffold 추출 (2~3분)

```bash
cd 20260420_new_pre_project_biso_Colon
python scripts/compute_scaffolds.py 2>&1 | tee logs/compute_scaffolds.log
```

**생성되는 파일**:
- `data/scaffold_groups.npy` — pair별 scaffold ID (9692,)
- `data/scaffold_mapping.json` — drug ↔ scaffold 매핑
- `data/scaffold_stats.json` — 분포 통계

**확인할 것**:
```
Unique scaffolds: ~100~150 (예상)
Max pairs/scaffold: 500 미만이면 양호
3-fold 불균형 경고: 단일 scaffold가 fold 50% 초과 시 주의
```

#### 2단계: ML Scaffold Split (40분)

```bash
python scripts/run_ml_scaffold_all.py 2>&1 | tee logs/colon_ml_scaffold.log
```

**실행 내용**: 3 Phase × 6 ML × GroupKFold 3-fold = **18 실험**

**출력**:
- `results/colon_numeric_ml_v1_scaffoldcv.json`
- `results/colon_numeric_smiles_ml_v1_scaffoldcv.json`
- `results/colon_numeric_context_smiles_ml_v1_scaffoldcv.json`
- `results/colon_numeric_*_ml_v1_scaffold_oof/*.npy`

**자동 리포트**: Drug vs Scaffold 비교 (🟢/🟡/🔴 판정)

#### 3단계: DL Scaffold Split (1.5~2시간)

```bash
python scripts/run_dl_scaffold_all.py 2>&1 | tee logs/colon_dl_scaffold.log
```

**실행 내용**: 3 Phase × 7 DL × GroupKFold 3-fold = **21 실험**

#### 4단계: Graph Scaffold Split (50분~1시간)

```bash
python scripts/run_graph_scaffold_all.py 2>&1 | tee logs/colon_graph_scaffold.log
```

**실행 내용**: 3 Phase × 2 Graph × GroupKFold 3-fold = **6 실험**

> ⚠️ **Graph Scaffold 주의**: KNN edge가 scaffold 경계를 넘을 수 있어 **완전 엄격한 검증은 불가능**. 상대 비교만 유효. (프로토콜 v2.4 Section 8-2 주의 2 참조)

### 자동 순차 실행 (전체)

사용자가 자리를 비울 때를 위한 자동 쉘 스크립트:

```bash
cd 20260420_new_pre_project_biso_Colon

# 백그라운드 실행 (터미널 꺼져도 계속)
nohup ./scripts/run_step4_all.sh > logs/step4_master.log 2>&1 &
echo $! > logs/step4_master.pid
disown
```

**실행 단계 (자동)**:
1. DL drug split
2. Graph drug split
3. compute_scaffolds
4. ML scaffold split
5. DL scaffold split
6. Graph scaffold split

**총 소요**: 약 6~7시간

**모니터링**:
```bash
tail -f logs/step4_master.log
```

### 결과 해석 (Drug vs Scaffold Drop)

각 모델에 대해 자동 계산되는 Drop:

| Drop | 판정 | 의미 |
|:----:|:----:|------|
| < 0.05 | 🟢 scaffold 독립적 | 새 chemotype 예측 우수 |
| 0.05~0.15 | 🟡 중간 의존 | 업계 평균 수준 |
| > 0.15 | 🔴 scaffold 의존 심함 | 새 chemotype 예측 어려움, 암기 경향 |

### Scaffold Split 결과 → 프로토콜 Section 13 업데이트

모두 완료되면:
- **지표 #21 (Scaffold split)** ❌ → ✅
- Colon 일반화 지표: 2/6 (Lung) → **3/6**
- 전체 지표 달성: 25/32 (Lung) → **28/32 (Colon 목표)**

---

## 🔍 중간 점검 포인트

### Phase 2A ML 완료 시점

가장 먼저 나오는 결과. 최소한 다음이 괜찮아야 함:
- **CatBoost / LightGBM / RandomForest GroupCV Spearman > 0.3**
- Gap < 0.2 (과적합 체크)

Lung 참고치: CatBoost GroupCV 2A = 0.4765.
Colon 예상치: 샘플 작으니 **0.35~0.45 범위**면 정상 추정 (확정은 실행해야 앎).

### 과적합 판단

`overfitting_check`, `stability_check` 확인:
- `overfitting_check.is_overfitting`: True면 주의
- Train-Val gap이 Spearman 기준 0.3 이상이면 과적합 심함

→ Colon에서 TabTransformer early stop 제거했으니 과적합 여부 직접 확인 필요.

---

## ⚠️ 트러블슈팅

### 문제 1: `ModuleNotFoundError: phase2_utils`

```bash
# scripts/ 디렉토리에서 실행해야 함
cd 20260420_new_pre_project_biso_Colon
python scripts/run_ml_all.py  # OK (경로 자동 해결)

# 또는
cd scripts/
python run_ml_all.py  # OK
```

### 문제 2: `FileNotFoundError: features_slim.parquet`

경로 확인:
```bash
ls -la fe_qc/20260420_colon_fe_v2/features_slim.parquet
```

없으면 Step 3.5 FS 결과를 해당 경로에 배치.

### 문제 3: MPS Out of Memory

```python
# run_dl_all.py에서 batch_size 줄이기
batch_size=128  →  batch_size=64  →  batch_size=32
```

### 문제 4: LightGBM/XGBoost 경고

기본 설정 그대로 (`verbose=-1`, `verbosity=0`)라 대부분 억제됨.
경고 남으면 무시 가능.

### 문제 5: GroupCV에서 fold 불균등

Colon 약물 수가 295개라 GroupKFold(n_splits=3)이면 fold당 ~100 drugs.
샘플 수 차이는 **정상적인 상황** (fold당 ~3,000~3,500 pairs 정도 예상).

### 문제 6: 실행 중단 후 재시작

- ML: OOF 파일 skip 로직 없음 → 처음부터 다시 돌아감 (출력 JSON은 덮어쓰기)
- DL: `run_dl_all.py`는 GroupCV OOF 파일 있으면 skip (안전장치)
- Graph: skip 로직 없음 → 덮어쓰기

부분 실행 원할 경우:
```python
# run_phase2a_only.py 류 개별 래퍼 사용
python scripts/run_phase2a_only.py  # Phase 2A만
```

---

## 📊 예상 실행 시간 (M1/M2/M3 Mac 기준)

| Step | 작업 | 예상 시간 | 32개 지표 중 커버 |
|------|------|:---:|:---:|
| 1 | Phase 2A 입력 생성 | 1분 | - |
| 2 | Phase 2B/2C 입력 생성 | 5-10분 | - |
| 3 | ML 전체 | 40분~1시간 | 13개 (예측 6 + 과적합 3 + 일반화 3, fold std는 추가 분석 필요) |
| 4 | DL 전체 | 1.5~2시간 | (위와 공유) |
| 5 | Graph (GraphSAGE + GAT) | 20-40분 | (위와 공유) |
| 6 | 결과 사후 분석 | 10분 | +3 (MedianAE, P95, Train/Val Ratio, fold std) |
| 7 | 앙상블 (Step 5) | 10분 | +4 (앙상블 4개) |
| **Step 4 합계** | | **약 3~4.5시간** | **~20/32** |

Step 6 (외부 검증)까지 돌려야 **27/32** 달성 (Lung 28/32 대비 -1).

---

## 📊 32개 지표 커버리지 맵 (프로토콜 v2.4 Section 13)

프로토콜 v2.4 Section 13에 정의된 **32개 지표 체크리스트**는 단일 스크립트가 아니라 **Step 4~6 전체**에서 채워짐. 각 지표가 어느 단계/스크립트에서 계산되는지 아래 표 참조.

**Lung 최종 달성률** (v2.4 정정): **25/32 (78.1%)**. 미진행 7개: scaffold split, multi-seed, cross-dataset, MAP, AUC-ROC, Consensus Overlap 부분 등.

> **v2.3 문서 오류 정정**: v2.3에서 "28/32"로 기재됐으나, 실제 합계 재확인 시 25/32. v2.4에서 정정됨.

**Colon 목표 달성률**: **28/32 (87.5%)**. Lung 대비 **Scaffold split #21 추가 달성** (일반화 2/6 → 3/6).

### 카테고리 1: 예측 성능 (8개)

| # | 지표 | Lung 상태 | 계산 위치 | Colon 대응 |
|:-:|------|:---:|----------|-----------|
| 1 | Spearman | ✅ | `phase2_utils.calculate_metrics` → ML/DL/Graph 결과 JSON의 `fold_results[*].val.spearman` | 학습 스크립트 자동 |
| 2 | Pearson | ✅ | 동일 (`.val.pearson`) | 자동 |
| 3 | R² | ✅ | 동일 (`.val.r2`) | 자동 |
| 4 | RMSE | ✅ | 동일 (`.val.rmse`) | 자동 |
| 5 | MAE | ✅ | 동일 (`.val.mae`) | 자동 |
| 6 | Kendall's Tau | ✅ | 동일 (`.val.kendall_tau`) | 자동 |
| 7 | MedianAE | ✅ | `phase2_comprehensive_metrics_analysis.py` L42-47: `median_absolute_error(y_true, OOF)` | 사후 분석 필요 |
| 8 | P95 Error | ✅ | 동일 L46: `np.percentile(abs(y_true - OOF), 95)` | 사후 분석 필요 |

→ **1~6번은 학습 스크립트에서 자동 계산**. 7~8번은 `phase2_comprehensive_metrics_analysis.py`가 `y_train.npy` + `OOF/*.npy`를 읽어 직접 계산 (Line 42-47).

### 카테고리 2: 과적합 (5개)

| # | 지표 | Lung 상태 | 계산 위치 | Colon 대응 |
|:-:|------|:---:|----------|-----------|
| 9 | Train Spearman | ✅ | JSON `fold_results[*].train.spearman` 평균 | 자동 |
| 10 | Val Spearman | ✅ | JSON `fold_results[*].val.spearman` 평균 | 자동 |
| 11 | Gap | ✅ | `train_mean - val_mean` (학습 스크립트 + 사후 분석 모두 계산) | 자동 |
| 12 | Train/Val Ratio | ✅ | `phase2_comprehensive_metrics_analysis.py` L181: `train_mean / val_mean` | 사후 분석 필요 |
| 13 | Fold std | ✅ | 동일 L182: `np.std(val_spearman_per_fold)` | 사후 분석 필요 |

→ 9~11은 학습 스크립트의 `overfitting_check`/`stability_check`에 저장. 12~13은 사후 스크립트가 fold별 값에서 계산.
→ 참고: 학습 스크립트 내 `check_overfitting`/`check_stability`도 있으나 (`data_validation.py`), 사후 스크립트가 결정적 계산 담당.

### 카테고리 3: 앙상블 (4개)

| # | 지표 | Lung 상태 | 계산 위치 | Colon 대응 |
|:-:|------|:---:|----------|-----------|
| 14 | Ensemble Gain | ✅ | `phase3_ensemble_analysis.py` (24조합) | Step 5에서 |
| 15 | Diversity | ✅ | 동일 | Step 5에서 |
| 16 | Error Overlap | ✅ | 동일 | Step 5에서 |
| 17 | Consensus Score | ✅ | 동일 | Step 5에서 |

### 카테고리 4: 일반화 (6개)

| # | 지표 | Lung 상태 | 계산 위치 | Colon 대응 |
|:-:|------|:---:|----------|-----------|
| 18 | Holdout | ✅ | 학습 스크립트 `eval_mode='holdout'` | 자동 |
| 19 | 5-Fold CV | ✅ | 학습 스크립트 `eval_mode='5foldcv'` | 자동 |
| 20 | GroupCV (unseen drug) | ✅ | 학습 스크립트 `eval_mode='groupcv'` | 자동 |
| 21 | **Scaffold split** | ❌ | **v2.4 추가** | **✅ `compute_scaffolds.py` + `run_{ml,dl,graph}_scaffold_all.py` (전체 15 모델 × 3 Phase)** |
| 22 | Multi-seed stability | ❌ | **미진행** | 프로토콜 미포함 |
| 23 | Cross-dataset | ❌ | **미진행** | Step 6 PRISM으로 부분 충족 |

### 카테고리 5: 약물 랭킹 (9개)

| # | 지표 | Lung 상태 | 계산 위치 | Colon 대응 |
|:-:|------|:---:|----------|-----------|
| 24 | Hit Rate@K | ✅ | `step6_2_prism_validation.py` (K=10, 50, 100) | Step 6 (PRISM 데이터 필요) |
| 25 | Precision@K | ✅ | `step6_2_prism_validation.py` + `step6_3_clinical_trials_validation.py` (K=10, 50) | Step 6 (PRISM + CT 데이터 필요) |
| 26 | Recall@K | ✅ | `step6_2_prism_validation.py` (K=100) | Step 6 (PRISM 데이터 필요) |
| 27 | Coverage Rate | ✅ | `step6_6_comprehensive_scoring.py` | Step 6 (모든 검증 통합) |
| 28 | MRR | ✅ | `step6_2_prism_validation.py` (Mean Reciprocal Rank) | Step 6 (PRISM 데이터 필요) |
| 29 | NDCG@K | ✅ | `step6_2_prism_validation.py` (sklearn.metrics.ndcg_score, K=10) | Step 6 (PRISM 데이터 필요) |
| 30 | MAP | ❌ | **Lung도 미계산** | 향후 추가 개발 필요 |
| 31 | AUC-ROC | ❌ | **Lung도 미계산** | 향후 추가 개발 필요 |
| 32 | Consensus Overlap | 🔄 | `step6_compare_top30_2b_vs_2c.py` (2B vs 2C Top 30 overlap) | Step 6 부분 확인 |

### 단계별 지표 계산 책임 요약

```
Step 4 (학습 스크립트)
├─ run_ml_all.py, run_dl_all.py, run_graph_sage_mps.py, run_graph_gat_mps.py
└─ 자동 계산: 1~6, 9~11, 18~20 = 12개
   (JSON에 fold별 train/val 6지표 + GroupCV OOF .npy 저장)

Step 4 사후 분석
├─ phase2_comprehensive_metrics_analysis.py (370 lines, Lung 검증 완료)
└─ OOF + JSON fold 기반 계산: 7, 8, 12, 13 = 4개
   (MedianAE, P95 Error, Train/Val Ratio, Fold std)

Step 5 앙상블
├─ phase3_ensemble_analysis.py
└─ 계산: 14~17 = 4개 (Ensemble Gain, Diversity, Error Overlap, Consensus Score)

Step 6 외부 검증
├─ step6_2_prism_validation.py       → Hit Rate@K, Precision@K, Recall@K, MRR, NDCG@K = 5개
├─ step6_3_clinical_trials_validation.py → Precision@K (보조)
├─ step6_4_cosmic_validation.py      → 드라이버 유전자 일치 (랭킹 지표 아니지만 가중치)
├─ step6_5_cptac_validation.py       → 타겟 발현 + Survival (랭킹 지표 아니지만 가중치)
├─ step6_6_comprehensive_scoring.py  → Coverage Rate + 신뢰도 통합
└─ step6_compare_top30_2b_vs_2c.py   → Consensus Overlap
   계산 합계: 24~29, 32 = 7개

합계: 12 + 4 + 4 + 7 = 27개
Colon 목표: 27/32 (Lung 28/32에 비해 -1, MAP/AUC-ROC/Scaffold/Multi-seed/Cross-dataset 미진행)
```

### Colon Step 4 실행 후 체크해야 할 것

Step 4 (학습 스크립트) 완료 시점에 다음을 확인:

1. **각 `results/colon_*_v1_*.json`** 에 `spearman`, `pearson`, `r2`, `rmse`, `mae`, `kendall_tau` 기록 확인 (6개 지표)
2. **`overfitting_check`**, **`stability_check`** 필드 존재 확인 (과적합 5개 지표 base)
3. **OOF 파일 (`results/colon_*_v1_oof/*.npy`)** 모든 모델 × 모든 Phase × GroupCV에서 저장 확인
4. **평가 방식 3종** (holdout/5foldcv/groupcv) 모두 실행되었는지 JSON 파일명으로 확인

Step 4 이후:
- `phase2_comprehensive_metrics_analysis.py` 실행 → MedianAE, P95 Error 등 추가
- `phase3_ensemble_analysis.py` 실행 → 앙상블 4개 지표
- `step6_*.py` 시리즈 실행 → 약물 랭킹 지표

---

## 🗃️ Colon Step 6 외부 검증 데이터 준비 현황

**🚨 중요**: Step 6 실행 전 외부 검증 데이터 수집이 필수. 현재 Colon 폴더 확인 결과, 대부분 **빈 폴더** 상태. Step 4/5 실행은 가능하지만 **Step 6 시작 전 데이터 수집 작업이 선행**되어야 함.

### 현재 준비 상태 (2026-04-21 확인)

| 경로 | 상태 | 비고 |
|------|:---:|------|
| `curated_data/validation/cosmic/` | ❌ **빈 폴더** | 폴더만 있고 데이터 없음 |
| `curated_data/validation/prism/` | ❌ **빈 폴더** | 폴더만 있고 데이터 없음 |
| `curated_data/validation/clinicaltrials/` | ❌ **빈 폴더** | 폴더만 있고 데이터 없음 |
| `curated_data/cbioportal/coad_cptac_2019/` | ✅ **존재** | cBioPortal Colon CPTAC 데이터 |
| `curated_data/cbioportal/coadread_tcga_pan_can_atlas_2018/` | ✅ **존재** | TCGA pan-cancer (subtype 태깅용) |

참고 Lung 상태: `curated_data/validation/{clinicaltrials, cosmic, dgidb, notes, prism}` 모두 데이터 채워진 상태.

### 필요 데이터 수집 목록

#### 1. PRISM (약물 반응 검증) — `step6_2_prism_validation.py`
- **필요 파일**:
  - `prism-repurposing-20q2-primary-screen-replicate-collapsed-treatment-info.csv`
  - `prism-repurposing-20q2-primary-screen-cell-line-info.csv`
- **출처**: DepMap portal → PRISM Repurposing Screen (20Q2)
- **Colon 특이사항**: `lineage` 필터를 `'lung'` → `'colorectal'` 또는 `'large_intestine'` 으로 변경 필요 (step6_2 Line 52)

#### 2. ClinicalTrials (임상시험 검증) — `step6_3_clinical_trials_validation.py`
- **필요 파일** (페이지네이션 방식 또는 통합):
  - `clinicaltrials_colorectal_cancer_summary.json`
  - `clinicaltrials_colorectal_cancer_all_studies.json` OR `clinicaltrials_colorectal_cancer_page_{001..015}.json`
- **출처**: ClinicalTrials.gov API (`https://clinicaltrials.gov/api/v2/studies`)
- **Colon 특이사항**:
  - 쿼리: `cond:colorectal+cancer` (또는 `cond:colon+cancer`)
  - Lung은 384 MB 크기였으나 Colon은 임상시험 수가 다를 수 있음

#### 3. COSMIC (드라이버 유전자 검증) — `step6_4_cosmic_validation.py`
- **필요 파일** (tar 포맷):
  - Cancer Gene Census (CGC)
  - Actionability Data
- **출처**: COSMIC (sanger.ac.uk/cosmic) — 로그인 필요
- **Colon 특이사항**: 드라이버 유전자는 pan-cancer DB라 Lung과 동일 파일 사용 가능. 분석 시 **COREAD tissue filter**만 수정하면 됨.

#### 4. CPTAC (환자 데이터 검증) — `step6_5_cptac_validation.py`
- **필요 파일**:
  - `curated_data/cptac/coad_cptac_2019/data_clinical_patient.txt`
  - `curated_data/cptac/coad_cptac_2019/data_mrna*.txt`
- **Colon 현황**: ✅ **`curated_data/cbioportal/coad_cptac_2019/` 에 이미 존재**
- **필요 작업**:
  - `cbioportal/coad_cptac_2019/` → `cptac/coad_cptac_2019/` 심볼릭 링크 또는 복사
  - 또는 스크립트의 경로를 `cbioportal`로 수정
- **Lung 대비 변경**: Lung은 `luad_cptac_2020` + `lusc_cptac_2021` 2개. Colon은 **`coad_cptac_2019` 1개**.

### Step 6 실행 전 준비 작업 체크리스트

```bash
cd 20260420_new_pre_project_biso_Colon

# [Step A] PRISM 데이터 다운로드
mkdir -p curated_data/validation/prism/
# DepMap portal에서 다운로드 후 배치 (수동)
# https://depmap.org/portal/download/all/?release=PRISM+Repurposing+Public+20Q2

# [Step B] ClinicalTrials 데이터 다운로드
mkdir -p curated_data/validation/clinicaltrials/
# 별도 수집 스크립트 필요 (Lung에 있던 수집 스크립트 참고 + query 변경)

# [Step C] COSMIC 데이터 다운로드 (Lung tar 파일 재사용 가능 여부 확인)
mkdir -p curated_data/validation/cosmic/
# 옵션 1: Lung 폴더에서 복사 (pan-cancer DB라 동일)
cp -r ../20260416_new_pre_project_biso_Lung/curated_data/validation/cosmic/*.tar curated_data/validation/cosmic/
# 옵션 2: 새로 다운로드

# [Step D] CPTAC 심볼릭 링크
mkdir -p curated_data/cptac/
ln -s ../cbioportal/coad_cptac_2019 curated_data/cptac/coad_cptac_2019

# 또는 step6_5_cptac_validation.py 의 경로를 직접 수정:
#   Line 22: cptac_base = Path('curated_data/cptac')
#        → cptac_base = Path('curated_data/cbioportal')
```

### Step 6 스크립트 Colon 수정 범위 (정독 결과 기반)

각 step6_*.py는 **Lung 특정 하드코딩**이 많아 Colon 적용 시 수정이 광범위함:

| 스크립트 | 수정할 것 |
|---------|----------|
| `step6_1_map_drug_names.py` | 경로만 (`curated_data/gdsc/Compounds-annotation.csv`) - 대부분 동일 |
| `step6_2_prism_validation.py` | `lineage ~ 'lung'` → `'colorectal'` / `'large_intestine'` (Line 52) |
| `step6_3_clinical_trials_validation.py` | 파일명 `lung_cancer` → `colorectal_cancer` (Line 26, 36, 45) |
| `step6_4_cosmic_validation.py` | tissue filter 로직 (구체 라인은 후반부, 추가 정독 필요) |
| `step6_5_cptac_validation.py` | **전면 수정**: `luad/lusc_cptac_2020/2021` → `coad_cptac_2019`, 2개 데이터셋 루프 → 1개 (Line 24) |
| `step6_6_comprehensive_scoring.py` | JSON 파일명 `lung_*_validation_results.json` → `colon_*_validation_results.json` (Line 24, 31, 38, 45) |
| `step6_compare_top30_2b_vs_2c.py` | 정독 못 함. Lung 출력명 기반 유사 수정 예상 |

이 수정 작업은 **Step 4 완료 후 별도 Phase**로 진행 권장. Step 4 실행 중에도 병렬로 데이터 수집 가능.

---

1. **Step 4 사후 분석**: `phase2_comprehensive_metrics_analysis.py` → MedianAE, P95 Error, Train/Val Ratio 계산
2. **Step 5**: `phase3_ensemble_analysis.py` → 24개 앙상블 실험 + 4개 앙상블 지표
3. **Step 6**: 외부 검증 (PRISM, COSMIC, CPTAC, ClinicalTrials) → 7개 약물 랭킹 지표
4. **Step 7**: ADMET Gate
5. **Step 8**: Neo4j 적재
6. **Step 9**: LLM 연동

---

## 📝 불확실점 (규칙 7)

### Claude가 직접 확인 못한 부분

1. **`run_graph_gat_mps.py` 전체 내용**: 정독 못 함. 수동 수정 가이드만 제공 (GraphSAGE 패턴 기반 추정).
2. **`phase2_utils.py`의 `check_overfitting/check_stability` 함수**: `data_validation.py`에서 import되는데 내용 미확인. 하지만 `phase2_comprehensive_metrics_analysis.py`가 fold 결과에서 직접 재계산하므로 최종 지표 계산에는 영향 없음.
3. **Colon `drug_features.parquet`에 `canonical_smiles` 컬럼 존재 여부**: 실행 전 체크 필요 (가이드 "사전 체크리스트" 참조).
4. **MPS에서 Graph 모델이 실제로 돌아가는지**: Lung은 OOM이라 CPU 강제했음. Colon은 작으니 가능 추정. fallback 로직으로 안전.
5. **Phase 2B/2C에서 Colon 성능**: Lung에서도 단순 hash 기반 context라 성능 보장 불가. 결과 보고 판단.
6. **`step6_4_cosmic_validation.py`의 COSMIC tissue filter 정확한 위치**: 스크립트 225줄 중 60줄만 정독. tissue filter 로직은 후반부에 있을 것으로 추정하나 구체 라인 미확인.
7. **`step6_compare_top30_2b_vs_2c.py` 내용**: 정독 못 함. Lung 출력 기반 유사 수정 예상.
8. **Colon Top 15 약물 선정 로직 (Step 7 ADMET Gate)**: Lung은 `step7_0_remove_duplicates.py` + `step7_1_admet_filtering.py` + `step7_2_select_top15.py` 3단계. Colon 적용 시 Lung 하드코딩 수정 범위 미확인.
9. **`phase3_ensemble_analysis.py` 내용**: 정독 못 함. 24조합 구성 방법, Gain 계산 방식 등 디테일 확인 필요.

### 해결된 불확실점 (정독 완료)

- ~~32개 지표 중 사후 분석 지표의 정확한 계산 스크립트~~ → `phase2_comprehensive_metrics_analysis.py` 정독 완료 (370 lines 전문, L42-47/L162-191)
- ~~Colon Step 6 외부 검증 데이터 준비 여부~~ → `curated_data/validation/{prism, cosmic, clinicaltrials}` **빈 폴더** 확인. `cbioportal/coad_cptac_2019/`는 존재. 상세는 "🗃️ Colon Step 6 외부 검증 데이터 준비 현황" 섹션 참조.

---

## 📝 문서 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|:----:|----------|
| 2026-04-21 | v1.0 | 초안 작성 (Scaffold split 없이 Drug split만 기준). 119 실험, 지표 27/32 목표. |
| 2026-04-21 | **v1.1** | **Scaffold split 전면 반영** (프로토콜 v2.4 동기화). 168 실험 (Drug 123 + Scaffold 45), 지표 28/32 목표. Graph Phase 2B/2C 추가. 신규 스크립트 4개 (compute_scaffolds, run_ml_scaffold_all, run_dl_scaffold_all, run_graph_scaffold_all). 자동 실행 쉘 스크립트 (run_step4_all.sh). |

---

*Claude가 작성 (2026-04-21 v1.0 → v1.1). 대부분 Lung 스크립트 정독 기반.*
