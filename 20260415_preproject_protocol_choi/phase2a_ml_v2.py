"""
Phase 2A: ML 모델 학습 (numeric-only) - with validation & monitoring
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent))

from phase2_utils import (
    calculate_metrics, create_group_folds, save_results,
    print_fold_summary, aggregate_results
)
from data_validation import check_overfitting, check_stability

from lightgbm import LGBMRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor

print("="*120)
print("Phase 2A: ML Models - numeric-only (with monitoring)")
print("="*120)

# 경로 설정
base_dir = Path(__file__).parent
data_dir = base_dir / "data"
results_dir = base_dir / "results"
oof_dir = results_dir / "choi_numeric_ml_v1_oof"
oof_dir.mkdir(exist_ok=True)

# 데이터 검증 결과 로드
with open(results_dir / "data_validation.json") as f:
    validation_results = json.load(f)

print("\n✓ Data validation results loaded")

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
folds = create_group_folds(groups, n_splits=3)
print(f"\n✓ Created {len(folds)}-fold GroupKFold")

# 간단한 모델로 테스트 (빠른 실행)
models = {
    'LightGBM': LGBMRegressor(
        n_estimators=100,  # 빠른 테스트
        learning_rate=0.1,
        max_depth=5,
        num_leaves=31,
        random_state=42,
        verbose=-1,
        n_jobs=-1
    ),
    'CatBoost': CatBoostRegressor(
        iterations=100,  # 빠른 테스트
        learning_rate=0.1,
        depth=5,
        random_state=42,
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

        # 새 모델 인스턴스 생성
        if model_name == 'LightGBM':
            model = LGBMRegressor(**model_class.get_params())
        elif model_name == 'CatBoost':
            model = CatBoostRegressor(**model_class.get_params())
        else:
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

        # Gap 출력
        gap_spearman = train_metrics['spearman'] - val_metrics['spearman']
        gap_rmse = train_metrics['rmse'] - val_metrics['rmse']

        print(f"  Train Spearman: {train_metrics['spearman']:.4f}")
        print(f"  Val   Spearman: {val_metrics['spearman']:.4f}")
        print(f"  Gap (Spearman): {gap_spearman:+.4f}")
        print(f"  Gap (RMSE):     {gap_rmse:+.4f}")

    # OOF 예측 저장
    np.save(oof_dir / f"{model_name}.npy", oof_predictions)

    # 과적합 & 안정성 체크
    overfitting_check = check_overfitting(fold_results, threshold=0.15)
    stability_check = check_stability(fold_results, threshold=0.05)

    # 결과 집계
    aggregated = aggregate_results(fold_results)
    aggregated['data_validation'] = validation_results['X_numeric']
    aggregated['overfitting_check'] = overfitting_check
    aggregated['stability_check'] = stability_check

    all_results[model_name] = aggregated

    # 요약 출력
    print_fold_summary(fold_results, model_name)

    # 과적합/안정성 경고
    if 'warning' in overfitting_check:
        print(f"\n{overfitting_check['warning']}")
    if 'warning' in stability_check:
        print(f"\n{stability_check['warning']}")

# 전체 결과 저장
save_results(all_results, results_dir / "choi_numeric_ml_v1.json")

print("\n" + "="*120)
print("Phase 2A ML Complete!")
print("="*120)

# 최종 요약
print("\nFinal Summary:")
print("-"*120)
for model_name, results in all_results.items():
    summary = results['summary']
    val_spearman = summary['spearman']['val_mean']
    val_std = summary['spearman']['val_std']
    gap = summary['spearman']['gap']

    warnings = []
    if results['overfitting_check'].get('warning'):
        warnings.append("Overfit")
    if results['stability_check'].get('warning'):
        warnings.append("Unstable")

    warning_str = " ⚠️ " + ", ".join(warnings) if warnings else ""

    print(f"{model_name:20s} | Val: {val_spearman:.4f}±{val_std:.4f} | Gap: {gap:+.4f}{warning_str}")
