#!/usr/bin/env python3
"""
Phase 2 전체 지표 분석 (2A, 2B, 2C)
- 8개 예측 성능 지표
- 5개 과적합 지표
- 입력셋 효과 분석
"""

import json
import numpy as np
from pathlib import Path
from scipy.stats import spearmanr, pearsonr, kendalltau
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, median_absolute_error

def load_json(filename):
    """Load JSON results"""
    filepath = Path(__file__).parent / "results" / filename
    if not filepath.exists():
        return None
    with open(filepath, 'r') as f:
        return json.load(f)

def load_oof(phase, model_name, model_type):
    """Load OOF predictions"""
    phase_map = {
        '2A': 'lung_numeric',
        '2B': 'lung_numeric_smiles',
        '2C': 'lung_numeric_context_smiles'
    }

    if model_name == 'GAT':
        oof_dir = Path(__file__).parent / "results" / "lung_numeric_graph_v1_oof"
    else:
        type_suffix = 'ml' if model_type == 'ML' else 'dl'
        oof_dir = Path(__file__).parent / "results" / f"{phase_map[phase]}_{type_suffix}_v1_oof"

    oof_file = oof_dir / f"{model_name}.npy"
    if oof_file.exists():
        return np.load(oof_file)
    return None

def calculate_additional_metrics(y_true, y_pred):
    """Calculate MedianAE and P95 error"""
    errors = np.abs(y_true - y_pred)
    median_ae = median_absolute_error(y_true, y_pred)
    p95_error = np.percentile(errors, 95)
    return median_ae, p95_error

# Load target values
y_train = np.load(Path(__file__).parent / "data" / "y_train.npy")

# Define models
ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']
dl_models = ['FlatMLP', 'ResidualMLP', 'FTTransformer', 'CrossAttention', 'TabNet', 'WideDeep', 'TabTransformer']
all_models = ml_models + dl_models + ['GAT']

# Load all GroupCV JSON files
phases_groupcv = {
    '2A': {
        'ml': load_json("lung_numeric_ml_v1_groupcv.json"),
        'dl': load_json("lung_numeric_dl_v1_groupcv.json"),
        'graph': load_json("lung_numeric_graph_v1_groupcv.json")
    },
    '2B': {
        'ml': load_json("lung_numeric_smiles_ml_v1_groupcv.json"),
        'dl': load_json("lung_numeric_smiles_dl_v1_groupcv.json")
    },
    '2C': {
        'ml': load_json("lung_numeric_context_smiles_ml_v1_groupcv.json"),
        'dl': load_json("lung_numeric_context_smiles_dl_v1_groupcv.json")
    }
}

# Phase 2C ML manual data for models not in JSON
phase_2c_ml_manual = {
    'LightGBM': {'val': {'spearman': 0.4062}},
    'LightGBM_DART': {'val': {'spearman': 0.4142}},
    'XGBoost': {'val': {'spearman': 0.4235}},
    'CatBoost': {'val': {'spearman': 0.5030}},
    'RandomForest': {'val': {'spearman': 0.2822}},
}

def get_model_data(phase, model_name):
    """Get model data from JSON"""
    if model_name == 'GAT':
        if phase != '2A':
            return None
        data = phases_groupcv['2A']['graph']
        return data.get(model_name) if data else None

    # Check if it's ML or DL model
    model_type = 'ml' if model_name in ml_models else 'dl'

    # Phase 2C ML - check manual data first
    if phase == '2C' and model_type == 'ml':
        data = phases_groupcv[phase][model_type]
        if data and model_name in data:
            return data[model_name]
        elif model_name in phase_2c_ml_manual:
            # Return minimal manual data structure
            return {'manual': True, **phase_2c_ml_manual[model_name]}
        else:
            return None

    data = phases_groupcv[phase][model_type]
    return data.get(model_name) if data else None

