#!/usr/bin/env python3
"""
Colon subtype tagging for TCGA COADREAD patients.

Colon-specific new script (no Lung/BRCA equivalent).
Extracts MSI, RAS, BRAF, subtype status from cBioPortal TCGA data
for downstream subtype stratification analysis.

Process:
  1. Load clinical_sample.txt -> SAMPLE_ID, PATIENT_ID, ONCOTREE_CODE, MSI scores
  2. Load clinical_patient.txt -> PATIENT_ID, SUBTYPE
  3. Load data_mutations.txt, filter KRAS/NRAS/BRAF, exclude silent/synonymous
  4. Per-sample aggregation: ras_mutation, braf_mutation, braf_v600e
  5. Merge sample × patient × mutation summary
  6. Tag: primary_site (COAD/READ), msi_status (MSI-H if MANTIS > 0.4)

Output:
  data/colon_subtype_metadata.parquet (~594 rows × 11 cols)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


# MSI-H threshold (MANTIS score)
MSI_MANTIS_THRESHOLD = 0.4

# Silent/synonymous variant classifications to exclude
# (non-coding / synonymous variants don't affect protein function)
SILENT_VARIANT_CLASSES = {
    "Silent",
    "Intron",
    "3'UTR",
    "5'UTR",
    "3'Flank",
    "5'Flank",
    "RNA",
    "IGR",
    "Splice_Region",
}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--clinical-sample-uri", required=True, type=Path, help="Path to data_clinical_sample.txt")
    p.add_argument("--clinical-patient-uri", required=True, type=Path, help="Path to data_clinical_patient.txt")
    p.add_argument("--mutations-uri", required=True, type=Path, help="Path to data_mutations.txt")
    p.add_argument("--output-uri", required=True, type=Path, help="Output: colon_subtype_metadata.parquet")
    p.add_argument("--report-uri", required=True, type=Path, help="Output: subtype tagging report JSON")
    p.add_argument(
        "--msi-threshold",
        type=float,
        default=MSI_MANTIS_THRESHOLD,
        help=f"MSI-H MANTIS threshold (default: {MSI_MANTIS_THRESHOLD})",
    )
    return p.parse_args()


def load_clinical_sample(path):
    """Load cBioPortal clinical_sample.txt (4 comment lines)."""
    log(f"Loading clinical_sample: {path.name}")
    df = pd.read_csv(path, sep="\t", comment="#", low_memory=False)
    log(f"  Shape: {df.shape}")

    # Required columns
    required = ["SAMPLE_ID", "PATIENT_ID", "ONCOTREE_CODE"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        log(f"  ERROR: Missing columns: {missing}")
        log(f"  Available: {df.columns.tolist()}")
        sys.exit(1)

    # MSI columns (optional but expected)
    msi_cols = ["MSI_SCORE_MANTIS", "MSI_SENSOR_SCORE"]
    for col in msi_cols:
        if col not in df.columns:
            log(f"  WARNING: {col} missing, will fill with NaN")
            df[col] = None

    return df


def load_clinical_patient(path):
    """Load cBioPortal clinical_patient.txt (4 comment lines)."""
    log(f"Loading clinical_patient: {path.name}")
    df = pd.read_csv(path, sep="\t", comment="#", low_memory=False)
    log(f"  Shape: {df.shape}")

    required = ["PATIENT_ID"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        log(f"  ERROR: Missing columns: {missing}")
        sys.exit(1)

    # SUBTYPE is optional
    if "SUBTYPE" not in df.columns:
        log("  WARNING: SUBTYPE missing, will fill with NaN")
        df["SUBTYPE"] = None

    return df[["PATIENT_ID", "SUBTYPE"]].copy()


def load_and_aggregate_mutations(path):
    """
    Load mutations, filter KRAS/NRAS/BRAF, exclude silent.
    Aggregate per Tumor_Sample_Barcode.
    """
    log(f"Loading mutations: {path.name}")

    # Only load necessary columns (save memory)
    usecols = ["Hugo_Symbol", "Tumor_Sample_Barcode", "HGVSp_Short", "Variant_Classification"]
    df = pd.read_csv(path, sep="\t", comment="#", low_memory=False, usecols=usecols)
    log(f"  Total mutations: {len(df):,}")

    # Filter to genes of interest
    genes = ["KRAS", "NRAS", "BRAF"]
    filtered = df[df["Hugo_Symbol"].isin(genes)].copy()
    log(f"  KRAS/NRAS/BRAF mutations (all): {len(filtered):,}")

    # Exclude silent/non-coding
    pre = len(filtered)
    filtered = filtered[~filtered["Variant_Classification"].isin(SILENT_VARIANT_CLASSES)]
    log(f"  After excluding silent/non-coding: {len(filtered):,} ({pre - len(filtered)} removed)")

    # Per-sample aggregation
    log("  Aggregating per sample...")

    # Sample IDs with each mutation type
    samples_ras = set(filtered[filtered["Hugo_Symbol"].isin(["KRAS", "NRAS"])]["Tumor_Sample_Barcode"])
    samples_braf = set(filtered[filtered["Hugo_Symbol"] == "BRAF"]["Tumor_Sample_Barcode"])
    samples_braf_v600e = set(
        filtered[(filtered["Hugo_Symbol"] == "BRAF") & (filtered["HGVSp_Short"] == "p.V600E")][
            "Tumor_Sample_Barcode"
        ]
    )

    log(f"  Samples with RAS mutation:      {len(samples_ras):,}")
    log(f"  Samples with BRAF mutation:     {len(samples_braf):,}")
    log(f"  Samples with BRAF V600E:        {len(samples_braf_v600e):,}")

    # Collect all unique samples
    all_samples = samples_ras | samples_braf

    mutation_df = pd.DataFrame({"SAMPLE_ID": list(all_samples)})
    mutation_df["ras_mutation"] = mutation_df["SAMPLE_ID"].isin(samples_ras).astype(int)
    mutation_df["braf_mutation"] = mutation_df["SAMPLE_ID"].isin(samples_braf).astype(int)
    mutation_df["braf_v600e"] = mutation_df["SAMPLE_ID"].isin(samples_braf_v600e).astype(int)

    log(f"  Mutation summary shape: {mutation_df.shape}")
    return mutation_df


def derive_primary_site(oncotree_code):
    """Derive COAD/READ from ONCOTREE_CODE."""
    if pd.isna(oncotree_code):
        return None
    code = str(oncotree_code).upper()
    if code == "COAD":
        return "COAD"
    if code == "READ":
        return "READ"
    if code == "COADREAD":
        return "COADREAD"  # ambiguous, both
    return code  # other or unknown


def derive_msi_status(mantis_score, threshold):
    """MSI-H if MANTIS > threshold (default 0.4)."""
    if pd.isna(mantis_score):
        return None
    try:
        score = float(mantis_score)
        return "MSI-H" if score > threshold else "MSS"
    except (ValueError, TypeError):
        return None


def main():
    args = parse_args()

    log("=" * 70)
    log("Step 2-8: Colon subtype tagging (TCGA COADREAD)")
    log("=" * 70)

    # Validate inputs
    for path, name in [
        (args.clinical_sample_uri, "clinical_sample"),
        (args.clinical_patient_uri, "clinical_patient"),
        (args.mutations_uri, "mutations"),
    ]:
        if not path.exists():
            log(f"ERROR: {name} not found: {path}")
            sys.exit(1)

    # Step 1: Load data
    sample_df = load_clinical_sample(args.clinical_sample_uri)
    patient_df = load_clinical_patient(args.clinical_patient_uri)
    mutation_df = load_and_aggregate_mutations(args.mutations_uri)

    # Step 2: Merge
    log("")
    log("=== Merging ===")

    # Start from sample (it has PATIENT_ID link)
    keep_cols = ["SAMPLE_ID", "PATIENT_ID", "ONCOTREE_CODE", "MSI_SCORE_MANTIS", "MSI_SENSOR_SCORE"]
    merged = sample_df[keep_cols].copy()

    # Merge patient subtype
    merged = merged.merge(patient_df, on="PATIENT_ID", how="left")
    log(f"  After patient merge: {merged.shape}")

    # Merge mutation summary
    merged = merged.merge(mutation_df, on="SAMPLE_ID", how="left")
    log(f"  After mutation merge: {merged.shape}")

    # Fill NaN mutation flags with 0 (sample has no RAS/BRAF mutation)
    for col in ["ras_mutation", "braf_mutation", "braf_v600e"]:
        merged[col] = merged[col].fillna(0).astype(int)

    # Step 3: Derived columns
    log("")
    log("=== Deriving tags ===")
    merged["primary_site"] = merged["ONCOTREE_CODE"].apply(derive_primary_site)
    merged["msi_status"] = merged["MSI_SCORE_MANTIS"].apply(lambda x: derive_msi_status(x, args.msi_threshold))

    # Rename to final schema
    result = pd.DataFrame(
        {
            "patient_id": merged["PATIENT_ID"],
            "sample_id": merged["SAMPLE_ID"],
            "primary_site": merged["primary_site"],
            "oncotree_code": merged["ONCOTREE_CODE"],
            "msi_score_mantis": pd.to_numeric(merged["MSI_SCORE_MANTIS"], errors="coerce"),
            "msi_sensor_score": pd.to_numeric(merged["MSI_SENSOR_SCORE"], errors="coerce"),
            "msi_status": merged["msi_status"],
            "subtype": merged["SUBTYPE"],
            "ras_mutation": merged["ras_mutation"].astype(int),
            "braf_mutation": merged["braf_mutation"].astype(int),
            "braf_v600e": merged["braf_v600e"].astype(int),
        }
    )

    log(f"Final shape: {result.shape}")

    # Step 4: Stats
    log("")
    log("=== Statistics ===")
    log(f"Total samples: {len(result):,}")
    log("")
    log("primary_site distribution:")
    log(result["primary_site"].value_counts(dropna=False).to_string())
    log("")
    log("msi_status distribution:")
    log(result["msi_status"].value_counts(dropna=False).to_string())
    log("")
    log("subtype distribution:")
    log(result["subtype"].value_counts(dropna=False).head(10).to_string())
    log("")
    log(f"ras_mutation=1:  {(result['ras_mutation'] == 1).sum()} ({(result['ras_mutation'] == 1).mean() * 100:.1f}%)")
    log(
        f"braf_mutation=1: {(result['braf_mutation'] == 1).sum()} ({(result['braf_mutation'] == 1).mean() * 100:.1f}%)"
    )
    log(f"braf_v600e=1:    {(result['braf_v600e'] == 1).sum()} ({(result['braf_v600e'] == 1).mean() * 100:.1f}%)")

    # Step 5: Save
    log("")
    args.output_uri.parent.mkdir(parents=True, exist_ok=True)
    args.report_uri.parent.mkdir(parents=True, exist_ok=True)

    result.to_parquet(args.output_uri, index=False)
    size_kb = args.output_uri.stat().st_size / 1024
    log(f"Saved: {args.output_uri} ({size_kb:.1f} KB)")

    # Report
    report = {
        "timestamp": datetime.now().isoformat(),
        "input": {
            "clinical_sample": str(args.clinical_sample_uri),
            "clinical_patient": str(args.clinical_patient_uri),
            "mutations": str(args.mutations_uri),
        },
        "config": {
            "msi_mantis_threshold": args.msi_threshold,
            "excluded_variant_classes": sorted(SILENT_VARIANT_CLASSES),
        },
        "output": {"path": str(args.output_uri), "shape": list(result.shape)},
        "stats": {
            "total_samples": int(len(result)),
            "primary_site": {
                k: int(v) for k, v in result["primary_site"].value_counts(dropna=False).items() if pd.notna(k)
            },
            "msi_status": {k: int(v) for k, v in result["msi_status"].value_counts(dropna=False).items() if pd.notna(k)},
            "subtype_top10": {str(k): int(v) for k, v in result["subtype"].value_counts(dropna=False).head(10).items()},
            "ras_mutation_positive": int((result["ras_mutation"] == 1).sum()),
            "braf_mutation_positive": int((result["braf_mutation"] == 1).sum()),
            "braf_v600e_positive": int((result["braf_v600e"] == 1).sum()),
            "msi_h_count": int((result["msi_status"] == "MSI-H").sum()),
            "mss_count": int((result["msi_status"] == "MSS").sum()),
        },
    }

    with open(args.report_uri, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    log(f"Report saved: {args.report_uri}")

    log("")
    log("=" * 70)
    log("Step 2-8 completed successfully")
    log("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
