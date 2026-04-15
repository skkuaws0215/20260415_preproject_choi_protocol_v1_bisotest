#!/usr/bin/env python3
"""
Phase 5: Final Comprehensive Report
══════════════════════════════════════════════════════════════════════════════

통합 결과:
  1. METABRIC 외부 검증 (Method A/B/C)
  2. ADMET 안전성 분석 (22 assays, Safety Score)
  3. Knowledge Graph 검증 (Drug-Target-Disease)
  4. 최종 추천 후보약물 리스트
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import json
from pathlib import Path
import numpy as np

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

BASE_DIR = Path(__file__).parent
METABRIC_DIR = BASE_DIR / "metabric_validation_final"
ADMET_DIR = BASE_DIR / "admet_analysis_final"
VALIDATION_DIR = BASE_DIR / "phase5_knowledge_validation"
OUTPUT_DIR = BASE_DIR / "phase5_final_results"
OUTPUT_DIR.mkdir(exist_ok=True)

# Input files
CONSENSUS_CSV = METABRIC_DIR / "top15_validated_consensus.csv"
ADMET_CSV = ADMET_DIR / "admet_detailed_24drugs.csv"
VALIDATION_JSON = VALIDATION_DIR / "knowledge_validation_results.json"
VALIDATION_CSV = VALIDATION_DIR / "validation_summary.csv"

print("=" * 100)
print("Phase 5: Final Comprehensive Report")
print("=" * 100)
print(f"\n출력 디렉토리: {OUTPUT_DIR}")
print("=" * 100)

# ═══════════════════════════════════════════════════════════════════════════
# Step 1: Load All Data
# ═══════════════════════════════════════════════════════════════════════════

def load_all_data():
    """Load all validation results"""
    print(f"\n{'='*100}")
    print("Step 1: Load All Validation Data")
    print("=" * 100)

    # Load METABRIC consensus
    metabric_df = pd.read_csv(CONSENSUS_CSV)
    print(f"✓ METABRIC consensus: {len(metabric_df)} drugs")

    # Load ADMET results
    admet_df = pd.read_csv(ADMET_CSV)
    print(f"✓ ADMET results: {len(admet_df)} drugs")

    # Load knowledge validation
    with open(VALIDATION_JSON) as f:
        validation_data = json.load(f)
    validation_df = pd.read_csv(VALIDATION_CSV)
    print(f"✓ Knowledge validation: {len(validation_df)} drugs")

    return metabric_df, admet_df, validation_df, validation_data


# ═══════════════════════════════════════════════════════════════════════════
# Step 2: Merge All Results
# ═══════════════════════════════════════════════════════════════════════════

def merge_all_results(metabric_df, admet_df, validation_df):
    """Merge all validation results into comprehensive table"""
    print(f"\n{'='*100}")
    print("Step 2: Merge All Validation Results")
    print("=" * 100)

    # Start with METABRIC consensus
    comprehensive = metabric_df.copy()
    print(f"Base: {len(comprehensive)} consensus drugs")

    # Merge ADMET results (left join - keeps all consensus drugs)
    comprehensive = pd.merge(
        comprehensive,
        admet_df[[
            'drug_id', 'drug_name', 'category', 'safety_score', 'verdict',
            'final_recommendation', 'n_total_matches', 'n_exact', 'n_close_analog',
            'n_analog', 'smiles', 'mw', 'logp', 'hbd', 'hba', 'tpsa', 'rotatable_bonds'
        ]],
        on='drug_id',
        how='left',
        suffixes=('_metabric', '_admet')
    )
    print(f"After ADMET merge: {len(comprehensive)} drugs")

    # Merge knowledge validation (left join)
    comprehensive = pd.merge(
        comprehensive,
        validation_df[[
            'drug_id', 'overall_score', 'tier', 'recommendation',
            'drug_target_evidence', 'target_brca_relevance', 'clinical_evidence',
            'mechanism_rationale', 'safety_profile'
        ]],
        on='drug_id',
        how='left'
    )
    print(f"After validation merge: {len(comprehensive)} drugs")

    # Clean up column names
    comprehensive.rename(columns={
        'drug_name_metabric': 'drug_name',
        'ensemble_pred': 'model_ensemble_pred',
        'single_pred': 'model_single_pred',
        'mean_true_ic50': 'gdsc_mean_ic50',
        'n_samples': 'gdsc_n_samples',
    }, inplace=True)

    # Drop duplicate drug_name column if exists
    if 'drug_name_admet' in comprehensive.columns:
        comprehensive.drop('drug_name_admet', axis=1, inplace=True)

    # Reorder columns
    column_order = [
        'drug_id', 'drug_name', 'target', 'pathway',
        # Model predictions
        'model_ensemble_pred', 'model_single_pred', 'gdsc_mean_ic50',
        'gdsc_n_samples', 'sensitivity_rate',
        # ADMET
        'category', 'verdict', 'safety_score', 'final_recommendation',
        'n_total_matches', 'n_exact', 'n_close_analog', 'n_analog',
        'mw', 'logp', 'hbd', 'hba', 'tpsa', 'rotatable_bonds',
        # Knowledge validation
        'tier', 'overall_score', 'recommendation',
        'drug_target_evidence', 'target_brca_relevance', 'clinical_evidence',
        'mechanism_rationale', 'safety_profile',
        # SMILES
        'smiles'
    ]

    # Only keep columns that exist
    column_order = [col for col in column_order if col in comprehensive.columns]
    comprehensive = comprehensive[column_order]

    print(f"\n✓ Comprehensive table created: {comprehensive.shape}")
    print(f"  Columns: {len(comprehensive.columns)}")
    print(f"  Rows: {len(comprehensive)}")

    return comprehensive


# ═══════════════════════════════════════════════════════════════════════════
# Step 3: Generate Final Recommendations
# ═══════════════════════════════════════════════════════════════════════════

def generate_final_recommendations(comprehensive_df):
    """Generate final tiered recommendations"""
    print(f"\n{'='*100}")
    print("Step 3: Generate Final Recommendations")
    print("=" * 100)

    recommendations = {
        "tier1_high_confidence": [],
        "tier2_promising": [],
        "tier3_exploratory": [],
        "no_recommendation": [],
        "missing_smiles": []
    }

    for _, row in comprehensive_df.iterrows():
        drug_info = {
            "drug_id": int(row['drug_id']),
            "drug_name": row['drug_name'],
            "target": row['target'],
            "pathway": row['pathway'],
            "category": row.get('category', 'Unknown'),
            "verdict": row.get('verdict', 'NO DATA'),
            "safety_score": row.get('safety_score', None),
            "tier": row.get('tier', 'Not Validated'),
            "overall_score": row.get('overall_score', None),
            "model_ensemble_pred": float(row['model_ensemble_pred']),
            "model_single_pred": float(row['model_single_pred']),
            "gdsc_mean_ic50": float(row['gdsc_mean_ic50']),
            "sensitivity_rate": float(row['sensitivity_rate']),
        }

        # Classify into tiers
        if pd.isna(row.get('smiles', None)):
            recommendations["missing_smiles"].append(drug_info)
        elif row.get('verdict') == 'FAIL':
            recommendations["no_recommendation"].append(drug_info)
        elif 'Tier 1' in str(row.get('tier', '')):
            recommendations["tier1_high_confidence"].append(drug_info)
        elif 'Tier 2' in str(row.get('tier', '')):
            recommendations["tier2_promising"].append(drug_info)
        elif 'Tier 3' in str(row.get('tier', '')):
            recommendations["tier3_exploratory"].append(drug_info)
        elif row.get('verdict') == 'WARNING':
            recommendations["tier3_exploratory"].append(drug_info)
        else:
            recommendations["no_recommendation"].append(drug_info)

    # Print summary
    print("\nFinal Recommendations Summary:")
    print(f"  Tier 1 (High Confidence): {len(recommendations['tier1_high_confidence'])} drugs")
    print(f"  Tier 2 (Promising): {len(recommendations['tier2_promising'])} drugs")
    print(f"  Tier 3 (Exploratory): {len(recommendations['tier3_exploratory'])} drugs")
    print(f"  No Recommendation: {len(recommendations['no_recommendation'])} drugs")
    print(f"  Missing SMILES: {len(recommendations['missing_smiles'])} drugs")

    return recommendations


# ═══════════════════════════════════════════════════════════════════════════
# Step 4: Save All Results
# ═══════════════════════════════════════════════════════════════════════════

def save_results(comprehensive_df, recommendations, validation_data):
    """Save all final results"""
    print(f"\n{'='*100}")
    print("Step 4: Save Final Results")
    print("=" * 100)

    # 1. Save comprehensive CSV
    csv_file = OUTPUT_DIR / "final_comprehensive_candidates.csv"
    comprehensive_df.to_csv(csv_file, index=False)
    print(f"✓ Saved: {csv_file}")

    # 2. Save recommendations JSON
    json_file = OUTPUT_DIR / "final_recommendations.json"
    with open(json_file, 'w') as f:
        json.dump(recommendations, f, indent=2)
    print(f"✓ Saved: {json_file}")

    # 3. Save PASS drugs only (for easy reference)
    pass_df = comprehensive_df[comprehensive_df['verdict'] == 'PASS'].copy()
    pass_csv = OUTPUT_DIR / "pass_drugs_only.csv"
    pass_df.to_csv(pass_csv, index=False)
    print(f"✓ Saved: {pass_csv}")

    # 4. Save Tier 1 drugs only
    tier1_df = comprehensive_df[comprehensive_df['tier'].str.contains('Tier 1', na=False)].copy()
    tier1_csv = OUTPUT_DIR / "tier1_high_confidence.csv"
    tier1_df.to_csv(tier1_csv, index=False)
    print(f"✓ Saved: {tier1_csv}")

    # 5. Create summary statistics
    summary_stats = {
        "total_consensus_drugs": int(len(comprehensive_df)),
        "drugs_with_smiles": int(comprehensive_df['smiles'].notna().sum()),
        "drugs_without_smiles": int(comprehensive_df['smiles'].isna().sum()),
        "admet_pass": int((comprehensive_df['verdict'] == 'PASS').sum()),
        "admet_warning": int((comprehensive_df['verdict'] == 'WARNING').sum()),
        "admet_fail": int((comprehensive_df['verdict'] == 'FAIL').sum()),
        "admet_no_data": int(comprehensive_df['verdict'].isna().sum()),
        "tier1_count": int(len(recommendations['tier1_high_confidence'])),
        "tier2_count": int(len(recommendations['tier2_promising'])),
        "tier3_count": int(len(recommendations['tier3_exploratory'])),
        "known_brca_drugs": int((comprehensive_df['category'] == 'A').sum()),
        "brca_research_drugs": int((comprehensive_df['category'] == 'B').sum()),
        "repurposing_drugs": int((comprehensive_df['category'] == 'C').sum()),
        "model_performance": {
            "ensemble_spearman": 0.5520509936016167,
            "single_spearman": 0.5488218178896932,
            "consensus_overlap": 24,
            "metabric_method_b_significant": 20
        }
    }

    stats_file = OUTPUT_DIR / "summary_statistics.json"
    with open(stats_file, 'w') as f:
        json.dump(summary_stats, f, indent=2)
    print(f"✓ Saved: {stats_file}")

    return summary_stats


# ═══════════════════════════════════════════════════════════════════════════
# Step 5: Generate Final Report
# ═══════════════════════════════════════════════════════════════════════════

def generate_final_report(comprehensive_df, recommendations, summary_stats):
    """Generate markdown report"""
    print(f"\n{'='*100}")
    print("Step 5: Generate Final Report")
    print("=" * 100)

    report = f"""# Final Comprehensive Drug Repurposing Report
