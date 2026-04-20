#!/usr/bin/env python3
"""
Extract LINCS signatures from GSE92742 gctx for Colon cell lines.

Colon-specific new script (no Lung/BRCA equivalent).
Uses GSE92742 only (Lung lincs_lung.parquet reference).

Process:
  1. Load sig_info, filter by pert_type=trt_cp and Colon 13 cells
  2. Decompress gctx.gz to temp directory
  3. Parse gctx using cmapPy, extracting filtered sig_ids (chunked)
  4. Combine metadata + gene matrix into Lung schema
  5. Save as parquet

Output schema (matches Lung lincs_lung.parquet):
  Columns (12,336 total):
    [0]         sig_id           (string)
    [1..12328]  <entrez_id>      (float32, 12,328 genes)
    [12329]     pert_id          (string)
    [12330]     pert_iname       (string)
    [12331]     pert_dose        (string)
    [12332]     pert_dose_unit   (string)
    [12333]     pert_time        (int64)
    [12334]     pert_time_unit   (string)
    [12335]     cell_id          (string)
"""

import argparse
import gzip
import json
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd


# Colon 13 cell lines (LINCS validated)
COLON_13 = [
    "CL34",
    "HCT116",
    "HT115",
    "HT29",
    "LOVO",
    "MDST8",
    "NCIH508",
    "RKO",
    "SNU1040",
    "SNUC5",
    "SW480",
    "SW620",
    "SW948",
]


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--gctx-uri", required=True, type=Path, help="Path to GSE92742 Level5 gctx.gz"
    )
    p.add_argument(
        "--sig-info-uri",
        required=True,
        type=Path,
        help="Path to GSE92742 sig_info.txt.gz",
    )
    p.add_argument(
        "--output-uri", required=True, type=Path, help="Output: lincs_colon.parquet"
    )
    p.add_argument(
        "--report-uri", required=True, type=Path, help="Output: extraction report JSON"
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=2000,
        help="Signature extraction chunk size (default: 2000)",
    )
    p.add_argument(
        "--tmp-dir",
        type=Path,
        default=None,
        help="Temp dir for gctx decompression (default: system tmp)",
    )
    return p.parse_args()


def decompress_gctx(gctx_gz_path: Path, output_dir: Path) -> Path:
    """Decompress .gctx.gz to .gctx in output_dir."""
    output_path = Path(output_dir) / gctx_gz_path.name.replace(".gz", "")
    log(f"Decompressing {gctx_gz_path.name} -> {output_path.name}")

    with gzip.open(gctx_gz_path, "rb") as f_in:
        with open(output_path, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out, length=1024 * 1024 * 64)  # 64MB buffer

    size_gb = output_path.stat().st_size / 1024**3
    log(f"  Decompressed size: {size_gb:.2f} GB")
    return output_path


def filter_sig_info(
    sig_info_path: Path, colon_cells: list[str], pert_type: str = "trt_cp"
) -> tuple[pd.DataFrame, str]:
    """Load sig_info and filter by cell and pert_type."""
    log(f"Loading sig_info: {sig_info_path.name}")
    sig_info = pd.read_csv(sig_info_path, sep="\t", compression="gzip", low_memory=False)
    log(f"  Total rows: {len(sig_info):,}")
    log(f"  Columns: {sig_info.columns.tolist()}")

    cell_col = "cell_id" if "cell_id" in sig_info.columns else "cell_iname"
    mask = (sig_info["pert_type"] == pert_type) & (sig_info[cell_col].isin(colon_cells))
    filtered = sig_info[mask].copy()

    log(f"  Filtered (pert_type={pert_type}, cells=Colon 13): {len(filtered):,}")
    log(f"  Cells present: {sorted(filtered[cell_col].unique())}")
    return filtered, cell_col


