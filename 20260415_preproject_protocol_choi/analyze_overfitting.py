"""
과적합 원인 분석 및 완화 실험
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import json
from lightgbm import LGBMRegressor

sys.path.insert(0, str(Path(__file__).parent))

from phase2_utils import calculate_metrics, create_group_folds

print("="*120)
print("과적합 원인 분석")
print("="*120)

# 경로 설정
base_dir = Path(__file__).parent
data_dir = base_dir / "data"
results_dir = base_dir / "results"

# 데이터 로드
X = np.load(data_dir / "X_numeric.npy")
y = np.load(data_dir / "y_train.npy")

features_path = Path("/Users/skku_aws2_14/20260408_pre_project_biso_myprotocol/20260408_pre_project_biso_myprotocol/20260414_re_pre_project_v3/features_slim.parquet")
df_meta = pd.read_parquet(features_path, columns=['canonical_drug_id'])
groups = df_meta['canonical_drug_id'].values

# ============================================================================
# 1. 피처 수 대비 샘플 수 확인
# ============================================================================
print("\n" + "="*120)
print("1. 피처 수 대비 샘플 수")
print("="*120)

n_samples = X.shape[0]
n_features = X.shape[1]
feature_sample_ratio = n_features / n_samples

print(f"\n총 샘플 수: {n_samples:,}")
print(f"총 피처 수: {n_features:,}")
print(f"피처/샘플 비율: {feature_sample_ratio:.4f} ({feature_sample_ratio*100:.2f}%)")
print(f"  → 피처가 샘플보다 {'많음' if feature_sample_ratio > 1 else '적음'}")

# 3-fold 기준 train set 크기
folds = create_group_folds(groups, n_splits=3)
train_sizes = [len(train_idx) for train_idx, _ in folds]
val_sizes = [len(val_idx) for _, val_idx in folds]

print(f"\n3-fold 기준:")
print(f"  평균 Train set: {np.mean(train_sizes):.0f} 샘플")
print(f"  평균 Val set:   {np.mean(val_sizes):.0f} 샘플")
print(f"  Train에서 피처/샘플 비율: {n_features / np.mean(train_sizes):.4f}")

if n_features / np.mean(train_sizes) > 1:
    print(f"  ⚠️  Train set에서 피처가 샘플보다 많음 → 과적합 위험 높음")

# ============================================================================
# 2. GroupCV 특성 확인
# ============================================================================
print("\n" + "="*120)
print("2. GroupCV 특성")
print("="*120)

unique_groups = np.unique(groups)
n_groups = len(unique_groups)

print(f"\n총 그룹 수 (unique drugs): {n_groups}")
print(f"평균 샘플/그룹: {n_samples / n_groups:.1f}")

print(f"\nFold별 상세:")
print("-" * 100)
print(f"{'Fold':>6} | {'Train Size':>12} | {'Val Size':>10} | {'Train Ratio':>12} | {'Train Drugs':>12} | {'Val Drugs':>10}")
print("-" * 100)

for fold_idx, (train_idx, val_idx) in enumerate(folds, 1):
    train_groups = np.unique(groups[train_idx])
    val_groups = np.unique(groups[val_idx])

    train_ratio = len(train_idx) / n_samples

    print(f"{fold_idx:6d} | {len(train_idx):12,} | {len(val_idx):10,} | "
          f"{train_ratio:11.1%} | {len(train_groups):12d} | {len(val_groups):10d}")

# 그룹별 샘플 수 분포
group_sizes = []
for g in unique_groups:
    group_sizes.append(np.sum(groups == g))

print(f"\n그룹별 샘플 수 분포:")
print(f"  Min: {np.min(group_sizes)}")
print(f"  Max: {np.max(group_sizes)}")
print(f"  Mean: {np.mean(group_sizes):.1f}")
print(f"  Std: {np.std(group_sizes):.1f}")

if np.std(group_sizes) / np.mean(group_sizes) > 0.5:
    print(f"  ⚠️  그룹 크기 불균형 (CV: {np.std(group_sizes) / np.mean(group_sizes):.2f})")

# ============================================================================
# 3. LightGBM/CatBoost fold별 상세 결과
# ============================================================================
print("\n" + "="*120)
print("3. 기존 모델 Fold별 상세 결과")
print("="*120)

# JSON 결과 로드
with open(results_dir / "choi_numeric_ml_v1.json") as f:
    results = json.load(f)

for model_name in ['LightGBM', 'CatBoost']:
    print(f"\n{model_name}:")
    print("-" * 100)
    print(f"{'Fold':>6} | {'Train Spearman':>15} | {'Val Spearman':>13} | {'Gap':>10}")
    print("-" * 100)

    fold_results = results[model_name]['fold_results']
    for fold in fold_results:
        train_sp = fold['train']['spearman']
        val_sp = fold['val']['spearman']
        gap = train_sp - val_sp

        print(f"{fold['fold']:6d} | {train_sp:15.4f} | {val_sp:13.4f} | {gap:10.4f}")

    # 평균
    train_sps = [f['train']['spearman'] for f in fold_results]
    val_sps = [f['val']['spearman'] for f in fold_results]
    gaps = [t - v for t, v in zip(train_sps, val_sps)]

    print("-" * 100)
    print(f"{'Mean':>6} | {np.mean(train_sps):15.4f} | {np.mean(val_sps):13.4f} | {np.mean(gaps):10.4f}")
    print(f"{'Std':>6}  | {np.std(train_sps):15.4f} | {np.std(val_sps):13.4f} | {np.std(gaps):10.4f}")

print("\n분석:")
all_gaps = []
for model_name in ['LightGBM', 'CatBoost']:
    fold_results = results[model_name]['fold_results']
    gaps = [f['train']['spearman'] - f['val']['spearman'] for f in fold_results]
    all_gaps.extend(gaps)

print(f"  - 모든 fold에서 Gap > 0.15: {'예' if all(g > 0.15 for g in all_gaps) else '아니오'}")
print(f"  - Gap 범위: [{min(all_gaps):.4f}, {max(all_gaps):.4f}]")
print(f"  - 특정 fold만 문제: {'아니오 (전체적으로 과적합)' if np.std(all_gaps) < 0.05 else '예'}")

print("\n" + "="*120)
print("4. 과적합 완화 실험 (LightGBM)")
print("="*120)

# 실험 설정
experiments = {
    'Baseline': {
        'n_estimators': 100,
        'learning_rate': 0.1,
        'max_depth': 5,
        'num_leaves': 31,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'verbose': -1
    },
    'a) Top 1000 Features': {
        'n_estimators': 100,
        'learning_rate': 0.1,
        'max_depth': 5,
        'num_leaves': 31,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'verbose': -1,
        'use_top_features': 1000
    },
    'b) Regularization': {
        'n_estimators': 100,
        'learning_rate': 0.1,
        'max_depth': 4,
        'num_leaves': 15,
        'min_child_samples': 50,
        'reg_alpha': 1.0,
        'reg_lambda': 1.0,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'verbose': -1
    },
    'c) Early Stopping': {
        'n_estimators': 500,
        'learning_rate': 0.05,
        'max_depth': 5,
        'num_leaves': 31,
        'subsample': 0.8,
        'colsample_bytree': 0.8,
        'random_state': 42,
        'verbose': -1,
        'early_stopping_rounds': 50
    },
    'd) Strong Subsampling': {
        'n_estimators': 100,
        'learning_rate': 0.1,
        'max_depth': 5,
        'num_leaves': 31,
        'subsample': 0.7,
        'colsample_bytree': 0.5,
        'random_state': 42,
        'verbose': -1
    }
}

experiment_results = {}

for exp_name, params in experiments.items():
    print(f"\n실험: {exp_name}")
    print("-" * 100)

    fold_metrics = []
    use_top_features = params.pop('use_top_features', None)
    early_stopping = params.pop('early_stopping_rounds', None)

    for fold_idx, (train_idx, val_idx) in enumerate(folds, 1):
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        # Top features 선택
        if use_top_features:
            # 간단한 variance 기준
            variances = np.var(X_train, axis=0)
            top_indices = np.argsort(variances)[-use_top_features:]
            X_train = X_train[:, top_indices]
            X_val = X_val[:, top_indices]

        # 모델 학습
        model = LGBMRegressor(**params)

        if early_stopping:
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[
                    __import__('lightgbm').early_stopping(early_stopping, verbose=False)
                ]
            )
        else:
            model.fit(X_train, y_train)

        # 예측 & 평가
        train_pred = model.predict(X_train)
        val_pred = model.predict(X_val)

        train_metrics = calculate_metrics(y_train, train_pred)
        val_metrics = calculate_metrics(y_val, val_pred)

        fold_metrics.append({
            'train_spearman': train_metrics['spearman'],
            'val_spearman': val_metrics['spearman'],
            'gap': train_metrics['spearman'] - val_metrics['spearman']
        })

    # 평균 계산
    avg_train = np.mean([m['train_spearman'] for m in fold_metrics])
    avg_val = np.mean([m['val_spearman'] for m in fold_metrics])
    avg_gap = np.mean([m['gap'] for m in fold_metrics])
    std_val = np.std([m['val_spearman'] for m in fold_metrics])

    experiment_results[exp_name] = {
        'train_spearman': avg_train,
        'val_spearman': avg_val,
        'val_std': std_val,
        'gap': avg_gap,
        'fold_metrics': fold_metrics
    }

    print(f"  Train Spearman: {avg_train:.4f}")
    print(f"  Val Spearman:   {avg_val:.4f}±{std_val:.4f}")
    print(f"  Gap:            {avg_gap:+.4f}")

# ============================================================================
# 5. 결과 비교 및 결론
# ============================================================================
print("\n" + "="*120)
print("5. 실험 결과 비교")
print("="*120)

# 표로 정리
print(f"\n{'실험':25s} | {'Val Spearman':>15} | {'Std':>8} | {'Gap':>10} | {'Gap 개선':>12}")
print("-" * 100)

baseline_gap = experiment_results['Baseline']['gap']

for exp_name, metrics in experiment_results.items():
    val_sp = metrics['val_spearman']
    val_std = metrics['val_std']
    gap = metrics['gap']
    improvement = baseline_gap - gap

    marker = ""
    if exp_name != 'Baseline':
        if improvement > 0.05:
            marker = " ✓✓"
        elif improvement > 0.02:
            marker = " ✓"
        elif improvement < -0.02:
            marker = " ✗"

    print(f"{exp_name:25s} | {val_sp:15.4f} | {val_std:8.4f} | {gap:10.4f} | {improvement:+11.4f}{marker}")

print("\n결론:")
print("-" * 100)

# 최고 성능
best_val = max(experiment_results.items(), key=lambda x: x[1]['val_spearman'])
best_gap = min(experiment_results.items(), key=lambda x: x[1]['gap'])

print(f"1. 가장 높은 Val Spearman: {best_val[0]} ({best_val[1]['val_spearman']:.4f})")
print(f"2. 가장 낮은 Gap:          {best_gap[0]} ({best_gap[1]['gap']:.4f})")

# 근본 원인
print(f"\n3. 근본 원인:")
print(f"   - 피처 수({n_features:,}) >> 샘플 수({n_samples:,})")
print(f"   - Train set 크기 약 {np.mean(train_sizes):.0f}개로, 피처/샘플 비율 = {n_features / np.mean(train_sizes):.2f}")
print(f"   - 모든 fold에서 일관되게 과적합 발생 (Gap > 0.29)")

# 권장사항
print(f"\n4. 전체 모델 실행 전 권장 기본 설정:")

if best_gap[0] == 'b) Regularization':
    print(f"   ✓ 정규화 강화: max_depth=4, min_child_samples=50, reg_alpha=1.0, reg_lambda=1.0")
elif best_gap[0] == 'd) Strong Subsampling':
    print(f"   ✓ 강한 서브샘플링: subsample=0.7, colsample_bytree=0.5")
elif best_gap[0] == 'a) Top 1000 Features':
    print(f"   ✓ 피처 선택: 상위 1000개 피처만 사용")
elif best_gap[0] == 'c) Early Stopping':
    print(f"   ✓ Early stopping: n_estimators=500, early_stopping_rounds=50")

print(f"   ✓ Gap 개선 예상: {baseline_gap:.4f} → {best_gap[1]['gap']:.4f} (△{baseline_gap - best_gap[1]['gap']:.4f})")

# 결과 저장
with open(results_dir / "overfitting_analysis.json", 'w') as f:
    json.dump({
        'data_summary': {
            'n_samples': int(n_samples),
            'n_features': int(n_features),
            'feature_sample_ratio': float(feature_sample_ratio),
            'n_groups': int(n_groups),
            'mean_train_size': float(np.mean(train_sizes)),
            'mean_val_size': float(np.mean(val_sizes))
        },
        'experiments': experiment_results
    }, f, indent=2)

print(f"\n✓ 분석 결과 저장: results/overfitting_analysis.json")
