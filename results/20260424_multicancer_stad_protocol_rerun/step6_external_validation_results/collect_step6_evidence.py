#!/usr/bin/env python3
"""Step6-1: EV evidence collection (read-only on local FE/parquet; public APIs for CT/ChEMBL)."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# --- paths ---
REPO = Path(__file__).resolve().parents[3]
if not (REPO / "results" / "20260424_multicancer_stad_protocol_rerun").exists():
    REPO = Path(__file__).resolve().parents[2]
Design = (
    REPO
    / "results"
    / "20260424_multicancer_stad_protocol_rerun"
    / "step6_external_validation_design"
)
Out = (
    REPO
    / "results"
    / "20260424_multicancer_stad_protocol_rerun"
    / "step6_external_validation_results"
)
LOCAL_GDSC_CANDIDATES: list[Path] = [
    REPO / "20260420_new_pre_project_biso_Colon" / "curated_data" / "gdsc" / "gdsc_ic50.csv.gz",
    REPO / "20260415_preproject_protocol_choi" / "data" / "drug_features_catalog.parquet",
]

RATE_SEC = 1.2
CTG_BASE = "https://clinicaltrials.gov/api/v2/studies"
CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"

CANCER_COND: dict[str, str] = {
    "brca": "Breast Cancer",
    "crc": "Colorectal Cancer",
    "luad": "Lung Cancer",
    "stad": "Stomach Cancer",
}

AXES: list[str] = [
    "clinical_trial_evidence",
    "approved_or_known_indication_evidence",
    "external_drug_response_evidence",
    "disease_relevance_evidence",
    "literature_or_moa_evidence",
    "target_moa_recovery",
    "cancer_specific_plausibility",
    "caveat_handling",
]

LUAD_TEXT = "Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations."


@dataclass
class Log:
    lines: list[str] = field(default_factory=list)
    n_http: int = 0
    n_fail: int = 0

    def add(self, s: str) -> None:
        self.lines.append(f"{datetime.now(timezone.utc).isoformat()} {s}")


log = Log()


def http_get_json(url: str) -> dict | list | None:
    req = urllib.request.Request(url, headers={"User-Agent": "Step6-EV-Collector/1.0 (research)"})
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            log.n_http += 1
            data = r.read().decode("utf-8", errors="replace")
            return json.loads(data)
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        log.n_fail += 1
        log.add(f"HTTP_FAIL {url[:120]}... err={e!r}")
        return None
    finally:
        time.sleep(RATE_SEC)


def clinical_trials_count(drug: str, cond: str) -> tuple[int, str, str]:
    qv = {
        "format": "json",
        "pageSize": 1,
        "countTotal": "true",
        "query.intr": drug[:200],
        "query.cond": cond[:200],
    }
    q = urllib.parse.urlencode(qv)
    url = f"{CTG_BASE}?{q}"
    out = http_get_json(url)
    if not isinstance(out, dict):
        return 0, url, "api_error"
    n = int(out.get("totalCount", 0) or 0)
    return n, url, "ok" if n >= 0 else "api_error"


def score_clinical(n: int) -> int:
    if n <= 0:
        return 0
    if n <= 5:
        return 1
    return 2


def chembl_molecule(drug: str) -> dict | None:
    safe = re.sub(r"[^\w\-\s\(\).,%+\[\]@/=\\#]", " ", drug)[:200].strip()
    if not safe:
        return None
    qv = {
        "pref_name__icontains": safe,
        "limit": 3,
        "format": "json",
    }
    q = urllib.parse.urlencode(qv)
    url = f"{CHEMBL}/molecule.json?{q}"
    j = http_get_json(url)
    if not isinstance(j, dict) or not j.get("molecules"):
        return None
    mols = j["molecules"]
    # prefer exact or highest phase
    def key(m: dict) -> tuple:
        name = (m.get("pref_name") or "").upper()
        d = (drug or "").upper()
        ex = 0 if name == d or d in name or name in d else 1
        phase = m.get("max_phase") or 0
        return (ex, -float(phase) if phase else 0.0, name)

    mols = sorted(mols, key=key)
    return mols[0] if mols else None


def chembl_mechanism(chembl_id: str) -> list[dict]:
    qv = {"molecule_chembl_id": chembl_id, "limit": 15, "format": "json"}
    q = urllib.parse.urlencode(qv)
    url = f"{CHEMBL}/mechanism.json?{q}"
    j = http_get_json(url)
    if not isinstance(j, dict) or not j.get("mechanisms"):
        return []
    return j["mechanisms"]


def chembl_indications(chembl_id: str) -> list[dict]:
    qv = {"molecule_chembl_id": chembl_id, "limit": 30, "format": "json"}
    q = urllib.parse.urlencode(qv)
    url = f"{CHEMBL}/drug_indication.json?{q}"
    j = http_get_json(url)
    if not isinstance(j, dict) or not j.get("indications"):
        return []
    return j["indications"]


def score_approved(m: dict) -> int:
    ph = m.get("max_phase")
    if ph is None:
        return 0
    if float(ph) >= 4.0:
        return 2
    if float(ph) >= 2.0:
        return 1
    return 0


def match_indication_to_cancer(inds: list[dict], cancer: str) -> int:
    if not inds:
        return 0
    blob = " ".join(
        str(x.get("mesh_heading", "")) + " " + str(x.get("efo_term", "")) for x in inds
    ).lower()
    if cancer == "brca" and any(k in blob for k in ("breast", "mammar")):
        return 2
    if cancer == "crc" and any(k in blob for k in ("colorect", "colon", "rectal")):
        return 2
    if cancer == "luad" and any(k in blob for k in ("lung", "nsclc", "non-small cell")):
        return 2
    if cancer == "stad" and any(k in blob for k in ("stomach", "gastric")):
        return 2
    if len(inds) > 0:
        return 1
    return 0


def mech_moa_text(mechs: list[dict]) -> str:
    parts = []
    for m in mechs[:5]:
        t = m.get("mechanism_of_action") or m.get("action_type") or ""
        name = m.get("target_chembl_id") or m.get("target_type") or ""
        if t or name:
            parts.append(f"{t} (target {name})")
    return "; ".join(parts)[:500]


def local_external_response_status() -> tuple[str, str]:
    for p in LOCAL_GDSC_CANDIDATES:
        if p.exists() and p.suffix == ".gz":
            return "unavailable", f"file_exists_but_not_evaluated: {p} (read policy)"
        if p.suffix == ".parquet" and "drug_feature" in p.name:
            return "unavailable", "no_ic50_in_catalog_parquet; GDSC not joined in this step"
    return "unavailable", "no local GDSC/PRISM response table in workspace (gitignored or absent)"


def run() -> None:
    Out.mkdir(parents=True, exist_ok=True)
    p15 = Design / "step6_ev_input_top15.csv"
    df = pd.read_csv(p15)
    if len(df) != 60 or df["canonical_drug_id"].nunique() != 60:
        raise ValueError("Expected 60 unique rows in top15")
    ccache: dict[str, dict] = {}
    mcache: dict[str, list[dict]] = {}
    icache: dict[str, list[dict]] = {}
    ctcache: dict[tuple[str, str], tuple[int, str, str]] = {}

    raw_rows: list[dict] = []
    by_c: list[dict] = []
    tm_rec: list[dict] = []
    local_st, local_note = local_external_response_status()
    for _, r in df.iterrows():
        cancer = str(r["cancer"]).lower()
        drug = str(r["drug_name"])
        smi = str(r.get("canonical_smiles") or "")
        rank = int(r["rank"])
        did = str(r["canonical_drug_id"])
        cond = CANCER_COND.get(cancer, "Cancer")
        glc = bool(r.get("graph_luad_caveat"))
        _mc = r.get("mandatory_caveat")
        mand = "" if pd.isna(_mc) else str(_mc)
        ev_r = bool(r.get("ev_ready", True))
        t_rec, moa_rec = "", ""
        if drug not in ccache:
            ccache[drug] = chembl_molecule(drug) or {}
        chembl_mol = ccache[drug]
        cid = chembl_mol.get("molecule_chembl_id")
        if cid:
            if cid not in mcache:
                mcache[cid] = chembl_mechanism(cid)
            if cid not in icache:
                icache[cid] = chembl_indications(cid)
            mechs = mcache.get(cid) or []
            inds = icache.get(cid) or []
        else:
            mechs, inds = [], []
        tnames: list = []
        for x in mechs:
            if not isinstance(x, dict):
                continue
            tnames.append(
                x.get("target_pref_name")
                or x.get("target_chembl_id")
                or x.get("target_type")
            )
        t_rec = ", ".join(str(t) for t in tnames[:5] if t)[:1000]
        moa_s = mech_moa_text(mechs) if mechs else ""
        if mechs:
            moa_rec = moa_s[:2000]
        if (drug, cond) not in ctcache:
            ctcache[(drug, cond)] = clinical_trials_count(drug, cond)
        ct_n, ct_url, ct_st = ctcache[(drug, cond)]
        s_clin = score_clinical(ct_n)
        s_app = score_approved(chembl_mol) if cid else 0
        s_drel = match_indication_to_cancer(inds, cancer) if inds else 0
        s_liter = 2 if (mechs and len(mechs) >= 2) else 1 if mechs else 0
        s_tm_bonus = 1 if (t_rec or mechs) else 0
        s_plau = 0
        if s_drel >= 2:
            s_plau = 2
        elif s_drel == 1 or s_app >= 1:
            s_plau = 1
        if s_liter and s_plau < 2:
            s_plau = min(2, s_plau + 1)

        # external response: no fabricated data
        s_gdsc = 0
        ext_st = "unavailable" if "unavailable" in local_st else "partial"
        ex_sum = f"{local_note} (scoring uses only confirmed external/local evidence)"
        s_ext = 0  # not guessing

        # caveats
        cav_pen = 0.0
        if cancer == "luad" and glc:
            cav_pen = 0.5  # user: caveat_penalty; reduces composite for reporting

        def row(
            axis: str,
            score: float | int,
            status: str,
            src: str,
            summ: str,
            path: str,
            prov: str,
            t_g: str,
            m_g: str,
        ) -> dict:
            return {
                "cancer": cancer,
                "rank": rank,
                "canonical_drug_id": did,
                "drug_name": drug,
                "canonical_smiles": smi,
                "evidence_axis": axis,
                "evidence_source": src,
                "evidence_status": status,
                "evidence_score": score,
                "evidence_summary": summ,
                "source_url_or_path": path,
                "source_provenance": prov,
                "target_recovered": t_g,
                "moa_recovered": m_g,
                "ev_ready": ev_r,
                "graph_luad_caveat": glc,
                "mandatory_caveat": mand,
            }

        raw_rows.append(
            row(
                "clinical_trial_evidence",
                s_clin,
                ct_st,
                "ClinicalTrials.gov v2",
                f"totalCount~{ct_n} for intervention={drug!r} AND cond={cond!r}",
                ct_url,
                "public_api;countTotal",
                t_rec,
                moa_rec,
            )
        )
        raw_rows.append(
            row(
                "approved_or_known_indication_evidence",
                s_app,
                "ok" if cid else "molecule_not_found",
                "ChEMBL",
                f"max_phase={chembl_mol.get('max_phase')!s}; pref_name={chembl_mol.get('pref_name')!s}",
                f"{CHEMBL}/molecule (search)",
                "public_api;EBI ChEMBL 2024+",
                t_rec,
                moa_rec,
            )
        )
        raw_rows.append(
            row(
                "external_drug_response_evidence",
                s_ext,
                ext_st,
                "local_GDSC_PRISM (none)",
                ex_sum,
                "n/a",
                local_note,
                t_rec,
                moa_rec,
            )
        )
        raw_rows.append(
            row(
                "disease_relevance_evidence",
                s_drel,
                "ok" if inds else "no_indications",
                "ChEMBL drug_indication",
                f"matched n={len(inds)}; cancer_match_score={s_drel}",
                f"{CHEMBL}/drug_indication",
                "ChEMBL",
                t_rec,
                moa_rec,
            )
        )
        raw_rows.append(
            row(
                "literature_or_moa_evidence",
                s_liter,
                "ok" if mechs else "no_mechanism",
                "ChEMBL mechanism",
                moa_s[:500] or "no rows",
                f"{CHEMBL}/mechanism",
                "ChEMBL",
                t_rec,
                moa_rec,
            )
        )
        raw_rows.append(
            row(
                "target_moa_recovery",
                s_tm_bonus,
                "recovered" if (t_rec or mechs) else "not_recovered",
                "ChEMBL mechanism+targets",
                t_rec or moa_s[:300],
                f"{CHEMBL}/mechanism",
                "inferred from ChEMBL",
                t_rec,
                moa_rec,
            )
        )
        raw_rows.append(
            row(
                "cancer_specific_plausibility",
                s_plau,
                "heuristic",
                "composite(approved+disease+mech heuristics)",
                f"heuristic plausibility 0-2; see sub-scores",
                "internal_rule",
                "no generative data",
                t_rec,
                moa_rec,
            )
        )
        raw = row(
            "caveat_handling",
            -cav_pen if cav_pen else 0,
            "luad_graph_caveat" if cancer == "luad" else "none",
            "protocol",
            LUAD_TEXT if cancer == "luad" and glc else "no_caveat",
            "MULTI_CANCER_PROTOCOL",
            "internal_policy",
            t_rec,
            moa_rec,
        )
        raw_rows.append(raw)

        w = (s_clin * 0.2 + s_app * 0.2 + s_ext * 0.15 * 0 + s_drel * 0.15 + s_liter * 0.15 + s_plau * 0.1 + s_tm_bonus * 0.05)
        # weighted EV proxy (disease relevance weighted higher per plan)
        ev_total = (
            s_clin
            + s_app
            + s_drel
            + s_liter
            + s_plau
            + s_tm_bonus
        )  # 0-11 roughly
        if cav_pen:
            ev_total = max(0.0, ev_total - cav_pen * 2)
        by_c.append(
            {
                "cancer": cancer,
                "rank": rank,
                "canonical_drug_id": did,
                "drug_name": drug,
                "canonical_smiles": smi,
                "score_clinical_trial": s_clin,
                "score_approved_ind": s_app,
                "score_ext_response": s_ext,
                "score_disease_relevance": s_drel,
                "score_literature_moa": s_liter,
                "score_cancer_plausibility": s_plau,
                "target_moa_recovery_bonus": s_tm_bonus,
                "caveat_penalty": cav_pen,
                "ev_composite_0_10": round(
                    min(
                        10.0,
                        s_clin * 1.0
                        + s_app * 1.0
                        + s_drel * 1.0
                        + s_liter * 1.0
                        + s_plau * 1.0
                        + s_tm_bonus * 1.0
                        - cav_pen * 2,
                    ),
                    2,
                ),
                "n_clinicaltrials_studies_total": ct_n,
                "chembl_molecule_chembl_id": cid or "",
                "target_recovered": t_rec,
                "moa_recovered": moa_rec,
                "ev_ready": ev_r,
                "graph_luad_caveat": glc,
                "mandatory_caveat": mand,
            }
        )
        tm_rec.append(
            {
                "cancer": cancer,
                "canonical_drug_id": did,
                "drug_name": drug,
                "target_recovered": t_rec,
                "moa_recovered": moa_rec,
                "chembl_id": cid or "",
                "recovery_status": "partial" if (t_rec or mechs) else "none",
                "source_provenance": "ChEMBL public API" if (t_rec or mechs) else "no_match",
            }
        )

    raw_df = pd.DataFrame(raw_rows)
    if len(raw_df) != 60 * len(AXES):
        log.add(f"WARN raw rows {len(raw_df)} expected {60*len(AXES)}")
    raw_df.to_csv(Out / "step6_ev_evidence_raw.csv", index=False)
    with open(Out / "step6_ev_evidence_raw.json", "w", encoding="utf-8") as f:
        json.dump(raw_rows, f, indent=2, ensure_ascii=False)
    bdf = pd.DataFrame(by_c)
    bdf.to_csv(Out / "step6_ev_evidence_by_candidate.csv", index=False)
    pd.DataFrame(tm_rec).to_csv(Out / "step6_ev_target_moa_recovery.csv", index=False)
    gbc = bdf.groupby("cancer", as_index=False).agg(
        n_drugs=("canonical_drug_id", "count"),
        mean_composite=("ev_composite_0_10", "mean"),
        mean_clin=("score_clinical_trial", "mean"),
        mean_app=("score_approved_ind", "mean"),
    )
    gbc.to_csv(Out / "step6_ev_evidence_by_cancer.csv", index=False)
    sa = [
        {
            "source": "ClinicalTrials.gov v2 (public API)",
            "used": "yes",
            "notes": f"http_calls={log.n_http} failures={log.n_fail}",
        },
        {
            "source": "ChEMBL API (public)",
            "used": "yes",
            "notes": "molecule, mechanism, drug_indication",
        },
        {
            "source": "local GDSC/PRISM IC50",
            "used": "no",
            "notes": local_note,
        },
    ]
    pd.DataFrame(sa).to_csv(Out / "step6_ev_source_availability.csv", index=False)
    pd.DataFrame(
        [
            {
                "source": "local_GDSC_IC50",
                "status": "unavailable",
                "reason": local_note,
            }
        ]
    ).to_csv(Out / "step6_ev_unavailable_sources.csv", index=False)
    # logs
    log.add(f"DONE n_http~{log.n_http} n_fail~{log.n_fail}")
    (Out / "step6_ev_execution_log.md").write_text(
        "\n".join(
            [
                f"# Step6-1 execution log (UTC {datetime.now(timezone.utc).isoformat()})",
                "",
                f"- rate_limit_seconds: {RATE_SEC}",
                f"- http_calls: ~{log.n_http} (molecule+mech+ind+ct per unique drug, cached)",
                f"- http_failures: {log.n_fail}",
                "- ADMET: not run",
                "",
                "## detail",
                *log.lines,
            ]
        ),
        encoding="utf-8",
    )
    (Out / "step6_ev_evidence_report.md").write_text(
        "\n".join(
            [
                "# Step6-1 EV Evidence Report",
                "",
                "- **ADMET: not run**; evidence for Step7 only.",
                "- Top15 / 60 candidates; composite score uses **only** API- or rule-backed fields (no fabrications).",
                f"- local drug-response tables: **unavailable** in workspace → `external_drug_response_evidence` score **0** with note.",
                f"- **LUAD**: mandatory Graph partial caveat; `caveat_handling` axis applies **penalty** in composite (see by_candidate).",
                "- **Target/MOA**: recovered when ChEMBL returns mechanism; else empty.",
                f"- ChEMBL/ClinicalTrials calls: {log.n_http} ; failures: {log.n_fail}",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    run()
    print("OK", Out)