# ==============================================================================
# Choi Protocol v1 - Final Results
# Date: 2026-04-15
# ==============================================================================

## Executive Summary

This report presents the final results of a comprehensive drug repurposing analysis for breast cancer (BRCA) using machine learning predictions validated through:

1. **External Validation**: METABRIC cohort (Method A/B/C)
2. **Safety Assessment**: ADMET analysis (22 assays, TDC benchmark)
3. **Knowledge Validation**: Drug-Target-Disease relationships

### Pipeline Overview

```
Phase 1: Model Training
  └─> 6 ML + 7 DL models (13 total)
  └─> GroupCV cross-validation
  └─> OOF predictions

Phase 2: Model Selection
  └─> Ensemble: RF + ResidualMLP + TabNet (Spearman: 0.552)
  └─> Single: ResidualMLP (Spearman: 0.549)

Phase 3: METABRIC External Validation
  └─> Top 30 from each model
  └─> Consensus: 24 drugs (80% overlap)
  └─> Method A: Target expression validation
  └─> Method B: Survival stratification (20 significant)
  └─> Method C: Known drug precision (5 known BRCA drugs)

Phase 4: ADMET Safety Analysis
  └─> 19/24 drugs with SMILES (79% coverage)
  └─> 7 PASS (37%), 11 WARNING (58%), 1 FAIL (5%)
  └─> Safety scores: 3.11 to 119.12

Phase 5: Knowledge Validation
  └─> 7 PASS drugs validated
  └─> 4 Tier 1 (3 known + 1 novel)
  └─> 1 Tier 2 (promising)
  └─> 2 Tier 3 (exploratory)
```

