#!/usr/bin/env python3
"""
Filter colorectal cancer cell lines from GDSC and generate labels.

Colon-specific new script (no Lung/BRCA equivalent).

Process:
  1. Filter GDSC2-dataset for TCGA_DESC == 'COREAD'
  2. Match with DepMap cell lines using 2-stage normalization
  3. Generate labels.parquet in team4 schema (sample_id, canonical_drug_id, ic50, binary_label)
  4. Generate matched cell lines CSV + JSON report

Schema (output labels.parquet):
  - sample_id          : str (StrippedCellLineName from DepMap)
  - canonical_drug_id  : str (GDSC DRUG_ID)
  - ic50               : float (LN_IC50 from GDSC)
  - binary_label       : int (0 or 1, based on ic50 quantile)
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


# ============================================================================
# Normalization
# ============================================================================

def normalize_strict(name):
    """Stage 1: Lung style + basic special chars removal."""
    return str(name).lower() \
        .replace('-', '') \
        .replace('/', '') \
        .replace(' ', '') \
        .replace('_', '') \
        .replace(':', '')


def normalize_fallback(name):
    """Stage 2: Remove all non-alphanumeric chars (last resort)."""
    s = normalize_strict(name)
    s = s.replace('.', '') \
         .replace(',', '') \
         .replace(';', '') \
         .replace('(', '').replace(')', '') \
         .replace('[', '').replace(']', '')
    # Remove any remaining non-alphanumeric
    s = re.sub(r'[^a-z0-9]', '', s)
    return s


def log(msg):
    """Simple logger with timestamp."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ============================================================================
# Main logic
# ============================================================================

def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gdsc-ic50', required=True, type=Path,
                   help='Path to GDSC2-dataset.parquet')
    p.add_argument('--gdsc-annotation', required=True, type=Path,
                   help='Path to Compounds-annotation.parquet')
    p.add_argument('--depmap-model', required=True, type=Path,
                   help='Path to Model.parquet')
    p.add_argument('--depmap-long', required=True, type=Path,
                   help='Path to depmap_crispr_long_colon.parquet')
    p.add_argument('--output-labels', required=True, type=Path,
                   help='Output: labels.parquet (team4 schema)')
    p.add_argument('--output-cells', required=True, type=Path,
                   help='Output: matched cell lines CSV')
    p.add_argument('--output-report', required=True, type=Path,
                   help='Output: matching report JSON')
    p.add_argument('--quantile', type=float, default=0.3,
                   help='Quantile for binary label threshold (default: 0.3)')
    return p.parse_args()


def build_depmap_lookup(model_df, long_df):
    """
    Build DepMap cell line lookup dict with 2 normalization levels.

    Returns:
        {
            'strict':   {normalized_key: {info_dict}},
            'fallback': {normalized_key: {info_dict}}
        }
    """
    # cell_line_name set from depmap_long (cells that actually have CRISPR data)
    cells_with_crispr = set(long_df['cell_line_name'].unique())

    strict_lookup = {}
    fallback_lookup = {}

    for _, row in model_df.iterrows():
        model_id = row.get('ModelID')
        stripped = row.get('StrippedCellLineName')
        cell_name = row.get('CellLineName')

        if pd.isna(stripped):
            continue

        has_crispr = stripped in cells_with_crispr

        info = {
            'model_id': model_id,
            'stripped_name': stripped,
            'cell_name': cell_name,
            'has_crispr': has_crispr
        }

        # Strict lookup
        key_strict = normalize_strict(stripped)
        if key_strict and key_strict not in strict_lookup:
            strict_lookup[key_strict] = info

        # Fallback lookup
        key_fallback = normalize_fallback(stripped)
        if key_fallback and key_fallback not in fallback_lookup:
            fallback_lookup[key_fallback] = info

    return {
        'strict': strict_lookup,
        'fallback': fallback_lookup
    }


