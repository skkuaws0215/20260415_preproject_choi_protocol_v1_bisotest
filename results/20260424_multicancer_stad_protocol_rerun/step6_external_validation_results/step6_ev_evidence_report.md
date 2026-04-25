# Step6-1 EV Evidence Report

- **ADMET: not run** (Step7). Evidence here is for **EV triage and Step7 prep** only.  
- **Input:** `step6_ev_input_top15.csv` — 60 row-level candidates (4 cancers × 15), globally unique `canonical_drug_id`.  
- **Raw evidence rows:** 480 = 60 candidates × 8 `evidence_axis` (long format: `step6_ev_evidence_raw.csv` / `.json`).

## 1) Sources

| Source | Use | When unavailable |
|--------|-----|------------------|
| **ClinicalTrials.gov** v2 (public) | `clinical_trial_evidence` — `query.intr` + `query.cond` (cancer string) | `evidence_status=api_error` if HTTP error (see log) |
| **ChEMBL** (EBI) | molecule search → `mechanism` → `drug_indication` | `molecule_not_found` / `no_mechanism` / `no_indications` |
| **Local** GDSC/PRISM/IC50 | `external_drug_response_evidence` | **Unusable** in this run — no evaluated IC50 join; score **0**, documented in `step6_ev_unavailable_sources.csv` |
| **Protocol** | `caveat_handling` for **LUAD** (Graph partial) | Penalty in composite, `mandatory_caveat` text preserved |

**Execution:** `rate_limit` ≈ 1.2s between requests; see `step6_ev_execution_log.md` for call/failure counts.

## 2) Scoring (availability-only; no fiction)

- **clinical_trial_evidence (0–2):** 0 = 0 studies; 1 = 1–5 totalCount; 2 = 6+  
- **approved_or_known_indication_evidence (0–2):** from ChEMBL `max_phase` (0 / 1–3 / 4)  
- **external_drug_response_evidence (0–3):** always **0** in this run (no local/confirmed response table used)  
- **disease_relevance_evidence (0–2):** heuristics on `drug_indication` text vs cancer (see per-row `evidence_summary`)  
- **literature_or_moa_evidence (0–2):** from ChEMBL mechanism count/coverage  
- **target_moa_recovery (0–1):** 1 if targets/MOA text recovered from ChEMBL  
- **cancer_specific_plausibility (0–2):** small heuristic from approved + disease + MOA signal  
- **caveat_handling:** **−0.5** score on axis for **LUAD** when Graph-partial policy applies; reduces **ev_composite_0_10**  

**`ev_composite_0_10` (per candidate, `step6_ev_evidence_by_candidate.csv`):**  
`min(10, s_clin + s_app + s_drel + s_liter + s_plau + s_tm_bonus − 2×caveat_penalty)` with `caveat_penalty=0.5` for LUAD Graph caveat.

## 3) By-cancer means (composites from this run)

| cancer | n | mean `ev_composite_0_10` | mean clinical | mean approved |
|--------|---|---------------------------|---------------|---------------|
| brca  | 15 | 2.6 | 0.8 | 0.8 |
| crc   | 15 | 2.4 | 0.67 | 0.53 |
| luad  | 15 | 0.93 | 0.4 | 0.47 |
| stad  | 15 | 2.67 | 0.27 | 0.67 |

LUAD mean is lower in part because of **caveat penalty** and partial ChEMBL/CTG matches for some drug names.

## 4) Target / MOA

- Recovered in **`step6_ev_target_moa_recovery.csv`** when ChEMBL returns `mechanism` rows.  
- Internal workspace `target` / `moa` columns in the input remain empty; ChEMBL is **separate provenance** (`source_provenance`).

## 5) Artifacts (this folder)

- `step6_ev_evidence_raw.csv` / `step6_ev_evidence_raw.json`  
- `step6_ev_evidence_by_candidate.csv`  
- `step6_ev_evidence_by_cancer.csv`  
- `step6_ev_target_moa_recovery.csv`  
- `step6_ev_source_availability.csv`  
- `step6_ev_unavailable_sources.csv`  
- `step6_ev_execution_log.md`  
- `collect_step6_evidence.py` (reproducible runner; read-only on FE/parquet per policy)

Step6 EV evidence collection completed. Review EV scores before Step7 ADMET.