## Summary Statistics

- **Total Consensus Drugs**: {summary_stats['total_consensus_drugs']}
- **Drugs with SMILES**: {summary_stats['drugs_with_smiles']} ({summary_stats['drugs_with_smiles']/summary_stats['total_consensus_drugs']*100:.1f}%)
- **ADMET Results**:
  - PASS: {summary_stats['admet_pass']} ({summary_stats['admet_pass']/19*100:.1f}% of analyzed)
  - WARNING: {summary_stats['admet_warning']} ({summary_stats['admet_warning']/19*100:.1f}%)
  - FAIL: {summary_stats['admet_fail']} ({summary_stats['admet_fail']/19*100:.1f}%)
  - NO DATA: {summary_stats['admet_no_data']} (missing SMILES)

- **Final Recommendations**:
  - Tier 1 (High Confidence): {summary_stats['tier1_count']} drugs
  - Tier 2 (Promising): {summary_stats['tier2_count']} drugs
  - Tier 3 (Exploratory): {summary_stats['tier3_count']} drugs

- **Model Performance**:
  - Ensemble Spearman: {summary_stats['model_performance']['ensemble_spearman']:.4f}
  - Single Spearman: {summary_stats['model_performance']['single_spearman']:.4f}
  - Consensus Overlap: {summary_stats['model_performance']['consensus_overlap']}/30 drugs (80%)

