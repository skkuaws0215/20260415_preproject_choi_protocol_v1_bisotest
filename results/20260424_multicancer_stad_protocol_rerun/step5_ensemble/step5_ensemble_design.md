# Step5 Ensemble Design (Pre-Execution)

- Scope: design and preflight only (no ensemble computation executed).
- Source: integrated Step4 audit outputs under `step4_models/fs_a_stad_baseline/integrated_step4_audit/`.

## Current Inputs
- ML: 320/360 (near-full, optional ElasticNet 2B/2C missing)
- DL: 420/420 (full)
- Graph: 95/120 (partial-full, LUAD missing 25)

Mandatory note:
`Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations.`

## Candidate Selection Logic
1. No fixed model slot.
2. Use all-model robust ranking as baseline.
3. Primary score axis: groupcv/scaffoldcv/unseen_drug Spearman.
4. Secondary: RMSE, MAE, NDCG@30.
5. Penalty: overfit gap/fold instability.
6. Exclude leakage-violating candidates and missing-essential-predictions candidates.

## Ensemble Strategy (Design Only)
1. Simple mean ensemble.
2. Rank mean ensemble.
3. Robust weighted ensemble (robust_score with penalty multipliers).
4. Missing-aware ensemble:
   - if Graph is missing for a combo (e.g. LUAD partial), use ML+DL only
   - always record available modality count per prediction bundle

## Preflight Outcome
- checked combos: 335
- essential prediction ready: 335
- blocked issues: 0
- leakage violations in integrated audit: 0

## Gate
- Step5 execution gate: proceed only after candidate table review and caveat acceptance.
