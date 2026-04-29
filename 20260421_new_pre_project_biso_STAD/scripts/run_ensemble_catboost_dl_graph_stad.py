#!/usr/bin/env python3
"""
STAD Step 5 OOF 앙상블 (프로토콜 2026-04-28):

  슬롯(ML / DL / Graph)마다 ``*_oof/*.npy`` 전역 ``y_train`` 대비 finite Spearman으로 후보를 비교한다.
  **권장 운영:** (1) 후보 전수 표를 파일로 남기고 검토 → (2) 확정 선택 JSON으로 앙상블.
  **빠른 실행:** 선택 JSON 없이 실행하면 자동으로 슬롯별 Spearman 최대 OOF를 쓴다 (기존과 동일).

  블렌드: Simple 평균 / GroupCV JSON ``val_spearman_mean`` 가중 / 0~1 그리드 3가중 최적화.

입력 OOF:
  results/<result_tag>/ml|dl|graph/<stem>_<eval_mode>_oof/<Model>.npy

출력:
  results/<result_tag>/ensemble_step5_oof_candidate_table_<eval_mode>.json|.csv
  results/<result_tag>/ensemble_catboost_dl_graph_<eval_mode>.json

플래그:
  --candidates-only          후보 표 + 선택 템플릿만 쓰고 종료 (앙상블 JSON 없음).
  --selection-json PATH      phase별 ml/dl/graph 모델 stem (또는 AUTO)로 OOF 고정 후 블렌드.
  --require-confirmed-selection  --selection-json 없으면 후보만 기록하고 exit 2 (CI 게이트용).
  --preview-only             stderr 요약만, 어떤 결과 파일도 쓰지 않음.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import spearmanr

AUTO_TOKEN = "AUTO"


PHASES: tuple[tuple[str, str, str, str], ...] = (
    ("2A", "stad_numeric_ml_v1", "stad_numeric_dl_v1", "stad_numeric_graph_v1"),
    ("2B", "stad_numeric_smiles_ml_v1", "stad_numeric_smiles_dl_v1", "stad_numeric_smiles_graph_v1"),
    (
        "2C",
        "stad_numeric_context_smiles_ml_v1",
        "stad_numeric_context_smiles_dl_v1",
        "stad_numeric_context_smiles_graph_v1",
    ),
)


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def val_spearman_from_groupcv(jpath: Path, model: str) -> float | None:
    data = load_json(jpath)
    if not data or model not in data:
        return None
    summ = data[model].get("summary") or {}
    v = summ.get("val_spearman_mean")
    return float(v) if v is not None else None


def finite_spearman(y: np.ndarray, pred: np.ndarray) -> float:
    m = np.isfinite(y) & np.isfinite(pred)
    if int(m.sum()) < 3:
        return float("nan")
    r, _ = spearmanr(y[m], pred[m])
    return float(r)


def pick_best_oof_in_dir(oof_dir: Path, y: np.ndarray) -> tuple[str, np.ndarray, float] | None:
    if not oof_dir.is_dir():
        return None
    best_name: str | None = None
    best_oof: np.ndarray | None = None
    best_score = float("-inf")
    for p in sorted(oof_dir.glob("*.npy")):
        oof = np.load(p).astype(np.float32)
        s = finite_spearman(y, oof)
        if np.isfinite(s) and s > best_score:
            best_score = s
            best_name = p.stem
            best_oof = oof
    if best_name is None or best_oof is None:
        return None
    return best_name, best_oof, best_score


def load_named_oof_file(oof_dir: Path, stem: str, y: np.ndarray) -> tuple[str, np.ndarray, float] | None:
    p = oof_dir / f"{stem}.npy"
    if not p.is_file():
        return None
    oof = np.load(p).astype(np.float32)
    s = finite_spearman(y, oof)
    return stem, oof, float(s)


def resolve_oof_pick(oof_dir: Path, spec: str, y: np.ndarray) -> tuple[str, np.ndarray, float] | None:
    if spec.strip().upper() == AUTO_TOKEN:
        return pick_best_oof_in_dir(oof_dir, y)
    return load_named_oof_file(oof_dir, spec.strip(), y)


def rank_oofs_in_dir(oof_dir: Path, y: np.ndarray) -> list[tuple[str, float]]:
    """All ``*.npy`` in directory with finite Spearman vs ``y``, descending by score."""
    if not oof_dir.is_dir():
        return []
    rows: list[tuple[str, float]] = []
    for p in sorted(oof_dir.glob("*.npy")):
        oof = np.load(p).astype(np.float32)
        s = finite_spearman(y, oof)
        if np.isfinite(s):
            rows.append((p.stem, float(s)))
    rows.sort(key=lambda x: -x[1])
    return rows


def _fmt_rank_lines(title: str, ranked: list[tuple[str, float]]) -> list[str]:
    lines = [title]
    if not ranked:
        lines.append("  (no finite OOF scores — missing dir or empty)")
        return lines
    for name, sc in ranked:
        lines.append(f"  {name:40s}  OOF Spearman vs y = {sc:+.6f}")
    lines.append(f"  → selected: {ranked[0][0]}  (ρ={ranked[0][1]:+.6f})")
    return lines


def print_ensemble_selection_preview(
    *,
    result_tag: str,
    run_id: str,
    eval_mode: str,
    y_n: int,
    phase_blocks: list[dict[str, Any]],
) -> None:
    sep = "=" * 88
    print(sep, file=sys.stderr)
    print(
        f"Ensemble selection preview  result_tag={result_tag}  run_id={run_id}  eval_mode={eval_mode}  y_n={y_n}",
        file=sys.stderr,
    )
    print(sep, file=sys.stderr)
    for block in phase_blocks:
        ph = block.get("phase", "?")
        if not block.get("ok"):
            print(f"\nPhase {ph}: NOT OK — {block.get('reason', '')}", file=sys.stderr)
            pc = block.get("paths_checked") or {}
            for k, v in pc.items():
                print(f"  {k}: {v}", file=sys.stderr)
            continue
        print(f"\n--- Phase {ph} ---", file=sys.stderr)
        prev = block.get("oof_candidate_rankings") or {}
        for slot in ("ml", "dl", "graph"):
            raw_pairs = prev.get(slot) or []
            ranked = [(str(a[0]), float(a[1])) for a in raw_pairs if isinstance(a, (list, tuple)) and len(a) >= 2]
            for line in _fmt_rank_lines(f"  [{slot.upper()}]", ranked):
                print(line, file=sys.stderr)
        m = block["models"]
        ens = block["ensemble"]
        ogw = ens.get("optimal_grid_weights") or [0.0, 0.0, 0.0]
        print(
            f"  Blended (GridOpt): ρ={ens.get('optimal_grid_spearman'):+.6f}  "
            f"w=({float(ogw[0]):.3f}, {float(ogw[1]):.3f}, {float(ogw[2]):.3f})",
            file=sys.stderr,
        )
        print(
            f"  Triplet: ML={m['ml']}  DL={m['dl']}  Graph={m['graph']}",
            file=sys.stderr,
        )
    print(sep + "\n", file=sys.stderr)


def mean_pairwise_oof_prediction_spearman(oofs: list[np.ndarray]) -> float:
    """Pairwise Spearman ρ between *OOF prediction vectors* (not error diversity).

    Lung `phase3_ensemble_analysis.calculate_diversity` 이름은 'diversity'지만,
    값이 **클수록** 세 모델의 랭킹/예측이 **서로 더 닮음** (보완적 다양성은 오히려 작음).
    직관적 '다양성' 지표로 쓰려면 `1 - rho` 형태의 complementarity를 함께 보면 됨.
    """
    if len(oofs) < 2:
        return 0.0
    cors: list[float] = []
    for i, j in combinations(range(len(oofs)), 2):
        m = np.isfinite(oofs[i]) & np.isfinite(oofs[j])
        if int(m.sum()) < 3:
            continue
        c, _ = spearmanr(oofs[i][m], oofs[j][m])
        cors.append(float(c))
    return float(np.mean(cors)) if cors else float("nan")


def consensus_mean(oofs: list[np.ndarray]) -> float:
    stacked = np.stack(oofs, axis=0)
    return float(np.mean(np.std(stacked, axis=0)))


def weighted_stack(oofs: list[np.ndarray], weights: np.ndarray) -> np.ndarray:
    w = weights.astype(np.float64)
    w = np.clip(w, 1e-8, None)
    w = w / w.sum()
    out = np.zeros_like(oofs[0], dtype=np.float64)
    for i, o in enumerate(oofs):
        out += w[i] * o.astype(np.float64)
    return out.astype(np.float32)


def find_best_weights_3(oofs: list[np.ndarray], y: np.ndarray, n_steps: int = 11) -> tuple[list[float], float]:
    """Colon `run_ensemble.py` 와 동일한 3-model grid (w1,w2,w3)."""
    if len(oofs) != 3:
        raise ValueError("Expected 3 OOF vectors")
    best_score = float("-inf")
    best_w: list[float] | None = None
    grid = np.linspace(0.0, 1.0, n_steps)
    for w1 in grid:
        for w2 in grid:
            w3 = 1.0 - w1 - w2
            if w3 < -1e-12:
                continue
            pred = (w1 * oofs[0] + w2 * oofs[1] + w3 * oofs[2]).astype(np.float32)
            s = finite_spearman(y, pred)
            if np.isfinite(s) and s > best_score:
                best_score = s
                best_w = [float(w1), float(w2), float(max(w3, 0.0))]
    if best_w is None:
        return [1 / 3, 1 / 3, 1 / 3], float("nan")
    return best_w, best_score


def flat_rows_for_slot(
    phase_label: str,
    modality: str,
    lane: str,
    oof_dir: Path,
    stem: str,
    eval_mode: str,
    results_root: Path,
    y: np.ndarray,
) -> list[dict[str, Any]]:
    jpath = results_root / lane / f"{stem}_{eval_mode}.json"
    rows: list[dict[str, Any]] = []
    for name, oof_sp in rank_oofs_in_dir(oof_dir, y):
        vs = val_spearman_from_groupcv(jpath, name) if eval_mode == "groupcv" else None
        rows.append(
            {
                "phase": phase_label,
                "modality": modality,
                "lane": lane,
                "model_stem": name,
                "oof_spearman_vs_y_train": oof_sp,
                "groupcv_json_val_spearman_mean": vs,
                "oof_npy_path": str(oof_dir / f"{name}.npy"),
            }
        )
    return rows


def load_selection_map(path: Path) -> dict[str, dict[str, str]]:
    data = load_json(path)
    if not data:
        raise ValueError(f"Empty or invalid selection JSON: {path}")
    phases = data.get("phases")
    if not isinstance(phases, dict):
        raise ValueError(f"Selection JSON must contain object 'phases': {path}")
    out: dict[str, dict[str, str]] = {}
    for ph, slots in phases.items():
        if not isinstance(slots, dict):
            continue
        out[str(ph)] = {str(k).lower(): str(v) for k, v in slots.items() if k in ("ml", "dl", "graph")}
    return out


def write_candidate_table_files(
    *,
    results_root: Path,
    eval_mode: str,
    flat_rows: list[dict[str, Any]],
    suggested_phases: dict[str, dict[str, str]],
    protocol_note: str,
) -> tuple[Path, Path, Path]:
    results_root.mkdir(parents=True, exist_ok=True)
    jpath = results_root / f"ensemble_step5_oof_candidate_table_{eval_mode}.json"
    cpath = results_root / f"ensemble_step5_oof_candidate_table_{eval_mode}.csv"
    tpath = results_root / f"ensemble_step5_selection_{eval_mode}.template.json"
    payload = {
        "experiment": "Step5 pre-ensemble: all OOF candidates vs y_train (+ optional GroupCV JSON column)",
        "eval_mode": eval_mode,
        "rows": flat_rows,
        "suggested_auto_pick_per_phase": suggested_phases,
        "protocol_note": protocol_note,
    }
    jpath.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if flat_rows:
        with cpath.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(flat_rows[0].keys()))
            w.writeheader()
            w.writerows(flat_rows)
    else:
        cpath.write_text("", encoding="utf-8")
    template = {
        "_comment": "Operator: copy to ensemble_step5_selection_<eval>.json, adjust stems or use AUTO, then rerun with --selection-json.",
        "phases": {k: {**v} for k, v in suggested_phases.items()},
    }
    tpath.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return jpath, cpath, tpath


def build_phase_picks(
    *,
    phase_label: str,
    ml_stem: str,
    dl_stem: str,
    gr_stem: str,
    eval_mode: str,
    results_root: Path,
    y: np.ndarray,
    selection_for_phase: dict[str, str] | None,
) -> dict[str, Any]:
    ml_oof_dir = results_root / "ml" / f"{ml_stem}_{eval_mode}_oof"
    dl_oof_dir = results_root / "dl" / f"{dl_stem}_{eval_mode}_oof"
    gr_oof_dir = results_root / "graph" / f"{gr_stem}_{eval_mode}_oof"

    ml_rank = rank_oofs_in_dir(ml_oof_dir, y)
    dl_rank = rank_oofs_in_dir(dl_oof_dir, y)
    gr_rank = rank_oofs_in_dir(gr_oof_dir, y)
    rankings_json = {
        "ml": [[n, s] for n, s in ml_rank],
        "dl": [[n, s] for n, s in dl_rank],
        "graph": [[n, s] for n, s in gr_rank],
    }

    auto_ml = pick_best_oof_in_dir(ml_oof_dir, y)
    auto_dl = pick_best_oof_in_dir(dl_oof_dir, y)
    auto_gr = pick_best_oof_in_dir(gr_oof_dir, y)

    if auto_ml is None or auto_dl is None or auto_gr is None:
        return {
            "phase": phase_label,
            "ok": False,
            "reason": "missing_ml_or_dl_or_graph_oof",
            "paths_checked": {
                "ml_oof_dir": str(ml_oof_dir),
                "dl_oof_dir": str(dl_oof_dir),
                "gr_oof_dir": str(gr_oof_dir),
            },
            "oof_candidate_rankings": rankings_json,
        }

    def spec(slot: str) -> str:
        if not selection_for_phase:
            return AUTO_TOKEN
        return selection_for_phase.get(slot, AUTO_TOKEN)

    ml_pick = resolve_oof_pick(ml_oof_dir, spec("ml"), y)
    dl_pick = resolve_oof_pick(dl_oof_dir, spec("dl"), y)
    gr_pick = resolve_oof_pick(gr_oof_dir, spec("graph"), y)

    if ml_pick is None or dl_pick is None or gr_pick is None:
        return {
            "phase": phase_label,
            "ok": False,
            "reason": "selection_resolve_failed",
            "paths_checked": {
                "ml_oof_dir": str(ml_oof_dir),
                "dl_oof_dir": str(dl_oof_dir),
                "gr_oof_dir": str(gr_oof_dir),
            },
            "oof_candidate_rankings": rankings_json,
            "selection_specs_attempted": {
                "ml": spec("ml"),
                "dl": spec("dl"),
                "graph": spec("graph"),
            },
        }

    ml_name, ml_oof, _ = ml_pick
    dl_name, dl_oof, _ = dl_pick
    gr_name, gr_oof, _ = gr_pick

    ml_json = results_root / "ml" / f"{ml_stem}_{eval_mode}.json"
    dl_json = results_root / "dl" / f"{dl_stem}_{eval_mode}.json"
    gr_json = results_root / "graph" / f"{gr_stem}_{eval_mode}.json"

    s_ml_json = val_spearman_from_groupcv(ml_json, ml_name) if eval_mode == "groupcv" else None
    s_dl_json = val_spearman_from_groupcv(dl_json, dl_name) if eval_mode == "groupcv" else None
    s_gr_json = val_spearman_from_groupcv(gr_json, gr_name) if eval_mode == "groupcv" else None

    oofs = [ml_oof, dl_oof, gr_oof]
    singles_oof = [
        finite_spearman(y, ml_oof),
        finite_spearman(y, dl_oof),
        finite_spearman(y, gr_oof),
    ]
    best_single = float(np.nanmax(singles_oof))

    simple_pred = np.mean(np.stack(oofs, axis=0), axis=0).astype(np.float32)
    simple_s = finite_spearman(y, simple_pred)

    json_scores = [s_ml_json, s_dl_json, s_gr_json]
    if all(v is not None and v > 0 for v in json_scores):
        w_json = np.array(json_scores, dtype=np.float64)
        weighted_pred = weighted_stack(oofs, w_json)
        weighted_s = finite_spearman(y, weighted_pred)
        w_json_list = (w_json / w_json.sum()).tolist()
    else:
        weighted_pred = simple_pred
        weighted_s = simple_s
        w_json_list = None

    opt_w, opt_s = find_best_weights_3(oofs, y)

    rho_pair = mean_pairwise_oof_prediction_spearman(oofs)
    complementarity = float(1.0 - rho_pair) if np.isfinite(rho_pair) else float("nan")
    cons = consensus_mean(oofs)

    return {
        "phase": phase_label,
        "ok": True,
        "oof_candidate_rankings": rankings_json,
        "models": {
            "ml": ml_name,
            "dl": dl_name,
            "graph": gr_name,
            "catboost_ml": ml_name,
        },
        "oof_spearman_vs_y": {
            "ml": singles_oof[0],
            "dl": singles_oof[1],
            "graph": singles_oof[2],
            "catboost": singles_oof[0],
            "best_single": best_single,
        },
        "groupcv_json_val_spearman_mean": {
            "ml": s_ml_json,
            "dl": s_dl_json,
            "graph": s_gr_json,
            "catboost": s_ml_json,
        },
        "ensemble": {
            "simple_spearman": simple_s,
            "weighted_json_spearman": weighted_s,
            "weighted_json_weights": w_json_list,
            "optimal_grid_weights": opt_w,
            "optimal_grid_spearman": opt_s,
        },
        "lung_style_aux": {
            "diversity_mean_pairwise_spearman": rho_pair,
            "mean_pairwise_oof_prediction_spearman": rho_pair,
            "complementarity_1_minus_pairwise_pred_rho": complementarity,
            "consensus_mean_std_across_models": cons,
            "gain_simple_vs_best_single": simple_s - best_single,
            "gain_weighted_vs_best_single": weighted_s - best_single,
            "gain_optimal_vs_best_single": opt_s - best_single,
        },
        "oof_dirs": {
            "ml": str(ml_oof_dir),
            "dl": str(dl_oof_dir),
            "graph": str(gr_oof_dir),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="STAD ML+DL+Graph ensemble: OOF table + optional confirmed selection")
    parser.add_argument("--run-id", default="step4_stad_inputs_20260422_002")
    parser.add_argument("--result-tag", default="20260422_stad_step4_v2")
    parser.add_argument("--eval-mode", default="groupcv", help="OOF suffix, e.g. groupcv")
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Print OOF candidate rankings to stderr, then exit without writing any files.",
    )
    parser.add_argument(
        "--candidates-only",
        action="store_true",
        help="Write ensemble_step5_oof_candidate_table_* and selection template only; no blend JSON.",
    )
    parser.add_argument(
        "--selection-json",
        type=str,
        default=None,
        help="JSON with {\"phases\": {\"2A\": {\"ml\": \"...\", \"dl\": \"AUTO\", \"graph\": \"...\"}, ...}}. "
        "Missing phase falls back to all-AUTO for that phase.",
    )
    parser.add_argument(
        "--require-confirmed-selection",
        action="store_true",
        help="If set, refuse to write blend JSON unless --selection-json is provided (after candidate table is written).",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parents[1]
    data_dir = base / "data" / args.run_id
    y_path = data_dir / "y_train.npy"
    if not y_path.exists():
        raise FileNotFoundError(f"Missing {y_path}")

    y = np.load(y_path).astype(np.float64)
    results_root = base / "results" / args.result_tag
    out_path = results_root / f"ensemble_catboost_dl_graph_{args.eval_mode}.json"

    flat_rows: list[dict[str, Any]] = []
    suggested_phases: dict[str, dict[str, str]] = {}

    for phase_label, ml_stem, dl_stem, gr_stem in PHASES:
        ml_oof_dir = results_root / "ml" / f"{ml_stem}_{args.eval_mode}_oof"
        dl_oof_dir = results_root / "dl" / f"{dl_stem}_{args.eval_mode}_oof"
        gr_oof_dir = results_root / "graph" / f"{gr_stem}_{args.eval_mode}_oof"
        flat_rows.extend(
            flat_rows_for_slot(phase_label, "tabular_ml", "ml", ml_oof_dir, ml_stem, args.eval_mode, results_root, y)
        )
        flat_rows.extend(
            flat_rows_for_slot(phase_label, "dl", "dl", dl_oof_dir, dl_stem, args.eval_mode, results_root, y)
        )
        flat_rows.extend(
            flat_rows_for_slot(phase_label, "graph", "graph", gr_oof_dir, gr_stem, args.eval_mode, results_root, y)
        )
        am = pick_best_oof_in_dir(ml_oof_dir, y)
        ad = pick_best_oof_in_dir(dl_oof_dir, y)
        ag = pick_best_oof_in_dir(gr_oof_dir, y)
        if am and ad and ag:
            suggested_phases[phase_label] = {"ml": am[0], "dl": ad[0], "graph": ag[0]}

    selection_map: dict[str, dict[str, str]] | None = None
    if args.selection_json:
        selection_map = load_selection_map(Path(args.selection_json).expanduser().resolve())

    protocol_note = (
        "Review rows (and stderr preview). To lock picks: copy ensemble_step5_selection_<eval>.template.json "
        "to a confirmed file, edit stems or AUTO, then run with --selection-json <path>. "
        f"Token {AUTO_TOKEN!r} keeps per-slot Spearman-best auto pick."
    )

    if not args.preview_only:
        jj, cc, tt = write_candidate_table_files(
            results_root=results_root,
            eval_mode=args.eval_mode,
            flat_rows=flat_rows,
            suggested_phases=suggested_phases,
            protocol_note=protocol_note,
        )
        print(f"Wrote candidate table JSON: {jj}", file=sys.stderr)
        print(f"Wrote candidate table CSV:  {cc}", file=sys.stderr)
        print(f"Wrote selection template:   {tt}", file=sys.stderr)

    phase_results: list[dict[str, Any]] = []
    for phase_label, ml_stem, dl_stem, gr_stem in PHASES:
        sel_phase = selection_map.get(phase_label) if selection_map else None
        phase_results.append(
            build_phase_picks(
                phase_label=phase_label,
                ml_stem=ml_stem,
                dl_stem=dl_stem,
                gr_stem=gr_stem,
                eval_mode=args.eval_mode,
                results_root=results_root,
                y=y,
                selection_for_phase=sel_phase,
            )
        )

    print_ensemble_selection_preview(
        result_tag=args.result_tag,
        run_id=args.run_id,
        eval_mode=args.eval_mode,
        y_n=int(len(y)),
        phase_blocks=phase_results,
    )

    if args.preview_only:
        print("[ensemble] --preview-only: no files written.", file=sys.stderr)
        return

    if args.candidates_only:
        print("[ensemble] --candidates-only: candidate table + template written; blend JSON skipped.", file=sys.stderr)
        return

    if args.require_confirmed_selection and not args.selection_json:
        print(
            "[ensemble] --require-confirmed-selection: provide --selection-json after operator sign-off. Exiting 2.",
            file=sys.stderr,
        )
        sys.exit(2)

    selection_origin = "selection_json" if args.selection_json else "auto_spearman_best_per_slot"
    payload = {
        "experiment": "STAD Step5: per-modality OOF (confirmed or auto) + Lung-style 3-way blend",
        "selection_origin": selection_origin,
        "selection_json_path": str(Path(args.selection_json).resolve()) if args.selection_json else None,
        "selection_policy": "Per slot: explicit stem from --selection-json, or AUTO / default auto = "
        "max finite Spearman vs y_train within that slot's *_oof directory.",
        "run_id": args.run_id,
        "result_tag": args.result_tag,
        "eval_mode": args.eval_mode,
        "y_n": int(len(y)),
        "candidate_table_json": f"ensemble_step5_oof_candidate_table_{args.eval_mode}.json",
        "candidate_table_csv": f"ensemble_step5_oof_candidate_table_{args.eval_mode}.csv",
        "phases": phase_results,
        "metric_notes": {
            "diversity_field": "Lung `diversity` = mean pairwise Spearman ρ of OOF *predictions* across ensemble members. "
            "Higher ρ ⇒ predictions/ranks are more aligned (less complementary diversity). "
            "See complementarity_1_minus_pairwise_pred_rho for an intuitive 'higher is more distinct' view.",
            "legacy_json_keys": "models.catboost_ml / oof_spearman_vs_y.catboost / groupcv_json_val_spearman_mean.catboost "
            "duplicate the ML slot for older consumers (e.g. step6_prepare_top30_stad.py).",
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
