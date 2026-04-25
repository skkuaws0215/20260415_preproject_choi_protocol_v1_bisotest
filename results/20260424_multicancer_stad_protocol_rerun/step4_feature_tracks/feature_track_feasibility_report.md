# Step4 Feature Track Feasibility Report

- generated_at: `2026-04-24`
- scope: track definition/audit only (no model training)

## 1) Existing Definition Check (2A/2B/2C)

- `MULTI_CANCER_REPRODUCTION_PROTOCOL_20260424_v01.md`: 2A/2B/2C 명시 없음 (Step4 일반 원칙만 존재)
- `step4_model_run_config_fs_a.yaml`: 현재 단일 FS-A track + scaffold split preflight 정의
- `step4_preflight_report.md`: split feasible 상태만 기록 (track-level 비교 없음)
- `fs_a_config.yaml`: unsupervised FS-A 규칙(variance/correlation) 정의
- 기존 근거 문서: `COLON_STEP4_EXECUTION_GUIDE.md`, `run_ml_all.py`, `run_ml_all_stad.py`에서
  - 2A = numeric-only
  - 2B = numeric + SMILES-derived
  - 2C = numeric + context + SMILES
  - GroupCV/Gap 기반 과적합 평가(Train-Val Spearman gap) 확인

## 2) Selected Feature Category Audit (FS-A)

| cancer | selected | expression | pathway | drug_chem | smiles_derived | target | lincs | unknown |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| stad | 3043 | 3042 | 0 | 0 | 1 | 0 | 0 | 0 |
| brca | 3047 | 3046 | 0 | 0 | 1 | 0 | 0 | 0 |
| luad | 2547 | 2546 | 0 | 0 | 1 | 0 | 0 | 0 |
| crc | 3127 | 3126 | 0 | 0 | 1 | 0 | 0 | 0 |

## 3) 2B/2C Candidate Source Audit

| cancer | source | join_key | row_count | columns | coverage | addable_features | overlap_2a | use_2B | use_2C | risk |
|---|---|---|---:|---:|---|---:|---:|---|---|---|
| stad | drug_chem_features.parquet | canonical_drug_id | 295 | 2059 | 1.0000 drug | 2058 | 0 | Yes | No | if overlap high, 2B gain may be limited |
| stad | pair_target_features.parquet | sample_id+canonical_drug_id | 5118 | 12 | 1.0000 pair | 10 | 0 | No | Yes | if overlap high, 2C incremental gain may be limited |
| stad | pair_lincs_features.parquet | sample_id+canonical_drug_id | 5118 | 7 | 1.0000 pair | 5 | 0 | No | Yes | if overlap high, 2C incremental gain may be limited |
| stad | sample_pathway_features.parquet | sample_id | 20 | 1 | 1.0000 sample | 0 | 0 | No | Yes | if overlap high, 2C incremental gain may be limited |
| stad | feature_manifest.json | sample_id+canonical_drug_id | 5118 | 0 | manifest_reference | 0 | 0 | No | No | metadata_only |
| stad | drug_scaffold_map.parquet | canonical_drug_id | 295 | 4 | 1.0000 drug | 0 | 0 | No | No | split_metadata_only |
| brca | drug_chem_features.parquet | canonical_drug_id | 295 | 2059 | 1.0000 drug | 2058 | 0 | Yes | No | if overlap high, 2B gain may be limited |
| brca | pair_target_features.parquet | sample_id+canonical_drug_id | 7730 | 12 | 1.0000 pair | 10 | 0 | No | Yes | if overlap high, 2C incremental gain may be limited |
| brca | pair_lincs_features.parquet | sample_id+canonical_drug_id | 7730 | 7 | 1.0000 pair | 5 | 0 | No | Yes | if overlap high, 2C incremental gain may be limited |
| brca | sample_pathway_features.parquet | sample_id | 1150 | 1 | 1.0000 sample | 0 | 0 | No | Yes | if overlap high, 2C incremental gain may be limited |
| brca | feature_manifest.json | sample_id+canonical_drug_id | 7730 | 0 | manifest_reference | 0 | 0 | No | No | metadata_only |
| brca | drug_scaffold_map.parquet | canonical_drug_id | 295 | 4 | 1.0000 drug | 0 | 0 | No | No | split_metadata_only |
| luad | drug_chem_features.parquet | canonical_drug_id | 295 | 2059 | 1.0000 drug | 2058 | 0 | Yes | No | if overlap high, 2B gain may be limited |
| luad | pair_target_features.parquet | sample_id+canonical_drug_id | 125427 | 12 | 1.0000 pair | 10 | 0 | No | Yes | if overlap high, 2C incremental gain may be limited |
| luad | pair_lincs_features.parquet | sample_id+canonical_drug_id | 125427 | 7 | 1.0000 pair | 5 | 0 | No | Yes | if overlap high, 2C incremental gain may be limited |
| luad | sample_pathway_features.parquet | sample_id | 1150 | 1 | 1.0000 sample | 0 | 0 | No | Yes | if overlap high, 2C incremental gain may be limited |
| luad | feature_manifest.json | sample_id+canonical_drug_id | 125427 | 0 | manifest_reference | 0 | 0 | No | No | metadata_only |
| luad | drug_scaffold_map.parquet | canonical_drug_id | 295 | 4 | 1.0000 drug | 0 | 0 | No | No | split_metadata_only |
| crc | drug_chem_features.parquet | canonical_drug_id | 295 | 2059 | 1.0000 drug | 2058 | 0 | Yes | No | if overlap high, 2B gain may be limited |
| crc | pair_target_features.parquet | sample_id+canonical_drug_id | 9692 | 12 | 1.0000 pair | 10 | 0 | No | Yes | if overlap high, 2C incremental gain may be limited |
| crc | pair_lincs_features.parquet | sample_id+canonical_drug_id | 9692 | 7 | 1.0000 pair | 5 | 0 | No | Yes | if overlap high, 2C incremental gain may be limited |
| crc | sample_pathway_features.parquet | sample_id | 35 | 1 | 1.0000 sample | 0 | 0 | No | Yes | if overlap high, 2C incremental gain may be limited |
| crc | feature_manifest.json | sample_id+canonical_drug_id | 9692 | 0 | manifest_reference | 0 | 0 | No | No | metadata_only |
| crc | drug_scaffold_map.parquet | canonical_drug_id | 295 | 4 | 1.0000 drug | 0 | 0 | No | No | split_metadata_only |

## 4) Decision / Next Config Change

- 2A는 현재 `features_slim_with_scaffold` + FS-A selected numeric features로 확정 가능
- 2B/2C는 후보 소스 존재하며 join key/coverage 확인됨
- 단, 다수 feature가 2A에 이미 포함되어 있어 2B/2C는 `중복 제거 + incremental feature only` 규칙 필요
- raw `canonical_smiles`는 model feature로 금지, `scaffold_id`는 split metadata only
- metric set은 `metric_definition_step4.yaml`로 별도 고정