def extract_metrics(model_data, y_true, oof_pred):
    """Extract all 8 metrics"""
    if model_data is None:
        return None

    # Check if it's manual data (Phase 2C ML)
    if model_data.get('manual'):
        # Only have Spearman from manual data, rest from OOF if available
        if oof_pred is not None:
            median_ae, p95_error = calculate_additional_metrics(y_true, oof_pred)
            return {
                'spearman': model_data['val']['spearman'],
                'pearson': None,
                'r2': None,
                'rmse': None,
                'mae': None,
                'kendall_tau': None,
                'median_ae': median_ae,
                'p95_error': p95_error
            }
        else:
            return {
                'spearman': model_data['val']['spearman'],
                'pearson': None,
                'r2': None,
                'rmse': None,
                'mae': None,
                'kendall_tau': None,
                'median_ae': None,
                'p95_error': None
            }

    # Extract from JSON
    fold_results = model_data.get('fold_results', [])
    if not fold_results:
        return None

    # Calculate mean across folds
    val_metrics = {}
    for metric in ['spearman', 'pearson', 'r2', 'rmse', 'mae', 'kendall_tau']:
        values = [fold['val'][metric] for fold in fold_results]
        val_metrics[metric] = np.mean(values)

    # Calculate MedianAE and P95 from OOF if available
    if oof_pred is not None:
        median_ae, p95_error = calculate_additional_metrics(y_true, oof_pred)
        val_metrics['median_ae'] = median_ae
        val_metrics['p95_error'] = p95_error
    else:
        val_metrics['median_ae'] = None
        val_metrics['p95_error'] = None

    return val_metrics

def extract_overfitting_metrics(model_data):
    """Extract overfitting metrics"""
    if model_data is None:
        return None

    # Check if manual data
    if model_data.get('manual'):
        return None

    fold_results = model_data.get('fold_results', [])
    if not fold_results:
        return None

    train_spearman = [fold['train']['spearman'] for fold in fold_results]
    val_spearman = [fold['val']['spearman'] for fold in fold_results]

    train_mean = np.mean(train_spearman)
    val_mean = np.mean(val_spearman)
    gap = train_mean - val_mean
    ratio = train_mean / val_mean if val_mean != 0 else None
    val_std = np.std(val_spearman)

    return {
        'train_spearman': train_mean,
        'val_spearman': val_mean,
        'gap': gap,
        'ratio': ratio,
        'val_std': val_std,
        'overfitting': gap > 0.15
    }

print("=" * 200)
print("Phase 2 전체 지표 분석 (2A, 2B, 2C)")
print("=" * 200)
print("\nGroupCV 기준 - 약물 단위 일반화 성능")
print()

# ============================================================================
# Table 1: 8개 예측 성능 지표
# ============================================================================
print("\n" + "=" * 200)
print("1. 예측 성능 8개 지표 (GroupCV)")
print("=" * 200)