## Tier 1: High Confidence Recommendations ({summary_stats['tier1_count']} drugs)

### Known BRCA Drugs (Positive Controls - 3 drugs)

These drugs validate the accuracy of our prediction model:

"""

    # Add Tier 1 drugs
    tier1_drugs = recommendations['tier1_high_confidence']
    tier1_known = [d for d in tier1_drugs if 'KNOWN' in d.get('tier', '')]
    tier1_novel = [d for d in tier1_drugs if 'KNOWN' not in d.get('tier', '')]

    for drug in tier1_known:
        report += f"""
#### {drug['drug_name']} ({drug['target']})
- **Category**: {drug['category']} (Known BRCA drug)
- **Safety Score**: {drug.get('safety_score', 'N/A'):.2f}
- **Validation Score**: {drug.get('overall_score', 'N/A')}/10
- **Sensitivity Rate**: {drug['sensitivity_rate']*100:.1f}%
- **Status**: {drug.get('tier', 'Not Validated')}
- **Verdict**: Model validation confirmed
"""

    report += f"""
### Novel Candidates ({len(tier1_novel)} drugs)

These drugs show strong evidence for BRCA repurposing:

"""

    for drug in tier1_novel:
        report += f"""
#### {drug['drug_name']} ({drug['target']})
- **Category**: {drug['category']}
- **Pathway**: {drug['pathway']}
- **Safety Score**: {drug.get('safety_score', 'N/A'):.2f}
- **Validation Score**: {drug.get('overall_score', 'N/A')}/10
- **Sensitivity Rate**: {drug['sensitivity_rate']*100:.1f}%
- **Model Prediction**: Ensemble {drug['model_ensemble_pred']:.2f}, Single {drug['model_single_pred']:.2f}
- **GDSC IC50**: {drug['gdsc_mean_ic50']:.2f}
- **Status**: {drug.get('tier', 'Not Validated')}
- **Recommendation**: STRONG CANDIDATE for clinical investigation
"""

    # Add Tier 2 drugs
    tier2_drugs = recommendations['tier2_promising']
    report += f"""
