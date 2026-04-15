"""
Phase 2A: ML 모델 학습 (numeric-only)
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from phase2_utils import (
    calculate_metrics, create_group_folds, save_results,
    print_fold_summary, aggregate_results
)

from lightgbm import LGBMRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor

print("="*120)
print("Phase 2A: ML Models - numeric-only")
print("="*120)

# 경로 설정
base_dir = Path(__file__).parent
data_dir = base_dir / "data"
results_dir = base_dir / "results"
oof_dir = results_dir / "choi_numeric_ml_v1_oof"

# 데이터 로드
print("\nLoading data...")
X = np.load(data_dir / "X_numeric.npy")
y = np.load(data_dir / "y_train.npy")

# features_slim에서 canonical_drug_id 로드
features_path = Path("/Users/skku_aws2_14/20260408_pre_project_biso_myprotocol/20260408_pre_project_biso_myprotocol/20260414_re_pre_project_v3/features_slim.parquet")
df_meta = pd.read_parquet(features_path, columns=['canonical_drug_id'])
groups = df_meta['canonical_drug_id'].values

print(f"X shape: {X.shape}")
print(f"y shape: {y.shape}")
print(f"Unique groups: {len(np.unique(groups))}")

# GroupKFold 생성
print("\nCreating 3-fold GroupKFold...")
folds = create_group_folds(groups, n_splits=3)
print(f"Created {len(folds)} folds")

# 모델 설정
models = {
    'LightGBM': LGBMRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=7,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,
        n_jobs=-1
    ),
    'LightGBM_DART': LGBMRegressor(
        boosting_type='dart',
        n_estimators=500,
        learning_rate=0.05,
        max_depth=7,
        num_leaves=31,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,
        n_jobs=-1
    ),
    'XGBoost': XGBRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=7,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        verbosity=0
    ),
    'CatBoost': CatBoostRegressor(
        iterations=500,
        learning_rate=0.05,
        depth=7,
        subsample=0.8,
        random_state=42,
        verbose=0,
        thread_count=-1
    ),
    'RandomForest': RandomForestRegressor(
        n_estimators=200,
        max_depth=15,
        min_samples_split=10,
        min_samples_leaf=5,
        max_features='sqrt',
        random_state=42,
        n_jobs=-1,
        verbose=0
    ),
    'ExtraTrees': ExtraTreesRegressor(
        n_estimators=200,
        max_depth=15,
        min_samples_split=10,
        min_samples_leaf=5,
        max_features='sqrt',
        random_state=42,
        n_jobs=-1,
        verbose=0
    )
}

all_results = {}

# 각 모델 학습
for model_name, model_class in models.items():
    print(f"\n{'='*120}")
    print(f"Training {model_name}")
    print(f"{'='*120}")

    fold_results = []
    oof_predictions = np.zeros(len(y))

    for fold_idx, (train_idx, val_idx) in enumerate(folds, 1):
        print(f"\nFold {fold_idx}/{len(folds)}")

        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        print(f"  Train: {len(train_idx)}, Val: {len(val_idx)}")

        # 모델 복사
        if hasattr(model_class, 'copy'):
            model = model_class.copy()
        else:
            # 새 인스턴스 생성
            model = type(model_class)(**model_class.get_params())

        # 학습
        model.fit(X_train, y_train)

        # 예측
        train_pred = model.predict(X_train)
        val_pred = model.predict(X_val)

        # OOF 저장
        oof_predictions[val_idx] = val_pred

        # 평가
        train_metrics = calculate_metrics(y_train, train_pred)
        val_metrics = calculate_metrics(y_val, val_pred)

        fold_results.append({
            'fold': fold_idx,
            'train': train_metrics,
            'val': val_metrics
        })

        print(f"  Train Spearman: {train_metrics['spearman']:.4f}")
        print(f"  Val   Spearman: {val_metrics['spearman']:.4f}")

    # OOF 예측 저장
    np.save(oof_dir / f"{model_name}.npy", oof_predictions)

    # 결과 집계
    aggregated = aggregate_results(fold_results)
    all_results[model_name] = aggregated

    # 요약 출력
    print_fold_summary(fold_results, model_name)

# 전체 결과 저장
save_results(all_results, results_dir / "choi_numeric_ml_v1.json")

print("\n" + "="*120)
print("Phase 2A ML Complete!")
print("="*120)

# 최종 요약
print("\nFinal Summary:")
print("-"*120)
for model_name, results in all_results.items():
    val_spearman = results['summary']['spearman']['val_mean']
    val_std = results['summary']['spearman']['val_std']
    print(f"{model_name:20s} | Val Spearman: {val_spearman:.4f}±{val_std:.4f}")
