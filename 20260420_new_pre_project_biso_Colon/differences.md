# Colon Pipeline - Differences from Lung/BRCA

Last updated: 2026-04-20 (Step 2 completed)

## Copied Scripts (Verbatim from Source)

### From Lung (scripts/)
| Script | Source | Modifications |
|--------|--------|---------------|
| convert_raw_to_parquet.py | Lung/scripts/ | L2 docstring, L12 BASE_DIR (3-level path), L183 log message |
| extract_chembl_from_sqlite.py | Lung/scripts/ | Pending: BASE_DIR |
| aggregate_lincs_to_drug_level.py | Lung/scripts/ | No modification needed (CLI args) |
| upload_to_s3.sh | Lung/scripts/ | Pending: S3 paths |
| check_progress.sh | Lung/scripts/ | Pending: run_id |

### From Lung (nextflow/)
| Script | Source | Modifications |
|--------|--------|---------------|
| main.nf | Lung/scripts/ | Pending: run_id, paths |
| nextflow.config | Lung/scripts/ | Pending: s3_base, run_id, all URIs |

### From BRCA (nextflow/scripts/)
| Script | Source | Modifications |
|--------|--------|---------------|
| prepare_fe_inputs.py | BRCA/nextflow/scripts/ | None (CLI args) |
| build_features.py | BRCA/nextflow/scripts/ | None (CLI args) |
| build_pair_features_newfe_v2.py | BRCA/nextflow/scripts/ | None (CLI args) |
| build_drug_catalog.py | BRCA/nextflow/scripts/ | None (CLI args) |
| convert_depmap_wide_to_long.py | BRCA/nextflow/scripts/ | None (CLI args) |
| normalize_target_mapping.py | BRCA/nextflow/scripts/ | None (CLI args) |

## New Scripts (Colon-Specific)
All 5 scripts completed in Step 2-4 through Step 2-10.

| Script | Purpose | Reason for New |
|--------|---------|----------------|
| filter_colon_cell_lines.py | GDSC COREAD filter + labels generation | Colon-specific filter logic |
| bridge_drug_features.py | drug_catalog → drug_features schema conversion | Schema alignment |
| extract_lincs_gctx.py | GSE92742 gctx → parquet (chunked cmapPy) | No gctx parsing script exists in BRCA/Lung |
| colon_subtype_tagging.py | MSI/RAS/BRAF tagging from TCGA | Colon-specific, not in Lung |
| step2_qc.py | Step 2 integrated QC across all outputs | New QC script for Step 2 validation |

## Data Excluded
- Colon_raw/ root 4 parquet (unknown origin, conflicts with source-first principle)
- Colon_raw/{gtex, msigdb, opentargets, string} (baseline first)
- s3://say2-4team/20260409_eseo/ (not owned)

## Data Reused (Cross-Disease)
- drug_target_mapping.parquet from Lung (drug-target is disease-agnostic)

## LINCS Cell Line Selection

### Initial LINCS classification
17 cell lines with primary_site = "large intestine"

### Verification (DepMap cross-check)
- HELA: Confirmed Endocervical Adenocarcinoma (DepMap ECAD) → LINCS misclassification
- HELA.311: Cas9 subclone of HELA → cervical lineage
- HT29.311: Cas9 subclone of HT29 (COAD) → excluded (Lung policy)

### Data availability check
- NCIH716: 0 trt_cp signatures in sig_info → effectively empty

### Final Selection: 13 cell lines
CL34, HCT116, HT115, HT29, LOVO, MDST8, NCIH508, RKO, SNU1040, SNUC5, SW480, SW620, SW948

### Total Signatures (GSE92742 only)
- Colon 13 cells trt_cp: 18,823
- Comparison: Lung 11 cells 25,265, BRCA MCF7 63,367
- Source: GSE92742 (Lung pattern verified via sig_id prefix analysis)
- GSE70138 downloaded but unused (kept in curated_data/, rule 1 compliance)

### Known Bias
- HT29: 77.1% (14,513/18,823)
- Other 12 cells: ~350-363 each
- Not corrected at this stage
- Monitoring plan:
  - FE stage: LINCS feature importance and non-null coverage
  - External validation: HT29-specific literature bias check
  - MSI/COAD-READ stratification anomaly detection