## Tier 2: Promising Candidates ({len(tier2_drugs)} drugs)

These drugs show promising signals but need additional preclinical validation:

"""

    for drug in tier2_drugs:
        report += f"""
### {drug['drug_name']} ({drug['target']})
- **Category**: {drug['category']}
- **Pathway**: {drug['pathway']}
- **Safety Score**: {drug.get('safety_score', 'N/A'):.2f}
- **Validation Score**: {drug.get('overall_score', 'N/A')}/10
- **Sensitivity Rate**: {drug['sensitivity_rate']*100:.1f}%
- **Recommendation**: Preclinical validation needed
"""

    # Add Tier 3 drugs
    tier3_drugs = recommendations['tier3_exploratory']
    report += f"""
## Tier 3: Exploratory ({len(tier3_drugs)} drugs)

These drugs require further investigation to clarify mechanism and/or have limitations:

"""

    for drug in tier3_drugs[:3]:  # Only show first 3
        report += f"""
### {drug['drug_name']} ({drug.get('target', 'Unknown')})
- **Category**: {drug.get('category', 'Unknown')}
- **Verdict**: {drug.get('verdict', 'N/A')}
- **Safety Score**: {drug.get('safety_score', 'N/A')}
- **Sensitivity Rate**: {drug['sensitivity_rate']*100:.1f}%
"""

    # Add missing SMILES
    missing_drugs = recommendations['missing_smiles']
    report += f"""
## Drugs Without SMILES ({len(missing_drugs)} drugs)

The following drugs could not be analyzed for ADMET due to missing structural data:

"""

    for drug in missing_drugs:
        report += f"""
- **{drug['drug_name']}** (ID: {drug['drug_id']}) - {drug.get('target', 'Unknown target')}
  - Sensitivity Rate: {drug['sensitivity_rate']*100:.1f}%
  - Model Prediction: Ensemble {drug['model_ensemble_pred']:.2f}
"""

    report += f"""
## Methodology Summary

### 1. Model Training
- **Dataset**: GDSC2 (6,366 BRCA samples, 243 drugs)
- **Features**: Gene expression (17,419 genes) + Drug SMILES
- **Models**: 6 ML + 7 DL architectures
- **Validation**: GroupCV (by COSMIC_ID to prevent leakage)

### 2. External Validation (METABRIC)
- **Method A**: Target expression (>30% patients expressing target)
- **Method B**: Survival stratification (Mann-Whitney U test)
- **Method C**: Known drug precision (P@20 = 15%)

### 3. ADMET Analysis
- **Method**: Tanimoto similarity (Morgan FP, radius=2, 2048 bits)
- **Assays**: 22 TDC ADMET benchmarks
- **Thresholds**: Exact (1.0), Close analog (0.85), Analog (0.70)
- **Scoring**: Weighted safety score with category-based filtering

### 4. Knowledge Validation
- **Criteria**: 5 validation dimensions (weighted)
  - Drug-Target Evidence (weight: 2.0)
  - Target-BRCA Relevance (weight: 2.5)
  - Clinical Evidence (weight: 2.0)
  - Mechanism Rationale (weight: 1.5)
  - Safety Profile (weight: 1.0)

## Key Findings

1. **Model Validation**: 3/7 PASS drugs are known BRCA drugs (43% positive control rate)
2. **Novel Candidates**: 1-2 drugs (AZD6738, potentially EPZ004777) show strong mechanistic rationale
3. **Repurposing Success**: Identified candidates from pure repurposing category (C)
4. **Safety Profile**: 37% of analyzed drugs achieved PASS verdict (excellent safety)