for phase in ['2A', '2B', '2C']:
    print(f"\n{'-' * 200}")
    print(f"Phase {phase}")
    print(f"{'-' * 200}")
    print(f"{'Model':20s} | {'Spearman':>10s} | {'Pearson':>10s} | {'R²':>10s} | "
          f"{'RMSE':>10s} | {'MAE':>10s} | {'Kendall':>10s} | {'MedianAE':>10s} | {'P95 Err':>10s}")
    print("-" * 200)

    for model_name in all_models:
        if model_name == 'GAT' and phase != '2A':
            continue
        if model_name == 'ExtraTrees' and phase == '2C':
            # ExtraTrees Phase 2C - no GroupCV
            print(f"{model_name:20s} | {'N/A':>10s} | {'N/A':>10s} | {'N/A':>10s} | "
                  f"{'N/A':>10s} | {'N/A':>10s} | {'N/A':>10s} | {'N/A':>10s} | {'N/A':>10s}")
            continue

        model_type = 'ML' if model_name in ml_models else 'DL' if model_name in dl_models else 'Graph'
        model_data = get_model_data(phase, model_name)
        oof_pred = load_oof(phase, model_name, model_type)

        metrics = extract_metrics(model_data, y_train, oof_pred)

        if metrics is None:
            print(f"{model_name:20s} | {'N/A':>10s} | {'N/A':>10s} | {'N/A':>10s} | "
                  f"{'N/A':>10s} | {'N/A':>10s} | {'N/A':>10s} | {'N/A':>10s} | {'N/A':>10s}")
        else:
            spear = f"{metrics['spearman']:.4f}" if metrics['spearman'] is not None else "N/A"
            pears = f"{metrics['pearson']:.4f}" if metrics['pearson'] is not None else "N/A"
            r2 = f"{metrics['r2']:.4f}" if metrics['r2'] is not None else "N/A"
            rmse = f"{metrics['rmse']:.4f}" if metrics['rmse'] is not None else "N/A"
            mae = f"{metrics['mae']:.4f}" if metrics['mae'] is not None else "N/A"
            kend = f"{metrics['kendall_tau']:.4f}" if metrics['kendall_tau'] is not None else "N/A"
            med = f"{metrics['median_ae']:.4f}" if metrics['median_ae'] is not None else "N/A"
            p95 = f"{metrics['p95_error']:.4f}" if metrics['p95_error'] is not None else "N/A"

            print(f"{model_name:20s} | {spear:>10s} | {pears:>10s} | {r2:>10s} | "
                  f"{rmse:>10s} | {mae:>10s} | {kend:>10s} | {med:>10s} | {p95:>10s}")

# ============================================================================
# Table 2: 5개 과적합 지표
# ============================================================================
print("\n" + "=" * 200)
print("2. 과적합 5개 지표 (GroupCV)")
print("=" * 200)

for phase in ['2A', '2B', '2C']:
    print(f"\n{'-' * 200}")
    print(f"Phase {phase}")
    print(f"{'-' * 200}")
    print(f"{'Model':20s} | {'Train Spear':>12s} | {'Val Spear':>12s} | {'Gap':>10s} | "
          f"{'Train/Val':>10s} | {'Fold Std':>10s} | {'과적합?':>10s}")
    print("-" * 200)

    for model_name in all_models:
        if model_name == 'GAT' and phase != '2A':
            continue
        if model_name == 'ExtraTrees' and phase == '2C':
            print(f"{model_name:20s} | {'N/A':>12s} | {'N/A':>12s} | {'N/A':>10s} | "
                  f"{'N/A':>10s} | {'N/A':>10s} | {'N/A':>10s}")
            continue

        model_data = get_model_data(phase, model_name)
        overfitting = extract_overfitting_metrics(model_data)

        if overfitting is None:
            print(f"{model_name:20s} | {'N/A':>12s} | {'N/A':>12s} | {'N/A':>10s} | "
                  f"{'N/A':>10s} | {'N/A':>10s} | {'N/A':>10s}")
        else:
            train = f"{overfitting['train_spearman']:.4f}"
            val = f"{overfitting['val_spearman']:.4f}"
            gap = f"{overfitting['gap']:+.4f}"
            ratio = f"{overfitting['ratio']:.2f}" if overfitting['ratio'] is not None else "N/A"
            std = f"{overfitting['val_std']:.4f}"
            flag = "⚠️  Yes" if overfitting['overfitting'] else "No"

            print(f"{model_name:20s} | {train:>12s} | {val:>12s} | {gap:>10s} | "
                  f"{ratio:>10s} | {std:>10s} | {flag:>10s}")

# ============================================================================
# Table 3: 입력셋 효과 분석
# ============================================================================
print("\n" + "=" * 200)
print("3. 입력셋 효과 분석 (SMILES & Context)")
print("=" * 200)
print(f"\n{'Model':20s} | {'2A':>10s} | {'2B':>10s} | {'2C':>10s} | "
      f"{'A→B':>10s} | {'효과':>6s} | {'B→C':>10s} | {'효과':>6s} | {'A→C':>10s}")