def match_cell_lines(gdsc_cells, depmap_lookup):
    """2-stage matching: strict first, fallback for unmatched."""
    matched = {}
    match_log = []
    unmatched = []

    # Stage 1: Strict
    for gdsc_name in gdsc_cells:
        key = normalize_strict(gdsc_name)
        if key in depmap_lookup['strict']:
            info = depmap_lookup['strict'][key]
            matched[gdsc_name] = info
            match_log.append({
                'gdsc_name': gdsc_name,
                'normalized': key,
                'stage': 'strict',
                'depmap_stripped': info['stripped_name'],
                'depmap_model_id': info['model_id'],
                'has_crispr': info['has_crispr']
            })
        else:
            unmatched.append(gdsc_name)

    log(f"Stage 1 (strict): matched {len(matched)}/{len(gdsc_cells)}")

    # Stage 2: Fallback for unmatched
    still_unmatched = []
    for gdsc_name in unmatched:
        key = normalize_fallback(gdsc_name)
        if key in depmap_lookup['fallback']:
            info = depmap_lookup['fallback'][key]
            matched[gdsc_name] = info
            match_log.append({
                'gdsc_name': gdsc_name,
                'normalized': key,
                'stage': 'fallback',
                'depmap_stripped': info['stripped_name'],
                'depmap_model_id': info['model_id'],
                'has_crispr': info['has_crispr']
            })
        else:
            still_unmatched.append(gdsc_name)

    log(f"Stage 2 (fallback): additionally matched {len(unmatched) - len(still_unmatched)}")
    log(f"Total matched: {len(matched)}/{len(gdsc_cells)}")
    log(f"Unmatched: {len(still_unmatched)}")

    return matched, still_unmatched, match_log


