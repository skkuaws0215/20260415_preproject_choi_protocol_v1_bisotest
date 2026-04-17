"""
데이터 검증 및 품질 체크
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, Tuple


def check_missing_values(X: np.ndarray, name: str = "X") -> Dict:
    """결측치 및 비정상 값 확인"""
    nan_count = np.isnan(X).sum()
    inf_count = np.isinf(X).sum()
    nan_ratio = nan_count / X.size * 100
    inf_ratio = inf_count / X.size * 100

    result = {
        'name': name,
        'nan_count': int(nan_count),
        'inf_count': int(inf_count),
        'nan_ratio_pct': float(nan_ratio),
        'inf_ratio_pct': float(inf_ratio),
        'total_elements': int(X.size)
    }

    print(f"\n{name} Missing Values Check:")
    print(f"  NaN count: {nan_count:,} ({nan_ratio:.4f}%)")
    print(f"  Inf count: {inf_count:,} ({inf_ratio:.4f}%)")

    # NaN/Inf가 있으면 0으로 대체
    if nan_count > 0 or inf_count > 0:
        print(f"  ⚠️  Replacing NaN/Inf with 0...")
        X_clean = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        result['cleaned'] = True
        return result, X_clean
    else:
        result['cleaned'] = False
        return result, X

def check_outliers(X: np.ndarray, name: str = "X", threshold: float = 5.0) -> Dict:
    """이상치 확인 (mean ± threshold*std)"""
    outlier_columns = []

    for col_idx in range(X.shape[1]):
        col_data = X[:, col_idx]

        # NaN 제외
        valid_data = col_data[~np.isnan(col_data)]

        if len(valid_data) == 0:
            continue

        mean = np.mean(valid_data)
        std = np.std(valid_data)

        if std == 0:
            continue

        # mean ± threshold*std 벗어나는 값
        outliers = np.abs(col_data - mean) > threshold * std
        outlier_ratio = outliers.sum() / len(col_data) * 100

        if outlier_ratio > 1.0:  # 1% 초과
            outlier_columns.append({
                'column_idx': int(col_idx),
                'outlier_ratio_pct': float(outlier_ratio),
                'mean': float(mean),
                'std': float(std)
            })

    result = {
        'name': name,
        'threshold_sigma': float(threshold),
        'n_outlier_columns': len(outlier_columns),
        'outlier_columns': outlier_columns[:20]  # 최대 20개만
    }

    print(f"\n{name} Outlier Check (>{threshold}σ):")
    print(f"  Columns with >1% outliers: {len(outlier_columns)}")
    if outlier_columns:
        print(f"  Top 5 columns:")
        for col_info in outlier_columns[:5]:
            print(f"    Column {col_info['column_idx']}: {col_info['outlier_ratio_pct']:.2f}% outliers")

    return result


def check_label_distribution(y: np.ndarray) -> Dict:
    """Label 분포 확인"""
    # 기본 통계
    y_min = float(np.min(y))
    y_max = float(np.max(y))
    y_mean = float(np.mean(y))
    y_std = float(np.std(y))
    y_skew = float(stats.skew(y))

    # IQR 이상치
    q1 = np.percentile(y, 25)
    q3 = np.percentile(y, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    outliers = (y < lower_bound) | (y > upper_bound)
    n_outliers = int(outliers.sum())
    outlier_ratio = float(n_outliers / len(y) * 100)

    result = {
        'min': y_min,
        'max': y_max,
        'mean': y_mean,
        'std': y_std,
        'skewness': y_skew,
        'q1': float(q1),
        'q3': float(q3),
        'iqr': float(iqr),
        'n_outliers_iqr': n_outliers,
        'outlier_ratio_pct': outlier_ratio
    }

    print(f"\nLabel (y) Distribution:")
    print(f"  Range: [{y_min:.4f}, {y_max:.4f}]")
    print(f"  Mean±Std: {y_mean:.4f}±{y_std:.4f}")
    print(f"  Skewness: {y_skew:.4f}")
    print(f"  IQR outliers: {n_outliers} ({outlier_ratio:.2f}%)")

    return result


def validate_datasets(data_dir) -> Dict:
    """전체 데이터셋 검증"""
    from pathlib import Path

    print("="*120)
    print("Data Validation")
    print("="*120)

    validation_results = {}

    # X_numeric.npy
    X_numeric = np.load(Path(data_dir) / "X_numeric.npy")
    missing_result, X_numeric_clean = check_missing_values(X_numeric, "X_numeric")
    outlier_result = check_outliers(X_numeric_clean, "X_numeric")

    validation_results['X_numeric'] = {
        'missing_values': missing_result,
        'outliers': outlier_result
    }

    # X_numeric_smiles.npy
    X_numeric_smiles = np.load(Path(data_dir) / "X_numeric_smiles.npy")
    missing_result, X_numeric_smiles_clean = check_missing_values(X_numeric_smiles, "X_numeric_smiles")
    outlier_result = check_outliers(X_numeric_smiles_clean, "X_numeric_smiles")

    validation_results['X_numeric_smiles'] = {
        'missing_values': missing_result,
        'outliers': outlier_result
    }

    # X_numeric_context_smiles.npy
    X_numeric_context_smiles = np.load(Path(data_dir) / "X_numeric_context_smiles.npy")
    missing_result, X_numeric_context_smiles_clean = check_missing_values(X_numeric_context_smiles, "X_numeric_context_smiles")
    outlier_result = check_outliers(X_numeric_context_smiles_clean, "X_numeric_context_smiles")

    validation_results['X_numeric_context_smiles'] = {
        'missing_values': missing_result,
        'outliers': outlier_result
    }

    # y_train.npy
    y = np.load(Path(data_dir) / "y_train.npy")
    label_result = check_label_distribution(y)

    validation_results['y_train'] = {
        'distribution': label_result
    }

    # Cleaned data 저장 (필요시)
    if validation_results['X_numeric']['missing_values']['cleaned']:
        np.save(Path(data_dir) / "X_numeric_clean.npy", X_numeric_clean)
        print("\n✓ X_numeric_clean.npy saved")

    if validation_results['X_numeric_smiles']['missing_values']['cleaned']:
        np.save(Path(data_dir) / "X_numeric_smiles_clean.npy", X_numeric_smiles_clean)
        print("\n✓ X_numeric_smiles_clean.npy saved")

    if validation_results['X_numeric_context_smiles']['missing_values']['cleaned']:
        np.save(Path(data_dir) / "X_numeric_context_smiles_clean.npy", X_numeric_context_smiles_clean)
        print("\n✓ X_numeric_context_smiles_clean.npy saved")

    print("\n" + "="*120)

    return validation_results


def check_overfitting(fold_results: list, threshold: float = 0.15) -> Dict:
    """과적합 체크"""
    gaps = []
    flags = []

    for result in fold_results:
        train_spearman = result['train']['spearman']
        val_spearman = result['val']['spearman']
        gap = train_spearman - val_spearman

        gaps.append(gap)
        flags.append(gap > threshold)

    overfitting = {
        'threshold': threshold,
        'gaps': [float(g) for g in gaps],
        'mean_gap': float(np.mean(gaps)),
        'max_gap': float(np.max(gaps)),
        'overfitting_flags': [bool(f) for f in flags],  # Convert numpy bool
        'n_overfitting_folds': int(sum(flags))
    }

    if any(flags):
        overfitting['warning'] = f"⚠️  Overfitting detected in {sum(flags)} fold(s)"

    return overfitting


def check_stability(fold_results: list, threshold: float = 0.05) -> Dict:
    """Fold 안정성 체크"""
    val_spearman_scores = [r['val']['spearman'] for r in fold_results]
    std_val = np.std(val_spearman_scores)

    stability = {
        'threshold': threshold,
        'val_spearman_std': float(std_val),
        'val_spearman_scores': [float(s) for s in val_spearman_scores],
        'unstable': bool(std_val > threshold)  # Convert to python bool
    }

    if stability['unstable']:
        stability['warning'] = f"⚠️  Unstable across folds (std={std_val:.4f})"

    return stability
