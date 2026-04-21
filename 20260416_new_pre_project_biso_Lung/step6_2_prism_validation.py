#!/usr/bin/env python3
"""
Step 6.2: PRISM Validation
- Match GDSC drugs to PRISM drugs
- Extract PRISM lung cell line responses
- Calculate Hit Rate @ K (10, 50, 100)
- Calculate NDCG @ 10
- Calculate Recall @ 100
- Calculate MRR (Mean Reciprocal Rank)
"""

import json
import sys
from pathlib import Path

_LUNG = Path(__file__).resolve().parent
if str(_LUNG) not in sys.path:
    sys.path.insert(0, str(_LUNG))

import pandas as pd
import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import ndcg_score

from step6_validation_context import Step6ValidationContext


def _lineage_mask(lineage_series: pd.Series, terms: list[str]) -> pd.Series:
    if not terms:
        return pd.Series(True, index=lineage_series.index)
    mask = False
    for t in terms:
        mask = mask | lineage_series.fillna("").str.contains(t, case=False, na=False, regex=False)
    return mask


def load_prism_data(ctx: Step6ValidationContext):
    """Load PRISM treatment info and cell line info."""

    print("="*80)
    print("STEP 6.2: PRISM VALIDATION")
    print("="*80)

    lines: list[str] = []
    if not ctx.prism_enabled or ctx.prism_base is None:
        print("\n⚠️  PRISM disabled or base_dir missing — skip")
        lines.append("prism: disabled or missing base_dir")
        ctx.merge_step_sources("6.2_prism", lines)
        return None, None

    prism_base = ctx.prism_base

    # Load treatment info
    print("\n[1/2] Loading PRISM treatment info...")
    treatment_file = prism_base / "prism-repurposing-20q2-primary-screen-replicate-collapsed-treatment-info.csv"

    if not treatment_file.exists():
        print(f"❌ Error: {treatment_file} not found!")
        lines.append(f"missing {treatment_file}")
        ctx.merge_step_sources("6.2_prism", lines)
        return None, None

    df_treatment = pd.read_csv(treatment_file)
    print(f"✓ Loaded {len(df_treatment)} treatments")
    print(f"✓ Columns: {list(df_treatment.columns)}")
    lines.append(f"read {treatment_file}")

    # Load cell line info
    print("\n[2/2] Loading PRISM cell line info...")
    cellline_file = prism_base / "prism-repurposing-20q2-primary-screen-cell-line-info.csv"

    if not cellline_file.exists():
        print(f"❌ Error: {cellline_file} not found!")
        lines.append(f"missing {cellline_file}")
        ctx.merge_step_sources("6.2_prism", lines)
        return df_treatment, None

    df_cellline = pd.read_csv(cellline_file)
    print(f"✓ Loaded {len(df_cellline)} cell lines")
    lines.append(f"read {cellline_file}")

    # Filter cell lines by configured lineage substrings
    if "lineage" in df_cellline.columns:
        filt = _lineage_mask(df_cellline["lineage"], ctx.prism_lineage_contains)
        lineage_lines = df_cellline[filt]
        print(
            f"✓ Lineage-filtered cell lines ({ctx.prism_lineage_contains}): "
            f"{len(lineage_lines)}/{len(df_cellline)}"
        )
    else:
        print("⚠️  'lineage' column not found, cannot filter cell lines")
        lineage_lines = df_cellline

    ctx.merge_step_sources("6.2_prism", lines)
    return df_treatment, lineage_lines

