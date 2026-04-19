#!/usr/bin/env python3
"""
Step 6.4: COSMIC Validation
- Extract COSMIC tar files
- Load Cancer Gene Census
- Load Actionability data (drug-mutation associations)
- Match Top 30 drugs to COSMIC actionable mutations
"""

import tarfile
import pandas as pd
import numpy as np
from pathlib import Path
import os

def extract_cosmic_tar_files():
    """Extract COSMIC tar files."""

    print("="*80)
    print("STEP 6.4: COSMIC VALIDATION")
    print("="*80)

    cosmic_dir = Path('curated_data/validation/cosmic')
    extract_dir = cosmic_dir / 'extracted'

    if not cosmic_dir.exists():
        print(f"❌ Error: {cosmic_dir} not found!")
        return None

    # Create extraction directory
    extract_dir.mkdir(exist_ok=True)

    print(f"\n[1/4] Extracting COSMIC tar files...")
    print(f"Source: {cosmic_dir}")
    print(f"Target: {extract_dir}")

    tar_files = list(cosmic_dir.glob('*.tar'))
    print(f"✓ Found {len(tar_files)} tar files")

    extracted_files = {}

    for tar_file in tar_files:
        print(f"\nExtracting: {tar_file.name}")

        try:
            with tarfile.open(tar_file, 'r') as tar:
                members = tar.getmembers()
                print(f"  - Contains {len(members)} files")

                for member in members:
                    if member.name.endswith('.tsv'):
                        # Extract to target directory
                        tar.extract(member, path=extract_dir)
                        extracted_path = extract_dir / member.name
                        print(f"  ✓ Extracted: {member.name} ({member.size / 1024 / 1024:.1f} MB)")
                        extracted_files[tar_file.stem] = extracted_path

        except Exception as e:
            print(f"  ❌ Error extracting {tar_file.name}: {e}")

    print(f"\n✓ Total extracted files: {len(extracted_files)}")

    return extract_dir, extracted_files

def load_cancer_gene_census(extract_dir):
    """Load Cancer Gene Census."""

    print(f"\n[2/4] Loading Cancer Gene Census...")

    # Find the file
    census_files = list(extract_dir.rglob('*CancerGeneCensus*.tsv'))

    if len(census_files) == 0:
        print("⚠️  Cancer Gene Census file not found")
        return None

    census_file = census_files[0]
    print(f"✓ Found: {census_file.name}")

    try:
        df = pd.read_csv(census_file, sep='\t')
        print(f"✓ Loaded {len(df)} cancer genes")
        print(f"✓ Columns: {list(df.columns[:10])}...")

        return df
    except Exception as e:
        print(f"❌ Error loading: {e}")
        return None

def load_actionability_data(extract_dir):
    """Load COSMIC Actionability data (drug-mutation associations)."""

    print(f"\n[3/4] Loading Actionability data...")

    # Find the file
    actionability_files = list(extract_dir.rglob('*Actionability*.tsv'))

    if len(actionability_files) == 0:
        print("⚠️  Actionability file not found")
        return None

    actionability_file = actionability_files[0]
    print(f"✓ Found: {actionability_file.name}")

    try:
        df = pd.read_csv(actionability_file, sep='\t', low_memory=False)
        print(f"✓ Loaded {len(df)} actionability records")
        print(f"✓ Columns: {list(df.columns)}")

        # Show sample
        print(f"\n✓ Sample data:")
        print(df.head(3).to_string())

        return df
    except Exception as e:
        print(f"❌ Error loading: {e}")
        return None

def match_top30_to_cosmic(top30_unified, actionability_df):
    """Match Top 30 drugs to COSMIC actionability data."""

    print(f"\n[4/4] Matching Top 30 → COSMIC Actionability...")

    if actionability_df is None:
        print("⚠️  No actionability data available")
        return None

    # Check column names
    print(f"\nActionability columns: {list(actionability_df.columns)}")

    # Find drug-related columns
    drug_columns = [col for col in actionability_df.columns if 'drug' in col.lower() or 'therapy' in col.lower() or 'compound' in col.lower()]
    print(f"✓ Drug-related columns: {drug_columns}")

    if len(drug_columns) == 0:
        print("⚠️  No drug columns found in actionability data")
        return None

    matches = []

    # Try to match drugs
    for idx, row in top30_unified.iterrows():
        drug_name = row['DRUG_NAME'].lower().strip()
        drug_id = row['canonical_drug_id']

        # Search in each drug column
        for col in drug_columns:
            drug_matches = actionability_df[
                actionability_df[col].str.lower().str.contains(drug_name, na=False, regex=False)
            ]

            if len(drug_matches) > 0:
                for _, cosmic_row in drug_matches.iterrows():
                    matches.append({
                        'canonical_drug_id': drug_id,
                        'DRUG_NAME': row['DRUG_NAME'],
                        'cosmic_drug_field': col,
                        'cosmic_drug_value': cosmic_row[col],
                        **{k: cosmic_row[k] for k in cosmic_row.index if k != col}
                    })

    df_matches = pd.DataFrame(matches)

    if len(df_matches) > 0:
        unique_drugs = df_matches['canonical_drug_id'].nunique()
        print(f"✓ Matched: {unique_drugs}/{len(top30_unified)} drugs ({unique_drugs/len(top30_unified)*100:.1f}%)")
        print(f"✓ Total actionability records: {len(df_matches)}")
    else:
        print("⚠️  No matches found")

    return df_matches

def main():
    # Extract tar files
    extract_dir, extracted_files = extract_cosmic_tar_files()

    if extract_dir is None:
        print("\n❌ Cannot proceed without COSMIC data!")
        return None

    # Load data
    cancer_gene_census = load_cancer_gene_census(extract_dir)
    actionability_data = load_actionability_data(extract_dir)

    # Load Top 30
    print(f"\n{'─'*80}")
    print("LOADING TOP 30 DRUGS")
    print(f"{'─'*80}")

    unified = pd.read_csv('results/lung_top30_unified_2b_and_2c_with_names.csv')
    print(f"✓ Loaded {len(unified)} drugs")

    # Match to COSMIC
    cosmic_matches = match_top30_to_cosmic(unified, actionability_data)

    # Save results
    results = {
        'cancer_gene_census_genes': len(cancer_gene_census) if cancer_gene_census is not None else 0,
        'actionability_records': len(actionability_data) if actionability_data is not None else 0,
        'cosmic_matched_drugs': 0,
        'cosmic_match_rate': 0.0
    }

    if cosmic_matches is not None and len(cosmic_matches) > 0:
        cosmic_matches.to_csv('results/lung_cosmic_matched_drugs.csv', index=False)
        print(f"\n✓ Saved: results/lung_cosmic_matched_drugs.csv")

        results['cosmic_matched_drugs'] = cosmic_matches['canonical_drug_id'].nunique()
        results['cosmic_match_rate'] = results['cosmic_matched_drugs'] / len(unified)
        results['cosmic_actionability_records'] = len(cosmic_matches)

    # Save summary
    import json
    with open('results/lung_cosmic_validation_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print("COSMIC VALIDATION COMPLETE")
    print(f"{'='*80}")
    print(f"✓ Saved: results/lung_cosmic_validation_results.json")

    return results

if __name__ == '__main__':
    main()
