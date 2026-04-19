#!/usr/bin/env python3
"""
Step 6.5: CPTAC Validation
- Load CPTAC LUAD and LUSC patient data
- Extract drug target expression (mRNA, protein)
- Match Top 30 drug targets to patient expression
- Calculate target expression statistics
"""

import pandas as pd
import numpy as np
from pathlib import Path
import re

def load_cptac_clinical_data():
    """Load CPTAC clinical data."""

    print("="*80)
    print("STEP 6.5: CPTAC VALIDATION")
    print("="*80)

    cptac_base = Path('curated_data/cptac')

    datasets = ['luad_cptac_2020', 'lusc_cptac_2021']
    clinical_data = {}

    for dataset in datasets:
        dataset_path = cptac_base / dataset
        if not dataset_path.exists():
            print(f"⚠️  {dataset} not found")
            continue

        print(f"\n[{dataset.upper()}] Loading clinical data...")

        # Load patient clinical data
        patient_file = dataset_path / 'data_clinical_patient.txt'
        if patient_file.exists():
            # Skip first 4 lines (comments)
            df = pd.read_csv(patient_file, sep='\t', skiprows=4)
            print(f"  ✓ Loaded {len(df)} patients")
            print(f"  ✓ Columns: {list(df.columns[:5])}...")
            clinical_data[dataset] = {'patients': df}
        else:
            print(f"  ⚠️  Patient data not found")

    return clinical_data

def load_target_expression(cptac_base, dataset, target_genes):
    """Load mRNA expression for target genes."""

    print(f"\n  Loading mRNA expression for {len(target_genes)} target genes...")

    dataset_path = cptac_base / dataset

    # Find mRNA expression file
    mrna_files = list(dataset_path.glob('data_mrna*.txt'))
    if len(mrna_files) == 0:
        print("  ⚠️  mRNA data file not found")
        return None

    # Use RPKM or FPKM file (not z-scores, not meta)
    mrna_file = None
    for f in mrna_files:
        if f.name.startswith('data_mrna'):
            if 'rpkm' in f.name.lower() or 'fpkm' in f.name.lower():
                if 'zscores' not in f.name.lower():
                    mrna_file = f
                    break

    if mrna_file is None and len(mrna_files) > 0:
        mrna_file = mrna_files[0]

    print(f"  ✓ Using: {mrna_file.name}")

    try:
        # Read first few rows to check format
        df_sample = pd.read_csv(mrna_file, sep='\t', nrows=5, skiprows=0)

        # Check if there are comment lines
        if df_sample.iloc[0, 0].startswith('#'):
            df = pd.read_csv(mrna_file, sep='\t', skiprows=4)
        else:
            df = pd.read_csv(mrna_file, sep='\t')

        print(f"  ✓ Shape: {df.shape}")
        print(f"  ✓ First column: {df.columns[0]}")

        # Find target genes in the data
        # First column should be Hugo_Symbol or similar
        gene_col = df.columns[0]
        available_targets = []

        for target in target_genes:
            if target in df[gene_col].values:
                available_targets.append(target)

        print(f"  ✓ Found {len(available_targets)}/{len(target_genes)} target genes")

        if len(available_targets) > 0:
            # Extract target gene expression
            target_df = df[df[gene_col].isin(available_targets)]
            return target_df

        return None

    except Exception as e:
        print(f"  ❌ Error loading: {e}")
        return None

def extract_drug_targets(top30_unified):
    """Extract target genes from Top 30 drugs."""

    print(f"\n{'─'*80}")
    print("EXTRACTING DRUG TARGETS")
    print(f"{'─'*80}")

    targets_dict = {}

    for idx, row in top30_unified.iterrows():
        drug_id = row['canonical_drug_id']
        drug_name = row['DRUG_NAME']
        target_str = row.get('TARGET', '')

        if pd.isna(target_str) or not target_str:
            continue

        # Parse target string (comma-separated)
        targets = [t.strip() for t in str(target_str).split(',')]
        targets_dict[drug_id] = {
            'drug_name': drug_name,
            'targets': targets
        }

    print(f"✓ Extracted targets for {len(targets_dict)}/{len(top30_unified)} drugs")

    # Get all unique targets
    all_targets = []
    for drug_info in targets_dict.values():
        all_targets.extend(drug_info['targets'])

    unique_targets = list(set(all_targets))
    print(f"✓ Total unique targets: {len(unique_targets)}")

    # Show most common targets
    from collections import Counter
    target_counts = Counter(all_targets)
    print(f"\n✓ Top 10 most common targets:")
    for target, count in target_counts.most_common(10):
        print(f"  - {target}: {count} drugs")

    return targets_dict, unique_targets

