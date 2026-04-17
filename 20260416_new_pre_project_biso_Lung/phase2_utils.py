"""
Phase 2 공통 Utility 함수
"""

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import GroupKFold
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from scipy.stats import spearmanr, pearsonr, kendalltau
import json
from typing import Dict, List, Tuple


def calculate_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """전체 평가 지표 계산"""
    spearman, _ = spearmanr(y_true, y_pred)
    pearson, _ = pearsonr(y_true, y_pred)
    kendall, _ = kendalltau(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)

    return {
        'spearman': float(spearman),
        'pearson': float(pearson),
        'r2': float(r2),
        'rmse': float(rmse),
        'mae': float(mae),
        'kendall_tau': float(kendall)
    }


def create_group_folds(groups: np.ndarray, n_splits: int = 3) -> List[Tuple[np.ndarray, np.ndarray]]:
    """GroupKFold 생성"""
    gkf = GroupKFold(n_splits=n_splits)
    folds = []

    # Dummy X (groups만 필요)
    X_dummy = np.zeros((len(groups), 1))

    for train_idx, val_idx in gkf.split(X_dummy, groups=groups):
        folds.append((train_idx, val_idx))

    return folds


def save_results(results: Dict, output_path: Path):
    """결과를 JSON으로 저장"""
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"✓ Results saved: {output_path}")


def print_fold_summary(fold_results: List[Dict], model_name: str):
    """Fold 결과 요약 출력"""
    print(f"\n{model_name} Results:")
    print("-" * 100)

    metrics = ['spearman', 'pearson', 'r2', 'rmse', 'mae', 'kendall_tau']

    for metric in metrics:
        train_values = [r['train'][metric] for r in fold_results]
        val_values = [r['val'][metric] for r in fold_results]

        train_mean = np.mean(train_values)
        train_std = np.std(train_values)
        val_mean = np.mean(val_values)
        val_std = np.std(val_values)
        gap = train_mean - val_mean

        print(f"{metric:15s} | Train: {train_mean:.4f}±{train_std:.4f} | "
              f"Val: {val_mean:.4f}±{val_std:.4f} | Gap: {gap:+.4f}")


def aggregate_results(fold_results: List[Dict]) -> Dict:
    """Fold 결과 집계"""
    metrics = ['spearman', 'pearson', 'r2', 'rmse', 'mae', 'kendall_tau']

    aggregated = {
        'fold_results': fold_results,
        'summary': {}
    }

    for metric in metrics:
        train_values = [r['train'][metric] for r in fold_results]
        val_values = [r['val'][metric] for r in fold_results]

        aggregated['summary'][metric] = {
            'train_mean': float(np.mean(train_values)),
            'train_std': float(np.std(train_values)),
            'val_mean': float(np.mean(val_values)),
            'val_std': float(np.std(val_values)),
            'gap': float(np.mean(train_values) - np.mean(val_values))
        }

    return aggregated
