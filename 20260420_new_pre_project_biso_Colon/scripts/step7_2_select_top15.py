#!/usr/bin/env python3
"""
Step 7-2: Select Final Top 15 Drugs and Categorize (Colon).

- Select ADMET PASS/WARNING drugs
- Categorize by colorectal cancer usage status
- Generate final recommendations
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


# Known colorectal cancer drug categories (clinical use + strong evidence)
CRC_CANCER_CATEGORIES: dict[str, list[str]] = {
    "current_use": [
        "Irinotecan",
        "Oxaliplatin",
        "Fluorouracil",
        "Capecitabine",
        "Trifluridine",
        "Cetuximab",
        "Panitumumab",
        "Bevacizumab",
        "Regorafenib",
        "Encorafenib",
        "Pembrolizumab",
        "Nivolumab",
        "Ipilimumab",
        "Topotecan",
    ],
    "research": [
        "Temsirolimus",
        "Rapamycin",
        "Entinostat",
        "Trametinib",
        "PD0325901",
        "MK-1775",
        "Navitoclax",
        "Sabutoclax",
        "TW 37",
        "Lestaurtinib",
        "Refametinib",
        "Camptothecin",
    ],
}


def _normalize_name(name: str) -> str:
    return str(name).strip().lower()


def _load_ct_trials_map(results_dir: Path) -> dict[str, dict[str, object]]:
    """Load clinical-trials matched details keyed by normalized drug name."""
    ct_path = results_dir / "colon_clinical_trials_validation_results.json"
    if not ct_path.exists():
        return {}

    with ct_path.open() as f:
        ct_data = json.load(f)

    out: dict[str, dict[str, object]] = {}
    for item in ct_data.get("matched_details", []):
        key = _normalize_name(item.get("drug_name", ""))
        if not key:
            continue
        out[key] = {
            "n_trials": int(item.get("n_trials", 0) or 0),
            "max_phase": str(item.get("max_phase", "")),
        }
    return out


def categorize_drug(drug_name: str, n_trials: int) -> str:
    """Categorize drug by colorectal cancer usage status."""
    normalized = _normalize_name(drug_name)
    current = {_normalize_name(x) for x in CRC_CANCER_CATEGORIES["current_use"]}
    research = {_normalize_name(x) for x in CRC_CANCER_CATEGORIES["research"]}

    if normalized in current:
        return "FDA_APPROVED_CRC"
    if normalized in research:
        return "RESEARCH_PHASE"
    if n_trials > 0:
        return "CLINICAL_TRIAL"
    return "REPURPOSING_CANDIDATE"


def select_top15(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select top 15 ADMET PASS/WARNING drugs."""
    print("=" * 80)
    print("STEP 7.2: SELECT FINAL TOP 15 (COLON)")
    print("=" * 80)

    # Filter ADMET PASS or WARNING (exclude FAIL)
    df_pass = df[df["verdict"].isin(["PASS", "WARNING"])].copy()
    print(f"\nADMET PASS/WARNING: {len(df_pass)}/{len(df)} drugs")

    # Sort by ADMET safety score first (descending), then lower IC50 as tiebreaker
    sort_cols = ["safety_score"]
    ascending = [False]
    if "pred_ic50_mean" in df_pass.columns:
        sort_cols.append("pred_ic50_mean")
        ascending.append(True)
    df_pass = df_pass.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)

    # Select Top 15
    df_top15 = df_pass.head(15).copy()
    return df_top15, df_pass


