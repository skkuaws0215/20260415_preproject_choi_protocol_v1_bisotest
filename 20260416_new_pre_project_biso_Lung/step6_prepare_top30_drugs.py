#!/usr/bin/env python3
"""
Step 6 Preparation: Extract Top 30 Drugs
- Use Phase 2B CatBoost (Spearman=0.4823) OOF predictions
- Calculate drug-level average predicted IC50
- Extract Top 30 drugs with lowest predicted IC50 (most effective)
"""

import numpy as np
import pandas as pd
from pathlib import Path

def load_oof_predictions(oof_path):
    """Load OOF predictions from npy file."""
    # OOF files contain only predictions as 1D array
    y_pred = np.load(oof_path, allow_pickle=True)
    return y_pred

def load_features_data(phase='2B'):
    """Load features_slim.parquet to get drug metadata and true IC50."""
    # Try multiple possible locations
    possible_paths = [
        'features_slim.parquet',
        'fe_qc/features_slim.parquet',
        'data/features_slim.parquet',
        '../healthomics-brca-project/pipeline-a-gdc/data/Lung/features_slim.parquet'
    ]

    for path in possible_paths:
        if Path(path).exists():
            print(f"✓ Loading features from: {path}")
            return pd.read_parquet(path)

    print("Error: Could not find features file!")
    return None

def extract_top30_drugs():
    """Extract top 30 drugs based on Phase 2B CatBoost predictions."""

    print("=" * 80)
    print("STEP 6 PREPARATION: TOP 30 DRUG EXTRACTION")
    print("=" * 80)

    # Load OOF predictions (Phase 2B CatBoost)
    oof_path = 'results/lung_numeric_smiles_ml_v1_oof/CatBoost.npy'
    print(f"\n[1/3] Loading OOF predictions from: {oof_path}")

    try:
        y_pred = load_oof_predictions(oof_path)
    except FileNotFoundError:
        print(f"Error: {oof_path} not found!")
        return None

    print(f"✓ Loaded {len(y_pred)} predictions")
    print(f"  - Predicted IC50 range: [{y_pred.min():.2f}, {y_pred.max():.2f}]")

    # Load features to get drug metadata and true IC50
    print(f"\n[2/3] Loading features data...")
    features_df = load_features_data()

    if features_df is None:
        print("Error: Cannot proceed without features file!")
        return None

    print(f"✓ Features shape: {features_df.shape}")
    print(f"✓ Columns: {list(features_df.columns[:10])}...")

    # Ensure prediction length matches
    if len(y_pred) != len(features_df):
        print(f"\nWarning: Prediction length ({len(y_pred)}) != Features length ({len(features_df)})")
        min_len = min(len(y_pred), len(features_df))
        y_pred = y_pred[:min_len]
        features_df = features_df.iloc[:min_len].copy()
        print(f"Using first {min_len} samples")

    # Extract required columns
    df = pd.DataFrame({
        'sample_id': features_df['sample_id'].values,
        'canonical_drug_id': features_df['canonical_drug_id'].values,
        'pred_ic50': y_pred
    })

    # Extract cell line name from sample_id (format: "CELLLINE-BA")
    df['cell_line_name'] = df['sample_id'].str.split('-').str[0]

    print(f"\n[3/3] Calculating drug-level statistics...")
    print(f"✓ Total samples: {len(df)}")
    print(f"✓ Unique drugs: {df['canonical_drug_id'].nunique()}")
    print(f"✓ Unique cell lines: {df['cell_line_name'].nunique()}")

    # Calculate drug-level statistics (aggregate across cell lines)
    drug_stats = df.groupby('canonical_drug_id').agg({
        'pred_ic50': ['mean', 'std', 'min', 'max', 'count'],
        'cell_line_name': 'nunique'
    }).reset_index()

    # Flatten column names
    drug_stats.columns = [
        'canonical_drug_id',
        'pred_ic50_mean', 'pred_ic50_std', 'pred_ic50_min', 'pred_ic50_max', 'n_samples',
        'n_celllines'
    ]

    # Sort by predicted IC50 (lower = more effective)
    drug_stats = drug_stats.sort_values('pred_ic50_mean')

    # Extract Top 30
    top30 = drug_stats.head(30).reset_index(drop=True)
    top30['rank'] = np.arange(1, 31)

    # Try to add drug names from curated_data
    try:
        drug_meta_paths = [
            '../../../curated_data/gdsc2/drug_annotation.parquet',
            '../../curated_data/gdsc2/drug_annotation.parquet'
        ]

        drug_meta = None
        for path in drug_meta_paths:
            if Path(path).exists():
                print(f"✓ Loading drug metadata from: {path}")
                drug_meta = pd.read_parquet(path)
                break

        if drug_meta is not None and 'canonical_drug_id' in drug_meta.columns:
            # Merge drug names
            name_col = 'drug_name' if 'drug_name' in drug_meta.columns else 'DRUG_NAME'
            drug_names = drug_meta[['canonical_drug_id', name_col]].drop_duplicates()
            drug_names.rename(columns={name_col: 'drug_name'}, inplace=True)
            top30 = top30.merge(drug_names, on='canonical_drug_id', how='left')
            print(f"✓ Added drug names from metadata")
        else:
            top30['drug_name'] = 'Unknown'
            print("Warning: Could not load drug metadata, using 'Unknown' for drug names")
    except Exception as e:
        print(f"Warning: Failed to load drug metadata: {e}")
        top30['drug_name'] = 'Unknown'

    # Reorder columns
    column_order = ['rank', 'canonical_drug_id', 'drug_name',
                    'pred_ic50_mean', 'pred_ic50_std', 'pred_ic50_min', 'pred_ic50_max',
                    'n_samples', 'n_celllines']
    top30 = top30[[col for col in column_order if col in top30.columns]]

    # Save results
    top30.to_csv('results/lung_top30_drugs_phase2b_catboost.csv', index=False)
    print(f"\n✓ Top 30 drugs saved to: results/lung_top30_drugs_phase2b_catboost.csv")

    # Print results
    print("\n" + "=" * 80)
    print("TOP 30 DRUGS (Phase 2B CatBoost - Lowest Predicted IC50)")
    print("=" * 80)
    print(top30.to_string(index=False))

    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print(f"Total unique drugs in dataset: {len(drug_stats)}")
    print(f"Top 30 pred IC50 range: [{top30['pred_ic50_mean'].min():.2f}, {top30['pred_ic50_mean'].max():.2f}]")
    print(f"Top 30 avg samples per drug: {top30['n_samples'].mean():.1f}")
    print(f"Top 30 avg cell lines per drug: {top30['n_celllines'].mean():.1f}")
    print(f"\nInterpretation:")
    print(f"  - Lower IC50 = More effective (higher drug sensitivity)")
    print(f"  - Rank 1 drug has lowest predicted IC50 (most promising)")

    return top30

if __name__ == '__main__':
    top30 = extract_top30_drugs()
