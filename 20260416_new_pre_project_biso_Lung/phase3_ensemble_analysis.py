#!/usr/bin/env python3
"""
Phase 3 앙상블 분석
- 4개 조합 × 2개 방식 × 3개 Phase = 24개 실험
"""

import json
import numpy as np
from pathlib import Path
from scipy.stats import spearmanr
from itertools import combinations

def load_json(filename):
    """Load JSON results"""
    filepath = Path(__file__).parent / "results" / filename
    if not filepath.exists():
        return None
    with open(filepath, 'r') as f:
        return json.load(f)

def load_oof(phase, model_name):
    """Load OOF predictions"""
    phase_map = {
        '2A': 'lung_numeric',
        '2B': 'lung_numeric_smiles',
        '2C': 'lung_numeric_context_smiles'
    }

    # Determine model type
    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']

    if model_name == 'GAT':
        oof_dir = Path(__file__).parent / "results" / "lung_numeric_graph_v1_oof"
    elif model_name in ml_models:
        oof_dir = Path(__file__).parent / "results" / f"{phase_map[phase]}_ml_v1_oof"
    else:
        oof_dir = Path(__file__).parent / "results" / f"{phase_map[phase]}_dl_v1_oof"

    oof_file = oof_dir / f"{model_name}.npy"
    if oof_file.exists():
        return np.load(oof_file)
    return None

def get_groupcv_spearman(phase, model_name):
    """Get GroupCV Spearman for a model"""
    phase_map = {
        '2A': 'lung_numeric',
        '2B': 'lung_numeric_smiles',
        '2C': 'lung_numeric_context_smiles'
    }

    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']

    if model_name in ml_models:
        data = load_json(f"{phase_map[phase]}_ml_v1_groupcv.json")
    else:
        data = load_json(f"{phase_map[phase]}_dl_v1_groupcv.json")

    if data is None or model_name not in data:
        # Phase 2C ML manual values
        manual_values = {
            '2C': {
                'LightGBM': 0.4062,
                'LightGBM_DART': 0.4142,
                'XGBoost': 0.4235,
                'CatBoost': 0.5030,
                'RandomForest': 0.2822
            }
        }
        if phase in manual_values and model_name in manual_values[phase]:
            return manual_values[phase][model_name]
        return None

    model_data = data[model_name]
    fold_results = model_data.get('fold_results', [])
    if not fold_results:
        return None

    val_scores = [fold['val']['spearman'] for fold in fold_results]
    return np.mean(val_scores)

def calculate_diversity(predictions_list):
    """Calculate average pairwise correlation (diversity)"""
    n = len(predictions_list)
    if n < 2:
        return 0.0

    correlations = []
    for i, j in combinations(range(n), 2):
        corr, _ = spearmanr(predictions_list[i], predictions_list[j])
        correlations.append(corr)

    return np.mean(correlations)

def calculate_error_overlap(y_true, predictions_list, threshold=1.0):
    """Calculate error overlap - how often models make errors together"""
    n = len(predictions_list)
    if n < 2:
        return 0.0

    # Calculate errors for each model
    errors = [np.abs(y_true - pred) > threshold for pred in predictions_list]

    # Calculate overlap
    overlaps = []
    for i, j in combinations(range(n), 2):
        overlap = np.mean(errors[i] & errors[j]) / (np.mean(errors[i] | errors[j]) + 1e-10)
        overlaps.append(overlap)

    return np.mean(overlaps)

def calculate_consensus_score(predictions_list):
    """Calculate consensus - standard deviation across models"""
    # Lower std = higher consensus
    stacked = np.stack(predictions_list, axis=0)
    std_per_sample = np.std(stacked, axis=0)
    return np.mean(std_per_sample)

# Load target
y_train = np.load(Path(__file__).parent / "data" / "y_train.npy")

# Define ensemble combinations
ensemble_configs = {
    'FRC': ['FlatMLP', 'ResidualMLP', 'CrossAttention'],
    'ML_Top3': ['CatBoost', 'XGBoost', 'LightGBM'],
    'DL_Top3': ['ResidualMLP', 'TabTransformer', 'TabNet'],
    'Mixed': ['CatBoost', 'ResidualMLP', 'TabNet']
}

phases = ['2A', '2B', '2C']
methods = ['Simple', 'Weighted']

print("=" * 200)
print("Phase 3 앙상블 분석")
print("=" * 200)
print("\n4개 조합 × 2개 방식 × 3개 Phase = 24개 실험")
print()

# Store all results
all_results = []

