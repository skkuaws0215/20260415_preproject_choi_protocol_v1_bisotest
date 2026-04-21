"""
Configurable paths for Step 6 external validation (Lung defaults + STAD JSON).

Usage (from any working directory):
  python step6_3_clinical_trials_validation.py \\
    --project-root /path/to/STAD \\
    --validation-config /path/to/step6_validation.stad.json

Omit ``--validation-config`` when running inside Lung with Lung layout (legacy).
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Step6ValidationContext:
    """Resolved Step 6 paths (absolute) and output prefix."""

    project_root: Path
    cancer_type: str
    results_prefix: str
    clinical_trials_enabled: bool
    clinical_trials_base: Optional[Path]
    clinical_trials_stem: str
    prism_enabled: bool
    prism_base: Optional[Path]
    prism_lineage_contains: List[str]
    cosmic_enabled: bool
    cosmic_mode: str
    cosmic_extract_dir: Optional[Path]
    cosmic_parquet_dir: Optional[Path]
    cosmic_actionability_parquet: str
    cosmic_cancer_gene_census_parquet: Optional[str]
    cptac_enabled: bool
    cptac_mode: str
    cptac_cbio_datasets: List[str]
    cptac_manifest_dir: Optional[Path]
    geo_enabled: bool
    geo_matrix_files: Dict[str, Path]
    top30_2b: Path
    top30_2c: Path
    top30_unified: Path

    def results_json(self, stem: str) -> Path:
        return self.project_root / "results" / f"{self.results_prefix}_{stem}.json"

    def results_csv(self, stem: str) -> Path:
        return self.project_root / "results" / f"{self.results_prefix}_{stem}.csv"

    def merge_step_sources(self, step_key: str, lines: List[str]) -> Path:
        """Merge per-step source lines into ``results/<prefix>_step6_sources_read.json``."""
        out = self.results_json("step6_sources_read")
        data: Dict[str, Any] = {}
        if out.exists():
            data = json.loads(out.read_text(encoding="utf-8"))
        data.setdefault("cancer_type", self.cancer_type)
        data.setdefault("results_prefix", self.results_prefix)
        data.setdefault("project_root", str(self.project_root))
        data.setdefault("steps", {})
        data["steps"][step_key] = lines
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return out

    @staticmethod
    def parse_argv(argv: Optional[List[str]] = None) -> tuple[argparse.Namespace, List[str]]:
        p = argparse.ArgumentParser(add_help=True)
        p.add_argument(
            "--project-root",
            type=Path,
            default=None,
            help="Project root for curated_data/ and results/ (default: cwd).",
        )
        p.add_argument(
            "--validation-config",
            type=Path,
            default=None,
            help="JSON config (STAD). If omitted, Lung legacy defaults apply.",
        )
        return p.parse_known_args(argv)

    @classmethod
    def load(cls, argv: Optional[List[str]] = None) -> "Step6ValidationContext":
        args, _unknown = cls.parse_argv(argv)
        root = (args.project_root or Path.cwd()).resolve()
        if args.validation_config and args.validation_config.exists():
            data = json.loads(args.validation_config.read_text(encoding="utf-8"))
            return cls.from_json(root, data)
        return cls.lung_legacy(root)


    @classmethod
    def lung_legacy(cls, root: Path) -> "Step6ValidationContext":
        return cls(
            project_root=root,
            cancer_type="lung",
            results_prefix="lung",
            clinical_trials_enabled=True,
            clinical_trials_base=root / "curated_data" / "validation" / "clinicaltrials",
            clinical_trials_stem="clinicaltrials_lung_cancer",
            prism_enabled=True,
            prism_base=root / "curated_data" / "validation" / "prism",
            prism_lineage_contains=["lung"],
            cosmic_enabled=True,
            cosmic_mode="extract",
            cosmic_extract_dir=root / "curated_data" / "validation" / "cosmic",
            cosmic_parquet_dir=None,
            cosmic_actionability_parquet="cosmic_actionability.parquet",
            cosmic_cancer_gene_census_parquet=None,
            cptac_enabled=True,
            cptac_mode="cbio_datasets",
            cptac_cbio_datasets=["luad_cptac_2020", "lusc_cptac_2021"],
            cptac_manifest_dir=None,
            geo_enabled=False,
            geo_matrix_files={},
            top30_2b=root / "results" / "lung_top30_phase2b_catboost_with_names.csv",
            top30_2c=root / "results" / "lung_top30_phase2c_catboost_with_names.csv",
            top30_unified=root / "results" / "lung_top30_unified_2b_and_2c_with_names.csv",
        )

    @classmethod
    def from_json(cls, root: Path, data: Dict[str, Any]) -> "Step6ValidationContext":
        def p(rel: Optional[str]) -> Optional[Path]:
            if not rel:
                return None
            return (root / rel).resolve()

        tr = data.get("training_results") or {}
        ct = data.get("clinical_trials") or {}
        pr = data.get("prism") or {}
        co = data.get("cosmic") or {}
        cp = data.get("cptac") or {}
        geo = data.get("geo") or {}

        matrix_files: Dict[str, Path] = {}
        if geo.get("enabled") and geo.get("matrix_files"):
            for gse, rel in geo["matrix_files"].items():
                pt = p(str(rel))
                if pt is not None:
                    matrix_files[str(gse)] = pt

        def req(key: str) -> Path:
            if key not in tr or not tr[key]:
                raise KeyError(f"training_results.{key} required in validation config")
            out = p(str(tr[key]))
            if out is None:
                raise ValueError(f"training_results.{key} invalid path")
            return out

        return cls(
            project_root=root,
            cancer_type=str(data.get("cancer_type", "unknown")),
            results_prefix=str(data.get("results_prefix", "run")),
            clinical_trials_enabled=bool(ct.get("enabled", True)),
            clinical_trials_base=p(ct.get("base_dir")),
            clinical_trials_stem=str(ct.get("file_stem", "clinicaltrials_unknown")),
            prism_enabled=bool(pr.get("enabled", True)),
            prism_base=p(pr.get("base_dir")),
            prism_lineage_contains=list(pr.get("lineage_contains_any_of", ["lung"])),
            cosmic_enabled=bool(co.get("enabled", True)),
            cosmic_mode=str(co.get("mode", "extract")),
            cosmic_extract_dir=p(co.get("extract_dir")),
            cosmic_parquet_dir=p(co.get("parquet_dir")),
            cosmic_actionability_parquet=str(
                co.get("actionability_filename", "cosmic_actionability.parquet")
            ),
            cosmic_cancer_gene_census_parquet=co.get("cancer_gene_census_filename"),
            cptac_enabled=bool(cp.get("enabled", True)),
            cptac_mode=str(cp.get("mode", "cbio_datasets")),
            cptac_cbio_datasets=list(cp.get("cbio_datasets", [])),
            cptac_manifest_dir=p(cp.get("manifest_dir")),
            geo_enabled=bool(geo.get("enabled", False)),
            geo_matrix_files=matrix_files,
            top30_2b=req("top30_2b_with_names"),
            top30_2c=req("top30_2c_with_names"),
            top30_unified=req("top30_unified_with_names"),
        )


def env_context() -> Optional[Step6ValidationContext]:
    """Optional: STEP6_VALIDATION_CONFIG + STEP6_PROJECT_ROOT environment variables."""
    cfg = os.environ.get("STEP6_VALIDATION_CONFIG", "").strip()
    root = os.environ.get("STEP6_PROJECT_ROOT", "").strip()
    if not cfg:
        return None
    r = Path(root or ".").resolve()
    return Step6ValidationContext.from_json(r, json.loads(Path(cfg).read_text(encoding="utf-8")))