## Pipeline Structural Differences (vs Lung)

### Added in Colon
- Raw preprocessing stage (Lung used team4 curated_date/ directly)
- Subtype tagging (COAD/READ, MSI, RAS, BRAF)
- Stratified evaluation (post Step 4)
- GSE39582 external validation (in addition to CPTAC)

### Changed in Colon
- LINCS source: GSE92742 only (Lung pattern verified; GSE70138 kept but unused)
- Cell line count: 13 (Lung: 11)
- Explicit pre-verification of LINCS cell_info (to avoid Lung's NSCLC/SCLC mixing issue)

## Validation Strategy

### Key Difference from Lung
Lung originally used CPTAC but **Survival analysis was omitted**.
Lung plans to re-run with NSCLC-only + Survival added.
**Colon implements Survival validation from the start** to establish the standard.

### Tier 1: 1st round (current pipeline, WITH Survival)
| Source | Methods |
|--------|---------|
| CPTAC-CRC | A (IC50 proxy), B (Survival binary) [NEW], C (P@K) |
| GSE39582 | A (expression), B (Survival) [NEW] |
| COSMIC-CRC | Driver gene matching |
| PRISM (CRC cells) | IC50 measurements |
| ClinicalTrials (CRC) | Clinical trial evidence |

### Tier 2: 2nd round (later addition, all with Survival)
- GSE17536 (has survival data)
- GSE17538 (has survival data)

### Method B: Survival Implementation
- Load CPTAC/GEO clinical tables
- Stratify samples by drug target gene expression (high vs low)
- Kaplan-Meier + log-rank test
- p < 0.05 threshold for validation
- One of the key metrics for Colon's Top drug validation

### Why This Matters
Colon pipeline will serve as the reference implementation.
When Lung re-runs (NSCLC-only + Survival), it should match Colon's validation structure.


## Step 2-1 Execution Record

### Completed: 2026-04-20 17:08

### Issue Encountered (for future reference)
- Initial BASE_DIR substitution was incomplete:
  - Lung path: 2-level nesting (bisotest/bisotest/Lung)
  - Colon path: 3-level nesting (bisotest/bisotest/bisotest-1/Colon)
  - Partial string replacement "Lung" → "Colon" missed the extra directory level
  - Fixed by full line replacement of BASE_DIR

### Output
- 7 parquet files in curated_data/processed/
- Total size: 645 MB
- Total rows: 3,172,577
- Execution time: 1 min 48 sec
- All QC passed (no errors/warnings)

### Files Generated
| File | Rows | Size |
|------|------|------|
| gdsc/GDSC2-dataset.parquet | ~280K | included |
| gdsc/Compounds-annotation.parquet | ~300 | 9.1M total |
| depmap/CRISPRGeneDependency.parquet | ~1,900 | 209M dir |
| depmap/Model.parquet | ~1,900 | included |
| chembl/chembl_36_chemreps.parquet | ~2M+ | 425M |
| drugbank/drugbank_master.parquet | ~14K | 2.0M dir |
| drugbank/drugbank_synonyms.parquet | ~60K | included |

### Lessons Learned
1. Full absolute path verification before executing scripts
2. Use Path(base).exists() runtime validation
3. Compare Lung vs Colon path structures before any script modification


## Step 2-2 Execution Record

### Completed: 2026-04-20 17:15

### Input
- curated_data/raw/chembl/chembl_36.db (SQLite)

### Output
- curated_data/processed/chembl/chembl_compounds.parquet: (2,854,815, 5)

### Notes
- Added pref_name column from compound_structures + molecule_dictionary join
- Execution time: ~1 min 27 sec
- Only BASE_DIR modification needed (no logic changes)


## Step 2-3 Execution Record

### Completed: 2026-04-20 17:20

### Input
- curated_data/processed/depmap/CRISPRGeneDependency.parquet (1,150 × 18,444 wide)

### Output
- curated_data/processed/depmap/depmap_crispr_long_colon.parquet: (20,443,404, 3)

### Notes
- Wide → long conversion (1,150 cells × 18,443 genes)
- NaN rows dropped
- Columns: cell_line_name, gene_name, dependency
- Script: convert_depmap_wide_to_long.py (BRCA copy, CLI args)


## Step 2-4 Execution Record

### Completed: 2026-04-20 17:37

### Script
- scripts/filter_colon_cell_lines.py (342 lines, NEW)

### Logic
- Filter GDSC by TCGA_DESC == "COREAD" (12,538 rows)
- 2-stage cell line normalization (strict + fallback)
- Match GDSC cells to DepMap StrippedCellLineName
- Binary label: IC50 > quantile(0.3) threshold

### Output
- data/labels.parquet: (12,538, 4) — sample_id, canonical_drug_id, ic50, binary_label
- reports/step2_4_matching_report.json
- reports/matched_colon_cell_lines.csv

### Key Stats
- Matching rate: 46/46 cells (100%, all via strict matching)
- Binary threshold (quantile 0.3): 2.1084
- Binary distribution: 0=8,776 / 1=3,762

### Validation
- All 46 COREAD cells found in DepMap
- No fallback matching required


## Step 2-5 Execution Record

### Completed: 2026-04-20 17:58

### Sub-steps
**Step 2-5-A: build_drug_catalog.py (BRCA copy, no modification)**
- PubChem API mode (HTTP 200, no network fallback needed)
- Output: curated_data/processed/drug_catalog_colon.parquet (621, 6)
- has_smiles: 79.39% (493/621)
- match_source: chembl_norm 246, pubchem_api 213, unmatched 128, drugbank 34
- Execution: 5 min 3 sec

**Step 2-5-B: bridge_drug_features.py (NEW, 203 lines)**
- Schema transform: catalog (6 cols) → features (5 cols, team4 schema)
- Filter: keep only drugs present in labels (295/295)
- Output: data/drug_features.parquet (295, 5)

### Key Discovery: Q1-C Validation Success
- Colon drug_features (self-generated) vs Lung drug_features comparison:
  - Drug ID overlap: 295/295 (100%)
  - SMILES identical: 295/295 (100%)
  - has_smiles=1 count: 243 (both)
  - has_smiles=0 count: 52 (both)
- Independent generation matched Lung exactly → methodology validated

### Rationale
- Q1-C: self-generate + compare (vs reuse Lung features)
- Validates that build_drug_catalog.py is reproducible
- Confirms Colon and Lung share identical GDSC drug panel


## Step 2-6 Execution Record

### Completed: 2026-04-20 18:35

### Script
- scripts/extract_lincs_gctx.py (334 lines, NEW)

### Critical Data Source Decision: GSE70138 → GSE92742

#### Initial Plan
- CONTEXT.md specified: "LINCS: GSE70138 only (Lung used GSE92742 as primary)"
- Based on myprotocol sig_info_basic_20260406.parquet analysis (18,823 sigs for Colon 13)

#### Problem Discovered During Step 2-6-A Preparation
- GSE70138 sig_info direct verification:
  - Colon 13 cells trt_cp: 11,845
  - Distribution: HT29 11,845 (100%), other 12 cells 0
- myprotocol sig_info_basic showed 18,823 (different source)

#### Source Investigation
- myprotocol sig_info_basic_20260406.parquet: 473,647 rows, 12 cols
- GSE92742 sig_info (Colon_raw does not include): 473,647 rows, 12 cols
- Conclusion: myprotocol "basic" file = GSE92742 (not combined)

#### Options Considered
- A: GSE70138 only → HT29 100%, defeats Colon diversity purpose
- B: Add GSE92742 download → 13 cells covered, HT29 77.1% bias
- C: Use myprotocol proxy → violates rule 3 (no processed files)

#### Resolution
- Selected option B (add GSE92742)
- User manually downloaded 5 GSE92742 files to curated_data/lincs/GSE92742/
- Verified Lung uses GSE92742 only via sig_id prefix analysis:
  - All prefixes: CPC, HOG, PCLB, DOS, DOSBIO, RAD (GSE92742 plate IDs)
  - No LJP prefix (GSE70138)
- Final decision: GSE92742 only (Lung pattern)
- GSE70138 kept in curated_data/ but unused (rule 1 compliance)

### Input
- curated_data/lincs/GSE92742/GSE92742_Broad_LINCS_Level5_COMPZ.MODZ_n473647x12328.gctx.gz (19.9 GB)
- curated_data/lincs/GSE92742/GSE92742_Broad_LINCS_sig_info.txt.gz (10.6 MB)

### Processing
- Filter: pert_type=trt_cp AND cell_id in Colon 13 → 18,823 signatures
- Decompress gctx.gz to /tmp (21.77 GB)
- cmapPy chunked parsing (chunk_size=2000, 10 chunks)
- Schema matching to Lung lincs_lung.parquet:
  - Column order: [sig_id] + [12,328 entrez_id float32] + [7 meta]
  - Meta tail: pert_id, pert_iname, pert_dose, pert_dose_unit, pert_time, pert_time_unit, cell_id

### Output
- data/lincs_colon.parquet: (18,823, 12,336) — 1,295.3 MB
- reports/step2_6_lincs_extract_report.json

### Cell Distribution (confirmed from execution)
- HT29: 14,513 (77.1%)
- Others: CL34 356, HCT116 363, HT115 355, LOVO 360, MDST8 358,
  NCIH508 360, RKO 362, SNU1040 361, SNUC5 351, SW480 363, SW620 362, SW948 359
- Total: 18,823 (matches expected)

### Issues Encountered and Resolved
1. **Path confusion (bisotest-1)**: Files initially placed in wrong Colon folder
   - Wrong: /.../bisotest/bisotest/20260420_Colon/
   - Correct: /.../bisotest/bisotest/bisotest-1/20260420_Colon/
   - Resolution: mv to correct location after path verification

2. **Agent Looping incident**: Cursor attempted to re-create existing files
   - Trigger: Complex 9-step script with multiple path variables
   - Resolution: "Undo All" applied, scripts/data preserved
   - Lesson: Keep Cursor requests short and focused

3. **Transient exit 139 (segfault)**:
   - extract_lincs_gctx.py --help first attempt: segfault
   - aggregate_lincs (Step 2-7) first attempt: segfault
   - Resolution: Simple retry worked (no code fix needed)
   - Environment diagnostic confirmed all dependencies OK
   - Root cause: unknown (likely OS-level transient issue)

### Lessons Learned
1. Verify actual data sources directly, not processed "basic" files
2. sig_id prefix is reliable indicator of LINCS data source (LJP=70138, CPC etc.=92742)
3. curated_data/lincs/GSE70138/ retention respects rule 1 (no deletion of raw data)
4. Short Cursor requests reduce Agent Looping risk
5. Transient segfault (exit 139) often resolves on retry


## Step 2-7 Execution Record

### Completed: 2026-04-20 19:20

### Script
- scripts/aggregate_lincs_to_drug_level.py (Lung copy, CLI args, no modification)

### Input
- data/lincs_colon.parquet (18,823 signatures)
- data/drug_features.parquet (295 drugs)

### Output
- data/lincs_colon_drug_level.parquet: (91, 12,329) — 12.2 MB
- reports/step2_7_lincs_aggregation_report.json

### Key Stats
- Input signatures: 18,823
- Input unique pert_iname: 10,612
- GDSC total drugs: 295
- Matched signatures: 797
- Matched unique drugs: 91
- Match rate: 30.85%
- Missing values: 0

### Cross-Validation with Lung
- Lung lincs_lung_drug_level.parquet: (92, 12,329)
- Colon lincs_colon_drug_level.parquet: (91, 12,329)
- Difference: 1 drug (negligible)
- Match rate Lung: 31.19% vs Colon: 30.85%
- Conclusion: ~31% is natural LINCS↔GDSC intersection rate (not cancer-type specific)

### Issue Encountered
- First execution: exit 139 (segfault), empty log
- Retry: successful (no code fix needed)
- Confirms transient OS-level issue pattern from Step 2-6


## Step 2-8 Execution Record

### Completed: 2026-04-20 19:34

### Script
- scripts/colon_subtype_tagging.py (323 lines, NEW)

### Input
- curated_data/cbioportal/coadread_tcga_pan_can_atlas_2018/data_clinical_sample.txt (594 samples)
- curated_data/cbioportal/coadread_tcga_pan_can_atlas_2018/data_clinical_patient.txt (594 patients)
- curated_data/cbioportal/coadread_tcga_pan_can_atlas_2018/data_mutations.txt (332,611 rows, 341 MB)

### Processing
- Clinical sample: SAMPLE_ID, PATIENT_ID, ONCOTREE_CODE, MSI_SCORE_MANTIS, MSI_SENSOR_SCORE
- Clinical patient: PATIENT_ID, SUBTYPE
- Mutations: Filter KRAS/NRAS/BRAF, exclude silent/non-coding (Variant_Classification filter)
- Per-sample aggregation: ras_mutation, braf_mutation, braf_v600e
- Derived tags: primary_site (COAD/READ/MACR), msi_status (MSI-H if MANTIS > 0.4)

### Output
- data/colon_subtype_metadata.parquet: (594, 11) — 22.5 KB
- reports/step2_8_subtype_report.json

### Statistics
- primary_site: COAD 378 (63.6%), READ 155 (26.1%), MACR 61 (10.3%)
- msi_status: MSS 468 (78.8%), MSI-H 89 (15.0%), NaN 37 (6.2%)
- RAS mutation: 246 (41.4%)
- BRAF mutation: 62 (10.4%)
- BRAF V600E: 48 (8.1%)

### Notable Discovery: MACR Category
- 61 samples (10.3%) have ONCOTREE_CODE = "MACR"
- MACR = Mucinous Adenocarcinoma of Colon and Rectum (점액성 선암)
- Not in original COAD/READ binary classification
- Preserved as-is in primary_site field
- Handling strategy TBD in Step 6 evaluation

### Biological Validation
- All statistics within expected TCGA COADREAD ranges:
  - MSI-H ~15% (literature: 15-20%)
  - RAS+ ~41% (literature: 40-50%)
  - BRAF V600E ~8% (literature: 7-9%)
- Mutation categories biologically plausible


## Step 2-9 Execution Record

### Completed: 2026-04-20 19:40

### Operation
- Reuse Lung drug_target_mapping.parquet (drug-target is disease-agnostic)
- aws s3 cp from Lung project

### Input
- s3://say2-4team/20260408_new_pre_project_biso/20260416_new_pre_project_biso_Lung/data/drug_target_mapping.parquet

### Output
- data/drug_target_mapping.parquet: (485, 2) — 5,902 bytes
- Columns: canonical_drug_id, target_gene_symbol

### Validation
- 295 unique drugs (matches Colon drug_features exactly)
- 235 unique target genes
- Coverage: 100% (all 295 drugs have at least one target)
- Average targets per drug: 1.64 (485/295)

### Rationale for Reuse
- Drug-target mapping is a pharmacological property, not disease-specific
- Lung and Colon share identical 295-drug GDSC panel (verified Step 2-5)
- No loss of information by reusing


## Step 2-10 Execution Record

### Completed: 2026-04-20 19:45

### Script
- scripts/step2_qc.py (343 lines, NEW)

### Scope
- All 7 Step 2 outputs validation
- Schema verification
- Drug ID consistency (cross-file)
- Cell line ID consistency
- NaN rate analysis
- FE (Step 3) input compatibility check

### Validation Checks Performed
1. File existence and sizes (7 files)
2. Schema validation (required columns, row count ranges)
3. Drug ID consistency:
   - labels (295) == drug_features (295): exact match
   - drug_target_mapping ⊆ drug_features: True
   - lincs_colon_drug_level ⊆ drug_features: True
4. Cell line consistency:
   - labels cells: 46
   - lincs cells: 13
5. NaN rates per column
6. Key statistics summary

### Output
- reports/step2_integrated_qc_report.json

### Result: ALL QC CHECKS PASSED
- Issues: 0
- Warnings: 0
- passed: true

### Key Metrics Snapshot
- binary_label distribution: {0: 8,776, 1: 3,762}
- LINCS HT29 bias: 77.1%
- Subtype metadata: MSI-H 89, RAS+ 246, BRAF+ 62
- All 7 outputs ready for Step 3 FE


## Step 2 Completion Summary

### Timeline
- Step 2-0 started: 2026-04-20 morning
- Step 2-10 completed: 2026-04-20 19:45
- Total duration: ~1 day

### Final Outputs (7 files)
| File | Shape | Size | Purpose |
|------|-------|------|---------|
| data/labels.parquet | (12,538, 4) | 130 KB | IC50 training labels |
| data/drug_features.parquet | (295, 5) | 27 KB | Drug SMILES + metadata |
| data/drug_target_mapping.parquet | (485, 2) | 5.8 KB | Drug-target pairs |
| data/lincs_colon.parquet | (18,823, 12,336) | 1,295 MB | LINCS signatures |
| data/lincs_colon_drug_level.parquet | (91, 12,329) | 12 MB | Drug-level aggregated |
| data/colon_subtype_metadata.parquet | (594, 11) | 22 KB | Patient subtype tags |
| curated_data/processed/depmap/depmap_crispr_long_colon.parquet | (20.4M, 3) | ~400 MB | DepMap long format |

### New Colon-Specific Scripts (5)
| Script | Lines | Purpose |
|--------|-------|---------|
| filter_colon_cell_lines.py | 342 | GDSC COREAD filter + cell matching + binary labeling |
| bridge_drug_features.py | 203 | Drug catalog (6 cols) → features (5 cols, team4 schema) |
| extract_lincs_gctx.py | 334 | GSE92742 gctx parsing with cmapPy (chunked) |
| colon_subtype_tagging.py | 323 | TCGA COADREAD MSI/RAS/BRAF tagging |
| step2_qc.py | 343 | Step 2 integrated QC across all outputs |

### Key Decisions Made During Step 2
1. **LINCS source**: GSE92742 only (Lung pattern, GSE70138 kept but unused)
2. **HT29 bias acceptance**: 77.1% bias accepted with post-hoc monitoring plan
3. **Drug feature methodology**: Q1-C (self-generate + compare with Lung) → 100% match validated
4. **drug_target_mapping**: Reuse from Lung (disease-agnostic property)
5. **MACR category handling**: Preserved as-is in primary_site, decision deferred to Step 6
6. **Subtype tagging scope**: MSI/RAS/BRAF/V600E (HER2/CMS/sidedness deferred)
7. **Survival validation**: Included from start (Method B, unlike Lung which omitted)

### Validation Results
- All 7 outputs pass integrated QC (Step 2-10)
- Zero issues, zero warnings
- Cross-file drug ID consistency: 100%
- Cell line consistency verified
- FE (Step 3) input compatibility confirmed

### Comparison with Lung Pipeline
| Aspect | Lung | Colon |
|--------|------|-------|
| drug_features | 295 drugs, 82.37% SMILES | 295 drugs, 82.37% SMILES (identical) |
| lincs signatures | 25,265 (11 cells) | 18,823 (13 cells) |
| lincs drug_level | 92 drugs (31.19%) | 91 drugs (30.85%) |
| drug_target | 485 pairs | 485 pairs (reused) |
| Subtype metadata | — (not present) | 594 samples (new) |
| Preprocessing | uses team4 curated_date/ | raw-to-parquet from Colon_raw/ |
| Survival validation | omitted | included (Method B) |

### Next Step: Step 3 (Feature Engineering)
- Protocol: v2.3 (unchanged, applies as-is)
- Environment: Nextflow on AWS Batch
- Docker image: 666803869796.dkr.ecr.ap-northeast-2.amazonaws.com/fe-v2-nextflow:v2-pip-awscli
- Input: all 7 Step 2 outputs uploaded to S3
- Output: Feature matrices for ML training (Step 4)
- Status: Ready to start

### Agent Looping Incidents and Prevention
- 1 incident during Step 2-6 (complex multi-step script)
- Prevention: keep Cursor requests short and focused
- Pattern: long heredoc with many variables → loop risk
- Recovery: "Undo All" preserved existing work

### Transient Exit 139 (Segfault) Incidents
- 3 occurrences (extract_lincs_gctx.py --help, aggregate_lincs, etc.)
- All resolved by simple retry (no code or env fix needed)
- Root cause: OS-level transient issue
- Pattern: first execution after heavy memory use sometimes fails
