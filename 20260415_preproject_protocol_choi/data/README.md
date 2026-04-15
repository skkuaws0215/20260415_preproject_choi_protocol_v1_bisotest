# Phase 1: 데이터 준비 완료

## 📊 개요

20260415_preproject_protocol_choi 프로토콜에 따라 Phase 1 데이터 준비 작업을 완료했습니다.

- **소스 데이터**: `20260414_re_pre_project_v3/features_slim.parquet`
- **Label**: `20260414_re_pre_project_v3/step4_results/y_train.npy`
- **Context**: features_slim.parquet에 이미 포함됨 (5개 약물 물리화학적 특성)
- **총 샘플 수**: 6,366 (29 cell lines × 243 drugs)

---

## 📁 생성된 파일 목록

### ML 입력셋 (NPY)

| 파일명 | Shape | Dtype | 설명 |
|--------|-------|-------|------|
| `X_numeric.npy` | (6366, 5524) | float32 | **입력셋 A**: Numeric features only |
| `X_numeric_smiles.npy` | (6366, 5588) | float32 | **입력셋 B**: Numeric + SMILES SVD(64) |
| `X_numeric_context_smiles.npy` | (6366, 5690) | float32 | **입력셋 C**: Numeric + Context(102) + SMILES(64) |
| `y_train.npy` | (6366,) | float64 | Label (IC50 약물 민감도) |

### DL 입력셋 (NPY)

| 파일명 | Shape | Dtype | 설명 |
|--------|-------|-------|------|
| `smiles_token_ids.npy` | (6366, 256) | int32 | SMILES character tokenization |
| `context_codes.npy` | (6366, 5) | int32 | Context label encoded codes |

### Vocab & Metadata (JSON)

| 파일명 | 설명 |
|--------|------|
| `smiles_vocab.json` | SMILES character vocab (38 tokens) |
| `context_vocab.json` | Context 5개 컬럼의 label encoding vocab |
| `context_onehot_info.json` | Context one-hot encoding 정보 (102 dims) |

---

## 🎯 입력셋 구성

### 입력셋 A: Numeric-only
```
Shape: (6366, 5524)
- Numeric features: 5,524개
- CRISPR knock-out 데이터 중심
```

### 입력셋 B: Numeric + SMILES
```
Shape: (6366, 5588)
- Numeric: 5,524
- SMILES SVD: 64 (TF-IDF → SVD, explained variance: 76.88%)
```

### 입력셋 C: Numeric + Context + SMILES
```
Shape: (6366, 5690)
- Numeric: 5,524
- Context one-hot: 102
- SMILES SVD: 64
```

---

## 🔧 Context 특징 (5개)

| 컬럼명 | Unique 값 수 | 설명 |
|--------|-------------|------|
| `drug_desc_hba` | 17 | 수소결합 수용체 수 (H-bond acceptors) |
| `drug_desc_hbd` | 9 | 수소결합 공여체 수 (H-bond donors) |
| `drug_desc_heavy_atoms` | 48 | 중원자 수 (분자 크기) |
| `drug_desc_ring_count` | 10 | 고리 구조 수 (안정성) |
| `drug_desc_rot_bonds` | 18 | 회전 가능 결합 수 (유연성) |

**One-hot encoding 총 차원**: 102

---

## 🧬 SMILES 처리

### ML용 (SVD)
- **TF-IDF**: Character n-gram (2~4), max_features=1000
- **SVD**: 64 components (explained variance: 76.88%)
- Drug 단위로 계산 후 row별로 매핑

### DL용 (Token IDs)
- **Tokenization**: Character-level
- **Vocab size**: 38 (+ `<PAD>`, `<UNK>`)
- **Max length**: 256
- **Padding**: Zero-padding

```python
vocab = {
    '<PAD>': 0,
    '<UNK>': 1,
    '#': 2, '(': 3, ')': 4, '+': 5, '-': 6,
    # ... 나머지 SMILES characters
}
```

---

## 💾 파일 크기

| 파일 | 크기 (MB) |
|------|----------|
| X_numeric.npy | 134.15 |
| X_numeric_smiles.npy | 135.70 |
| X_numeric_context_smiles.npy | 138.18 |
| smiles_token_ids.npy | 6.22 |
| context_codes.npy | 0.12 |
| y_train.npy | 0.05 |
| JSON 파일들 | < 0.01 |

**총 용량**: ~414 MB

---

## 📝 사용 예시

### ML 모델 학습
```python
import numpy as np

# 입력셋 A (baseline)
X = np.load('X_numeric.npy')
y = np.load('y_train.npy')

# 입력셋 B (+ SMILES)
X = np.load('X_numeric_smiles.npy')

# 입력셋 C (full)
X = np.load('X_numeric_context_smiles.npy')
```

### DL 모델 학습
```python
import numpy as np
import json

# SMILES tokenization
smiles_ids = np.load('smiles_token_ids.npy')  # (6366, 256)
with open('smiles_vocab.json') as f:
    smiles_vocab = json.load(f)

# Context codes
context = np.load('context_codes.npy')  # (6366, 5)
with open('context_vocab.json') as f:
    context_vocab = json.load(f)
```

---

## ⚠️ 주의사항

1. **GroupCV 사용 필수**
   - Group key: `canonical_drug_id`
   - Unseen drug 시나리오 (약물 기준 split)
   - 기존 fold split: `20260414_re_pre_project_v3/step4_results/step2_groupkfold_*.pkl`

2. **Context 제약**
   - 팀장 프로토콜의 strong context 5개 중 3개 없음 (TCGA_DESC, drug_bridge_strength, stage3_resolution_status)
   - 현재 5개는 모두 약물 물리화학적 특성
   - Sample 특성(PATHWAY)은 별도 추가 필요 시 `20260413_feature_reconstruction` 활용

3. **SMILES SVD**
   - Explained variance: 76.88% (정보 손실 ~23%)
   - DL 모델에서는 token IDs 직접 사용 권장

---

## 🔄 다음 단계 (Phase 2)

1. GroupCV 설정 (canonical_drug_id 기준)
2. 모델 학습:
   - Baseline: 입력셋 A
   - + SMILES: 입력셋 B
   - + Full: 입력셋 C
3. DL 모델 실험 (SMILES token embedding)
4. Context ablation study

---

생성 일시: 2026-04-15
프로토콜: 20260415_preproject_protocol_choi