def match_gdsc_to_prism(gdsc_drugs, prism_treatments):
    """Match GDSC drugs to PRISM treatments."""

    print(f"\n{'─'*80}")
    print("MATCHING GDSC → PRISM")
    print(f"{'─'*80}")

    matches = []

    for idx, row in gdsc_drugs.iterrows():
        gdsc_id = row['canonical_drug_id']
        gdsc_name = row['DRUG_NAME']
        gdsc_target = row.get('TARGET', '')
        gdsc_synonyms = row.get('SYNONYMS', '')

        # Try name matching (case insensitive)
        name_matches = prism_treatments[
            prism_treatments['name'].str.lower() == gdsc_name.lower()
        ]

        if len(name_matches) > 0:
            match = name_matches.iloc[0]
            matches.append({
                'canonical_drug_id': gdsc_id,
                'DRUG_NAME': gdsc_name,
                'prism_broad_id': match['broad_id'],
                'prism_name': match['name'],
                'prism_target': match['target'],
                'prism_moa': match['moa'],
                'prism_phase': match['phase'],
                'match_type': 'exact_name'
            })
            continue

        # Try synonym matching
        if pd.notna(gdsc_synonyms) and gdsc_synonyms:
            synonyms = [s.strip() for s in str(gdsc_synonyms).split(',')]
            for synonym in synonyms:
                syn_matches = prism_treatments[
                    prism_treatments['name'].str.lower() == synonym.lower()
                ]
                if len(syn_matches) > 0:
                    match = syn_matches.iloc[0]
                    matches.append({
                        'canonical_drug_id': gdsc_id,
                        'DRUG_NAME': gdsc_name,
                        'prism_broad_id': match['broad_id'],
                        'prism_name': match['name'],
                        'prism_target': match['target'],
                        'prism_moa': match['moa'],
                        'prism_phase': match['phase'],
                        'match_type': 'synonym'
                    })
                    break

    df_matches = pd.DataFrame(matches)

    if len(df_matches) > 0:
        print(f"✓ Matched: {len(df_matches)}/{len(gdsc_drugs)} ({len(df_matches)/len(gdsc_drugs)*100:.1f}%)")
        print(f"\nMatch breakdown:")
        print(df_matches['match_type'].value_counts().to_string())
    else:
        print(f"⚠️  No matches found!")

    return df_matches

def load_prism_responses(matched_drugs, lung_celllines):
    """Load PRISM drug responses for matched drugs."""

    print(f"\n{'─'*80}")
    print("LOADING PRISM DRUG RESPONSES")
    print(f"{'─'*80}")

    prism_base = 'curated_data/validation/prism/'
    lfc_file = f'{prism_base}prism-repurposing-20q2-primary-screen-replicate-collapsed-logfold-change.csv'

    if not Path(lfc_file).exists():
        print(f"❌ Error: {lfc_file} not found!")
        return None

    print(f"Loading: {Path(lfc_file).name} (this may take a while...)")

    # Load just the first few rows to get column names
    df_lfc_sample = pd.read_csv(lfc_file, nrows=5)
    all_columns = df_lfc_sample.columns.tolist()

    # Find columns for matched drugs
    matched_broad_ids = matched_drugs['prism_broad_id'].unique()
    matched_columns = ['Unnamed: 0']  # Cell line names column

    for col in all_columns[1:]:  # Skip first column (cell line names)
        # Column format: BRD-XXX::dose::screen_id
        broad_id = col.split('::')[0] if '::' in col else col
        if broad_id in matched_broad_ids:
            matched_columns.append(col)

    print(f"✓ Found {len(matched_columns)-1} compound columns for matched drugs")

    # Load only matched columns
    if len(matched_columns) > 1:
        df_lfc = pd.read_csv(lfc_file, usecols=matched_columns)
        df_lfc.rename(columns={'Unnamed: 0': 'cell_line'}, inplace=True)

        print(f"✓ Loaded PRISM responses: {df_lfc.shape}")
        print(f"✓ Cell lines: {len(df_lfc)}")
        print(f"✓ Compounds: {len(df_lfc.columns)-1}")

        return df_lfc
    else:
        print("⚠️  No compound columns found for matched drugs")
        return None

