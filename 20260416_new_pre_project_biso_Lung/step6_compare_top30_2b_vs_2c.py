#!/usr/bin/env python3
"""
Extract and compare Top 30 drugs from Phase 2B vs 2C CatBoost models.
"""

import numpy as np
import pandas as pd
from pathlib import Path

def extract_top30(phase_name, oof_path, features_path='features_slim.parquet'):
    """Extract top 30 drugs based on OOF predictions."""

    print(f"\n{'='*80}")
    print(f"EXTRACTING TOP 30: {phase_name}")
    print(f"{'='*80}")

    # Load OOF predictions
    print(f"[1/3] Loading OOF predictions: {oof_path}")
    y_pred = np.load(oof_path, allow_pickle=True)
    print(f"✓ Loaded {len(y_pred)} predictions")
    print(f"  - Predicted IC50 range: [{y_pred.min():.2f}, {y_pred.max():.2f}]")

    # Load features
    print(f"\n[2/3] Loading features: {features_path}")
    features_df = pd.read_parquet(features_path)
    print(f"✓ Features shape: {features_df.shape}")

    # Ensure length matches
    if len(y_pred) != len(features_df):
        min_len = min(len(y_pred), len(features_df))
        y_pred = y_pred[:min_len]
        features_df = features_df.iloc[:min_len].copy()
        print(f"⚠️  Adjusted to {min_len} samples")

    # Create DataFrame
    df = pd.DataFrame({
        'sample_id': features_df['sample_id'].values,
        'canonical_drug_id': features_df['canonical_drug_id'].values,
        'pred_ic50': y_pred
    })
    df['cell_line_name'] = df['sample_id'].str.split('-').str[0]

    print(f"\n[3/3] Calculating drug-level statistics...")
    print(f"✓ Total samples: {len(df)}")
    print(f"✓ Unique drugs: {df['canonical_drug_id'].nunique()}")
    print(f"✓ Unique cell lines: {df['cell_line_name'].nunique()}")

    # Calculate drug-level statistics
    drug_stats = df.groupby('canonical_drug_id').agg({
        'pred_ic50': ['mean', 'std', 'min', 'max', 'count'],
        'cell_line_name': 'nunique'
    }).reset_index()

    drug_stats.columns = [
        'canonical_drug_id',
        'pred_ic50_mean', 'pred_ic50_std', 'pred_ic50_min', 'pred_ic50_max', 'n_samples',
        'n_celllines'
    ]

    # Sort by predicted IC50 (lower = more effective)
    drug_stats = drug_stats.sort_values('pred_ic50_mean').reset_index(drop=True)

    # Extract Top 30
    top30 = drug_stats.head(30).copy()
    top30['rank'] = np.arange(1, 31)

    # Reorder columns
    top30 = top30[['rank', 'canonical_drug_id', 'pred_ic50_mean', 'pred_ic50_std',
                   'pred_ic50_min', 'pred_ic50_max', 'n_samples', 'n_celllines']]

    return top30, drug_stats

