#!/usr/bin/env python3
"""
Step 6.1 (optional): GEO external cohort matrix audit.

Resolves configured paths (file or directory with ``*series_matrix*.txt*``),
checks for tabular matrix-like content, logs I/O under ``logs/``, and records
sources in ``results/<prefix>_step6_sources_read.json``.

Input / output shapes:
  - Input: ``Step6ValidationContext`` (``geo.enabled``, ``geo.matrix_files``).
  - Output: ``results/<prefix>_geo_matrix_audit.json`` with one row per GSE;
    merges step key ``6.1_geo_external_cohorts``.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_LUNG = Path(__file__).resolve().parent
if str(_LUNG) not in sys.path:
    sys.path.insert(0, str(_LUNG))

import pandas as pd

from step6_validation_context import Step6ValidationContext


def _log_io(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}\n"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def _resolve_matrix_path(raw: Path) -> Optional[Path]:
    if not raw.exists():
        return None
    if raw.is_file():
        return raw
    if raw.is_dir():
        patterns = (
            "*series_matrix*.txt*",
            "matrix/*series_matrix*.txt*",
            "suppl/*series_matrix*.txt*",
            "*.soft",
            "matrix/*.soft",
        )
        for pat in patterns:
            found = sorted(raw.glob(pat))
            if found:
                return found[0]
    return None


def _looks_like_expression_matrix(path: Path) -> tuple[bool, str]:
    """Heuristic: GEO series matrix or tabular gene × sample."""
    name = path.name.lower()
    if "series_matrix" in name:
        return True, "filename contains series_matrix"
    try:
        head = pd.read_csv(path, sep="\t", nrows=8, comment="!", low_memory=False)
    except Exception as exc:  # noqa: BLE001
        return False, f"read_error: {exc}"
    if head.shape[1] < 2:
        return False, f"too_few_columns shape={head.shape}"
    if head.shape[0] < 2:
        return False, f"too_few_rows shape={head.shape}"
    return True, f"tabular_preview shape={head.shape}"


def main(argv: Optional[List[str]] = None) -> Dict[str, Any]:
    ctx = Step6ValidationContext.load(argv)
    logs_dir = ctx.project_root / "logs"
    ts = time.strftime("%Y%m%d_%H%M%S")
    log_path = logs_dir / f"step6_geo_external_cohorts_{ts}.log"
    _log_io(log_path, f"begin Step 6.1 GEO audit project_root={ctx.project_root}")

    lines: List[str] = []
    audit_rows: List[Dict[str, Any]] = []

    if not ctx.geo_enabled:
        print("\n⚠️  GEO disabled — skip external cohort matrix audit")
        lines.append("geo: disabled in validation config")
        ctx.merge_step_sources("6.1_geo_external_cohorts", lines)
        _log_io(log_path, "skip geo_disabled")
        return {"geo_enabled": False, "cohorts": []}

    if not ctx.geo_matrix_files:
        print("\n⚠️  GEO enabled but no matrix_files configured — skip")
        lines.append("geo: enabled but matrix_files empty")
        ctx.merge_step_sources("6.1_geo_external_cohorts", lines)
        _log_io(log_path, "skip matrix_files empty")
        return {"geo_enabled": True, "cohorts": []}

    print("=" * 80)
    print("STEP 6.1: GEO EXTERNAL COHORTS (MATRIX AUDIT)")
    print("=" * 80)

    for gse, configured in sorted(ctx.geo_matrix_files.items()):
        resolved = _resolve_matrix_path(configured)
        row: Dict[str, Any] = {
            "gse": gse,
            "configured_path": str(configured),
            "resolved_path": str(resolved) if resolved else None,
            "matrix_like": False,
            "note": "",
        }
        if resolved is None:
            msg = f"skip {gse}: missing or empty directory {configured}"
            print(f"⚠️  {msg}")
            lines.append(msg)
            row["note"] = "missing_or_unresolved"
            audit_rows.append(row)
            _log_io(log_path, msg)
            continue

        ok, reason = _looks_like_expression_matrix(resolved)
        row["matrix_like"] = ok
        row["note"] = reason
        audit_rows.append(row)
        if ok:
            print(f"✓ {gse}: {resolved} ({reason})")
            lines.append(f"read matrix {gse} -> {resolved} ({reason})")
            _log_io(log_path, f"read_ok {gse} {resolved}")
        else:
            warn = f"warning {gse}: not matrix-like ({reason}) path={resolved}"
            print(f"⚠️  {warn}")
            lines.append(warn)
            _log_io(log_path, warn)

    out = ctx.results_json("geo_matrix_audit")
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cancer_type": ctx.cancer_type,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "cohorts": audit_rows,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _log_io(log_path, f"wrote {out}")
    lines.append(f"wrote {out}")

    ctx.merge_step_sources("6.1_geo_external_cohorts", lines)
    print(f"\n✓ Saved: {out}")
    return payload


if __name__ == "__main__":
    main(sys.argv[1:])