for phase in phases:
    print(f"\n{'='*200}")
    print(f"Phase {phase}")
    print(f"{'='*200}")
    print(f"\n{'Ensemble':15s} | {'Method':10s} | {'Models':60s} | {'Spearman':>10s} | "
          f"{'Best Single':>12s} | {'Gain':>10s} | {'Diversity':>10s} | {'Err Overlap':>12s} | {'Consensus':>10s}")
    print("-" * 200)

    for ens_name, model_list in ensemble_configs.items():
        # Load OOF predictions
        oof_preds = []
        valid_models = []
        model_scores = []

        for model in model_list:
            oof = load_oof(phase, model)
            score = get_groupcv_spearman(phase, model)

            if oof is not None and score is not None:
                oof_preds.append(oof)
                valid_models.append(model)
                model_scores.append(score)

        if len(oof_preds) == 0:
            print(f"{ens_name:15s} | {'N/A':10s} | {'No valid models':60s} | "
                  f"{'N/A':>10s} | {'N/A':>12s} | {'N/A':>10s} | {'N/A':>10s} | {'N/A':>12s} | {'N/A':>10s}")
            continue

        # Best single model score
        best_single = max(model_scores)

        # Calculate metrics once (shared between methods)
        diversity = calculate_diversity(oof_preds)
        error_overlap = calculate_error_overlap(y_train, oof_preds)
        consensus = calculate_consensus_score(oof_preds)

        models_str = '+'.join(valid_models)

        for method in methods:
            if method == 'Simple':
                # Simple average
                ensemble_pred = np.mean(oof_preds, axis=0)
            else:  # Weighted
                # Weighted by GroupCV Spearman
                weights = np.array(model_scores)
                weights = weights / weights.sum()
                ensemble_pred = np.average(oof_preds, axis=0, weights=weights)

            # Calculate ensemble Spearman
            ens_spearman, _ = spearmanr(y_train, ensemble_pred)

            # Calculate gain
            gain = ens_spearman - best_single
            gain_str = f"{gain:+.4f}"
            if gain > 0:
                gain_str = f"{gain:+.4f}✓"

            print(f"{ens_name:15s} | {method:10s} | {models_str:60s} | {ens_spearman:10.4f} | "
                  f"{best_single:12.4f} | {gain_str:>10s} | {diversity:10.4f} | {error_overlap:12.4f} | {consensus:10.4f}")

            all_results.append({
                'phase': phase,
                'ensemble': ens_name,
                'method': method,
                'models': valid_models,
                'spearman': ens_spearman,
                'best_single': best_single,
                'gain': gain,
                'diversity': diversity,
                'error_overlap': error_overlap,
                'consensus': consensus
            })

# Summary tables
print("\n" + "=" * 200)
print("Phase별 최고 앙상블")
print("=" * 200)
print(f"\n{'Phase':6s} | {'Ensemble':15s} | {'Method':10s} | {'Spearman':>10s} | {'Gain':>10s} | {'Models':60s}")
print("-" * 200)

for phase in phases:
    phase_results = [r for r in all_results if r['phase'] == phase]
    if phase_results:
        best = max(phase_results, key=lambda x: x['spearman'])
        models_str = '+'.join(best['models'])
        gain_str = f"{best['gain']:+.4f}" + ("✓" if best['gain'] > 0 else "")
        print(f"{phase:6s} | {best['ensemble']:15s} | {best['method']:10s} | {best['spearman']:10.4f} | "
              f"{gain_str:>10s} | {models_str:60s}")

print("\n" + "=" * 200)
print("조합별 평균 성능 (3개 Phase)")
print("=" * 200)
print(f"\n{'Ensemble':15s} | {'Method':10s} | {'Avg Spearman':>12s} | {'Avg Gain':>10s} | "
      f"{'Positive':>8s} | {'Avg Diversity':>12s}")
print("-" * 200)

for ens_name in ensemble_configs.keys():
    for method in methods:
        ens_results = [r for r in all_results if r['ensemble'] == ens_name and r['method'] == method]
        if ens_results:
            avg_spearman = np.mean([r['spearman'] for r in ens_results])
            avg_gain = np.mean([r['gain'] for r in ens_results])
            positive_count = sum(1 for r in ens_results if r['gain'] > 0)
            avg_diversity = np.mean([r['diversity'] for r in ens_results])

            print(f"{ens_name:15s} | {method:10s} | {avg_spearman:12.4f} | {avg_gain:+10.4f} | "
                  f"{positive_count}/{len(ens_results):>6} | {avg_diversity:12.4f}")

print("\n" + "=" * 200)
print("Gain 양수인 조합 (앙상블이 최고 단일 모델보다 우수)")
print("=" * 200)
print(f"\n{'Phase':6s} | {'Ensemble':15s} | {'Method':10s} | {'Spearman':>10s} | {'Best Single':>12s} | "
      f"{'Gain':>10s} | {'Models':60s}")
print("-" * 200)

positive_gains = [r for r in all_results if r['gain'] > 0]
positive_gains.sort(key=lambda x: x['gain'], reverse=True)

for r in positive_gains:
    models_str = '+'.join(r['models'])
    print(f"{r['phase']:6s} | {r['ensemble']:15s} | {r['method']:10s} | {r['spearman']:10.4f} | "
          f"{r['best_single']:12.4f} | {r['gain']:+10.4f} | {models_str:60s}")

if not positive_gains:
    print("양수 Gain 없음 - 단일 모델이 모든 앙상블보다 우수")

print("\n" + "=" * 200)
print("Diversity vs Performance 분석")
print("=" * 200)

# Correlation between diversity and gain
diversities = [r['diversity'] for r in all_results]
gains = [r['gain'] for r in all_results]
from scipy.stats import pearsonr
corr, pval = pearsonr(diversities, gains)

print(f"\nDiversity와 Gain 상관계수: {corr:.4f} (p-value: {pval:.4f})")
print(f"해석: {'낮은 상관은 다양성만으로 앙상블 성능을 설명하기 어려움' if abs(corr) < 0.5 else '다양성과 앙상블 성능 간 유의미한 관계'}")

print("\n" + "=" * 200)
print("✅ Phase 3 앙상블 분석 완료!")
print("=" * 200)
print(f"\n총 {len(all_results)}개 앙상블 실험 완료")
print(f"양수 Gain: {len(positive_gains)}개")
print(f"음수 Gain: {len(all_results) - len(positive_gains)}개")
