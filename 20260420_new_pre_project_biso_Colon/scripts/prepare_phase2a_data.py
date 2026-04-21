"""
Phase 2A 학습용 .npy 파일 생성 - Colon 버전

Lung README L109-133의 재생성 방법을 그대로 Colon에 적용.
features_slim.parquet → X_numeric.npy, labels.parquet → y_train.npy

실행 위치: scripts/ 폴더에서 실행 시
  python prepare_phase2a_data.py

출력:
  ../data/X_numeric.npy      (9692, ~5660, float32)
  ../data/y_train.npy        (9692,, float32)
"""

import numpy as np
import pandas as pd
from pathlib import Path

# Colon 경로 (scripts/의 상위 = 프로젝트 루트)
base_dir = Path(__file__).parent.parent
data_dir = base_dir / "data"
data_dir.mkdir(exist_ok=True)

features_slim_path = base_dir / "fe_qc" / "20260420_colon_fe_v2" / "features_slim.parquet"
labels_path = base_dir / "fe_qc" / "20260420_colon_fe_v2" / "features" / "labels.parquet"

print("="*120)
print("Phase 2A 입력 생성 (Colon)")
print("="*120)

# 1. features_slim.parquet → X_numeric.npy
print("\n1. features_slim.parquet 로드...")
df = pd.read_parquet(features_slim_path)
print(f"   Shape: {df.shape}")

# Lung README 방식: numeric columns 추출 (sample_id, canonical_drug_id 제외)
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
feature_cols = [c for c in numeric_cols if c not in ['sample_id', 'canonical_drug_id']]
print(f"   Numeric feature cols: {len(feature_cols)}")

non_numeric = [c for c in df.columns if c not in numeric_cols]
print(f"   Non-numeric cols (제외됨): {non_numeric}")

# X_numeric 생성
X = df[feature_cols].values.astype(np.float32)
print(f"\n   X_numeric shape: {X.shape}")
print(f"   dtype: {X.dtype}")
print(f"   NaN count: {np.isnan(X).sum()}")
print(f"   Inf count: {np.isinf(X).sum()}")

# 저장
x_path = data_dir / "X_numeric.npy"
np.save(x_path, X)
print(f"\n   ✓ Saved: {x_path}")
print(f"   File size: {x_path.stat().st_size / (1024**2):.1f} MB")

# 2. labels.parquet → y_train.npy
print("\n2. labels.parquet 로드...")
df_labels = pd.read_parquet(labels_path)
print(f"   Shape: {df_labels.shape}")
print(f"   Columns: {list(df_labels.columns)}")

if 'label_regression' not in df_labels.columns:
    raise ValueError(f"label_regression 컬럼 없음. 사용 가능한 컬럼: {list(df_labels.columns)}")

y = df_labels['label_regression'].values.astype(np.float32)
print(f"\n   y_train shape: {y.shape}")
print(f"   dtype: {y.dtype}")
print(f"   Range: {y.min():.4f} ~ {y.max():.4f}")
print(f"   Mean: {y.mean():.4f}, Std: {y.std():.4f}")
print(f"   NaN count: {np.isnan(y).sum()}")

# 저장
y_path = data_dir / "y_train.npy"
np.save(y_path, y)
print(f"\n   ✓ Saved: {y_path}")
print(f"   File size: {y_path.stat().st_size / 1024:.1f} KB")

# 3. Shape 일치 검증
print("\n3. 검증...")
assert X.shape[0] == y.shape[0], f"Shape mismatch: X={X.shape}, y={y.shape}"
print(f"   ✓ Rows match: X={X.shape[0]}, y={y.shape[0]}")

# 4. drug_features.parquet 위치 확인 (Phase 2B/2C 준비)
print("\n4. drug_features.parquet 확인 (Phase 2B/2C용)...")
drug_features_candidates = [
    data_dir / "drug_features.parquet",
    base_dir / "data" / "drug_features.parquet",
    base_dir / "fe_qc" / "20260420_colon_fe_v2" / "drug_features.parquet",
]

drug_features_found = None
for candidate in drug_features_candidates:
    if candidate.exists():
        drug_features_found = candidate
        print(f"   ✓ Found: {candidate}")
        # canonical_smiles 컬럼 확인
        df_drug = pd.read_parquet(candidate)
        if 'canonical_smiles' in df_drug.columns:
            smiles_coverage = df_drug['canonical_smiles'].notna().sum() / len(df_drug) * 100
            print(f"   ✓ canonical_smiles 컬럼 존재 ({smiles_coverage:.1f}% coverage)")
        else:
            print(f"   ⚠ canonical_smiles 컬럼 없음. 있는 컬럼: {list(df_drug.columns)}")
        break

if drug_features_found is None:
    print(f"   ⚠ drug_features.parquet 찾을 수 없음. Phase 2B/2C 실행 전 data/ 폴더에 배치 필요.")

print("\n" + "="*120)
print("Phase 2A 입력 생성 완료!")
print("="*120)
print(f"\n다음 단계:")
print(f"  - Phase 2A 실행: python scripts/run_ml_all.py  (내부에서 Phase 2B/2C도 호출)")
print(f"  - 또는 Phase 2B/2C 데이터 생성: python scripts/prepare_phase2bc_data.py")
