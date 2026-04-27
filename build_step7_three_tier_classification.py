#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RERUN = ROOT / "results/20260424_multicancer_stad_protocol_rerun"
FINAL_UPDATE = RERUN / "restored_protocol_top30_ev_top15_admet_multiresponse" / "final_update"
DASH_EXTRACTS = RERUN / "dashboard_extracts"


def classify_protocol_stage(row: pd.Series) -> tuple[str, str, str]:
    # Protocol-aligned 3-stage mapping (STAD protocol Step7 style):
    # stage1: ADMET PASS and (FDA_APPROVED_GASTRIC OR clinical trials >=3)
    # stage2: ADMET PASS and not stage1
    # stage3: ADMET WARNING
    admet_status = str(row.get("admet_status_22assay", "WARNING") or "WARNING").upper()
    ct_total = float(row.get("n_clinicaltrials_studies_total", 0) or 0)
    fda_approved_gastric_proxy = bool(row.get("fda_approved_gastric_proxy", False))

    if admet_status == "PASS":
        if fda_approved_gastric_proxy or ct_total >= 3:
            return (
                "stage1_transition_standard",
                "1단계 약물",
                "ADMET_PASS_and_(FDA_APPROVED_GASTRIC_PROXY_or_CT>=3)",
            )
        return (
            "stage2_evidence_review",
            "2단계 약물",
            "ADMET_PASS_and_not_stage1",
        )
    return (
        "stage3_exploratory_supportive",
        "3단계 약물",
        "ADMET_WARNING",
    )


