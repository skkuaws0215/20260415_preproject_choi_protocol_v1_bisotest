"""
Phase 2 ML 모델 전체 실행 (기본 하이퍼파라미터)
3가지 평가 방식: Holdout, 5-Fold CV, GroupCV
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import json
from sklearn.model_selection import train_test_split, KFold, GroupKFold

sys.path.insert(0, str(Path(__file__).parent))

from phase2_utils import calculate_metrics, save_results
from data_validation import check_overfitting, check_stability

from lightgbm import LGBMRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor

def train_evaluate_ml(X, y, groups, model_name, model_class, eval_mode, output_stem, oof_dir=None):
    """
    ML 모델 학습 및 평가

    eval_mode: 'holdout', '5foldcv', 'groupcv'
    """
    print(f"\n{'='*120}")
    print(f"{model_name} - {eval_mode.upper()}")
    print(f"{'='*120}")

    if eval_mode == 'holdout':
        # Holdout (8:2)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )

        model = model_class()
        model.fit(X_train, y_train)

        train_pred = model.predict(X_train)
        test_pred = model.predict(X_test)

        train_metrics = calculate_metrics(y_train, train_pred)
        test_metrics = calculate_metrics(y_test, test_pred)

        results = {
            'model': model_name,
            'eval_mode': 'holdout',
            'train': train_metrics,
            'test': test_metrics,
            'gap': {
                'spearman': train_metrics['spearman'] - test_metrics['spearman'],
                'rmse': train_metrics['rmse'] - test_metrics['rmse']
            }
        }

        print(f"  Train Spearman: {train_metrics['spearman']:.4f}")
        print(f"  Test  Spearman: {test_metrics['spearman']:.4f}")
        print(f"  Gap:            {results['gap']['spearman']:+.4f}")

    elif eval_mode == '5foldcv':
        # 5-Fold CV (일반)
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        fold_results = []

        for fold_idx, (train_idx, val_idx) in enumerate(kf.split(X), 1):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            model = model_class()
            model.fit(X_train, y_train)

            train_pred = model.predict(X_train)
            val_pred = model.predict(X_val)

            train_metrics = calculate_metrics(y_train, train_pred)
            val_metrics = calculate_metrics(y_val, val_pred)

            fold_results.append({
                'fold': fold_idx,
                'train': train_metrics,
                'val': val_metrics
            })

            print(f"  Fold {fold_idx}: Train={train_metrics['spearman']:.4f}, Val={val_metrics['spearman']:.4f}")

        # 집계
        overfitting_check = check_overfitting(fold_results)
        stability_check = check_stability(fold_results)

        results = {
            'model': model_name,
            'eval_mode': '5foldcv',
            'fold_results': fold_results,
            'overfitting_check': overfitting_check,
            'stability_check': stability_check
        }

    else:  # groupcv
        # GroupCV (3-fold by canonical_drug_id)
        gkf = GroupKFold(n_splits=3)
        fold_results = []
        oof_predictions = np.zeros(len(y))

        for fold_idx, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups=groups), 1):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            model = model_class()
            model.fit(X_train, y_train)

            train_pred = model.predict(X_train)
            val_pred = model.predict(X_val)

            # OOF 저장
            oof_predictions[val_idx] = val_pred

            train_metrics = calculate_metrics(y_train, train_pred)
            val_metrics = calculate_metrics(y_val, val_pred)

            fold_results.append({
                'fold': fold_idx,
                'train': train_metrics,
                'val': val_metrics
            })

            print(f"  Fold {fold_idx}: Train={train_metrics['spearman']:.4f}, Val={val_metrics['spearman']:.4f}")

        # OOF 저장
        if oof_dir:
            np.save(oof_dir / f"{model_name}.npy", oof_predictions)

        # 집계
        overfitting_check = check_overfitting(fold_results)
        stability_check = check_stability(fold_results)

        results = {
            'model': model_name,
            'eval_mode': 'groupcv',
            'fold_results': fold_results,
            'overfitting_check': overfitting_check,
            'stability_check': stability_check
        }

    return results


def run_phase_ml(input_file, output_stem, phase_name):
    """
    하나의 입력셋에 대해 ML 모델 전체 실행
    """
    print("\n" + "="*120)
    print(f"{phase_name}: ML Models")
    print("="*120)

    # 경로 설정
    base_dir = Path(__file__).parent
    data_dir = base_dir / "data"
    results_dir = base_dir / "results"

    # OOF 디렉토리
    oof_dir = results_dir / f"{output_stem}_oof"
    oof_dir.mkdir(exist_ok=True)

    # 데이터 로드
    X = np.load(data_dir / input_file)
    y = np.load(data_dir / "y_train.npy")

    # Groups 로드
    features_path = Path("/Users/skku_aws2_14/20260408_pre_project_biso_myprotocol/20260408_pre_project_biso_myprotocol/20260414_re_pre_project_v3/features_slim.parquet")
    df_meta = pd.read_parquet(features_path, columns=['canonical_drug_id'])
    groups = df_meta['canonical_drug_id'].values

    print(f"\nData: {input_file}")
    print(f"X shape: {X.shape}")
    print(f"y shape: {y.shape}")

    # 모델 정의 (기본 하이퍼파라미터)
    models = {
        'LightGBM': lambda: LGBMRegressor(random_state=42, verbose=-1, n_jobs=-1),
        'LightGBM_DART': lambda: LGBMRegressor(boosting_type='dart', random_state=42, verbose=-1, n_jobs=-1),
        'XGBoost': lambda: XGBRegressor(random_state=42, verbosity=0, n_jobs=-1),
        'CatBoost': lambda: CatBoostRegressor(random_state=42, verbose=0),
        'RandomForest': lambda: RandomForestRegressor(random_state=42, n_jobs=-1),
        'ExtraTrees': lambda: ExtraTreesRegressor(random_state=42, n_jobs=-1)
    }

    # 3가지 평가 방식
    eval_modes = ['holdout', '5foldcv', 'groupcv']

    all_results = {mode: {} for mode in eval_modes}

    for model_name, model_class in models.items():
        for eval_mode in eval_modes:
            oof_dir_arg = oof_dir if eval_mode == 'groupcv' else None

            results = train_evaluate_ml(
                X, y, groups,
                model_name, model_class,
                eval_mode, output_stem,
                oof_dir=oof_dir_arg
            )

            all_results[eval_mode][model_name] = results

    # 결과 저장 (평가 방식별로 분리)
    for eval_mode in eval_modes:
        output_file = results_dir / f"{output_stem}_{eval_mode}.json"
        save_results(all_results[eval_mode], output_file)

    # 중간 요약
    print("\n" + "="*120)
    print(f"{phase_name} 완료 - 중간 요약")
    print("="*120)

    for eval_mode in eval_modes:
        print(f"\n[{eval_mode.upper()}]")
        print("-" * 100)
        print(f"{'Model':20s} | {'Val/Test Spearman':>18} | {'Gap':>10}")
        print("-" * 100)

        for model_name, result in all_results[eval_mode].items():
            if eval_mode == 'holdout':
                val_spearman = result['test']['spearman']
                gap = result['gap']['spearman']
                print(f"{model_name:20s} | {val_spearman:18.4f} | {gap:10.4f}")
            else:
                # fold 평균
                val_sps = [f['val']['spearman'] for f in result['fold_results']]
                train_sps = [f['train']['spearman'] for f in result['fold_results']]
                val_mean = np.mean(val_sps)
                gap = np.mean(train_sps) - val_mean
                print(f"{model_name:20s} | {val_mean:18.4f} | {gap:10.4f}")

    return all_results


if __name__ == "__main__":
    # Phase 2A: numeric-only
    print("\n" + "="*120)
    print("Phase 2A: numeric-only")
    print("="*120)

    results_2a = run_phase_ml(
        input_file="X_numeric.npy",
        output_stem="choi_numeric_ml_v1",
        phase_name="Phase 2A"
    )

    # Phase 2B: numeric + SMILES
    print("\n" + "="*120)
    print("Phase 2B: numeric + SMILES")
    print("="*120)

    results_2b = run_phase_ml(
        input_file="X_numeric_smiles.npy",
        output_stem="choi_numeric_smiles_ml_v1",
        phase_name="Phase 2B"
    )

    # Phase 2C: numeric + context + SMILES
    print("\n" + "="*120)
    print("Phase 2C: numeric + context + SMILES")
    print("="*120)

    results_2c = run_phase_ml(
        input_file="X_numeric_context_smiles.npy",
        output_stem="choi_numeric_context_smiles_ml_v1",
        phase_name="Phase 2C"
    )

    print("\n" + "="*120)
    print("전체 ML 학습 완료!")
    print("="*120)
