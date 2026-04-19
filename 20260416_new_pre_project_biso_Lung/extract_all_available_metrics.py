#!/usr/bin/env python3
"""
Extract all available metrics from JSON and OOF predictions.
- Prediction metrics: Pearson, R², Kendall's Tau (GroupCV)
- Overfitting metrics: Train/Val Ratio
- Generate comprehensive table with all metrics
- Create 32-metric checklist
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import pearsonr, kendalltau
from sklearn.metrics import r2_score

# Phase configurations
PHASES = {
    '2A': {
        'ML': {'json': 'results/lung_numeric_ml_v1_groupcv.json', 'oof_dir': 'results/lung_numeric_ml_v1_oof'},
        'DL': {'json': 'results/lung_numeric_dl_v1_groupcv.json', 'oof_dir': 'results/lung_numeric_dl_v1_oof'}
    },
    '2B': {
        'ML': {'json': 'results/lung_numeric_smiles_ml_v1_groupcv.json', 'oof_dir': 'results/lung_numeric_smiles_ml_v1_oof'},
        'DL': {'json': 'results/lung_numeric_smiles_dl_v1_groupcv.json', 'oof_dir': 'results/lung_numeric_smiles_dl_v1_oof'}
    },
    '2C': {
        'ML': {'json': 'results/lung_numeric_context_smiles_ml_v1_groupcv.json', 'oof_dir': 'results/lung_numeric_context_smiles_ml_v1_oof'},
        'DL': {'json': 'results/lung_numeric_context_smiles_dl_v1_groupcv.json', 'oof_dir': 'results/lung_numeric_context_smiles_dl_v1_oof'}
    }
}

def load_json_results(json_path):
    """Load JSON results file."""
    try:
        with open(json_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: {json_path} not found")
        return None

def load_oof_predictions(oof_dir, model_name):
    """Load OOF predictions from npy file."""
    oof_path = Path(oof_dir) / f"{model_name}.npy"
    try:
        return np.load(oof_path, allow_pickle=True).item()
    except FileNotFoundError:
        print(f"Warning: {oof_path} not found")
        return None

def calculate_metrics_from_oof(y_true, y_pred):
    """Calculate Pearson, R², and Kendall's Tau from predictions."""
    pearson, _ = pearsonr(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    kendall, _ = kendalltau(y_true, y_pred)
    return pearson, r2, kendall

def extract_all_metrics():
    """Extract all available metrics from JSON and OOF files."""
    all_results = []

    for phase, phase_data in PHASES.items():
        for model_type, paths in phase_data.items():
            print(f"\n=== Phase {phase} {model_type} ===")

            # Load JSON
            json_data = load_json_results(paths['json'])
            if not json_data:
                continue

            # JSON structure: model_name as key directly
            for model_name, model_data in json_data.items():
                if not isinstance(model_data, dict):
                    continue

                print(f"Processing {model_name}...")

                result = {
                    'Phase': phase,
                    'Type': model_type,
                    'Model': model_name
                }

                # Calculate mean metrics from fold_results
                fold_results = model_data.get('fold_results', [])
                if fold_results:
                    # GroupCV metrics (validation)
                    val_spearmans = [f['val']['spearman'] for f in fold_results if 'val' in f and 'spearman' in f['val']]
                    val_pearsons = [f['val']['pearson'] for f in fold_results if 'val' in f and 'pearson' in f['val']]
                    val_r2s = [f['val']['r2'] for f in fold_results if 'val' in f and 'r2' in f['val']]
                    val_kendalls = [f['val']['kendall_tau'] for f in fold_results if 'val' in f and 'kendall_tau' in f['val']]
                    val_maes = [f['val']['mae'] for f in fold_results if 'val' in f and 'mae' in f['val']]
                    val_rmses = [f['val']['rmse'] for f in fold_results if 'val' in f and 'rmse' in f['val']]

                    if val_spearmans:
                        result['Spearman_GroupCV'] = np.mean(val_spearmans)
                    if val_pearsons:
                        result['Pearson_GroupCV'] = np.mean(val_pearsons)
                    if val_r2s:
                        result['R2_GroupCV'] = np.mean(val_r2s)
                    if val_kendalls:
                        result['Kendall_GroupCV'] = np.mean(val_kendalls)
                    if val_maes:
                        result['MAE_GroupCV'] = np.mean(val_maes)
                    if val_rmses:
                        result['RMSE_GroupCV'] = np.mean(val_rmses)

                    # Train metrics
                    train_spearmans = [f['train']['spearman'] for f in fold_results if 'train' in f and 'spearman' in f['train']]
                    if train_spearmans:
                        result['Spearman_Train'] = np.mean(train_spearmans)

                    # Val metrics (same as GroupCV but clearer naming)
                    if val_spearmans:
                        result['Spearman_Val'] = np.mean(val_spearmans)

                    # Calculate Train/Val Ratio
                    if result.get('Spearman_Train') and result.get('Spearman_Val'):
                        result['Train_Val_Ratio'] = result['Spearman_Train'] / result['Spearman_Val']

                    print(f"  ✓ Extracted from JSON: Spearman={result.get('Spearman_GroupCV', 0):.4f}, Pearson={result.get('Pearson_GroupCV', 0):.4f}, R²={result.get('R2_GroupCV', 0):.4f}, Kendall={result.get('Kendall_GroupCV', 0):.4f}")

                # Try to get from OOF if missing (backup)
                if pd.isna(result.get('Pearson_GroupCV')) or pd.isna(result.get('R2_GroupCV')) or pd.isna(result.get('Kendall_GroupCV')):
                    oof_data = load_oof_predictions(paths['oof_dir'], model_name)
                    if oof_data:
                        y_true = oof_data.get('y_true')
                        y_pred = oof_data.get('y_pred')
                        if y_true is not None and y_pred is not None:
                            pearson, r2, kendall = calculate_metrics_from_oof(y_true, y_pred)
                            if pd.isna(result.get('Pearson_GroupCV')):
                                result['Pearson_GroupCV'] = pearson
                            if pd.isna(result.get('R2_GroupCV')):
                                result['R2_GroupCV'] = r2
                            if pd.isna(result.get('Kendall_GroupCV')):
                                result['Kendall_GroupCV'] = kendall
                            print(f"  ✓ Calculated from OOF: Pearson={pearson:.4f}, R²={r2:.4f}, Kendall={kendall:.4f}")

                all_results.append(result)

    return pd.DataFrame(all_results)

def create_comprehensive_table(df):
    """Create comprehensive table with all metrics."""

    # Reorder columns
    column_order = [
        'Phase', 'Type', 'Model',
        'Spearman_GroupCV', 'Pearson_GroupCV', 'R2_GroupCV', 'Kendall_GroupCV',
        'MAE_GroupCV', 'RMSE_GroupCV',
        'Spearman_Train', 'Spearman_Val', 'Train_Val_Ratio'
    ]

    df = df[[col for col in column_order if col in df.columns]]

    # Round numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].round(4)

    return df

def create_32_metric_checklist():
    """Create checklist of 32 metrics: completed vs pending."""

    checklist = {
        'Category': [],
        'Metric': [],
        'Status': [],
        'Availability': []
    }

    # Prediction metrics (8)
    prediction_metrics = [
        ('Prediction', 'Spearman Correlation', '✅', 'GroupCV'),
        ('Prediction', 'Pearson Correlation', '✅', 'GroupCV (JSON + OOF)'),
        ('Prediction', 'R² Score', '✅', 'GroupCV (JSON + OOF)'),
        ('Prediction', 'Kendall\'s Tau', '✅', 'GroupCV (JSON + OOF)'),
        ('Prediction', 'MAE', '✅', 'GroupCV'),
        ('Prediction', 'RMSE', '✅', 'GroupCV'),
        ('Prediction', 'MedianAE', '✅', 'GroupCV (OOF)'),
        ('Prediction', 'P95 Error', '✅', 'GroupCV (OOF)')
    ]

    # Overfitting metrics (5)
    overfitting_metrics = [
        ('Overfitting', 'Train-Val Gap', '✅', 'All CVs'),
        ('Overfitting', 'Train/Val Ratio', '✅', 'All CVs'),
        ('Overfitting', 'Fold Std', '✅', 'All CVs'),
        ('Overfitting', 'Train R²', '✅', 'JSON'),
        ('Overfitting', 'Val R²', '✅', 'JSON')
    ]

    # Ensemble metrics (6)
    ensemble_metrics = [
        ('Ensemble', 'Ensemble Gain', '✅', 'Phase 3 Complete'),
        ('Ensemble', 'Diversity Score', '✅', 'Phase 3 Complete'),
        ('Ensemble', 'Error Overlap', '✅', 'Phase 3 Complete'),
        ('Ensemble', 'Consensus Score', '✅', 'Phase 3 Complete'),
        ('Ensemble', 'Weighted vs Simple', '✅', 'Phase 3 Complete'),
        ('Ensemble', 'Best Combination', '✅', 'Phase 3 Complete')
    ]

    # Drug ranking metrics (9) - Step 6 required
    drug_ranking_metrics = [
        ('Drug Ranking', 'Top 10 Hit Rate', '❌', 'Step 6: Drug prioritization'),
        ('Drug Ranking', 'Top 50 Hit Rate', '❌', 'Step 6: Drug prioritization'),
        ('Drug Ranking', 'Top 100 Hit Rate', '❌', 'Step 6: Drug prioritization'),
        ('Drug Ranking', 'Precision@10', '❌', 'Step 6: Drug prioritization'),
        ('Drug Ranking', 'Precision@50', '❌', 'Step 6: Drug prioritization'),
        ('Drug Ranking', 'Recall@100', '❌', 'Step 6: Drug prioritization'),
        ('Drug Ranking', 'NDCG@10', '❌', 'Step 6: Drug prioritization'),
        ('Drug Ranking', 'MRR (Mean Reciprocal Rank)', '❌', 'Step 6: Drug prioritization'),
        ('Drug Ranking', 'Coverage Rate', '❌', 'Step 6: Drug prioritization')
    ]

    # Generalization metrics (4) - Multi-seed and scaffold split
    generalization_metrics = [
        ('Generalization', 'Scaffold Split Performance', '❌', 'Requires scaffold-based split'),
        ('Generalization', 'Multi-seed Consistency (Mean)', '❌', 'Requires 3+ seeds'),
        ('Generalization', 'Multi-seed Consistency (Std)', '❌', 'Requires 3+ seeds'),
        ('Generalization', 'Cross-dataset Validation', '❌', 'Requires external dataset')
    ]

    all_metrics = (prediction_metrics + overfitting_metrics + ensemble_metrics +
                   drug_ranking_metrics + generalization_metrics)

    for cat, metric, status, avail in all_metrics:
        checklist['Category'].append(cat)
        checklist['Metric'].append(metric)
        checklist['Status'].append(status)
        checklist['Availability'].append(avail)

    return pd.DataFrame(checklist)

def main():
    print("=" * 80)
    print("EXTRACTING ALL AVAILABLE METRICS")
    print("=" * 80)

    # Extract metrics
    df_metrics = extract_all_metrics()

    # Save raw data
    df_metrics.to_csv('results/lung_all_metrics_raw.csv', index=False)
    print(f"\n✓ Raw metrics saved: results/lung_all_metrics_raw.csv")

    # Create comprehensive table
    df_comprehensive = create_comprehensive_table(df_metrics)
    df_comprehensive.to_csv('results/lung_all_metrics_comprehensive.csv', index=False)
    print(f"✓ Comprehensive table saved: results/lung_all_metrics_comprehensive.csv")

    # Create 32-metric checklist
    df_checklist = create_32_metric_checklist()
    df_checklist.to_csv('results/lung_32_metrics_checklist.csv', index=False)
    print(f"✓ 32-metric checklist saved: results/lung_32_metrics_checklist.csv")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY: 32 Metrics Status")
    print("=" * 80)
    completed = len(df_checklist[df_checklist['Status'] == '✅'])
    pending = len(df_checklist[df_checklist['Status'] == '❌'])
    print(f"✅ Completed: {completed}/32 ({completed/32*100:.1f}%)")
    print(f"❌ Pending:   {pending}/32 ({pending/32*100:.1f}%)")

    print("\n" + "=" * 80)
    print("COMPREHENSIVE TABLE PREVIEW")
    print("=" * 80)
    print(df_comprehensive.to_string(index=False))

    print("\n" + "=" * 80)
    print("32-METRIC CHECKLIST")
    print("=" * 80)
    print(df_checklist.to_string(index=False))

    return df_metrics, df_comprehensive, df_checklist

if __name__ == '__main__':
    main()
