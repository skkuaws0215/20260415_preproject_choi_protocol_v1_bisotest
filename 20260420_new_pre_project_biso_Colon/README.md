# 20260420_new_pre_project_biso_Colon

Drug repurposing pipeline for Colorectal Cancer (COAD+READ).

## Base
- BRCA myprotocol + Lung pipeline extension
- Option B (moderate expansion)

## Start Date
2026-04-20

## Pipeline Stages

### Completed
- [x] Step 1: Raw data download (~19GB)
- [x] Step 2-0: Environment setup + script copy
- [x] Step 2-1: Raw → Parquet format conversion
- [x] Step 2-2: ChEMBL SQLite extraction
- [x] Step 2-3: DepMap wide → long conversion
- [x] Step 2-4: Colon cell line filter + labels generation (new)
- [x] Step 2-5: Drug catalog + Bridge
- [x] Step 2-6: LINCS gctx → parquet (new, GSE92742)
- [x] Step 2-7: LINCS drug-level aggregation
- [x] Step 2-8: Subtype tagging (new)
- [x] Step 2-9: drug_target_mapping reuse (from Lung)
- [x] Step 2-10: Integrated QC (ALL PASSED)

### In Progress
- (Step 2 complete, Step 3 not yet started)

### Upcoming
- [ ] Step 3: Feature Engineering (Nextflow + AWS Batch)
- [ ] Step 3.5: Feature Selection
- [ ] Step 4: Model training (15 models × 3 inputs × 3 evaluations)
- [ ] Step 5: Ensemble
- [ ] Step 6: Multi-objective ranking + External validation
- [ ] Step 7: ADMET Gate
- [ ] Step 8: Neo4j loading

## Directory Structure    20260420_new_pre_project_biso_Colon/
├── curated_data/           # Raw data (read-only)
├── data/                   # Processed outputs (Step 2 final)
├── scripts/                # Host-executable scripts
├── nextflow/
│   ├── main.nf
│   ├── nextflow.config
│   └── scripts/            # Docker-executed scripts
├── configs/
│   ├── CONTEXT.md          # Full project context
│   └── backup/             # Initial file backups
├── logs/
├── reports/
├── results/
├── .cursorrules            # Cursor AI rules
├── differences.md          # Differences from Lung/BRCA
└── README.md               # This file

## Key Policies

### LINCS Cell Lines (13)
CL34, HCT116, HT115, HT29, LOVO, MDST8, NCIH508, RKO, SNU1040, SNUC5, SW480, SW620, SW948

### Subtype Tagging
- Evaluation: COAD/READ, MSI
- Metadata only: RAS, BRAF, BRAF V600E
- Additional category discovered: MACR (Mucinous Adenocarcinoma, 10.3%)
- Skipped: HER2, CMS, sidedness

### External Validation (Tier 1)
CPTAC-CRC, GSE39582, COSMIC-CRC, PRISM(CRC), ClinicalTrials(CRC)

## Step 2 Outputs (completed 2026-04-20)

| File | Shape | Purpose |
|------|-------|---------|
| data/labels.parquet | (12,538, 4) | IC50 training labels |
| data/drug_features.parquet | (295, 5) | Drug SMILES + metadata |
| data/drug_target_mapping.parquet | (485, 2) | Drug-target pairs |
| data/lincs_colon.parquet | (18,823, 12,336) | LINCS signatures (GSE92742) |
| data/lincs_colon_drug_level.parquet | (91, 12,329) | Drug-level aggregated |
| data/colon_subtype_metadata.parquet | (594, 11) | Patient subtype tags |

Integrated QC: ALL PASSED (0 issues). Ready for Step 3 FE.

See `differences.md` for detailed execution records.

## 대시보드 (Dashboard)

- **경로:** `dashboard/`
- **기술 스택:** Streamlit + Plotly + Pandas
- **실행:** `cd <프로젝트 루트> && streamlit run dashboard/app.py`
- **구조:**
  - `dashboard/app.py` — 메인 Streamlit 앱 (탭 7개)
  - `dashboard/parsers/` — Step별 결과 파서
  - `dashboard/views/` — 각 탭 뷰 구현
  - `dashboard/utils/` — 상수, 스타일
- **참고:** `lung_pipeline_dashboard.html` (Lung 대시보드, 정적 HTML)
- **미완료 작업:** `dashboard/TODO.md` 참조 (통합 재진행 시 반영)

## References
- Protocol: drug_repurposing_pipeline_protocol.md v2.3
- Source pipelines: BRCA myprotocol, Lung pipeline
- Reference data: Colon_raw/ (s3://say2-4team/Colon_raw/)

## Backup
- Initial README (2026-04-20): configs/backup/README_initial_20260420.md