def print_final_recommendations(df_top15: pd.DataFrame) -> None:
    """Print final recommendations."""
    print(f"\n{'=' * 80}")
    print("FINAL TOP 15 DRUG RECOMMENDATIONS FOR COLORECTAL CANCER")
    print(f"{'=' * 80}")

    for category in ["FDA_APPROVED_CRC", "RESEARCH_PHASE", "CLINICAL_TRIAL", "REPURPOSING_CANDIDATE"]:
        df_cat = df_top15[df_top15["usage_category"] == category]
        if len(df_cat) == 0:
            continue

        print(f"\n{category} ({len(df_cat)} drugs):")
        print("-" * 80)
        for _, row in df_cat.iterrows():
            print(
                f"  #{row['recommendation_rank']:2d}. {row['drug_name']:20s} "
                f"(Safety: {row['safety_score']:.2f}, "
                f"Trials: {int(row['n_clinical_trials']):3d}, "
                f"ADMET: {row['verdict']})"
            )

    print(f"\n{'=' * 80}")
    print("CATEGORY SUMMARY")
    print(f"{'=' * 80}")
    for category in ["FDA_APPROVED_CRC", "RESEARCH_PHASE", "CLINICAL_TRIAL", "REPURPOSING_CANDIDATE"]:
        count = int((df_top15["usage_category"] == category).sum())
        print(f"  {category:30s}: {count:2d} drugs")


def main() -> tuple[pd.DataFrame, dict[str, object]]:
    base_dir = Path(__file__).parent.parent
    results_dir = base_dir / "results"

    # Load ADMET filtered data from Step 7-1
    input_path = results_dir / "colon_drugs_with_admet.csv"
    df = pd.read_csv(input_path)
    print(f"Total drugs: {len(df)}")
    print("ADMET status distribution:")
    print(df["verdict"].value_counts())

    # Add clinical trial stats for categorization
    ct_map = _load_ct_trials_map(results_dir)
    df["n_clinical_trials"] = df["drug_name"].map(lambda x: ct_map.get(_normalize_name(x), {}).get("n_trials", 0))
    df["ct_max_phase"] = df["drug_name"].map(lambda x: ct_map.get(_normalize_name(x), {}).get("max_phase", ""))

    # Select Top 15
    df_top15, df_pass = select_top15(df)

    # Categorize
    df_top15["usage_category"] = df_top15.apply(
        lambda row: categorize_drug(str(row["drug_name"]), int(row["n_clinical_trials"])),
        axis=1,
    )

    # Add recommendation priority
    category_priority = {
        "FDA_APPROVED_CRC": 1,
        "RESEARCH_PHASE": 2,
        "CLINICAL_TRIAL": 3,
        "REPURPOSING_CANDIDATE": 4,
    }
    df_top15["priority"] = df_top15["usage_category"].map(category_priority)
    df_top15 = df_top15.sort_values(["priority", "safety_score"], ascending=[True, False]).reset_index(drop=True)
    df_top15["recommendation_rank"] = range(1, len(df_top15) + 1)

    # Save Top 15
    top15_path = results_dir / "colon_final_top15.csv"
    df_top15.to_csv(top15_path, index=False)
    print(f"\n✓ Saved: {top15_path}")

    # Save all PASS/WARNING drugs
    pass_path = results_dir / "colon_all_admet_pass.csv"
    df_pass.to_csv(pass_path, index=False)
    print(f"✓ Saved: {pass_path}")

    # Print recommendations
    print_final_recommendations(df_top15)

    # Save summary
    category_counts = df_top15["usage_category"].value_counts().to_dict()
    summary: dict[str, object] = {
        "total_candidates": int(len(df)),
        "admet_pass_warning": int(len(df_pass)),
        "top_15_selected": int(len(df_top15)),
        "category_distribution": category_counts,
        "top_5_recommendations": df_top15.head(5)[
            ["recommendation_rank", "drug_name", "usage_category", "safety_score", "n_clinical_trials", "verdict"]
        ].to_dict("records"),
    }

    summary_path = results_dir / "colon_final_top15_summary.json"
    with summary_path.open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n✓ Saved: {summary_path}")

    print(f"\n{'=' * 80}")
    print("TOP 15 SELECTION COMPLETE")
    print(f"{'=' * 80}")
    return df_top15, summary


if __name__ == "__main__":
    df_top15, summary = main()
