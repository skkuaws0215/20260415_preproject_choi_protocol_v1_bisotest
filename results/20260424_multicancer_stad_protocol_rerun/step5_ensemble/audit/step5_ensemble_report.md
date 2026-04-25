# Step5 Ensemble Report

- Step5는 ready_with_caveat 상태에서 수행됨.
- ML은 near-full 상태이며 ElasticNet 2B/2C optional baseline 40개가 누락됨.
- DL은 420/420 full complete 상태임.
- Graph는 95/120 partial-full 상태임.
- Graph component is partial for LUAD due to missing LUAD 2-model graph evaluations.
- Graph missing 조합에서는 missing-aware ensemble을 적용함.
- 특정 모델 고정 없이 all-model robust ranking 기반 후보를 사용함.
- strict leakage violation은 Step4 통합 audit 기준 0건.
- Step5 join key는 sample_id/canonical_drug_id를 string으로 정규화하여 수행함.
- Step5 결과는 외부검증/ADMET 전 내부 앙상블 후보 선정 결과임.
- Step5 이후에는 외부검증/ADMET/최종 후보 랭킹으로 넘어가기 전에 결과 리뷰가 필요함.

## Execution Scope
- Ensemble methods: simple_mean, rank_mean, robust_weighted
- Prediction rows: 1505658
- Metric rows: 180
- Error rows: 0

## Missing-Aware Handling
- Combos with missing modalities: 10
- LUAD graph-missing combos flagged: 10

## Integrity Checks
- Prediction row count and target row count consistency: True
- Component prediction join success: True
- Join keys: sample_id + canonical_drug_id
- Target contract: sensitivity_score (higher_is_more_sensitive)
- Leakage check file generated: step5_ensemble_leakage_check.csv
- Overfit/severe flags file generated: step5_ensemble_overfit_flags.csv

## Method Comparison (mean)
- rank_mean: spearman=0.4687, rmse=3.5745, mae=3.1233, ndcg@30=0.3317
- robust_weighted: spearman=0.4650, rmse=2.2504, mae=1.7069, ndcg@30=0.3293
- simple_mean: spearman=0.4627, rmse=2.2580, mae=1.7121, ndcg@30=0.3312