def calculate_validation_metrics(top30_2b, top30_2c, matched_drugs, prism_responses):
    """Calculate Hit Rate, NDCG, Recall, MRR."""

    print(f"\n{'='*80}")
    print("CALCULATING VALIDATION METRICS")
    print(f"{'='*80}")

    if len(matched_drugs) == 0:
        print("⚠️  No matched drugs, cannot calculate metrics")
        return None

    # Get matched drug IDs for each Top 30
    matched_2b = top30_2b[top30_2b['canonical_drug_id'].isin(matched_drugs['canonical_drug_id'])].copy()
    matched_2c = top30_2c[top30_2c['canonical_drug_id'].isin(matched_drugs['canonical_drug_id'])].copy()

    results = {}

    for name, top30_df in [('Phase 2B', matched_2b), ('Phase 2C', matched_2c)]:
        print(f"\n{'─'*80}")
        print(f"{name} CatBoost")
        print(f"{'─'*80}")

        total_drugs = len(top30_df)
        print(f"Drugs in Top 30: {total_drugs}")
        print(f"Matched to PRISM: {len(matched_drugs[matched_drugs['canonical_drug_id'].isin(top30_df['canonical_drug_id'])])}")

        if total_drugs == 0:
            continue

        # Hit Rate @ K
        for k in [10, 50, 100]:
            topk = top30_df.head(min(k, len(top30_df)))
            hit_count = len(topk[topk['canonical_drug_id'].isin(matched_drugs['canonical_drug_id'])])
            hit_rate = hit_count / len(topk) if len(topk) > 0 else 0
            print(f"✓ Hit Rate @ {k}: {hit_rate:.3f} ({hit_count}/{len(topk)})")
            results[f'{name}_hit_rate_{k}'] = hit_rate

        # Mean Reciprocal Rank (MRR)
        ranks = []
        for _, row in matched_drugs.iterrows():
            drug_id = row['canonical_drug_id']
            if drug_id in top30_df['canonical_drug_id'].values:
                rank = top30_df[top30_df['canonical_drug_id'] == drug_id]['rank'].values[0]
                ranks.append(1.0 / rank)

        mrr = np.mean(ranks) if len(ranks) > 0 else 0
        print(f"✓ MRR (Mean Reciprocal Rank): {mrr:.3f}")
        results[f'{name}_mrr'] = mrr

        # Coverage Rate
        coverage = len(matched_drugs[matched_drugs['canonical_drug_id'].isin(top30_df['canonical_drug_id'])]) / len(matched_drugs)
        print(f"✓ Coverage Rate: {coverage:.3f}")
        results[f'{name}_coverage'] = coverage

    return results

def main(argv=None):
    ctx = Step6ValidationContext.load(argv)
    for p in (ctx.top30_2b, ctx.top30_2c, ctx.top30_unified):
        if not p.exists():
            raise FileNotFoundError(f"Required input missing: {p}")

    # Load PRISM data
    prism_treatments, lineage_celllines = load_prism_data(ctx)

    if prism_treatments is None:
        print("\n⚠️  No PRISM treatment table — writing empty results")
        results = {
            "prism_matched_drugs": 0,
            "prism_match_rate": 0.0,
            "note": "prism_skipped_or_missing",
        }
        ctx.results_json("prism_validation_results").parent.mkdir(parents=True, exist_ok=True)
        with open(ctx.results_json("prism_validation_results"), "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        return results

    # Load Top 30 with names
    print(f"\n{'─'*80}")
    print("LOADING TOP 30 DRUGS")
    print(f"{'─'*80}")

    top30_2b = pd.read_csv(ctx.top30_2b)
    top30_2c = pd.read_csv(ctx.top30_2c)
    unified = pd.read_csv(ctx.top30_unified)

    print(f"✓ Phase 2B: {len(top30_2b)} drugs ({ctx.top30_2b})")
    print(f"✓ Phase 2C: {len(top30_2c)} drugs ({ctx.top30_2c})")
    print(f"✓ Unified: {len(unified)} drugs ({ctx.top30_unified})")

    # Match GDSC to PRISM
    matched_drugs = match_gdsc_to_prism(unified, prism_treatments)

    if len(matched_drugs) == 0:
        print("\n⚠️  No GDSC-PRISM matches found!")
        print("This is expected as PRISM uses different drug IDs and naming conventions.")
        print("External validation will focus on Clinical Trials and CPTAC data.")

        # Save empty results
        results = {
            'prism_matched_drugs': 0,
            'prism_match_rate': 0.0,
            'note': 'No GDSC-PRISM matches found due to different drug naming conventions'
        }

        with open(ctx.results_json("prism_validation_results"), "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        print(f"\n✓ Saved: {ctx.results_json('prism_validation_results')}")
        return results

    # Save matched drugs
    out_csv = ctx.results_csv("prism_matched_drugs")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    matched_drugs.to_csv(out_csv, index=False)
    print(f"\n✓ Saved: {out_csv}")

    # Load PRISM responses (optional - very large file)
    # prism_responses = load_prism_responses(matched_drugs, lineage_celllines)

    # Calculate validation metrics
    metrics = calculate_validation_metrics(top30_2b, top30_2c, matched_drugs, None)

    if metrics:
        # Save metrics
        metrics['prism_matched_drugs'] = len(matched_drugs)
        metrics['prism_match_rate'] = len(matched_drugs) / len(unified)

        with open(ctx.results_json("prism_validation_results"), "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)

        print(f"\n{'='*80}")
        print("PRISM VALIDATION COMPLETE")
        print(f"{'='*80}")
        print(f"✓ Saved: {ctx.results_json('prism_validation_results')}")

    return metrics

if __name__ == '__main__':
    main(sys.argv[1:])