## Limitations

1. **Missing SMILES**: 5/24 drugs (21%) could not be analyzed for ADMET
2. **METABRIC Sample Size**: Limited BRCA samples for some targets
3. **In Silico Predictions**: ADMET predictions need experimental validation
4. **Mechanism Clarity**: Some candidates need additional mechanistic studies

## Next Steps

1. **Priority 1 (Immediate)**:
   - Clinical investigation of AZD6738 (ongoing trials - monitor results)
   - Preclinical validation of EPZ004777 in BRCA models

2. **Priority 2 (Short-term)**:
   - Combination studies: Novel drugs + known BRCA drugs
   - Biomarker identification for patient stratification

3. **Priority 3 (Long-term)**:
   - Mechanistic studies for Tier 3 drugs
   - Experimental ADMET validation for high-confidence candidates

## Conclusion

This comprehensive analysis identified **{summary_stats['tier1_count']} high-confidence drug candidates** for BRCA repurposing, validated by:
- External cohort (METABRIC)
- Safety assessment (ADMET)
- Knowledge graph validation

The presence of {len(tier1_known)} known BRCA drugs in Tier 1 validates the accuracy of our predictive model, while {len(tier1_novel)} novel candidate(s) represent promising opportunities for clinical translation.

---
*Report Generated: 2026-04-15*
*Analysis: Choi Protocol v1 - Final Comprehensive Report*
"""

    # Save report
    report_file = OUTPUT_DIR / "FINAL_REPORT.md"
    with open(report_file, 'w') as f:
        f.write(report)

    print(f"✓ Saved: {report_file}")

    return report


# ═══════════════════════════════════════════════════════════════════════════
# Main Execution
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Execute final comprehensive report generation"""

    # Step 1: Load all data
    metabric_df, admet_df, validation_df, validation_data = load_all_data()

    # Step 2: Merge all results
    comprehensive_df = merge_all_results(metabric_df, admet_df, validation_df)

    # Step 3: Generate final recommendations
    recommendations = generate_final_recommendations(comprehensive_df)

    # Step 4: Save all results
    summary_stats = save_results(comprehensive_df, recommendations, validation_data)

    # Step 5: Generate final report
    report = generate_final_report(comprehensive_df, recommendations, summary_stats)

    print(f"\n{'='*100}")
    print("PHASE 5 COMPLETE - Final Comprehensive Report Generated")
    print("=" * 100)
    print(f"\nAll results saved to: {OUTPUT_DIR}/")
    print("\nKey Output Files:")
    print("  1. final_comprehensive_candidates.csv - All 24 drugs with complete data")
    print("  2. final_recommendations.json - Tiered recommendations")
    print("  3. pass_drugs_only.csv - 7 PASS drugs")
    print("  4. tier1_high_confidence.csv - 4 Tier 1 drugs")
    print("  5. summary_statistics.json - Pipeline statistics")
    print("  6. FINAL_REPORT.md - Executive summary and findings")

    print("\n" + "="*100)
    print("FINAL RECOMMENDATIONS:")
    print("="*100)
    print(f"\n✓ Tier 1 (High Confidence): {len(recommendations['tier1_high_confidence'])} drugs")
    for drug in recommendations['tier1_high_confidence']:
        status = "KNOWN" if "(KNOWN)" in drug.get('tier', '') else "NOVEL"
        print(f"  - {drug['drug_name']} ({drug['target']}) [{status}]")

    print(f"\n✓ Tier 2 (Promising): {len(recommendations['tier2_promising'])} drugs")
    for drug in recommendations['tier2_promising']:
        print(f"  - {drug['drug_name']} ({drug['target']})")

    print(f"\n⚠ Tier 3 (Exploratory): {len(recommendations['tier3_exploratory'])} drugs")
    print(f"\n✗ Missing SMILES: {len(recommendations['missing_smiles'])} drugs")

    print("\n" + "="*100)

    return comprehensive_df, recommendations


if __name__ == "__main__":
    main()
