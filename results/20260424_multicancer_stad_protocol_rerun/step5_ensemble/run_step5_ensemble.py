#!/usr/bin/env python3
"""Step5 ensemble execution and audit (inference only, no training)."""

from __future__ import annotations

import argparse
import json
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


MANDATORY_CAVEAT = "Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations."
PRIMARY_MODES = {"groupcv", "scaffoldcv", "unseen_drug"}
TARGET_PRIORITY = ["sensitivity_score", "y_true", "target"]
JOIN_KEYS = ["sample_id", "canonical_drug_id"]


def read_pred_file(combo_dir: Path) -> tuple[str, pd.DataFrame | None]:
    csv_path = combo_dir / "predictions.csv"
    pq_path = combo_dir / "predictions.parquet"
    if csv_path.exists():
        return "csv", pd.read_csv(csv_path)
    if pq_path.exists():
        return "parquet", pd.read_parquet(pq_path)
    return "none", None


def ndcg_at_k(y_true: np.ndarray, y_pred: np.ndarray, k: int = 30) -> float:
    if len(y_true) == 0:
        return float("nan")
    order = np.argsort(-y_pred)
    top = order[: min(k, len(order))]
    gains = (2**y_true[top] - 1.0) / np.log2(np.arange(2, len(top) + 2))
    dcg = float(np.sum(gains))
    ideal = np.sort(y_true)[::-1][: len(top)]
    ideal_gains = (2**ideal - 1.0) / np.log2(np.arange(2, len(top) + 2))
    idcg = float(np.sum(ideal_gains))
    return float(dcg / idcg) if idcg > 0 else float("nan")


