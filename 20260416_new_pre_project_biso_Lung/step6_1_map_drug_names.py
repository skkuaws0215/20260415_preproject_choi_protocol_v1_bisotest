#!/usr/bin/env python3
"""
Step 6.1: Map drug IDs to drug names using GDSC metadata.
"""

import pandas as pd
import numpy as np
from pathlib import Path

def load_gdsc_drug_metadata():
    """Load GDSC drug annotation."""

    print("="*80)
    print("STEP 6.1: DRUG NAME MAPPING")
    print("="*80)

    # Try multiple paths
    possible_paths = [
        'curated_data/gdsc/Compounds-annotation.csv',
        '../curated_data/gdsc/Compounds-annotation.csv',
        '../../curated_data/gdsc/Compounds-annotation.csv'
    ]

    for path in possible_paths:
        if Path(path).exists():
            print(f"\n✓ Loading GDSC drug metadata: {path}")
            df = pd.read_csv(path)
            print(f"✓ Loaded {len(df)} drugs")
            print(f"✓ Columns: {list(df.columns)}")
            return df

    print("\n❌ Error: Could not find GDSC drug annotation file!")
    return None

def map_drug_names(top30_file, drug_metadata):
    """Map drug IDs to names."""

    print(f"\n{'─'*80}")
    print(f"Mapping: {Path(top30_file).name}")
    print(f"{'─'*80}")

    # Load Top 30
    top30 = pd.read_csv(top30_file)
    print(f"✓ Loaded {len(top30)} drugs")

    # Merge with metadata
    # GDSC uses DRUG_ID, we use canonical_drug_id
    # They should match
    top30_with_names = top30.merge(
        drug_metadata[['DRUG_ID', 'DRUG_NAME', 'TARGET', 'TARGET_PATHWAY', 'SYNONYMS']],
        left_on='canonical_drug_id',
        right_on='DRUG_ID',
        how='left'
    )

    # Check match rate
    matched = top30_with_names['DRUG_NAME'].notna().sum()
    print(f"✓ Matched: {matched}/{len(top30)} ({matched/len(top30)*100:.1f}%)")

    if matched < len(top30):
        unmatched = top30_with_names[top30_with_names['DRUG_NAME'].isna()]['canonical_drug_id'].tolist()
        print(f"⚠️  Unmatched drug IDs: {unmatched}")

    return top30_with_names

def main():
    # Load GDSC metadata
    drug_metadata = load_gdsc_drug_metadata()

    if drug_metadata is None:
        print("\n❌ Cannot proceed without GDSC drug metadata!")
        return None

    # Map names for all Top 30 files
    files_to_map = [
        'results/lung_top30_phase2b_catboost.csv',
        'results/lung_top30_phase2c_catboost.csv',
        'results/lung_top30_unified_2b_and_2c.csv'
    ]

    mapped_files = {}

    for file in files_to_map:
        if not Path(file).exists():
            print(f"\n⚠️  File not found: {file}")
            continue

        mapped_df = map_drug_names(file, drug_metadata)

        # Save with names
        output_file = file.replace('.csv', '_with_names.csv')
        mapped_df.to_csv(output_file, index=False)
        print(f"✓ Saved: {output_file}")

        mapped_files[file] = mapped_df

    # Display sample results
    if 'results/lung_top30_unified_2b_and_2c.csv' in mapped_files:
        print(f"\n{'='*80}")
        print("UNIFIED TOP 30 WITH DRUG NAMES (First 10)")
        print(f"{'='*80}")

        df_unified = mapped_files['results/lung_top30_unified_2b_and_2c.csv']
        display_cols = ['canonical_drug_id', 'DRUG_NAME', 'TARGET', 'in_2b', 'in_2c', 'rank_2b', 'rank_2c']
        available_cols = [col for col in display_cols if col in df_unified.columns]
        print(df_unified[available_cols].head(10).to_string(index=False))

    print(f"\n{'='*80}")
    print("DRUG NAME MAPPING COMPLETE")
    print(f"{'='*80}")

    return mapped_files

if __name__ == '__main__':
    main()
