# Integrated Step4 Audit Report

## Consolidated Status
- ML: near-full (320/360). Missing 40 are optional ElasticNet 2B/2C baseline results.
- DL: full complete (420/420).
- Graph: partial-full (95/120). Missing 25 are LUAD-only partial missing.
- Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations.

## Coverage and Missing Classification
- ML: 320/360 (near-full) - missing: ElasticNet 2B/2C optional baseline 40
- DL: 420/420 (full) - complete 420/420
- Graph: 95/120 (partial-full) - missing: LUAD 25 due to local computation bottleneck
- ML missing classification: optional ElasticNet 2B/2C baseline missing.
- Graph missing classification: LUAD 25 partial missing due to local computation bottleneck.

## Metrics Schema Compatibility
- Checked fields: core_mean, overfit, ranking_mean, split_leakage_mean, label_drift_mean, imputation_summary.
- ML: core=1.00, overfit=1.00, ranking=1.00, leakage=1.00, drift=1.00, imputation=0.00
- DL: core=1.00, overfit=1.00, ranking=1.00, leakage=1.00, drift=1.00, imputation=1.00
- Graph: core=1.00, overfit=1.00, ranking=1.00, leakage=1.00, drift=1.00, imputation=1.00

## Leakage and Overfit Checks
- Strict leakage violations (groupcv/unseen_drug drug overlap, scaffoldcv scaffold overlap): 0
- Holdout overlap is not treated as strict violation.
- Overfit warnings: 217, severe: 106
- Thresholds: spearman_gap > 0.3 warning, > 0.5 severe; fold_std > 0.05 warning, > 0.1 severe.

## Model/Input Profile Audit
- Config profiles seen in integrated results: dl_7model_full, existing_result, graph_2model_full, light_resume
- Expected profile map: existing_result=present, light_resume=present, dl_full=not_seen, graph_full=not_seen, graph_nan_repair=not_seen
- Imputation policy: model_input_only with NaN/Inf sanitized at model input scope where configured.

## Modality Best and Robust Ranking
- Modality-wise best-by-eval table exported to integrated_modality_best_by_eval.csv.
- All-model robust ranking exported to integrated_robust_model_ranking.csv.
- Primary ranking signal: groupcv/scaffoldcv/unseen_drug Spearman.
- Secondary signals: RMSE, MAE, NDCG@30.
- Penalties: spearman_gap, fold_std.
- Exclusion rule: leakage violation combos are excluded from robust ranking.
- CatBoost or any fixed single-model slot policy is not used.

## Step5 Readiness
- Readiness decision: ready_with_caveat
- Step5 should proceed only based on integrated audit outputs.
- Integrated interpretation should use ML + DL + Graph partial with LUAD Graph caveat explicitly marked.
- Mandatory Step5 note: Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations.