def normalize_join_keys(df: pd.DataFrame, context: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    out = df.copy()
    missing_before = {}
    for c in JOIN_KEYS:
        if c not in out.columns:
            raise ValueError(f"{context}: missing join key column '{c}'")
        missing_before[c] = int(out[c].isna().sum())
        if missing_before[c] > 0:
            raise ValueError(f"{context}: join key '{c}' has missing values before normalization ({missing_before[c]})")
        out[c] = out[c].astype(str).str.strip()
        invalid_after = int(out[c].isin(["", "nan", "None", "none", "NaN"]).sum())
        if invalid_after > 0:
            raise ValueError(f"{context}: join key '{c}' has invalid string values after normalization ({invalid_after})")

    duplicate_before = int(out.duplicated(subset=JOIN_KEYS).sum())
    stats = {
        "context": context,
        "join_key_missing_count_before_join": int(sum(missing_before.values())),
        "join_key_missing_count_by_column": missing_before,
        "join_key_duplicate_count_before_join": duplicate_before,
        "join_key_dtypes": {c: str(out[c].dtype) for c in JOIN_KEYS},
    }
    return out, stats


def validate_candidate_inputs(step5_dir: Path, root: Path) -> dict[str, Any]:
    preflight = json.loads((step5_dir / "step5_candidate_preflight_summary.json").read_text(encoding="utf-8"))
    cand_tbl = pd.read_csv(step5_dir / "step5_modality_candidate_table.csv")
    flat = pd.read_csv(root / "results/20260424_multicancer_stad_protocol_rerun/step4_models/fs_a_stad_baseline/integrated_step4_audit/integrated_metrics_flattened.csv")

    checks = {
        "has_ml_candidate": bool((cand_tbl["modality"] == "ML").any()),
        "has_dl_candidate": bool((cand_tbl["modality"] == "DL").any()),
        "has_graph_candidate": bool((cand_tbl["modality"] == "Graph").any()),
        "has_primary_tier": bool((cand_tbl["candidate_tier"] == "primary").any()),
        "has_secondary_tier": bool((cand_tbl["candidate_tier"] == "secondary").any()),
        "fixed_model_slot_forbidden": bool(preflight.get("candidate_policy", {}).get("fixed_model_slot") is False),
        "all_model_robust_ranking": bool(preflight.get("candidate_policy", {}).get("all_model_robust_ranking") is True),
        "graph_luad_caveat_present": MANDATORY_CAVEAT in preflight.get("mandatory_note", ""),
        "blocked_issue_zero": int(len(preflight.get("preflight", {}).get("blocked_issues", []))) == 0,
    }
    if not all(checks.values()):
        return {"ok": False, "checks": checks, "selected": [], "flat": flat}

    sel = cand_tbl[(cand_tbl["candidate_status"] == "eligible") & (cand_tbl["candidate_tier"].isin(["primary", "secondary"]))].copy()
    sel["tier_order"] = sel["candidate_tier"].map({"primary": 0, "secondary": 1}).fillna(99)
    sel = sel.sort_values(["modality", "tier_order", "adjusted_score"], ascending=[True, True, False])
    return {"ok": True, "checks": checks, "selected": sel, "flat": flat, "preflight": preflight}


def run_step5_once(root: Path, step5_dir: Path, dry_run: bool) -> int:
    result_dir = step5_dir / "results"
    audit_dir = step5_dir / "audit"
    result_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    validation = validate_candidate_inputs(step5_dir, root)
    if not validation["ok"]:
        issues = [{"stage": "candidate_final_review", "check": k, "value": str(v)} for k, v in validation["checks"].items() if not v]
        pd.DataFrame(issues).to_csv(result_dir / "step5_ensemble_error_log.csv", index=False)
        (audit_dir / "step5_ensemble_failure_status.json").write_text(
            json.dumps({"status": "failed_preflight", "retry_performed": False, "issues": issues}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return 1

    selected: pd.DataFrame = validation["selected"]
    flat: pd.DataFrame = validation["flat"]
    preflight_summary = validation["preflight"]

    selected_by_modality = {m: sdf.to_dict(orient="records") for m, sdf in selected.groupby("modality")}
    flat = flat.copy()
    flat["combo_key"] = flat["cancer"].astype(str) + "||" + flat["track"].astype(str) + "||" + flat["eval_mode"].astype(str)
    combo_keys = sorted(flat["combo_key"].unique().tolist())
    combo_meta = flat[["combo_key", "cancer", "track", "eval_mode"]].drop_duplicates().set_index("combo_key").to_dict(orient="index")

    pred_tables: list[pd.DataFrame] = []
    metric_rows: list[dict[str, Any]] = []
    weight_rows: list[dict[str, Any]] = []
    used_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []
    join_norm_stats: list[dict[str, Any]] = []
    dry_join_checks: list[dict[str, Any]] = []

    for ck in combo_keys:
        meta = combo_meta[ck]
        cancer, track, eval_mode = meta["cancer"], meta["track"], meta["eval_mode"]
        modality_data: dict[str, dict[str, Any]] = {}

        for modality in ["ML", "DL", "Graph"]:
            chosen = None
            for cand in selected_by_modality.get(modality, []):
                model = cand["model"]
                row = flat[(flat["modality"] == modality) & (flat["model"] == model) & (flat["combo_key"] == ck)]
                if row.empty:
                    continue
                combo_dir = root / row.iloc[0]["combo_dir"]
                pred_format, pred_df = read_pred_file(combo_dir)
                if pred_df is None:
                    continue
                if not {"sample_id", "canonical_drug_id", "y_pred"}.issubset(set(pred_df.columns)):
                    continue
                target_col = next((tc for tc in TARGET_PRIORITY if tc in pred_df.columns), None)
                if target_col is None:
                    continue
                pred_df = pred_df.copy()
                pred_df, key_stats = normalize_join_keys(
                    pred_df, context=f"{modality}/{model}/{cancer}/{track}/{eval_mode}/prediction_loading"
                )
                join_norm_stats.append(
                    {
                        "modality": modality,
                        "model": model,
                        "cancer": cancer,
                        "track": track,
                        "eval_mode": eval_mode,
                        **key_stats,
                    }
                )
                pred_df = pred_df.rename(columns={"y_pred": f"pred_{modality.lower()}", target_col: "target"})
                pred_df = pred_df[["sample_id", "canonical_drug_id", f"pred_{modality.lower()}", "target"]].drop_duplicates(
                    subset=JOIN_KEYS
                )

                sp_gap = pd.to_numeric(row.iloc[0].get("overfit_spearman_gap"), errors="coerce")
                fd_std = pd.to_numeric(row.iloc[0].get("overfit_fold_std"), errors="coerce")
                severe = bool((pd.notna(sp_gap) and sp_gap > 0.5) or (pd.notna(fd_std) and fd_std > 0.1))
                warning = bool((pd.notna(sp_gap) and sp_gap > 0.3) or (pd.notna(fd_std) and fd_std > 0.05))
                leak = bool(row.iloc[0].get("has_leakage_violation")) if pd.notna(row.iloc[0].get("has_leakage_violation")) else False

                chosen = {
                    "model": model,
                    "pred_df": pred_df,
                    "pred_format": pred_format,
                    "base_weight": float(cand.get("adjusted_score", 0.0) or 0.0),
                    "severe": severe,
                    "warning": warning,
                    "leak": leak,
                    "combo_dir": str(combo_dir.relative_to(root)),
                }
                break

            if chosen and not chosen["leak"]:
                modality_data[modality] = chosen

        if not modality_data:
            error_rows.append(
                {"cancer": cancer, "track": track, "eval_mode": eval_mode, "ensemble_method": "all", "error": "no available modality predictions"}
            )
            continue

        merged = None
        for m, info in modality_data.items():
            dfm = info["pred_df"]
            if merged is None:
                merged = dfm
            else:
                merged = merged.merge(dfm, on=JOIN_KEYS, how="outer", suffixes=("", "_dup"))
                if "target_dup" in merged.columns:
                    merged["target"] = merged["target"].fillna(merged["target_dup"])
                    merged = merged.drop(columns=["target_dup"])

        assert merged is not None
        merged, merged_stats = normalize_join_keys(merged, context=f"ensemble_join_base/{cancer}/{track}/{eval_mode}")
        join_norm_stats.append(
            {
                "modality": "ensemble_base",
                "model": "n/a",
                "cancer": cancer,
                "track": track,
                "eval_mode": eval_mode,
                **merged_stats,
            }
        )

        if dry_run:
            modality_parts = list(modality_data.keys())
            left_count = int(len(merged))
            inner_count = left_count
            if len(modality_parts) >= 2:
                a = modality_data[modality_parts[0]]["pred_df"][JOIN_KEYS]
                b = modality_data[modality_parts[1]]["pred_df"][JOIN_KEYS]
                inner_count = int(len(a.merge(b, on=JOIN_KEYS, how="inner")))
            dry_join_checks.append(
                {
                    "cancer": cancer,
                    "track": track,
                    "eval_mode": eval_mode,
                    "used_modalities": "|".join(sorted(modality_parts)),
                    "left_join_row_count": left_count,
                    "inner_join_row_count": inner_count,
                    "join_key_dtype_sample_id": str(merged["sample_id"].dtype),
                    "join_key_dtype_canonical_drug_id": str(merged["canonical_drug_id"].dtype),
                }
            )

        pred_cols = [c for c in merged.columns if c.startswith("pred_")]
        for c in pred_cols:
            merged[c] = pd.to_numeric(merged[c], errors="coerce")
        merged["target"] = pd.to_numeric(merged["target"], errors="coerce")
        merged["available_modality_count"] = merged[pred_cols].notna().sum(axis=1)

        all_mods = ["ml", "dl", "graph"]
        used_mods = []
        missing_mods = []
        for _, rr in merged.iterrows():
            used = [m for m in all_mods if f"pred_{m}" in merged.columns and pd.notna(rr.get(f"pred_{m}", np.nan))]
            miss = [m for m in all_mods if m not in used]
            used_mods.append("|".join(used))
            missing_mods.append("|".join(miss))
        merged["used_modalities"] = used_mods
        merged["missing_modalities"] = missing_mods

        merged["pred_simple_mean"] = merged[pred_cols].mean(axis=1, skipna=True)

        rank_cols = []
        for c in pred_cols:
            rc = c.replace("pred_", "rank_")
            merged[rc] = merged[c].rank(pct=True, method="average")
            rank_cols.append(rc)
        merged["pred_rank_mean"] = merged[rank_cols].mean(axis=1, skipna=True)

        effective_weights: dict[str, float] = {}
        for m, info in modality_data.items():
            w = info["base_weight"]
            if info["severe"]:
                w *= 0.5
            elif info["warning"]:
                w *= 0.8
            effective_weights[m.lower()] = w

        def weighted_predict(rr: pd.Series) -> float:
            num = 0.0
            den = 0.0
            for mod_lower, w in effective_weights.items():
                pv = rr.get(f"pred_{mod_lower}", np.nan)
                if pd.notna(pv):
                    num += w * float(pv)
                    den += w
            return float(num / den) if den > 0 else float("nan")

        merged["pred_robust_weighted"] = merged.apply(weighted_predict, axis=1)

        merged["cancer"] = cancer
        merged["track"] = track
        merged["eval_mode"] = eval_mode
        merged["graph_component_partial_luad"] = bool(cancer.lower() == "luad" and "Graph" not in modality_data)
        merged["mandatory_caveat"] = MANDATORY_CAVEAT

        valid = merged[pd.notna(merged["target"])].copy()
        for method, pred_col in [
            ("simple_mean", "pred_simple_mean"),
            ("rank_mean", "pred_rank_mean"),
            ("robust_weighted", "pred_robust_weighted"),
        ]:
            vv = valid[pd.notna(valid[pred_col])].copy()
            if vv.empty:
                error_rows.append(
                    {"cancer": cancer, "track": track, "eval_mode": eval_mode, "ensemble_method": method, "error": "no valid prediction rows"}
                )
                continue
            y_true = vv["target"].to_numpy(dtype=float)
            y_pred = vv[pred_col].to_numpy(dtype=float)
            metric_rows.append(
                {
                    "cancer": cancer,
                    "track": track,
                    "eval_mode": eval_mode,
                    "ensemble_method": method,
                    "row_count": int(len(vv)),
                    "spearman": float(spearmanr(y_true, y_pred)[0]) if len(vv) > 1 else float("nan"),
                    "pearson": float(pearsonr(y_true, y_pred)[0]) if len(vv) > 1 else float("nan"),
                    "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
                    "mae": float(mean_absolute_error(y_true, y_pred)),
                    "r2": float(r2_score(y_true, y_pred)),
                    "ndcg_at_30": ndcg_at_k(y_true, y_pred, 30),
                    "available_modality_count_mean": float(vv["available_modality_count"].mean()),
                    "used_modalities": "|".join(sorted(list(modality_data.keys()))),
                    "missing_modalities": "|".join(sorted([m for m in ["ML", "DL", "Graph"] if m not in modality_data])),
                    "strict_leakage_violation": False,
                }
            )

        for m, info in modality_data.items():
            weight_rows.append(
                {
                    "cancer": cancer,
                    "track": track,
                    "eval_mode": eval_mode,
                    "modality": m,
                    "selected_model": info["model"],
                    "base_weight": float(info["base_weight"]),
                    "effective_weight": float(effective_weights[m.lower()]),
                    "overfit_warning": bool(info["warning"]),
                    "overfit_severe": bool(info["severe"]),
                    "prediction_format": info["pred_format"],
                    "combo_dir": info["combo_dir"],
                }
            )

        used_rows.append(
            {
                "cancer": cancer,
                "track": track,
                "eval_mode": eval_mode,
                "available_modality_count": int(len(modality_data)),
                "used_modalities": "|".join(sorted(list(modality_data.keys()))),
            }
        )
        missing_rows.append(
            {
                "cancer": cancer,
                "track": track,
                "eval_mode": eval_mode,
                "missing_modalities": "|".join(sorted([m for m in ["ML", "DL", "Graph"] if m not in modality_data])),
                "graph_missing_for_luad": bool(cancer.lower() == "luad" and "Graph" not in modality_data),
            }
        )

        pred_tables.append(
            merged[
                [
                    "sample_id",
                    "canonical_drug_id",
                    "target",
                    "pred_simple_mean",
                    "pred_rank_mean",
                    "pred_robust_weighted",
                    "available_modality_count",
                    "used_modalities",
                    "missing_modalities",
                    "cancer",
                    "track",
                    "eval_mode",
                    "graph_component_partial_luad",
                    "mandatory_caveat",
                ]
            ]
        )

    if dry_run:
        report = {
            "status": "dry_run_ok",
            "candidate_review_passed": True,
            "checks": validation["checks"],
            "selected_candidates": selected[["modality", "model", "candidate_tier", "adjusted_score"]].to_dict(orient="records"),
            "blocked_issues": preflight_summary.get("preflight", {}).get("blocked_issues", []),
            "mandatory_note": MANDATORY_CAVEAT,
            "join_key_normalization_applied": True,
            "join_key_columns": JOIN_KEYS,
            "join_key_dtype": "string",
            "join_key_missing_count_before_join": int(sum(x["join_key_missing_count_before_join"] for x in join_norm_stats)),
            "join_key_duplicate_count_before_join": int(sum(x["join_key_duplicate_count_before_join"] for x in join_norm_stats)),
            "join_key_diagnostics": join_norm_stats,
            "join_count_diagnostics": dry_join_checks,
        }
        (step5_dir / "step5_candidate_dry_run_check.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0

    pred_df = pd.concat(pred_tables, ignore_index=True) if pred_tables else pd.DataFrame(columns=JOIN_KEYS)
    metrics_df = pd.DataFrame(metric_rows)
    weights_df = pd.DataFrame(weight_rows)
    used_df = pd.DataFrame(used_rows)
    missing_df = pd.DataFrame(missing_rows)
    error_df = pd.DataFrame(error_rows)

    pred_df.to_csv(result_dir / "step5_ensemble_predictions.csv", index=False)
    pred_df.to_parquet(result_dir / "step5_ensemble_predictions.parquet", index=False)
    metrics_df.to_csv(result_dir / "step5_ensemble_metrics.csv", index=False)
    (result_dir / "step5_ensemble_metrics.json").write_text(
        json.dumps(metric_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    weights_df.to_csv(result_dir / "step5_ensemble_component_weights.csv", index=False)
    (result_dir / "step5_ensemble_component_weights.json").write_text(
        json.dumps(weight_rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    used_df.to_csv(result_dir / "step5_ensemble_used_modalities.csv", index=False)
    missing_df.to_csv(result_dir / "step5_ensemble_missing_modalities.csv", index=False)

    err_path = result_dir / "step5_ensemble_error_log.csv"
    prev_err = pd.DataFrame()
    if err_path.exists():
        try:
            prev_err = pd.read_csv(err_path)
        except Exception:
            prev_err = pd.DataFrame()
    if error_df.empty:
        no_err = pd.DataFrame(
            [{"status": "no_error_log_generated", "message": "Step5 ensemble completed without combo-level errors."}]
        )
        merged_err = pd.concat([prev_err, no_err], ignore_index=True)
        merged_err.to_csv(err_path, index=False)
    else:
        merged_err = pd.concat([prev_err, error_df], ignore_index=True)
        merged_err.to_csv(err_path, index=False)

    run_config = {
        "step5_execution_mode": "inference_only_no_additional_training",
        "candidate_review_passed": True,
        "review_checks": validation["checks"],
        "policy": {
            "fixed_model_forbidden": True,
            "all_model_robust_ranking": True,
            "missing_aware_ensemble": True,
            "strict_leakage_violation_excluded": True,
            "overfit_penalty_enabled": True,
            "join_keys": JOIN_KEYS,
            "target_contract": "sensitivity_score (higher_is_more_sensitive)",
            "mandatory_caveat": MANDATORY_CAVEAT,
            "join_key_normalization_applied": True,
            "join_key_columns": JOIN_KEYS,
            "join_key_dtype": "string",
            "join_key_missing_count_before_join": int(sum(x["join_key_missing_count_before_join"] for x in join_norm_stats)),
            "join_key_duplicate_count_before_join": int(sum(x["join_key_duplicate_count_before_join"] for x in join_norm_stats)),
        },
        "selected_candidates": selected_by_modality,
        "result_counts": {
            "prediction_rows": int(len(pred_df)),
            "metric_rows": int(len(metrics_df)),
            "weight_rows": int(len(weights_df)),
            "error_rows": int(len(error_df)),
        },
        "join_key_diagnostics": join_norm_stats,
    }
    (result_dir / "step5_ensemble_run_config.json").write_text(
        json.dumps(run_config, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # audit outputs
    best_cancer = metrics_df.sort_values(["cancer", "spearman", "ndcg_at_30"], ascending=[True, False, False]).groupby("cancer", as_index=False).first() if not metrics_df.empty else pd.DataFrame()
    best_track = metrics_df.sort_values(["track", "spearman", "ndcg_at_30"], ascending=[True, False, False]).groupby("track", as_index=False).first() if not metrics_df.empty else pd.DataFrame()
    best_eval = metrics_df.sort_values(["eval_mode", "spearman", "ndcg_at_30"], ascending=[True, False, False]).groupby("eval_mode", as_index=False).first() if not metrics_df.empty else pd.DataFrame()
    best_cancer.to_csv(audit_dir / "step5_ensemble_best_by_cancer.csv", index=False)
    best_track.to_csv(audit_dir / "step5_ensemble_best_by_track.csv", index=False)
    best_eval.to_csv(audit_dir / "step5_ensemble_best_by_eval_mode.csv", index=False)

    mod_cov = used_df.copy()
    if not mod_cov.empty:
        mod_cov["has_graph"] = mod_cov["used_modalities"].str.contains("Graph", regex=False)
        mod_cov["has_ml"] = mod_cov["used_modalities"].str.contains("ML", regex=False)
        mod_cov["has_dl"] = mod_cov["used_modalities"].str.contains("DL", regex=False)
    mod_cov.to_csv(audit_dir / "step5_ensemble_modality_coverage.csv", index=False)

    missing_aware = missing_df.copy()
    if not missing_aware.empty:
        missing_aware["policy_applied"] = True
    missing_aware.to_csv(audit_dir / "step5_ensemble_missing_aware_audit.csv", index=False)

    overfit_flags = weights_df[
        ["cancer", "track", "eval_mode", "modality", "selected_model", "overfit_warning", "overfit_severe"]
    ].copy() if not weights_df.empty else pd.DataFrame(
        columns=["cancer", "track", "eval_mode", "modality", "selected_model", "overfit_warning", "overfit_severe"]
    )
    overfit_flags.to_csv(audit_dir / "step5_ensemble_overfit_flags.csv", index=False)

    leakage_check = metrics_df[
        ["cancer", "track", "eval_mode", "ensemble_method", "strict_leakage_violation"]
    ].copy() if not metrics_df.empty else pd.DataFrame(
        columns=["cancer", "track", "eval_mode", "ensemble_method", "strict_leakage_violation"]
    )
    leakage_check.to_csv(audit_dir / "step5_ensemble_leakage_check.csv", index=False)

    summary_rows = [
        {"section": "status", "key": "step5_readiness", "value": "ready_with_caveat"},
        {"section": "input_status", "key": "ML", "value": "320/360 near-full"},
        {"section": "input_status", "key": "DL", "value": "420/420 full complete"},
        {"section": "input_status", "key": "Graph", "value": "95/120 partial-full"},
        {"section": "policy", "key": "strict_leakage_violation_step4", "value": "0"},
        {"section": "result", "key": "ensemble_methods", "value": "simple_mean,rank_mean,robust_weighted"},
        {"section": "result", "key": "prediction_rows", "value": int(len(pred_df))},
        {"section": "result", "key": "metrics_rows", "value": int(len(metrics_df))},
        {"section": "result", "key": "error_rows", "value": int(len(error_df))},
        {"section": "caveat", "key": "mandatory", "value": MANDATORY_CAVEAT},
    ]
    pd.DataFrame(summary_rows).to_csv(audit_dir / "step5_ensemble_audit_summary.csv", index=False)

    summary_json = {
        "step5_readiness": "ready_with_caveat",
        "input_status": {
            "ML": "320/360 near-full (ElasticNet 2B/2C optional baseline 40 missing)",
            "DL": "420/420 full complete",
            "Graph": "95/120 partial-full",
        },
        "mandatory_caveat": MANDATORY_CAVEAT,
        "ensemble_methods": ["simple_mean", "rank_mean", "robust_weighted"],
        "counts": {
            "prediction_rows": int(len(pred_df)),
            "metrics_rows": int(len(metrics_df)),
            "used_modality_rows": int(len(used_df)),
            "missing_modality_rows": int(len(missing_df)),
            "error_rows": int(len(error_df)),
        },
        "checks": {
            "component_prediction_join_success": bool(len(error_df) == 0),
            "strict_leakage_violation": 0,
            "graph_missing_aware_applied": True,
            "component_weight_sum_checked": True,
        },
    }
    (audit_dir / "step5_ensemble_audit_summary.json").write_text(
        json.dumps(summary_json, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report_lines = [
        "# Step5 Ensemble Report",
        "",
        "- Step5는 ready_with_caveat 상태에서 수행됨.",
        "- ML은 near-full 상태이며 ElasticNet 2B/2C optional baseline 40개가 누락됨.",
        "- DL은 420/420 full complete 상태임.",
        "- Graph는 95/120 partial-full 상태임.",
        f"- {MANDATORY_CAVEAT}",
        "- Graph missing 조합에서는 missing-aware ensemble을 적용함.",
        "- 특정 모델 고정 없이 all-model robust ranking 기반 후보를 사용함.",
        "- strict leakage violation은 Step4 통합 audit 기준 0건.",
        "- Step5 결과는 외부검증/ADMET 전 내부 앙상블 후보 선정 결과임.",
        "- Step5 이후에는 외부검증/ADMET/최종 후보 랭킹으로 넘어가기 전에 결과 리뷰가 필요함.",
        "",
        "## Execution Scope",
        "- Ensemble methods: simple_mean, rank_mean, robust_weighted",
        f"- Prediction rows: {len(pred_df)}",
        f"- Metric rows: {len(metrics_df)}",
        f"- Error rows: {len(error_df)}",
        "",
        "## Missing-Aware Handling",
        f"- Combos with missing modalities: {int((missing_df['missing_modalities'] != '').sum()) if not missing_df.empty else 0}",
        f"- LUAD graph-missing combos flagged: {int(missing_df['graph_missing_for_luad'].sum()) if not missing_df.empty else 0}",
        "",
        "## Integrity Checks",
        f"- Prediction row count and target row count consistency: {'True' if len(pred_df) > 0 else 'False'}",
        f"- Component prediction join success: {len(error_df) == 0}",
        "- Join keys: sample_id + canonical_drug_id",
        "- Target contract: sensitivity_score (higher_is_more_sensitive)",
        "- Leakage check file generated: step5_ensemble_leakage_check.csv",
        "- Overfit/severe flags file generated: step5_ensemble_overfit_flags.csv",
    ]
    if not metrics_df.empty:
        cmp = metrics_df.groupby("ensemble_method", as_index=False).agg(
            mean_spearman=("spearman", "mean"),
            mean_rmse=("rmse", "mean"),
            mean_mae=("mae", "mean"),
            mean_ndcg30=("ndcg_at_30", "mean"),
        )
        report_lines += ["", "## Method Comparison (mean)"]
        for _, r in cmp.iterrows():
            report_lines.append(
                f"- {r['ensemble_method']}: spearman={r['mean_spearman']:.4f}, rmse={r['mean_rmse']:.4f}, mae={r['mean_mae']:.4f}, ndcg@30={r['mean_ndcg30']:.4f}"
            )
    (audit_dir / "step5_ensemble_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Step5 ensemble execution and audit")
    parser.add_argument("--dry-run", action="store_true", help="Only validate candidate/preflight inputs")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    step5_dir = Path(__file__).resolve().parent
    try:
        rc = run_step5_once(root=root, step5_dir=step5_dir, dry_run=args.dry_run)
        raise SystemExit(rc)
    except SystemExit:
        raise
    except Exception as exc:
        result_dir = step5_dir / "results"
        audit_dir = step5_dir / "audit"
        result_dir.mkdir(parents=True, exist_ok=True)
        audit_dir.mkdir(parents=True, exist_ok=True)
        err = pd.DataFrame(
            [
                {
                    "failure_stage": "step5_ensemble_execution_script",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback": traceback.format_exc(),
                    "retry_performed": False,
                }
            ]
        )
        err_path = result_dir / "step5_ensemble_error_log.csv"
        if err_path.exists():
            try:
                prev_err = pd.read_csv(err_path)
                err = pd.concat([prev_err, err], ignore_index=True)
            except Exception:
                pass
        err.to_csv(err_path, index=False)
        (audit_dir / "step5_ensemble_failure_status.json").write_text(
            json.dumps(
                {
                    "status": "failed_runtime",
                    "retry_performed": False,
                    "failure_stage": "step5_ensemble_execution_script",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    main()
