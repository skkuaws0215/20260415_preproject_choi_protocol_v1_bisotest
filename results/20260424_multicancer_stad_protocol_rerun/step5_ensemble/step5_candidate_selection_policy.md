# Step5 Candidate Selection Policy

## Policy Core
- Fixed single-model policy is prohibited.
- Final ML/DL/Graph candidates are selected from all-model robust ranking.
- Leakage violation candidates are excluded.
- Severe overfit candidates are marked as exclusion candidates unless no viable alternative exists.

## Scoring
- Primary metrics: groupcv Spearman, scaffoldcv Spearman, unseen_drug Spearman.
- Secondary metrics: RMSE, MAE, NDCG@30.
- Penalty thresholds:
  - spearman_gap > 0.3 warning
  - spearman_gap > 0.5 severe
  - fold_std > 0.05 warning
  - fold_std > 0.1 severe

## Missing Policy
- ML ElasticNet 2B/2C missing is treated as optional baseline missing.
- Graph LUAD missing 25 is handled by missing-aware policy (no forced retry in this step).

## Required Step5 Caveat
`Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations.`

## Current Selected Candidates (primary/secondary)
modality         model candidate_tier  adjusted_score
      DL   ResidualMLP        primary        0.523213
      DL FTTransformer      secondary        0.513501
   Graph     GraphSAGE        primary        0.423943
   Graph           GAT      secondary        0.348511
      ML       XGBoost        primary        0.553038
      ML      CatBoost      secondary        0.550433