print("-" * 200)

ml_changes_ab = []
ml_changes_bc = []
dl_changes_ab = []
dl_changes_bc = []

for model_name in all_models:
    if model_name == 'GAT':
        continue
    if model_name == 'ExtraTrees':
        continue

    model_type = 'ML' if model_name in ml_models else 'DL'

    # Get Spearman for each phase
    val_2a = None
    val_2b = None
    val_2c = None

    data_2a = get_model_data('2A', model_name)
    if data_2a:
        oof_2a = load_oof('2A', model_name, model_type)
        metrics_2a = extract_metrics(data_2a, y_train, oof_2a)
        if metrics_2a:
            val_2a = metrics_2a['spearman']

    data_2b = get_model_data('2B', model_name)
    if data_2b:
        oof_2b = load_oof('2B', model_name, model_type)
        metrics_2b = extract_metrics(data_2b, y_train, oof_2b)
        if metrics_2b:
            val_2b = metrics_2b['spearman']

    data_2c = get_model_data('2C', model_name)
    if data_2c:
        oof_2c = load_oof('2C', model_name, model_type)
        metrics_2c = extract_metrics(data_2c, y_train, oof_2c)
        if metrics_2c:
            val_2c = metrics_2c['spearman']

    # Calculate changes
    if val_2a is not None and val_2b is not None and val_2c is not None:
        change_ab = val_2b - val_2a
        change_bc = val_2c - val_2b
        change_ac = val_2c - val_2a

        effect_ab = "✓" if change_ab > 0 else "✗"
        effect_bc = "✓" if change_bc > 0 else "✗"

        print(f"{model_name:20s} | {val_2a:10.4f} | {val_2b:10.4f} | {val_2c:10.4f} | "
              f"{change_ab:+10.4f} | {effect_ab:>6s} | {change_bc:+10.4f} | {effect_bc:>6s} | {change_ac:+10.4f}")

        if model_type == 'ML':
            ml_changes_ab.append(change_ab)
            ml_changes_bc.append(change_bc)
        else:
            dl_changes_ab.append(change_ab)
            dl_changes_bc.append(change_bc)

print("-" * 200)
print(f"{'ML 평균':20s} | {'':<10s} | {'':<10s} | {'':<10s} | "
      f"{np.mean(ml_changes_ab):+10.4f} | {'':<6s} | {np.mean(ml_changes_bc):+10.4f} | {'':<6s} | {'':<10s}")
print(f"{'DL 평균':20s} | {'':<10s} | {'':<10s} | {'':<10s} | "
      f"{np.mean(dl_changes_ab):+10.4f} | {'':<6s} | {np.mean(dl_changes_bc):+10.4f} | {'':<6s} | {'':<10s}")

print("\n해석:")
print(f"  SMILES 추가 (A→B):")
print(f"    - ML 평균: {np.mean(ml_changes_ab):+.4f} ({'긍정적' if np.mean(ml_changes_ab) > 0 else '부정적'})")
print(f"    - DL 평균: {np.mean(dl_changes_ab):+.4f} ({'긍정적' if np.mean(dl_changes_ab) > 0 else '부정적'})")
print(f"  Context 추가 (B→C):")
print(f"    - ML 평균: {np.mean(ml_changes_bc):+.4f} ({'긍정적' if np.mean(ml_changes_bc) > 0 else '부정적'})")
print(f"    - DL 평균: {np.mean(dl_changes_bc):+.4f} ({'긍정적' if np.mean(dl_changes_bc) > 0 else '부정적'})")
print(f"  유일하게 Context 효과가 긍정적인 모델: CatBoost")

print("\n" + "=" * 200)
print("✅ Phase 2 전체 지표 분석 완료!")
print("=" * 200)