def compare_top30(top30_2b, top30_2c):
    """Compare two Top 30 lists."""

    print(f"\n{'='*80}")
    print(f"COMPARING TOP 30: Phase 2B vs 2C")
    print(f"{'='*80}")

    # Get drug sets
    drugs_2b = set(top30_2b['canonical_drug_id'])
    drugs_2c = set(top30_2c['canonical_drug_id'])

    # Calculate overlap
    overlap = drugs_2b & drugs_2c
    only_2b = drugs_2b - drugs_2c
    only_2c = drugs_2c - drugs_2b

    print(f"\n[1] OVERLAP ANALYSIS")
    print(f"{'─'*80}")
    print(f"✓ Common drugs (Overlap): {len(overlap)}/30 ({len(overlap)/30*100:.1f}%)")
    print(f"✓ Only in 2B: {len(only_2b)}/30 ({len(only_2b)/30*100:.1f}%)")
    print(f"✓ Only in 2C: {len(only_2c)}/30 ({len(only_2c)/30*100:.1f}%)")

    # Common drugs ranking comparison
    print(f"\n[2] RANKING CHANGES (Common Drugs)")
    print(f"{'─'*80}")

    common_drugs = []
    for drug_id in overlap:
        rank_2b = top30_2b[top30_2b['canonical_drug_id'] == drug_id]['rank'].values[0]
        rank_2c = top30_2c[top30_2c['canonical_drug_id'] == drug_id]['rank'].values[0]
        ic50_2b = top30_2b[top30_2b['canonical_drug_id'] == drug_id]['pred_ic50_mean'].values[0]
        ic50_2c = top30_2c[top30_2c['canonical_drug_id'] == drug_id]['pred_ic50_mean'].values[0]

        common_drugs.append({
            'canonical_drug_id': drug_id,
            'rank_2b': rank_2b,
            'rank_2c': rank_2c,
            'rank_change': rank_2c - rank_2b,
            'ic50_2b': ic50_2b,
            'ic50_2c': ic50_2c,
            'ic50_change': ic50_2c - ic50_2b
        })

    df_common = pd.DataFrame(common_drugs).sort_values('rank_change')

    # Biggest improvements (2C better)
    improved = df_common[df_common['rank_change'] < 0].head(5)
    if len(improved) > 0:
        print(f"\n▲ Top 5 Improved in 2C (moved up):")
        print(improved[['canonical_drug_id', 'rank_2b', 'rank_2c', 'rank_change']].to_string(index=False))

    # Biggest declines (2B better)
    declined = df_common[df_common['rank_change'] > 0].tail(5).sort_values('rank_change', ascending=False)
    if len(declined) > 0:
        print(f"\n▼ Top 5 Declined in 2C (moved down):")
        print(declined[['canonical_drug_id', 'rank_2b', 'rank_2c', 'rank_change']].to_string(index=False))

    # Stable rankings
    stable = df_common[df_common['rank_change'].abs() <= 2]
    print(f"\n═ Stable rankings (±2 positions): {len(stable)}/{len(df_common)} ({len(stable)/len(df_common)*100:.1f}%)")

    # New entrants in 2C
    print(f"\n[3] NEW ENTRANTS IN 2C (Top 30)")
    print(f"{'─'*80}")
    if len(only_2c) > 0:
        new_2c = top30_2c[top30_2c['canonical_drug_id'].isin(only_2c)].copy()
        print(new_2c[['rank', 'canonical_drug_id', 'pred_ic50_mean']].to_string(index=False))
    else:
        print("No new drugs in 2C Top 30")

    # Dropped from 2B
    print(f"\n[4] DROPPED FROM 2B (Not in 2C Top 30)")
    print(f"{'─'*80}")
    if len(only_2b) > 0:
        dropped_2b = top30_2b[top30_2b['canonical_drug_id'].isin(only_2b)].copy()
        print(dropped_2b[['rank', 'canonical_drug_id', 'pred_ic50_mean']].to_string(index=False))
    else:
        print("No drugs dropped from 2B")

    # Summary statistics
    print(f"\n[5] PREDICTION CHANGES")
    print(f"{'─'*80}")
    print(f"✓ Mean IC50 2B: {top30_2b['pred_ic50_mean'].mean():.3f}")
    print(f"✓ Mean IC50 2C: {top30_2c['pred_ic50_mean'].mean():.3f}")
    print(f"✓ IC50 change: {top30_2c['pred_ic50_mean'].mean() - top30_2b['pred_ic50_mean'].mean():.3f}")

    if len(df_common) > 0:
        print(f"\n✓ Common drugs mean IC50 change: {df_common['ic50_change'].mean():.3f}")
        print(f"✓ Common drugs mean rank change: {df_common['rank_change'].mean():.2f}")

    return df_common, new_2c if len(only_2c) > 0 else pd.DataFrame(), dropped_2b if len(only_2b) > 0 else pd.DataFrame()

