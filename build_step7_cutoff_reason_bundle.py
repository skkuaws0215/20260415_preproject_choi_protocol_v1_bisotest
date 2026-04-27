#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
RERUN = ROOT / "results/20260424_multicancer_stad_protocol_rerun"
FINAL_UPDATE = RERUN / "restored_protocol_top30_ev_top15_admet_multiresponse" / "final_update"
DASH = RERUN / "dashboard_extracts"


def cutoff_reason(r: pd.Series) -> str:
    if bool(r.get("selected_top15", False)):
        return "selected_top15_by_step7_protocol_rank"
    s = str(r.get("recommendation_stage_code", ""))
    rank = int(r.get("protocol_stage_rank_within_top30", 999))
    if s == "stage3_exploratory_supportive":
        return "not_selected_stage3_warning_priority"
    if rank > 15:
        return "not_selected_rank_outside_top15_after_stage_order"
    return "not_selected_tie_or_priority_cutoff"


def main() -> None:
    ts = datetime.now(timezone.utc).isoformat()
    prestage = pd.read_csv(FINAL_UPDATE / "step7_protocol_prestage_top30.csv")
    final15 = pd.read_csv(FINAL_UPDATE / "final_multiresponse_ev_admet_integrated_ranking.csv")
    final15 = final15[final15["final_rank_by_cancer"].astype(int) <= 15][["cancer", "canonical_drug_id"]].drop_duplicates()
    final15["selected_top15"] = True

    out = prestage.merge(final15, on=["cancer", "canonical_drug_id"], how="left")
    out["selected_top15"] = out["selected_top15"].eq(True)
    out["cutoff_reason"] = out.apply(cutoff_reason, axis=1)
    out = out.sort_values(["cancer", "selected_top15", "protocol_stage_rank_within_top30", "ev_composite_0_10"], ascending=[True, False, True, False])

    out_csv = FINAL_UPDATE / "step7_top30_to_top15_cutoff_reason_table.csv"
    out.to_csv(out_csv, index=False)

    summary = (
        out.groupby(["cancer", "selected_top15", "recommendation_stage_code", "cutoff_reason"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["cancer", "selected_top15", "recommendation_stage_code"])
    )
    summary_csv = FINAL_UPDATE / "step7_top30_to_top15_cutoff_reason_summary.csv"
    summary.to_csv(summary_csv, index=False)

    payload = {
        "generated_utc": ts,
        "source_prestage_csv": str((FINAL_UPDATE / "step7_protocol_prestage_top30.csv").relative_to(ROOT)),
        "source_top15_csv": str((FINAL_UPDATE / "final_multiresponse_ev_admet_integrated_ranking.csv").relative_to(ROOT)),
        "output_cutoff_csv": str(out_csv.relative_to(ROOT)),
        "output_summary_csv": str(summary_csv.relative_to(ROOT)),
        "rows_by_cancer": {
            k: v.to_dict(orient="records")
            for k, v in out.groupby("cancer")
        },
        "summary_by_cancer": {
            k: v.to_dict(orient="records")
            for k, v in summary.groupby("cancer")
        },
    }
    (DASH / "dashboard_step7_cutoff_bundle.js").write_text(
        "window.STEP7_CUTOFF_BUNDLE=" + json.dumps(payload, ensure_ascii=False) + ";",
        encoding="utf-8",
    )
    print(f"wrote: {out_csv}")
    print(f"wrote: {summary_csv}")
    print(f"wrote: {DASH / 'dashboard_step7_cutoff_bundle.js'}")


if __name__ == "__main__":
    main()

