#!/usr/bin/env python3
"""
ADMET Analysis - Final Protocol Models (Consensus Top 24)
══════════════════════════════════════════════════════════════════════════════

입력: Consensus Top 24 약물 (두 모델 모두 Top 30에 포함)
방법: TDC ADMET Benchmark (22 assays), Tanimoto Similarity v1
출력: Safety Score, PASS/WARNING/FAIL 판정, 최종 추천
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import json
import time
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import DataStructs, AllChem, Descriptors

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

S3_BASE = "s3://say2-4team/20260408_new_pre_project_biso/20260408_pre_project_biso_myprotocol"

# Data paths
DRUG_CATALOG = f"{S3_BASE}/data/drug_features_catalog.parquet"
ADMET_BASE = f"{S3_BASE}/data/admet"

# Local paths
BASE_DIR = Path(__file__).parent
METABRIC_DIR = BASE_DIR / "metabric_validation_final"
OUTPUT_DIR = BASE_DIR / "admet_analysis_final"
OUTPUT_DIR.mkdir(exist_ok=True)

# Input
CONSENSUS_CSV = METABRIC_DIR / "top15_validated_consensus.csv"

# Known BRCA drugs (Category A)
CATEGORY_A_DRUGS = {
    "Docetaxel", "Paclitaxel", "Vinblastine", "Vinorelbine",
    "Dactinomycin", "Epirubicin", "Topotecan", "Irinotecan",
    "Rapamycin", "Fulvestrant", "Methotrexate", "Doxorubicin",
    "Cisplatin", "Carboplatin", "Tamoxifen", "Letrozole",
    "Trastuzumab", "Lapatinib", "Palbociclib", "Olaparib",
    "Gemcitabine", "Capecitabine", "Fluorouracil", "Eribulin",
    "Bortezomib",
}

# Pure repurposing (Category C)
CATEGORY_C_DRUGS = {
    "Avagacestat", "Tozasertib", "SB505124", "UNC0638",
    "AZD1208", "AZD6738", "Ibrutinib",
}

# 22 ADMET Assays with weights
ADMET_ASSAYS = {
    'ames': {'category': 'Toxicity', 'name': 'Ames Mutagenicity', 'weight': -2.0, 'good_value': 0},
    'dili': {'category': 'Toxicity', 'name': 'DILI (Liver Injury)', 'weight': -2.0, 'good_value': 0},
    'herg': {'category': 'Toxicity', 'name': 'hERG Cardiotoxicity', 'weight': -1.5, 'good_value': 0},
    'ld50_zhu': {'category': 'Toxicity', 'name': 'Acute Toxicity (LD50)', 'weight': 1.0, 'good_direction': 'high'},
    'bioavailability_ma': {'category': 'Absorption', 'name': 'Oral Bioavailability', 'weight': 1.0, 'good_value': 1},
    'bbb_martins': {'category': 'Distribution', 'name': 'BBB Penetration', 'weight': 0.5, 'good_value': None},
    'caco2_wang': {'category': 'Absorption', 'name': 'Caco-2 Permeability', 'weight': 0.5, 'good_direction': 'high'},
    'hia_hou': {'category': 'Absorption', 'name': 'HIA (Intestinal Absorption)', 'weight': 0.5, 'good_value': 1},
    'pgp_broccatelli': {'category': 'Absorption', 'name': 'P-gp Inhibitor', 'weight': -0.5, 'good_value': 0},
    'ppbr_az': {'category': 'Distribution', 'name': 'Plasma Protein Binding', 'weight': 0.3, 'good_direction': 'low'},
    'vdss_lombardo': {'category': 'Distribution', 'name': 'Volume of Distribution', 'weight': 0.3, 'good_direction': None},
    'cyp2c9_veith': {'category': 'Metabolism', 'name': 'CYP2C9 Inhibitor', 'weight': -0.5, 'good_value': 0},
    'cyp2d6_veith': {'category': 'Metabolism', 'name': 'CYP2D6 Inhibitor', 'weight': -0.5, 'good_value': 0},
    'cyp3a4_veith': {'category': 'Metabolism', 'name': 'CYP3A4 Inhibitor', 'weight': -0.5, 'good_value': 0},
    'cyp2c9_substrate_carbonmangels': {'category': 'Metabolism', 'name': 'CYP2C9 Substrate', 'weight': 0.2, 'good_value': None},
    'cyp2d6_substrate_carbonmangels': {'category': 'Metabolism', 'name': 'CYP2D6 Substrate', 'weight': 0.2, 'good_value': None},
    'cyp3a4_substrate_carbonmangels': {'category': 'Metabolism', 'name': 'CYP3A4 Substrate', 'weight': 0.2, 'good_value': None},
    'clearance_hepatocyte_az': {'category': 'Excretion', 'name': 'Hepatocyte Clearance', 'weight': 0.5, 'good_direction': None},
    'clearance_microsome_az': {'category': 'Excretion', 'name': 'Microsome Clearance', 'weight': 0.5, 'good_direction': None},
    'half_life_obach': {'category': 'Excretion', 'name': 'Half-Life', 'weight': 0.5, 'good_direction': 'high'},
    'lipophilicity_astrazeneca': {'category': 'Properties', 'name': 'Lipophilicity (logD)', 'weight': 0.3, 'good_direction': None},
    'solubility_aqsoldb': {'category': 'Properties', 'name': 'Aqueous Solubility', 'weight': 0.5, 'good_direction': 'high'},
}

# Tanimoto thresholds
SIMILARITY_THRESHOLDS = {
    'exact': 1.0,
    'close_analog': 0.85,
    'analog': 0.70,
}

print("=" * 100)
print("ADMET Analysis - Final Protocol Models (Consensus Top 24)")
print("=" * 100)
print(f"\n입력: {CONSENSUS_CSV.name}")
print(f"방법: TDC ADMET Benchmark (22 assays), Tanimoto Similarity v1")
print(f"출력: {OUTPUT_DIR}/")
print("=" * 100)

# ═══════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════

def get_fingerprint(smiles):
    """Generate Morgan fingerprint"""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            return AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048)
    except:
        pass
    return None


def get_drug_category(drug_name):
    """Categorize drug: A (Known BRCA), B (BRCA research), C (Pure repurposing)"""
    if drug_name in CATEGORY_A_DRUGS:
        return "A"
    elif drug_name in CATEGORY_C_DRUGS:
        return "C"
    else:
        return "B"


def calculate_rdkit_properties(smiles):
    """Calculate RDKit molecular properties"""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            return {
                'mw': Descriptors.MolWt(mol),
                'logp': Descriptors.MolLogP(mol),
                'hbd': Descriptors.NumHDonors(mol),
                'hba': Descriptors.NumHAcceptors(mol),
                'tpsa': Descriptors.TPSA(mol),
                'rotatable_bonds': Descriptors.NumRotatableBonds(mol),
            }
    except:
        pass
    return {
        'mw': None, 'logp': None, 'hbd': None,
        'hba': None, 'tpsa': None, 'rotatable_bonds': None
    }


# ═══════════════════════════════════════════════════════════════════════════
# Step 1: Load Data
# ═══════════════════════════════════════════════════════════════════════════

def load_data():
    """Load consensus drugs and map SMILES"""
    print(f"\n{'='*100}")
    print("Step 1: Load Consensus Drugs and Map SMILES")
    print("=" * 100)

    # Load consensus drugs
    consensus = pd.read_csv(CONSENSUS_CSV)
    print(f"✓ Consensus drugs: {len(consensus)}")

    # Load drug catalog for SMILES
    catalog = pd.read_parquet(DRUG_CATALOG)
    print(f"✓ Drug catalog: {len(catalog)} drugs")

    # Map SMILES
    smiles_map = catalog.set_index('DRUG_ID')['canonical_smiles'].to_dict()
    consensus['smiles'] = consensus['drug_id'].map(smiles_map)

    # Check SMILES availability
    has_smiles = consensus['smiles'].notna().sum()
    print(f"✓ SMILES mapped: {has_smiles}/{len(consensus)}")

    if has_smiles < len(consensus):
        print(f"\n  ⚠️  Missing SMILES for:")
        missing = consensus[consensus['smiles'].isna()]
        for _, row in missing.iterrows():
            print(f"     - {row['drug_name']} (ID: {row['drug_id']})")

    # Add drug category
    consensus['category'] = consensus['drug_name'].map(get_drug_category)

    # Count by category
    cat_counts = consensus['category'].value_counts().sort_index()
    print(f"\n  Category distribution:")
    for cat, cnt in cat_counts.items():
        label = {"A": "Known BRCA", "B": "BRCA Research", "C": "Pure Repurposing"}[cat]
        print(f"    {cat} ({label}): {cnt}")

    return consensus


# ═══════════════════════════════════════════════════════════════════════════
# Step 2: Load ADMET Assay Libraries
# ═══════════════════════════════════════════════════════════════════════════

def load_admet_libraries():
    """Load ADMET assay data and generate fingerprints"""
    print(f"\n{'='*100}")
    print("Step 2: Load ADMET Assay Libraries")
    print("=" * 100)

    assay_libraries = {}

    for assay_name, assay_info in ADMET_ASSAYS.items():
        assay_path = f"{ADMET_BASE}/{assay_name}/train_val_basic_clean_20260406.parquet"

        try:
            df_assay = pd.read_parquet(assay_path)

            fps = []
            y_values = []

            for _, row in df_assay.iterrows():
                smiles = row.get('Drug', '')
                y = row.get('Y')

                fp = get_fingerprint(smiles)
                if fp is not None:
                    fps.append(fp)
                    y_values.append(y)

            if fps:
                assay_libraries[assay_name] = {
                    'fps': fps,
                    'y_values': y_values,
                    'info': assay_info,
                    'n_compounds': len(fps)
                }
                print(f"  ✓ {assay_name:40s}: {len(fps):6d} compounds")

        except Exception as e:
            print(f"  ✗ {assay_name:40s}: Error - {str(e)[:50]}")

    print(f"\n✓ Loaded {len(assay_libraries)}/22 assays")
    return assay_libraries


# ═══════════════════════════════════════════════════════════════════════════
# Step 3: Tanimoto Matching
# ═══════════════════════════════════════════════════════════════════════════

def perform_tanimoto_matching(consensus, assay_libraries):
    """Perform Tanimoto similarity matching for each drug"""
    print(f"\n{'='*100}")
    print("Step 3: Tanimoto Similarity Matching (threshold > 0.7)")
    print("=" * 100)

    results = {}

    for idx, row in consensus.iterrows():
        drug_name = row['drug_name']
        drug_id = row['drug_id']
        smiles = row.get('smiles')

        if pd.isna(smiles):
            print(f"  ⚠️  Skipping {drug_name} (no SMILES)")
            continue

        drug_fp = get_fingerprint(smiles)
        if drug_fp is None:
            print(f"  ⚠️  Skipping {drug_name} (invalid SMILES)")
            continue

        result = {
            'drug_id': drug_id,
            'drug_name': drug_name,
            'smiles': smiles,
            'assays': {},
            'n_exact': 0,
            'n_close_analog': 0,
            'n_analog': 0,
            'n_total_matches': 0,
        }

        # Match against each assay
        for assay_name, lib in assay_libraries.items():
            best_similarity = 0.0
            best_value = None

            for fp, y_val in zip(lib['fps'], lib['y_values']):
                similarity = DataStructs.TanimotoSimilarity(drug_fp, fp)

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_value = y_val

            # Check threshold
            if best_similarity >= SIMILARITY_THRESHOLDS['analog']:
                match_type = 'analog'
                if best_similarity >= SIMILARITY_THRESHOLDS['close_analog']:
                    match_type = 'close_analog'
                if best_similarity >= SIMILARITY_THRESHOLDS['exact']:
                    match_type = 'exact'

                result['assays'][assay_name] = {
                    'similarity': float(best_similarity),
                    'value': float(best_value) if best_value is not None else None,
                    'match_type': match_type
                }

                if match_type == 'exact':
                    result['n_exact'] += 1
                elif match_type == 'close_analog':
                    result['n_close_analog'] += 1
                else:
                    result['n_analog'] += 1

                result['n_total_matches'] += 1

        results[drug_name] = result

        print(f"  {drug_name:<25}: {result['n_total_matches']:2d}/22 assays "
              f"(exact={result['n_exact']}, close={result['n_close_analog']}, analog={result['n_analog']})")

    return results


# ═══════════════════════════════════════════════════════════════════════════
# Step 4: Calculate Safety Score
# ═══════════════════════════════════════════════════════════════════════════

def calculate_safety_scores(results, consensus):
    """Calculate safety score for each drug"""
    print(f"\n{'='*100}")
    print("Step 4: Calculate Safety Scores")
    print("=" * 100)

    safety_results = []

    for drug_name, result in results.items():
        # Get drug info
        drug_row = consensus[consensus['drug_name'] == drug_name].iloc[0]

        # Calculate safety score
        safety_score = 5.0  # Base score
        assay_scores = {}

        for assay_name, assay_info in ADMET_ASSAYS.items():
            if assay_name in result['assays']:
                match = result['assays'][assay_name]
                value = match['value']
                weight = assay_info['weight']

                if value is not None:
                    # Apply weight
                    contribution = value * weight
                    safety_score += contribution
                    assay_scores[assay_name] = {
                        'value': value,
                        'weight': weight,
                        'contribution': contribution,
                        'similarity': match['similarity'],
                        'match_type': match['match_type']
                    }

        # Determine verdict
        if safety_score >= 6.0:
            verdict = "PASS"
        elif safety_score >= 4.0:
            verdict = "WARNING"
        else:
            verdict = "FAIL"

        # Get category
        category = drug_row['category']

        # Apply category-based filtering
        if category == "A":  # Known BRCA - toxicity allowed
            final_recommendation = "APPROVED" if verdict in ["PASS", "WARNING"] else "APPROVED (Known Drug)"
        elif category == "C":  # Pure repurposing - strict
            final_recommendation = "CANDIDATE" if verdict == "PASS" else "REJECTED"
        else:  # Category B - moderate
            final_recommendation = "CANDIDATE" if verdict in ["PASS", "WARNING"] else "CAUTION"

        safety_results.append({
            'drug_id': result['drug_id'],
            'drug_name': drug_name,
            'category': category,
            'safety_score': safety_score,
            'verdict': verdict,
            'final_recommendation': final_recommendation,
            'n_total_matches': result['n_total_matches'],
            'n_exact': result['n_exact'],
            'n_close_analog': result['n_close_analog'],
            'n_analog': result['n_analog'],
            'ensemble_pred': drug_row.get('ensemble_pred', None),
            'single_pred': drug_row.get('single_pred', None),
            'mean_true_ic50': drug_row.get('mean_true_ic50', None),
            'sensitivity_rate': drug_row.get('sensitivity_rate', None),
            'assay_scores': assay_scores,
            'smiles': result['smiles'],
        })

    df_safety = pd.DataFrame(safety_results)
    df_safety = df_safety.sort_values('safety_score', ascending=False)

    print(f"\n  {'Drug':<25} {'Category':>8} {'Score':>6} {'Verdict':>8} {'Matches':>7} {'Recommendation':<20}")
    print(f"  {'-'*90}")
    for _, row in df_safety.iterrows():
        print(f"  {row['drug_name']:<25} {row['category']:>8} {row['safety_score']:>6.2f} "
              f"{row['verdict']:>8} {row['n_total_matches']:>2}/22   {row['final_recommendation']:<20}")

    # Summary statistics
    print(f"\n  Summary:")
    print(f"    PASS:    {(df_safety['verdict'] == 'PASS').sum()}/{len(df_safety)}")
    print(f"    WARNING: {(df_safety['verdict'] == 'WARNING').sum()}/{len(df_safety)}")
    print(f"    FAIL:    {(df_safety['verdict'] == 'FAIL').sum()}/{len(df_safety)}")

    return df_safety


# ═══════════════════════════════════════════════════════════════════════════
# Step 5: Generate Final Outputs
# ═══════════════════════════════════════════════════════════════════════════

def save_results(results, df_safety, consensus):
    """Save all results"""
    print(f"\n{'='*100}")
    print("Step 5: Save Results")
    print("=" * 100)

    # 1. Detailed ADMET results JSON
    admet_json = OUTPUT_DIR / "admet_results_consensus.json"
    with open(admet_json, 'w') as f:
        json.dump(results, f, indent=2, default=lambda x: float(x) if isinstance(x, np.floating) else x)
    print(f"✓ Saved: {admet_json.name}")

    # 2. Safety scores with RDKit properties
    df_detailed = df_safety.copy()

    # Add RDKit properties
    rdkit_props = []
    for smiles in df_detailed['smiles']:
        rdkit_props.append(calculate_rdkit_properties(smiles))
    rdkit_df = pd.DataFrame(rdkit_props)

    df_detailed = pd.concat([df_detailed.drop('assay_scores', axis=1), rdkit_df], axis=1)

    detailed_csv = OUTPUT_DIR / "admet_detailed_24drugs.csv"
    df_detailed.to_csv(detailed_csv, index=False)
    print(f"✓ Saved: {detailed_csv.name}")

    # 3. Final drug candidates (PASS + WARNING)
    df_candidates = df_safety[df_safety['verdict'].isin(['PASS', 'WARNING'])].copy()
    candidates_csv = OUTPUT_DIR / "final_drug_candidates.csv"
    df_candidates.drop('assay_scores', axis=1).to_csv(candidates_csv, index=False)
    print(f"✓ Saved: {candidates_csv.name} ({len(df_candidates)} drugs)")

    # 4. Final repurposing candidates (Category C, PASS only)
    df_repurposing = df_safety[
        (df_safety['category'] == 'C') &
        (df_safety['verdict'] == 'PASS')
    ].copy()
    repurposing_csv = OUTPUT_DIR / "final_repurposing_candidates.csv"
    df_repurposing.drop('assay_scores', axis=1).to_csv(repurposing_csv, index=False)
    print(f"✓ Saved: {repurposing_csv.name} ({len(df_repurposing)} drugs)")

    # 5. Summary report
    summary = {
        'total_drugs': len(df_safety),
        'verdict_counts': df_safety['verdict'].value_counts().to_dict(),
        'category_counts': df_safety['category'].value_counts().to_dict(),
        'recommendation_counts': df_safety['final_recommendation'].value_counts().to_dict(),
        'avg_safety_score': float(df_safety['safety_score'].mean()),
        'avg_matches': float(df_safety['n_total_matches'].mean()),
        'top_5_drugs': df_safety.head(5)[['drug_name', 'safety_score', 'verdict', 'final_recommendation']].to_dict('records'),
    }

    summary_json = OUTPUT_DIR / "admet_summary.json"
    with open(summary_json, 'w') as f:
        json.dump(summary, f, indent=2, default=lambda x: float(x) if isinstance(x, np.floating) else x)
    print(f"✓ Saved: {summary_json.name}")

    return df_detailed


# ═══════════════════════════════════════════════════════════════════════════
# Main Execution
# ═══════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()

    # Step 1: Load data
    consensus = load_data()

    # Step 2: Load ADMET libraries
    assay_libraries = load_admet_libraries()

    # Step 3: Tanimoto matching
    results = perform_tanimoto_matching(consensus, assay_libraries)

    # Step 4: Calculate safety scores
    df_safety = calculate_safety_scores(results, consensus)

    # Step 5: Save results
    df_detailed = save_results(results, df_safety, consensus)

    elapsed = time.time() - t0
    print(f"\n{'='*100}")
    print(f"ADMET Analysis COMPLETE ({elapsed/60:.1f} min)")
    print(f"{'='*100}")
    print(f"\n생성된 파일:")
    print(f"  - admet_results_consensus.json")
    print(f"  - admet_detailed_24drugs.csv")
    print(f"  - final_drug_candidates.csv")
    print(f"  - final_repurposing_candidates.csv")
    print(f"  - admet_summary.json")
    print("=" * 100)

    return df_detailed


if __name__ == "__main__":
    df_result = main()
