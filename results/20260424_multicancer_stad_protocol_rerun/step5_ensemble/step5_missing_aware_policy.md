# Step5 Missing-Aware Ensemble Policy

## Objective
Enable ensemble scoring despite partial Graph availability (LUAD missing 25 combos).

## Rules
1. If ML, DL, Graph all available: run 3-modality ensemble candidates (simple/rank/robust-weighted).
2. If Graph missing and ML+DL available: run ML+DL fallback ensemble and mark `available_modality_count=2`.
3. If any modality prediction is missing essential keys/columns: mark combo as blocked.
4. Never silently impute missing modality predictions.

## Join Contract
- Join keys: `sample_id`, `canonical_drug_id`
- Required prediction column: `y_pred`
- Required target column: one of `y_true`, `sensitivity_score`, `target`
- Prediction format: CSV or Parquet accepted

## LUAD Graph Partial Handling
- LUAD Graph missing rows detected: 25
- Step5 interpretation must preserve caveat and avoid overclaiming Graph contribution for LUAD.

## Output Annotation Requirement
- All Step5 outputs must include:
  - `graph_component_partial_luad=true/false`
  - `available_modality_count`
  - mandatory caveat text when LUAD involved