def main():
    args = parse_args()

    log("=" * 70)
    log("Step 2-4: Filter Colon cell lines and generate labels")
    log("=" * 70)

    # --- Load ---
    log("Loading GDSC IC50 data...")
    gdsc = pd.read_parquet(args.gdsc_ic50)
    log(f"  GDSC total: {gdsc.shape}")

    log("Loading DepMap Model data...")
    model = pd.read_parquet(args.depmap_model)
    log(f"  Model: {model.shape}")

    log("Loading DepMap CRISPR long data...")
    long_df = pd.read_parquet(args.depmap_long)
    log(f"  DepMap long: {long_df.shape}")
    log(f"  Cells with CRISPR data: {long_df['cell_line_name'].nunique()}")

    # --- Filter COREAD ---
    log("")
    log("Filtering GDSC for TCGA_DESC == 'COREAD'...")
    coread = gdsc[gdsc['TCGA_DESC'] == 'COREAD'].copy()
    gdsc_coread_cells = sorted(coread['CELL_LINE_NAME'].unique())
    log(f"  COREAD rows: {len(coread):,}")
    log(f"  COREAD cells: {len(gdsc_coread_cells)}")
    log(f"  COREAD drugs: {coread['DRUG_ID'].nunique()}")

    # --- Build lookup ---
    log("")
    log("Building DepMap lookup (2-level normalization)...")
    depmap_lookup = build_depmap_lookup(model, long_df)
    log(f"  Strict lookup size: {len(depmap_lookup['strict'])}")
    log(f"  Fallback lookup size: {len(depmap_lookup['fallback'])}")

    # --- Match ---
    log("")
    log("Matching GDSC COREAD cells with DepMap (2-stage)...")
    matched, unmatched, match_log = match_cell_lines(gdsc_coread_cells, depmap_lookup)

    # --- Create labels ---
    log("")
    log("Creating labels.parquet...")

    # Only keep matched cells
    matched_gdsc_names = set(matched.keys())
    coread_matched = coread[coread['CELL_LINE_NAME'].isin(matched_gdsc_names)].copy()

    # Add StrippedCellLineName (for sample_id)
    coread_matched['sample_id'] = coread_matched['CELL_LINE_NAME'].map(
        lambda x: matched[x]['stripped_name'] if x in matched else None
    )

    # Build labels df
    labels = coread_matched[['sample_id', 'DRUG_ID', 'LN_IC50']].copy()
    labels = labels.rename(columns={
        'DRUG_ID': 'canonical_drug_id',
        'LN_IC50': 'ic50'
    })
    labels['canonical_drug_id'] = labels['canonical_drug_id'].astype(str)

    # Drop NaN ic50
    before = len(labels)
    labels = labels.dropna(subset=['ic50'])
    after = len(labels)
    log(f"  Dropped NaN ic50: {before - after}")
    log(f"  Final labels rows: {after:,}")

    # Binary label
    threshold = labels['ic50'].quantile(args.quantile)
    labels['binary_label'] = (labels['ic50'] < threshold).astype(int)
    log(f"  Binary threshold (quantile {args.quantile}): {threshold:.4f}")
    log(f"  Binary distribution: 0={sum(labels['binary_label']==0):,}, 1={sum(labels['binary_label']==1):,}")

    # Ensure column order
    labels = labels[['sample_id', 'canonical_drug_id', 'ic50', 'binary_label']]

    # --- Save outputs ---
    args.output_labels.parent.mkdir(parents=True, exist_ok=True)
    args.output_cells.parent.mkdir(parents=True, exist_ok=True)
    args.output_report.parent.mkdir(parents=True, exist_ok=True)

    log("")
    log("Saving outputs...")

    # 1. labels.parquet
    labels.to_parquet(args.output_labels, index=False)
    log(f"  Saved: {args.output_labels} ({labels.shape})")

    # 2. matched cells CSV
    match_log_df = pd.DataFrame(match_log)

    # Add n_drugs per cell
    n_drugs_per_cell = coread_matched.groupby('CELL_LINE_NAME')['DRUG_ID'].nunique().to_dict()
    match_log_df['n_drugs_measured'] = match_log_df['gdsc_name'].map(n_drugs_per_cell).fillna(0).astype(int)

    match_log_df.to_csv(args.output_cells, index=False)
    log(f"  Saved: {args.output_cells} ({len(match_log_df)} cells)")

    # 3. JSON report
    report = {
        'timestamp': datetime.now().isoformat(),
        'input': {
            'gdsc_ic50': str(args.gdsc_ic50),
            'depmap_model': str(args.depmap_model),
            'depmap_long': str(args.depmap_long)
        },
        'gdsc_total': {
            'rows': int(gdsc.shape[0]),
            'cells': int(gdsc['CELL_LINE_NAME'].nunique())
        },
        'coread_filter': {
            'rows': int(len(coread)),
            'cells': len(gdsc_coread_cells),
            'drugs': int(coread['DRUG_ID'].nunique())
        },
        'matching': {
            'matched_strict': sum(1 for m in match_log if m['stage'] == 'strict'),
            'matched_fallback': sum(1 for m in match_log if m['stage'] == 'fallback'),
            'total_matched': len(matched),
            'unmatched': len(unmatched),
            'match_rate': len(matched) / len(gdsc_coread_cells) if gdsc_coread_cells else 0
        },
        'matched_with_crispr': sum(1 for m in match_log if m['has_crispr']),
        'unmatched_cells': unmatched,
        'labels_output': {
            'rows': int(after),
            'cells': int(labels['sample_id'].nunique()),
            'drugs': int(labels['canonical_drug_id'].nunique()),
            'binary_threshold': float(threshold),
            'binary_distribution': {
                '0': int(sum(labels['binary_label'] == 0)),
                '1': int(sum(labels['binary_label'] == 1))
            }
        }
    }

    with open(args.output_report, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log(f"  Saved: {args.output_report}")

    # --- Summary ---
    log("")
    log("=" * 70)
    log("Step 2-4 completed successfully")
    log(f"  Matched cells: {len(matched)}/{len(gdsc_coread_cells)} ({report['matching']['match_rate']*100:.1f}%)")
    log(f"  Labels generated: {after:,} rows")
    log(f"  Cells with CRISPR data: {report['matched_with_crispr']}")
    log("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