def main() -> None:
    ts = datetime.now(timezone.utc).isoformat()
    inp = FINAL_UPDATE / "final_multiresponse_ev_admet_integrated_ranking.csv"
    if not inp.exists():
        raise FileNotFoundError(f"Missing input: {inp}")

    df = pd.read_csv(inp)
    ev_inp = RERUN / "restored_protocol_top30_ev_top15_admet_multiresponse" / "step6_top30_ev_evidence_with_multiresponse.csv"
    ev = pd.read_csv(ev_inp)[["cancer", "canonical_drug_id", "n_clinicaltrials_studies_total"]].drop_duplicates(
        ["cancer", "canonical_drug_id"]
    )
    df = df.merge(ev, on=["cancer", "canonical_drug_id"], how="left", suffixes=("", "_ev"))
    if "n_clinicaltrials_studies_total_ev" in df.columns:
        if "n_clinicaltrials_studies_total" in df.columns:
            df["n_clinicaltrials_studies_total"] = df["n_clinicaltrials_studies_total"].fillna(
                df["n_clinicaltrials_studies_total_ev"]
            )
        else:
            df["n_clinicaltrials_studies_total"] = df["n_clinicaltrials_studies_total_ev"]
    if "final_rank_by_cancer" in df.columns:
        df = df[df["final_rank_by_cancer"].astype(int) <= 15].copy()

    mapping_csv = FINAL_UPDATE / "cancer_approved_drug_mapping_table.csv"
    if mapping_csv.exists():
        m = pd.read_csv(mapping_csv)
        approval_col = "final_approved_for_same_cancer" if "final_approved_for_same_cancer" in m.columns else "approved_for_same_cancer"
        m = m[m.get(approval_col, False).astype(bool)].copy()
        m = m[["cancer", "canonical_drug_id"]].drop_duplicates(["cancer", "canonical_drug_id"])
        m["fda_approved_cancer_based"] = True
        df = df.merge(m, on=["cancer", "canonical_drug_id"], how="left", suffixes=("", "_map"))
        if "fda_approved_cancer_based_map" in df.columns:
            if "fda_approved_cancer_based" in df.columns:
                df["fda_approved_cancer_based"] = df["fda_approved_cancer_based"].eq(True) | df[
                    "fda_approved_cancer_based_map"
                ].eq(True)
            else:
                df["fda_approved_cancer_based"] = df["fda_approved_cancer_based_map"].eq(True)
        else:
            df["fda_approved_cancer_based"] = df.get("fda_approved_cancer_based", False)
        df["fda_approved_cancer_based"] = df["fda_approved_cancer_based"].eq(True)
    else:
        # Fallback proxy when explicit mapping table does not exist yet.
        df["fda_approved_cancer_based"] = df["drug_repurposing_category"].eq("current_use_same_cancer")
    # Backward-compatibility alias for previous dashboard field name.
    df["fda_approved_gastric_proxy"] = df["fda_approved_cancer_based"]

    # Keep previous tier columns for backward compatibility, but main stage uses protocol mapping.
    df["repurposing_tier3_code"] = "legacy_recomputed"
    df["repurposing_tier3_ko"] = "legacy_recomputed"
    df["repurposing_tier3_rule"] = "replaced_by_protocol_stage"

    stages = df.apply(classify_protocol_stage, axis=1, result_type="expand")
    df["recommendation_stage_code"] = stages[0]
    df["recommendation_stage_label_ko"] = stages[1]
    df["recommendation_stage_rule"] = stages[2]

    keep_cols = [
        "cancer",
        "final_rank_by_cancer",
        "final_rank_overall",
        "canonical_drug_id",
        "drug_name",
        "score_approved_ind",
        "score_clinical_trial",
        "n_clinicaltrials_studies_total",
        "fda_approved_cancer_based",
        "fda_approved_gastric_proxy",
        "admet_status_22assay",
        "drug_repurposing_category",
        "recommendation_stage_code",
        "recommendation_stage_label_ko",
        "recommendation_stage_rule",
        "repurposing_tier3_code",
        "repurposing_tier3_ko",
        "repurposing_tier3_rule",
        "final_priority_score",
        "final_recommendation_tier",
        "admet_tier",
        "ev_composite_0_10",
    ]
    out_df = df[[c for c in keep_cols if c in df.columns]].copy()

    FINAL_UPDATE.mkdir(parents=True, exist_ok=True)
    DASH_EXTRACTS.mkdir(parents=True, exist_ok=True)

    out_csv = FINAL_UPDATE / "final_multiresponse_three_tier_classification_top15.csv"
    out_df.to_csv(out_csv, index=False)

    summary = (
        out_df.groupby(["cancer", "recommendation_stage_code", "recommendation_stage_label_ko"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["cancer", "recommendation_stage_code"])
    )
    summary_csv = FINAL_UPDATE / "final_multiresponse_three_tier_summary_by_cancer.csv"
    summary.to_csv(summary_csv, index=False)

    payload = {
        "generated_utc": ts,
        "source_csv": str(inp.relative_to(ROOT)),
        "evidence_csv": str(ev_inp.relative_to(ROOT)),
        "mapping_csv": str(mapping_csv.relative_to(ROOT)) if mapping_csv.exists() else None,
        "classification_csv": str(out_csv.relative_to(ROOT)),
        "summary_csv": str(summary_csv.relative_to(ROOT)),
        "n_rows": int(len(out_df)),
        "rows_by_cancer": {
            k: v.sort_values("final_rank_by_cancer").to_dict(orient="records")
            for k, v in out_df.groupby("cancer")
        },
        "summary_by_cancer": {
            k: v[["recommendation_stage_code", "recommendation_stage_label_ko", "count"]].to_dict(orient="records")
            for k, v in summary.groupby("cancer")
        },
    }

    (FINAL_UPDATE / "final_multiresponse_three_tier_classification_top15.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (DASH_EXTRACTS / "dashboard_step7_three_tier_bundle.js").write_text(
        "window.STEP7_THREE_TIER_BUNDLE=" + json.dumps(payload, ensure_ascii=False) + ";",
        encoding="utf-8",
    )
    print(f"wrote: {out_csv}")
    print(f"wrote: {summary_csv}")
    print(f"wrote: {DASH_EXTRACTS / 'dashboard_step7_three_tier_bundle.js'}")


if __name__ == "__main__":
    main()