def extract_gctx_chunked(gctx_path: Path, sig_ids: list[str], chunk_size: int = 2000) -> pd.DataFrame:
    """Extract signatures from gctx in chunks using cmapPy."""
    from cmapPy.pandasGEXpress.parse import parse

    total = len(sig_ids)
    log(f"Extracting {total:,} signatures in chunks of {chunk_size}")

    chunks: list[pd.DataFrame] = []
    n_chunks = (total + chunk_size - 1) // chunk_size

    for i in range(0, total, chunk_size):
        chunk_ids = sig_ids[i : i + chunk_size]
        chunk_num = (i // chunk_size) + 1
        log(f"  Chunk {chunk_num}/{n_chunks}: parsing {len(chunk_ids)} sigs...")

        gctoo = parse(str(gctx_path), cid=chunk_ids)
        chunk_df = gctoo.data_df.T  # (genes, signatures) -> (signatures, genes)
        chunks.append(chunk_df)
        del gctoo

    log(f"Concatenating {n_chunks} chunks...")
    gene_matrix = pd.concat(chunks, axis=0)
    log(f"  Gene matrix shape: {gene_matrix.shape}")
    return gene_matrix


def build_final_df(gene_matrix: pd.DataFrame, sig_info_filtered: pd.DataFrame, cell_col: str) -> pd.DataFrame:
    """
    Combine gene matrix + metadata into Lung schema.

    Lung schema (12,336 cols):
      [0]         sig_id
      [1..12328]  <entrez_id> (float32)
      [12329]     pert_id
      [12330]     pert_iname
      [12331]     pert_dose
      [12332]     pert_dose_unit
      [12333]     pert_time (int64)
      [12334]     pert_time_unit
      [12335]     cell_id
    """
    log("Building final DataFrame (Lung schema)...")

    gene_matrix.index.name = "sig_id"
    gene_matrix = gene_matrix.reset_index()

    gene_cols = [c for c in gene_matrix.columns if c != "sig_id"]
    gene_matrix[gene_cols] = gene_matrix[gene_cols].astype("float32")

    required_meta = [
        "sig_id",
        "pert_id",
        "pert_iname",
        "pert_dose",
        "pert_dose_unit",
        "pert_time",
        "pert_time_unit",
    ]

    missing = [c for c in required_meta if c not in sig_info_filtered.columns]
    if missing:
        log(f"  WARNING: Missing meta cols in sig_info: {missing}")
        log(f"  Available: {sig_info_filtered.columns.tolist()}")
        for c in missing:
            sig_info_filtered[c] = None

    meta = sig_info_filtered[required_meta + [cell_col]].copy()
    if cell_col != "cell_id":
        meta = meta.rename(columns={cell_col: "cell_id"})

    try:
        meta["pert_time"] = pd.to_numeric(meta["pert_time"], errors="coerce").astype("Int64")
    except Exception as e:
        log(f"  WARNING: pert_time conversion issue: {e}")

    result = gene_matrix.merge(
        meta[
            [
                "sig_id",
                "pert_id",
                "pert_iname",
                "pert_dose",
                "pert_dose_unit",
                "pert_time",
                "pert_time_unit",
                "cell_id",
            ]
        ],
        on="sig_id",
        how="left",
    )

    final_cols = ["sig_id"] + gene_cols + [
        "pert_id",
        "pert_iname",
        "pert_dose",
        "pert_dose_unit",
        "pert_time",
        "pert_time_unit",
        "cell_id",
    ]
    result = result[final_cols]

    log(f"  Final shape: {result.shape}")
    log(f"  First col: {result.columns[0]}")
    log(f"  Last 8 cols: {result.columns[-8:].tolist()}")
    return result


def main() -> int:
    args = parse_args()

    log("=" * 70)
    log("Step 2-6-C: Extract LINCS gctx for Colon (GSE92742)")
    log("=" * 70)

    for path, name in [(args.gctx_uri, "gctx"), (args.sig_info_uri, "sig_info")]:
        if not path.exists():
            log(f"ERROR: {name} not found: {path}")
            sys.exit(1)

    filtered_sigs, cell_col = filter_sig_info(args.sig_info_uri, COLON_13, pert_type="trt_cp")
    if len(filtered_sigs) == 0:
        log("ERROR: No signatures matched Colon 13 + trt_cp")
        sys.exit(1)

    log("")
    log("=== Colon cell distribution (trt_cp) ===")
    cell_counts = filtered_sigs[cell_col].value_counts()
    for cell in COLON_13:
        n = cell_counts.get(cell, 0)
        log(f"  {cell:10s}: {n:>6,}")
    log(f"  {'TOTAL':10s}: {len(filtered_sigs):>6,}")

    sig_ids_to_extract = filtered_sigs["sig_id"].tolist()

    log("")
    tmp_dir = args.tmp_dir or tempfile.mkdtemp(prefix="lincs_gctx_")
    tmp_path = Path(tmp_dir)
    tmp_path.mkdir(parents=True, exist_ok=True)
    log(f"Using temp dir: {tmp_path}")

    try:
        gctx_path = decompress_gctx(args.gctx_uri, tmp_path)

        log("")
        gene_matrix = extract_gctx_chunked(gctx_path, sig_ids_to_extract, args.chunk_size)

        log("")
        final_df = build_final_df(gene_matrix, filtered_sigs, cell_col)

        log("")
        log("=== Validation ===")
        actual_meta_cols = [c for c in final_df.columns if final_df[c].dtype == "object" or c == "pert_time"]
        log(f"Meta columns: {len(actual_meta_cols)} (expected 8)")
        log(f"Gene columns: {len(final_df.columns) - 8} (expected 12,328)")
        log(f"Total cols: {len(final_df.columns)} (expected 12,336)")
        log(f"Total rows: {len(final_df):,} (expected 18,823)")
        if len(final_df.columns) != 12336:
            log("WARNING: Column count mismatch!")

        log("")
        args.output_uri.parent.mkdir(parents=True, exist_ok=True)
        args.report_uri.parent.mkdir(parents=True, exist_ok=True)

        log(f"Saving to {args.output_uri}...")
        final_df.to_parquet(args.output_uri, index=False, engine="pyarrow")
        size_mb = args.output_uri.stat().st_size / 1024**2
        log(f"  Saved: {size_mb:.1f} MB")

        report = {
            "timestamp": datetime.now().isoformat(),
            "input": {"gctx": str(args.gctx_uri), "sig_info": str(args.sig_info_uri)},
            "filter": {"pert_type": "trt_cp", "cells": COLON_13},
            "output": {
                "path": str(args.output_uri),
                "shape": list(final_df.shape),
                "size_mb": round(size_mb, 2),
                "meta_cols": 8,
                "gene_cols": len(final_df.columns) - 8,
            },
            "cell_distribution": {cell: int(cell_counts.get(cell, 0)) for cell in COLON_13},
            "total_sigs": int(len(filtered_sigs)),
            "ht29_ratio": round(cell_counts.get("HT29", 0) / len(filtered_sigs), 4)
            if len(filtered_sigs) > 0
            else 0,
        }

        with open(args.report_uri, "w") as f:
            json.dump(report, f, indent=2)
        log(f"Report saved: {args.report_uri}")

    finally:
        if args.tmp_dir is None and tmp_path.exists():
            log("")
            log(f"Cleaning up temp dir: {tmp_path}")
            shutil.rmtree(tmp_path, ignore_errors=True)

    log("")
    log("=" * 70)
    log("Step 2-6-C completed successfully")
    log("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
