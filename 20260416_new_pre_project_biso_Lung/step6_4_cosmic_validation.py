#!/usr/bin/env python3
"""
Step 6.4: COSMIC Validation
- Extract COSMIC tar files
- Load Cancer Gene Census
- Load Actionability data (drug-mutation associations)
- Match Top 30 drugs to COSMIC actionable mutations
"""

import json
import sys
import tarfile
import os
from pathlib import Path

_LUNG = Path(__file__).resolve().parent
if str(_LUNG) not in sys.path:
    sys.path.insert(0, str(_LUNG))

import pandas as pd
import numpy as np

from step6_validation_context import Step6ValidationContext


def extract_cosmic_tar_files(cosmic_dir: Path):
    """Extract COSMIC tar files."""

    print("="*80)
    print("STEP 6.4: COSMIC VALIDATION")
    print("="*80)

    extract_dir = cosmic_dir / 'extracted'

    if not cosmic_dir.exists():
        print(f"❌ Error: {cosmic_dir} not found!")
        return None, None

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


def load_cosmic_parquet_bundle(ctx: Step6ValidationContext):
    """Load pre-built COSMIC actionability (and optional CGC) parquet from ``cosmic_parquet_dir``."""
    lines: list[str] = []
    if ctx.cosmic_parquet_dir is None:
        print("⚠️  cosmic_parquet_dir not set")
        lines.append("cosmic: parquet_bundle missing cosmic_parquet_dir")
        ctx.merge_step_sources("6.4_cosmic", lines)
        return None, None, None
    d = ctx.cosmic_parquet_dir
    act_path = d / ctx.cosmic_actionability_parquet
    if not act_path.exists():
        print(f"⚠️  Actionability parquet not found: {act_path}")
        lines.append(f"missing {act_path}")
        ctx.merge_step_sources("6.4_cosmic", lines)
        return None, None, None
    actionability = pd.read_parquet(act_path)
    lines.append(f"read parquet {act_path}")
    census = None
    if ctx.cosmic_cancer_gene_census_parquet:
        cpath = d / ctx.cosmic_cancer_gene_census_parquet
        if cpath.exists():
            census = pd.read_parquet(cpath)
            lines.append(f"read parquet {cpath}")
        else:
            print(f"⚠️  Cancer Gene Census parquet missing (optional): {cpath}")
            lines.append(f"optional missing {cpath}")
    ctx.merge_step_sources("6.4_cosmic", lines)
    return None, actionability, census

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

def main(argv=None):
    ctx = Step6ValidationContext.load(argv)
    for p in (ctx.top30_unified,):
        if not p.exists():
            raise FileNotFoundError(f"Required input missing: {p}")

    extract_dir = None
    actionability_data = None
    cancer_gene_census = None

    if not ctx.cosmic_enabled:
        print("\n⚠️  COSMIC disabled — skip with empty summary")
        ctx.merge_step_sources("6.4_cosmic", ["cosmic: disabled"])
    elif ctx.cosmic_mode == "parquet_bundle":
        extract_dir, actionability_data, cancer_gene_census = load_cosmic_parquet_bundle(ctx)
    else:
        base = ctx.cosmic_extract_dir or (ctx.project_root / "curated_data" / "validation" / "cosmic")
        extract_dir, _ = extract_cosmic_tar_files(base)
        if extract_dir is None:
            print("\n⚠️  COSMIC extract_dir missing — skip")
            ctx.merge_step_sources("6.4_cosmic", ["cosmic: extract_dir missing"])
        else:
            cancer_gene_census = load_cancer_gene_census(extract_dir)
            actionability_data = load_actionability_data(extract_dir)
            ctx.merge_step_sources(
                "6.4_cosmic",
                [
                    f"extract_dir={extract_dir}",
                    f"actionability_rows={0 if actionability_data is None else len(actionability_data)}",
                ],
            )

    if actionability_data is None:
        print("\n⚠️  No COSMIC actionability — writing empty summary")
        results = {
            "cancer_gene_census_genes": len(cancer_gene_census) if cancer_gene_census is not None else 0,
            "actionability_records": 0,
            "cosmic_matched_drugs": 0,
            "cosmic_match_rate": 0.0,
            "note": "cosmic_skipped_or_empty",
        }
        ctx.merge_step_sources(
            "6.4_cosmic",
            ["cosmic: no actionability; wrote empty cosmic_validation_results"],
        )
        ctx.results_json("cosmic_validation_results").parent.mkdir(parents=True, exist_ok=True)
        with open(ctx.results_json("cosmic_validation_results"), "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        return results

    # Load Top 30
    print(f"\n{'─'*80}")
    print("LOADING TOP 30 DRUGS")
    print(f"{'─'*80}")

    unified = pd.read_csv(ctx.top30_unified)
    print(f"✓ Loaded {len(unified)} drugs from {ctx.top30_unified}")

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
        out_csv = ctx.results_csv("cosmic_matched_drugs")
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        cosmic_matches.to_csv(out_csv, index=False)
        print(f"\n✓ Saved: {out_csv}")

        results['cosmic_matched_drugs'] = cosmic_matches['canonical_drug_id'].nunique()
        results['cosmic_match_rate'] = results['cosmic_matched_drugs'] / len(unified)
        results['cosmic_actionability_records'] = len(cosmic_matches)

    # Save summary
    with open(ctx.results_json("cosmic_validation_results"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print("COSMIC VALIDATION COMPLETE")
    print(f"{'='*80}")
    print(f"✓ Saved: {ctx.results_json('cosmic_validation_results')}")

    return results

if __name__ == '__main__':
    main(sys.argv[1:])
