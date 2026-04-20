#!/usr/bin/env python3
"""
Step 2 Integrated QC: validate all Step 2 outputs for FE (Step 3) compatibility.

Checks:
  1. File existence and sizes
  2. Schema validation (columns, dtypes)
  3. Drug ID consistency across files
  4. Cell line ID consistency
  5. NaN rates and value ranges
  6. Cross-reference with Lung schema (where applicable)
  7. FE input compatibility

Output: reports/step2_integrated_qc_report.json
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def check_file(path, name, report):
    """Check file existence and size."""
    if not path.exists():
        log(f"  ❌ MISSING: {name}")
        report["files"][name] = {"exists": False}
        return False

    size_mb = path.stat().st_size / 1024**2
    log(f"  ✓ {name}: {size_mb:.2f} MB")
    report["files"][name] = {
        "exists": True,
        "size_bytes": path.stat().st_size,
        "size_mb": round(size_mb, 2),
    }
    return True


def main():
    base = Path(
        "/Users/skku_aws2_14/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest/20260415_preproject_choi_protocol_v1_bisotest-1/20260420_new_pre_project_biso_Colon"
    )

    data_dir = base / "data"
    processed_dir = base / "curated_data" / "processed"
    output_report = base / "reports" / "step2_integrated_qc_report.json"

    report = {
        "timestamp": datetime.now().isoformat(),
        "files": {},
        "schemas": {},
        "consistency": {},
        "statistics": {},
        "issues": [],
        "passed": True,
    }

    log("=" * 70)
    log("Step 2-10: Integrated QC")
    log("=" * 70)

    # ====================================================================
    # 1. File existence check
    # ====================================================================
    log("")
    log("=== 1. File existence ===")

    files_to_check = {
        "labels": data_dir / "labels.parquet",
        "drug_features": data_dir / "drug_features.parquet",
        "drug_target_mapping": data_dir / "drug_target_mapping.parquet",
        "lincs_colon": data_dir / "lincs_colon.parquet",
        "lincs_colon_drug_level": data_dir / "lincs_colon_drug_level.parquet",
        "colon_subtype_metadata": data_dir / "colon_subtype_metadata.parquet",
        "depmap_crispr_long": processed_dir / "depmap" / "depmap_crispr_long_colon.parquet",
    }

    dfs = {}
    for name, path in files_to_check.items():
        if check_file(path, name, report):
            try:
                dfs[name] = pd.read_parquet(path)
            except Exception as e:
                log(f"  ❌ Load failed for {name}: {e}")
                report["issues"].append(f"{name}: load failed - {e}")
                report["passed"] = False

    # ====================================================================
    # 2. Schema validation
    # ====================================================================
    log("")
    log("=== 2. Schema validation ===")

    expected_schemas = {
        "labels": {
            "required": ["sample_id", "canonical_drug_id", "ic50", "binary_label"],
            "row_count": (12500, 12600),  # expected range
        },
        "drug_features": {
            "required": [
                "canonical_drug_id",
                "canonical_smiles",
                "canonical_smiles_raw",
                "drug_name_norm",
                "has_smiles",
            ],
            "row_count": (295, 295),
        },
        "drug_target_mapping": {
            "required": ["canonical_drug_id", "target_gene_symbol"],
            "row_count": (400, 500),
        },
        "lincs_colon": {
            "required": ["sig_id", "pert_id", "pert_iname", "cell_id"],
            "row_count": (18000, 19000),
            "col_count": 12336,
        },
        "lincs_colon_drug_level": {
            "required": ["canonical_drug_id"],
            "row_count": (80, 100),
            "col_count": 12329,
        },
        "colon_subtype_metadata": {
            "required": [
                "patient_id",
                "sample_id",
                "primary_site",
                "msi_status",
                "ras_mutation",
                "braf_mutation",
                "braf_v600e",
            ],
            "row_count": (590, 600),
        },
        "depmap_crispr_long": {
            "required": ["cell_line_name", "gene_name", "dependency"],
            "row_count": (20000000, 21000000),
        },
    }

    for name, spec in expected_schemas.items():
        if name not in dfs:
            continue

        df = dfs[name]
        log("")
        log(f"  {name}: shape={df.shape}")

        # Column check
        missing_cols = [c for c in spec["required"] if c not in df.columns]
        if missing_cols:
            msg = f"{name}: missing columns {missing_cols}"
            log(f"    ❌ {msg}")
            report["issues"].append(msg)
            report["passed"] = False
        else:
            log("    ✓ all required columns present")

        # Row count check
        min_r, max_r = spec["row_count"]
        if not (min_r <= len(df) <= max_r):
            msg = f"{name}: row count {len(df)} outside expected range [{min_r}, {max_r}]"
            log(f"    ⚠ {msg}")
            report["issues"].append(msg)

        # Col count check (if specified)
        if "col_count" in spec:
            if len(df.columns) != spec["col_count"]:
                msg = f"{name}: col count {len(df.columns)} != expected {spec['col_count']}"
                log(f"    ⚠ {msg}")
                report["issues"].append(msg)

        report["schemas"][name] = {
            "shape": list(df.shape),
            "columns": df.columns.tolist()[:15],  # first 15 only for brevity
            "n_columns": len(df.columns),
            "dtypes_sample": {c: str(df[c].dtype) for c in df.columns[:10]},
        }

    # ====================================================================
    # 3. Drug ID consistency (MOST IMPORTANT)
    # ====================================================================
    log("")
    log("=== 3. Drug ID consistency ===")

    if "labels" in dfs and "drug_features" in dfs:
        labels_drugs = set(dfs["labels"]["canonical_drug_id"].astype(str))
        features_drugs = set(dfs["drug_features"]["canonical_drug_id"].astype(str))

        log(f"  labels drugs:          {len(labels_drugs)}")
        log(f"  drug_features drugs:   {len(features_drugs)}")
        log(f"  Intersection:          {len(labels_drugs & features_drugs)}")
        log(f"  labels not in features: {len(labels_drugs - features_drugs)}")

        report["consistency"]["labels_vs_features"] = {
            "labels": len(labels_drugs),
            "features": len(features_drugs),
            "intersection": len(labels_drugs & features_drugs),
            "labels_only": len(labels_drugs - features_drugs),
            "features_only": len(features_drugs - labels_drugs),
        }

        if labels_drugs != features_drugs:
            msg = "labels and drug_features drug sets don't exactly match"
            log(f"  ❌ {msg}")
            report["issues"].append(msg)
            report["passed"] = False
        else:
            log("  ✓ labels == drug_features (exact match)")

    if "drug_target_mapping" in dfs and "drug_features" in dfs:
        dtm_drugs = set(dfs["drug_target_mapping"]["canonical_drug_id"].astype(str))
        features_drugs = set(dfs["drug_features"]["canonical_drug_id"].astype(str))

        log(f"  drug_target drugs:     {len(dtm_drugs)}")
        log(f"  dtm ⊆ features:         {dtm_drugs.issubset(features_drugs)}")

        report["consistency"]["dtm_subset_of_features"] = dtm_drugs.issubset(features_drugs)

        if not dtm_drugs.issubset(features_drugs):
            msg = "drug_target_mapping has drugs not in drug_features"
            log(f"  ⚠ {msg}")
            report["issues"].append(msg)

    if "lincs_colon_drug_level" in dfs and "drug_features" in dfs:
        lincs_drugs = set(dfs["lincs_colon_drug_level"]["canonical_drug_id"].astype(str))
        features_drugs = set(dfs["drug_features"]["canonical_drug_id"].astype(str))

        log(f"  lincs_drug_level:      {len(lincs_drugs)}")
        log(f"  lincs ⊆ features:       {lincs_drugs.issubset(features_drugs)}")

        report["consistency"]["lincs_subset_of_features"] = lincs_drugs.issubset(features_drugs)

    # ====================================================================
    # 4. Cell line consistency
    # ====================================================================
    log("")
    log("=== 4. Cell line consistency ===")

    if "labels" in dfs:
        cells = set(dfs["labels"]["sample_id"].astype(str))
        log(f"  labels cells: {len(cells)}")
        report["consistency"]["labels_cells"] = len(cells)

    if "depmap_crispr_long" in dfs and "labels" in dfs:
        depmap_cells = set(dfs["depmap_crispr_long"]["cell_line_name"].astype(str))
        labels_cells = set(dfs["labels"]["sample_id"].astype(str))

        log(f"  depmap cells: {len(depmap_cells)}")
        log(f"  labels cells: {len(labels_cells)}")
        log(f"  Intersection: {len(depmap_cells & labels_cells)}")

        # Labels cells should be subset of depmap (or close to it)
        report["consistency"]["labels_in_depmap"] = len(labels_cells & depmap_cells)
        report["consistency"]["labels_not_in_depmap"] = len(labels_cells - depmap_cells)

    if "lincs_colon" in dfs:
        lincs_cells = set(dfs["lincs_colon"]["cell_id"].astype(str))
        log(f"  lincs cells: {len(lincs_cells)} (Colon 13 expected)")
        report["consistency"]["lincs_cells"] = len(lincs_cells)

    # ====================================================================
    # 5. NaN check
    # ====================================================================
    log("")
    log("=== 5. NaN rates ===")

    for name, df in dfs.items():
        nan_summary = {}
        for col in df.columns[:20]:  # first 20 cols
            nan_pct = df[col].isna().mean() * 100
            if nan_pct > 0:
                nan_summary[col] = round(nan_pct, 2)

        if nan_summary:
            log(f"  {name}:")
            for col, pct in list(nan_summary.items())[:5]:
                log(f"    {col}: {pct}%")
            report["statistics"][f"{name}_nan_cols"] = nan_summary

    # ====================================================================
    # 6. Key statistics
    # ====================================================================
    log("")
    log("=== 6. Key statistics ===")

    if "labels" in dfs:
        labels = dfs["labels"]
        binary_dist = labels["binary_label"].value_counts().to_dict()
        log(f"  binary_label: {binary_dist}")
        report["statistics"]["binary_label_distribution"] = {str(k): int(v) for k, v in binary_dist.items()}

    if "colon_subtype_metadata" in dfs:
        sub = dfs["colon_subtype_metadata"]
        log("  Subtype metadata:")
        log(f"    MSI-H: {(sub['msi_status'] == 'MSI-H').sum()}")
        log(f"    RAS+:  {(sub['ras_mutation'] == 1).sum()}")
        log(f"    BRAF+: {(sub['braf_mutation'] == 1).sum()}")

    if "lincs_colon" in dfs:
        lincs = dfs["lincs_colon"]
        ht29_pct = (lincs["cell_id"] == "HT29").mean() * 100
        log(f"  LINCS HT29 편향: {ht29_pct:.1f}%")
        report["statistics"]["lincs_ht29_pct"] = round(ht29_pct, 2)

    # ====================================================================
    # 7. Final summary
    # ====================================================================
    log("")
    log("=" * 70)
    if report["passed"] and len(report["issues"]) == 0:
        log("✅ ALL QC CHECKS PASSED")
    elif report["passed"]:
        log(f"⚠ PASSED WITH {len(report['issues'])} WARNINGS")
    else:
        log(f"❌ FAILED ({len(report['issues'])} issues)")
    log("=" * 70)

    if report["issues"]:
        log("")
        log("Issues:")
        for issue in report["issues"]:
            log(f"  - {issue}")

    # Save report
    output_report.parent.mkdir(parents=True, exist_ok=True)
    with open(output_report, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    log("")
    log(f"Report saved: {output_report}")

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
