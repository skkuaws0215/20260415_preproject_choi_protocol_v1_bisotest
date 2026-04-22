"""
Step 4 Modeling results parser.

Convert JSON files in results/ into a single pandas DataFrame.

Filename pattern:
  colon_<phase_key>_<category>_v1_<split>.json

  phase_key: numeric | numeric_smiles | numeric_context_smiles
  category : ml | dl | graph
  split    : groupcv | scaffoldcv | 5foldcv | holdout

Each JSON file contains multiple model blocks:
  {
    "LightGBM":      { "model": ..., "fold_results": [...] },
    "LightGBM_DART": { "model": ..., "fold_results": [...] },
    ...
  }
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

_UTILS_PATH = Path(__file__).resolve().parent.parent / "utils"
if str(_UTILS_PATH.parent.parent) not in sys.path:
    sys.path.insert(0, str(_UTILS_PATH.parent.parent))

from dashboard.utils.constants import (  # noqa: E402
    CATEGORY_MAP,
    OVERFITTING_THRESHOLD,
    PHASE_MAP,
    RESULTS_DIR,
    SPLIT_MAP,
    STABILITY_THRESHOLD,
    get_model_category,
)

# Pattern: colon_{phase}_{category}_v1_{split}.json
# phase can include underscores (numeric_smiles, numeric_context_smiles)
FILENAME_RE = re.compile(
    r"^colon_(?P<phase>.+?)_(?P<category>ml|dl|graph)_v1_(?P<split>\w+)\.json$"
)


def parse_filename(filename: str) -> Optional[Dict[str, str]]:
    """
    Extract (phase_key, category_key, split_key) from filename.

    Args:
        filename: e.g. "colon_numeric_smiles_ml_v1_groupcv.json"

    Returns:
        dict or None if parsing fails.
    """
    match = FILENAME_RE.match(filename)
    if not match:
        return None

    phase_key = match.group("phase")
    category_key = match.group("category")
    split_key = match.group("split")

    if phase_key not in PHASE_MAP:
        return None
    if category_key not in CATEGORY_MAP:
        return None
    if split_key not in SPLIT_MAP:
        return None

    return {
        "phase_key": phase_key,
        "category_key": category_key,
        "split_key": split_key,
    }


def parse_model_result(
    model_name: str,
    model_data: Dict[str, Any],
    file_meta: Dict[str, str],
    source_file: Path,
) -> Dict[str, Any]:
    """
    Convert one model result block into a DataFrame row dict.
    """
    fold_results = model_data.get("fold_results", [])
    n_folds = len(fold_results)

    val_spearman_folds: List[Optional[float]] = []
    train_spearman_folds: List[Optional[float]] = []
    fold_details: Dict[int, Dict[str, Any]] = {}

    for fold in fold_results:
        fold_num = fold.get("fold", -1)
        val_metrics = fold.get("val", {}) or {}
        train_metrics = fold.get("train", {}) or {}

        val_spearman_folds.append(val_metrics.get("spearman"))
        train_spearman_folds.append(train_metrics.get("spearman"))

        fold_details[fold_num] = {
            "train": train_metrics,
            "val": val_metrics,
        }

    val_valid = [v for v in val_spearman_folds if v is not None]
    train_valid = [v for v in train_spearman_folds if v is not None]

    val_mean = sum(val_valid) / len(val_valid) if val_valid else None
    train_mean = sum(train_valid) / len(train_valid) if train_valid else None
    val_std = pd.Series(val_valid).std() if len(val_valid) >= 2 else None

    gap_mean = (
        train_mean - val_mean
        if (train_mean is not None and val_mean is not None)
        else None
    )

    overfit_check = model_data.get("overfitting_check") or {}
    stability_check = model_data.get("stability_check") or {}

    overfitting_flag = None
    if overfit_check:
        overfitting_flag = overfit_check.get("n_overfitting_folds", 0) > 0
    elif gap_mean is not None:
        overfitting_flag = gap_mean > OVERFITTING_THRESHOLD

    stability_flag = None
    if stability_check:
        stability_flag = not stability_check.get("unstable", False)
    elif val_std is not None:
        stability_flag = val_std <= STABILITY_THRESHOLD

    phase_name = PHASE_MAP[file_meta["phase_key"]]
    split_name = SPLIT_MAP[file_meta["split_key"]]
    category_name = CATEGORY_MAP[file_meta["category_key"]]

    inferred_cat = get_model_category(model_name)
    category_final = category_name
    if inferred_cat != "Unknown" and inferred_cat != category_name:
        # Trust filename category when mismatch happens.
        pass

    phase_short = phase_name.replace("Phase ", "")
    split_short = split_name.replace(" ", "")
    experiment_id = f"{phase_short}_{category_final}_{model_name}_{split_short}"

    return {
        "experiment_id": experiment_id,
        "phase": phase_name,
        "phase_key": file_meta["phase_key"],
        "split": split_name,
        "split_key": file_meta["split_key"],
        "category": category_final,
        "category_key": file_meta["category_key"],
        "model": model_name,
        "val_spearman_mean": val_mean,
        "val_spearman_std": val_std,
        "train_spearman_mean": train_mean,
        "gap_mean": gap_mean,
        "val_spearman_folds": val_spearman_folds,
        "train_spearman_folds": train_spearman_folds,
        "n_folds": n_folds,
        "overfitting_flag": overfitting_flag,
        "stability_flag": stability_flag,
        "source_file": str(source_file.name),
        "fold_details": fold_details,
    }


def parse_json_file(json_path: Path) -> List[Dict[str, Any]]:
    """
    Parse one JSON file into model row dicts.
    """
    file_meta = parse_filename(json_path.name)
    if file_meta is None:
        return []

    try:
        with json_path.open("r", encoding="utf-8") as file_obj:
            data = json.load(file_obj)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"WARNING: failed to parse {json_path.name}: {exc}")
        return []

    if not isinstance(data, dict):
        return []

    rows: List[Dict[str, Any]] = []
    for model_name, model_data in data.items():
        if not isinstance(model_data, dict):
            continue
        if "fold_results" not in model_data:
            continue

        row = parse_model_result(model_name, model_data, file_meta, json_path)
        rows.append(row)

    return rows


def load_step4_results(
    results_dir: Optional[Path] = None,
    splits: Optional[List[str]] = None,
) -> pd.DataFrame:
    """
    Scan results/ and load all Step 4 JSONs into one DataFrame.

    Args:
        results_dir: default RESULTS_DIR from constants.
        splits: optional split_key filter, e.g. ["groupcv", "scaffoldcv"].
    """
    target_dir = results_dir or RESULTS_DIR

    if not target_dir.exists():
        print(f"WARNING: RESULTS_DIR does not exist: {target_dir}")
        return pd.DataFrame()

    json_files = sorted(target_dir.glob("colon_*_v1_*.json"))
    all_rows: List[Dict[str, Any]] = []

    for json_file in json_files:
        meta = parse_filename(json_file.name)
        if meta is None:
            continue
        if splits is not None and meta["split_key"] not in splits:
            continue

        all_rows.extend(parse_json_file(json_file))

    df = pd.DataFrame(all_rows)

    if len(df) > 0:
        df = df.sort_values(
            "val_spearman_mean", ascending=False, na_position="last"
        ).reset_index(drop=True)
        df["rank"] = df.index + 1

    return df


def _print_summary(df: pd.DataFrame) -> None:
    """Print compact parser summary for CLI quick check."""
    if len(df) == 0:
        print("No parsed rows.")
        return

    print(f"\nTotal experiments: {len(df)}")
    print(f"  JSON files: {df['source_file'].nunique()}")
    print(f"  Model names: {df['model'].nunique()}")
    print()

    print("Experiments by split:")
    print(df["split"].value_counts().to_string())
    print()

    print("Experiments by phase:")
    print(df["phase"].value_counts().to_string())
    print()

    print("Experiments by category:")
    print(df["category"].value_counts().to_string())
    print()

    print("=" * 80)
    print("Top 10 by val_spearman_mean")
    print("=" * 80)
    cols = [
        "rank",
        "split",
        "phase",
        "category",
        "model",
        "val_spearman_mean",
        "val_spearman_std",
    ]
    top = df[cols].head(10).copy()
    top["val_spearman_mean"] = top["val_spearman_mean"].round(4)
    top["val_spearman_std"] = top["val_spearman_std"].round(4)
    print(top.to_string(index=False))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Step 4 Parser")
    parser.add_argument(
        "--save-csv",
        action="store_true",
        help="결과를 reports/step4_parser_summary.csv 로 저장",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=None,
        help="포함할 split_key 리스트 (e.g. --splits groupcv scaffoldcv)",
    )
    args = parser.parse_args()

    print("=" * 80)
    print("Step 4 Parser — Quick Test")
    print("=" * 80)

    parsed_df = load_step4_results(splits=args.splits)
    _print_summary(parsed_df)

    if args.save_csv and len(parsed_df) > 0:
        from dashboard.utils.constants import REPORTS_DIR

        REPORTS_DIR.mkdir(exist_ok=True)
        csv_path = REPORTS_DIR / "step4_parser_summary.csv"

        export_cols = [
            "rank",
            "experiment_id",
            "phase",
            "split",
            "category",
            "model",
            "val_spearman_mean",
            "val_spearman_std",
            "train_spearman_mean",
            "gap_mean",
            "n_folds",
            "overfitting_flag",
            "stability_flag",
            "source_file",
        ]
        parsed_df[export_cols].to_csv(csv_path, index=False)
        print(f"\n✅ CSV 저장: {csv_path}")