def calculate_target_expression_stats(target_expression_data, targets_dict):
    """Calculate target expression statistics."""

    print(f"\n{'─'*80}")
    print("CALCULATING TARGET EXPRESSION STATISTICS")
    print(f"{'─'*80}")

    if target_expression_data is None or len(target_expression_data) == 0:
        print("⚠️  No target expression data available")
        return None

    stats = []

    for drug_id, drug_info in targets_dict.items():
        for target in drug_info['targets']:
            # Check if target is in expression data
            gene_col = target_expression_data.columns[0]
            target_row = target_expression_data[target_expression_data[gene_col] == target]

            if len(target_row) > 0:
                # Get expression values (all columns except first)
                expr_values = target_row.iloc[0, 1:].values
                expr_values = pd.to_numeric(expr_values, errors='coerce')
                expr_values = expr_values[~np.isnan(expr_values)]

                if len(expr_values) > 0:
                    stats.append({
                        'canonical_drug_id': drug_id,
                        'drug_name': drug_info['drug_name'],
                        'target': target,
                        'n_patients': len(expr_values),
                        'mean_expression': expr_values.mean(),
                        'std_expression': expr_values.std(),
                        'median_expression': np.median(expr_values),
                        'min_expression': expr_values.min(),
                        'max_expression': expr_values.max()
                    })

    df_stats = pd.DataFrame(stats)

    if len(df_stats) > 0:
        print(f"✓ Expression stats for {len(df_stats)} drug-target pairs")
        print(f"✓ Unique drugs: {df_stats['canonical_drug_id'].nunique()}")
        print(f"✓ Unique targets: {df_stats['target'].nunique()}")

        print(f"\n✓ Top 10 highest expressing targets:")
        top_expressed = df_stats.nlargest(10, 'mean_expression')
        print(top_expressed[['drug_name', 'target', 'mean_expression']].to_string(index=False))
    else:
        print("⚠️  No expression stats calculated")

    return df_stats

def main():
    # Load clinical data
    clinical_data = load_cptac_clinical_data()

    # Load Top 30
    print(f"\n{'─'*80}")
    print("LOADING TOP 30 DRUGS")
    print(f"{'─'*80}")

    unified = pd.read_csv('results/lung_top30_unified_2b_and_2c_with_names.csv')
    print(f"✓ Loaded {len(unified)} drugs")

    # Extract drug targets
    targets_dict, unique_targets = extract_drug_targets(unified)

    # Load target expression from CPTAC
    cptac_base = Path('curated_data/cptac')
    all_target_expression = {}

    for dataset in ['luad_cptac_2020', 'lusc_cptac_2021']:
        print(f"\n[{dataset.upper()}]")
        target_expr = load_target_expression(cptac_base, dataset, unique_targets)
        if target_expr is not None:
            all_target_expression[dataset] = target_expr

    # Calculate statistics
    all_stats = []

    for dataset, target_expr in all_target_expression.items():
        print(f"\n[{dataset.upper()}] Target Expression Statistics")
        stats = calculate_target_expression_stats(target_expr, targets_dict)
        if stats is not None:
            stats['dataset'] = dataset
            all_stats.append(stats)

    # Combine stats
    if len(all_stats) > 0:
        df_combined_stats = pd.concat(all_stats, ignore_index=True)
        df_combined_stats.to_csv('results/lung_cptac_target_expression_stats.csv', index=False)
        print(f"\n✓ Saved: results/lung_cptac_target_expression_stats.csv")

        # Save summary
        results = {
            'cptac_datasets': len(all_target_expression),
            'drugs_with_targets': len(targets_dict),
            'unique_targets': len(unique_targets),
            'drug_target_pairs_with_expression': len(df_combined_stats),
            'drugs_with_expression_data': df_combined_stats['canonical_drug_id'].nunique(),
            'targets_with_expression_data': df_combined_stats['target'].nunique()
        }

        import json
        with open('results/lung_cptac_validation_results.json', 'w') as f:
            json.dump(results, f, indent=2)

        print(f"✓ Saved: results/lung_cptac_validation_results.json")
    else:
        print("\n⚠️  No expression data extracted")

        results = {
            'cptac_datasets': len(clinical_data),
            'drugs_with_targets': len(targets_dict),
            'unique_targets': len(unique_targets),
            'note': 'Expression data extraction incomplete'
        }

        import json
        with open('results/lung_cptac_validation_results.json', 'w') as f:
            json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print("CPTAC VALIDATION COMPLETE")
    print(f"{'='*80}")

    return results

if __name__ == '__main__':
    main()
