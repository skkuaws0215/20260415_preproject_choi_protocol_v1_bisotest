# Integrated Step4 Dashboard

## Run

```bash
streamlit run "results/20260424_multicancer_stad_protocol_rerun/step4_models/fs_a_stad_baseline/integrated_step4_audit/integrated_step4_dashboard.py"
```

## Data Sources

- `integrated_result_coverage.csv`
- `integrated_metrics_flattened.csv`
- `integrated_missing_results.csv`
- `integrated_leakage_warnings.csv`
- `integrated_overfit_warnings.csv`
- `integrated_modality_best_by_eval.csv`
- `integrated_robust_model_ranking.csv`

## Mandatory Caveat

`Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations.`