def main():
    print("="*80)
    print("STEP 6: TOP 30 COMPARISON (Phase 2B vs 2C CatBoost)")
    print("="*80)

    # Extract Top 30 from both phases
    top30_2b, all_drugs_2b = extract_top30(
        "Phase 2B CatBoost (Spearman=0.4823)",
        "results/lung_numeric_smiles_ml_v1_oof/CatBoost.npy"
    )

    top30_2c, all_drugs_2c = extract_top30(
        "Phase 2C CatBoost (Spearman=0.5030)",
        "results/lung_numeric_context_smiles_ml_v1_oof/CatBoost.npy"
    )

    # Save individual Top 30 lists
    top30_2b.to_csv('results/lung_top30_phase2b_catboost.csv', index=False)
    top30_2c.to_csv('results/lung_top30_phase2c_catboost.csv', index=False)
    print(f"\n✓ Saved: results/lung_top30_phase2b_catboost.csv")
    print(f"✓ Saved: results/lung_top30_phase2c_catboost.csv")

    # Compare
    df_common, df_new_2c, df_dropped_2b = compare_top30(top30_2b, top30_2c)

    # Save comparison results
    if len(df_common) > 0:
        df_common.to_csv('results/lung_top30_common_2b_vs_2c.csv', index=False)
        print(f"\n✓ Saved: results/lung_top30_common_2b_vs_2c.csv")

    if len(df_new_2c) > 0:
        df_new_2c.to_csv('results/lung_top30_new_in_2c.csv', index=False)
        print(f"✓ Saved: results/lung_top30_new_in_2c.csv")

    if len(df_dropped_2b) > 0:
        df_dropped_2b.to_csv('results/lung_top30_dropped_from_2b.csv', index=False)
        print(f"✓ Saved: results/lung_top30_dropped_from_2b.csv")

    # Create unified Top 30 list (union)
    all_top30_drugs = set(top30_2b['canonical_drug_id']) | set(top30_2c['canonical_drug_id'])
    print(f"\n{'='*80}")
    print(f"UNIFIED TOP 30 LIST (Union of 2B and 2C)")
    print(f"{'='*80}")
    print(f"✓ Total unique drugs for external validation: {len(all_top30_drugs)}")

    # Create unified DataFrame
    unified_drugs = []
    for drug_id in all_top30_drugs:
        row = {'canonical_drug_id': drug_id}

        if drug_id in set(top30_2b['canonical_drug_id']):
            row['in_2b'] = True
            row['rank_2b'] = top30_2b[top30_2b['canonical_drug_id'] == drug_id]['rank'].values[0]
            row['ic50_2b'] = top30_2b[top30_2b['canonical_drug_id'] == drug_id]['pred_ic50_mean'].values[0]
        else:
            row['in_2b'] = False
            row['rank_2b'] = None
            row['ic50_2b'] = None

        if drug_id in set(top30_2c['canonical_drug_id']):
            row['in_2c'] = True
            row['rank_2c'] = top30_2c[top30_2c['canonical_drug_id'] == drug_id]['rank'].values[0]
            row['ic50_2c'] = top30_2c[top30_2c['canonical_drug_id'] == drug_id]['pred_ic50_mean'].values[0]
        else:
            row['in_2c'] = False
            row['rank_2c'] = None
            row['ic50_2c'] = None

        unified_drugs.append(row)

    df_unified = pd.DataFrame(unified_drugs)
    df_unified.to_csv('results/lung_top30_unified_2b_and_2c.csv', index=False)
    print(f"✓ Saved: results/lung_top30_unified_2b_and_2c.csv")

    print(f"\n{'='*80}")
    print(f"TOP 30 EXTRACTION AND COMPARISON COMPLETE")
    print(f"{'='*80}")

    return top30_2b, top30_2c, df_unified

if __name__ == '__main__':
    main()
