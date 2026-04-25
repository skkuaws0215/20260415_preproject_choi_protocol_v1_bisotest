# Step7 ADMET Candidate Prep (no ADMET run)

- **ADMET: not executed**; this pack prepares **candidate sets** and documents EV score review.  
- **No new** EV API, ML/DL/Graph/Step5, or deletions. Read-only on Step6 folder.

## Step6 EV context (for readers)

- EV evidence used **ClinicalTrials.gov** + **ChEMBL** (see `step6_ev_evidence_report.md`, `step6_ev_execution_log.md`).  
- **GDSC/PRISM** external response IC50 table was **not** joined → `external_drug_response_evidence` = **0 / unavailable** for all; **no fabricated** scores.  
- **LUAD:** **Graph partial** caveat → **caveat_penalty** applied in `ev_composite_0_10` for all 15 rows.  
- **SMILES:** 100% in Step6-0 input → **ADMET structurally feasible** when execution is approved.

## Checklist (1–10)

1. Total candidates: **60**  
2. Per cancer: **15 each** (brca, crc, luad, stad)  
3. `ev_composite_0_10`: min -1.00, max 9.00, mean 2.15  
4. **Top EV (composite) by cancer:**  
     - brca: Temozolomide (id=1375, comp=8.0, internal_rank=2)
  - crc: Fludarabine (id=1813, comp=9.0, internal_rank=5)
  - luad: Veliparib (id=1018, comp=6.0, internal_rank=3)
  - stad: Dacarbazine (id=1815, comp=8.0, internal_rank=2)  
5. Clinical trial score: value_counts in `step7_ev_score_review_summary.csv`  
6. Approved indication score: value_counts in summary CSV  
7. Target/MOA **partial** recovery: **17/60** (28.3%)  
8. External response: **all scores 0** (table unavailable); see impact in EV narrative only  
9. **LUAD caveat:** **15** rows with `caveat_penalty>0` (all LUAD)  
10. **ADMET plan:** **40** = top10×4 (primary), **20** = top5×4 (focused), **60** = full (backup/audit)

## ADMET candidate files

| File | Count | Use |
|------|-------|-----|
| `step7_admet_candidate_top10.csv` | 40 | **Primary** (per-cancer top 10 by EV composite) |
| `step7_admet_candidate_top5.csv` | 20 | **Focused** run / budget-limited |
| `step7_admet_candidate_full60.csv` | 60 | **Full / backup** (aligns with all Step6 top15 drugs) |

Selection within cancer: `ev_composite_0_10` **desc**; tie-break: **internal `rank` (asc)** = higher ensemble list rank first.

**Backup policy:** `internal_rank_backup_note` flags rows with **strong internal rank (≤3)** but **EV composite below median** — keep in **full60** for manual review, not to override ADMET primary without human sign-off.

## Source files consumed

- `step6_ev_evidence_by_candidate.csv`, `by_cancer`, `target_moa_recovery`, `source_availability`, `unavailable_sources`, `evidence_report`, `execution_log`

Step7 ADMET candidate prep completed. Review candidate set before ADMET execution.
