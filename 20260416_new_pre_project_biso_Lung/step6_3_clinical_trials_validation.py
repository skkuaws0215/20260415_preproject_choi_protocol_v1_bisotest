#!/usr/bin/env python3
"""
Step 6.3: Clinical Trials Validation
- Match GDSC drugs to ClinicalTrials.gov interventions
- Calculate Precision @ K (10, 50)
- Analyze clinical trial phases
- Count completed vs ongoing trials
"""

import json
import pandas as pd
import numpy as np
from pathlib import Path
import re

def load_clinical_trials_data():
    """Load Clinical Trials JSON data."""

    print("="*80)
    print("STEP 6.3: CLINICAL TRIALS VALIDATION")
    print("="*80)

    ct_base = 'curated_data/validation/clinicaltrials/'

    # Load summary first
    summary_file = f'{ct_base}clinicaltrials_lung_cancer_summary.json'
    if Path(summary_file).exists():
        with open(summary_file, 'r') as f:
            summary = json.load(f)
        print(f"\n✓ Clinical Trials Summary:")
        print(f"  - Query: {summary.get('query')}")
        print(f"  - Total studies: {summary.get('study_count')}")
        print(f"  - Pages: {summary.get('pages')}")

    # Load all studies (this is large - 384 MB)
    all_studies_file = f'{ct_base}clinicaltrials_lung_cancer_all_studies.json'

    if not Path(all_studies_file).exists():
        print(f"\n⚠️  All studies file not found: {all_studies_file}")
        print("Loading from paginated files instead...")

        # Load from page files
        all_studies = []
        for page_num in range(1, 16):  # 15 pages
            page_file = f'{ct_base}clinicaltrials_lung_cancer_page_{page_num:03d}.json'
            if Path(page_file).exists():
                print(f"  Loading page {page_num}/15...", end='\r')
                with open(page_file, 'r') as f:
                    page_data = json.load(f)
                    if 'studies' in page_data:
                        all_studies.extend(page_data['studies'])

        print(f"\n✓ Loaded {len(all_studies)} studies from paginated files")
        return all_studies

    print(f"\nLoading: {Path(all_studies_file).name} (this may take a while...)")
    with open(all_studies_file, 'r') as f:
        data = json.load(f)

    if 'studies' in data:
        studies = data['studies']
    else:
        studies = data

    print(f"✓ Loaded {len(studies)} studies")

    return studies

def extract_interventions(studies):
    """Extract drug interventions from clinical trials."""

    print(f"\n{'─'*80}")
    print("EXTRACTING DRUG INTERVENTIONS")
    print(f"{'─'*80}")

    interventions_list = []

    for study in studies:
        protocol = study.get('protocolSection', {})
        nct_id = protocol.get('identificationModule', {}).get('nctId', 'Unknown')
        status = protocol.get('statusModule', {}).get('overallStatus', 'Unknown')

        # Get interventions
        arms_module = protocol.get('armsInterventionsModule', {})
        interventions = arms_module.get('interventions', [])

        for intervention in interventions:
            if intervention.get('type', '').upper() == 'DRUG':
                drug_name = intervention.get('name', '').strip()
                if drug_name:
                    interventions_list.append({
                        'nct_id': nct_id,
                        'drug_name': drug_name.lower(),
                        'status': status,
                        'description': intervention.get('description', '')
                    })

    df_interventions = pd.DataFrame(interventions_list)

    if len(df_interventions) > 0:
        print(f"✓ Total drug interventions: {len(df_interventions)}")
        print(f"✓ Unique drugs: {df_interventions['drug_name'].nunique()}")
        print(f"✓ Unique trials: {df_interventions['nct_id'].nunique()}")

        # Status breakdown
        print(f"\n✓ Trial status breakdown:")
        print(df_interventions['status'].value_counts().head(10).to_string())
    else:
        print("⚠️  No drug interventions found!")

    return df_interventions

def match_gdsc_to_clinical_trials(gdsc_drugs, ct_interventions):
    """Match GDSC drugs to clinical trial interventions."""

    print(f"\n{'─'*80}")
    print("MATCHING GDSC → CLINICAL TRIALS")
    print(f"{'─'*80}")

    matches = []

    for idx, row in gdsc_drugs.iterrows():
        gdsc_id = row['canonical_drug_id']
        gdsc_name = row['DRUG_NAME'].lower().strip()
        gdsc_synonyms = row.get('SYNONYMS', '')

        # Try exact name match
        name_matches = ct_interventions[ct_interventions['drug_name'] == gdsc_name]

        if len(name_matches) > 0:
            for _, ct_row in name_matches.iterrows():
                matches.append({
                    'canonical_drug_id': gdsc_id,
                    'DRUG_NAME': row['DRUG_NAME'],
                    'nct_id': ct_row['nct_id'],
                    'ct_drug_name': ct_row['drug_name'],
                    'ct_status': ct_row['status'],
                    'match_type': 'exact_name'
                })
            continue

        # Try synonym matching
        if pd.notna(gdsc_synonyms) and gdsc_synonyms:
            synonyms = [s.strip().lower() for s in str(gdsc_synonyms).split(',')]
            for synonym in synonyms:
                syn_matches = ct_interventions[ct_interventions['drug_name'] == synonym]
                if len(syn_matches) > 0:
                    for _, ct_row in syn_matches.iterrows():
                        matches.append({
                            'canonical_drug_id': gdsc_id,
                            'DRUG_NAME': row['DRUG_NAME'],
                            'nct_id': ct_row['nct_id'],
                            'ct_drug_name': ct_row['drug_name'],
                            'ct_status': ct_row['status'],
                            'match_type': 'synonym'
                        })
                    break

    df_matches = pd.DataFrame(matches)

    if len(df_matches) > 0:
        # Remove duplicates (same drug-trial pairs)
        df_matches = df_matches.drop_duplicates(subset=['canonical_drug_id', 'nct_id'])

        unique_drugs = df_matches['canonical_drug_id'].nunique()
        total_trials = len(df_matches)

        print(f"✓ Matched drugs: {unique_drugs}/{len(gdsc_drugs)} ({unique_drugs/len(gdsc_drugs)*100:.1f}%)")
        print(f"✓ Total trials: {total_trials}")
        print(f"✓ Avg trials per drug: {total_trials/unique_drugs:.1f}")

        print(f"\n✓ Match type breakdown:")
        print(df_matches['match_type'].value_counts().to_string())

        print(f"\n✓ Trial status breakdown:")
        print(df_matches['ct_status'].value_counts().head(10).to_string())
    else:
        print(f"⚠️  No matches found!")

    return df_matches

def calculate_clinical_trial_metrics(top30_2b, top30_2c, ct_matches):
    """Calculate Precision @ K for clinical trials."""

    print(f"\n{'='*80}")
    print("CALCULATING CLINICAL TRIAL METRICS")
    print(f"{'='*80}")

    if len(ct_matches) == 0:
        print("⚠️  No clinical trial matches, cannot calculate metrics")
        return None

    # Get unique drugs with trials
    drugs_with_trials = ct_matches['canonical_drug_id'].unique()

    results = {}

    for name, top30_df in [('Phase 2B', top30_2b), ('Phase 2C', top30_2c)]:
        print(f"\n{'─'*80}")
        print(f"{name} CatBoost")
        print(f"{'─'*80}")

        # Precision @ K
        for k in [10, 50]:
            topk = top30_df.head(min(k, len(top30_df)))
            in_trials = topk[topk['canonical_drug_id'].isin(drugs_with_trials)]
            precision = len(in_trials) / len(topk) if len(topk) > 0 else 0

            print(f"✓ Precision @ {k}: {precision:.3f} ({len(in_trials)}/{len(topk)})")
            results[f'{name}_precision_{k}'] = precision

        # Drugs with trials in Top 30
        top30_with_trials = top30_df[top30_df['canonical_drug_id'].isin(drugs_with_trials)]
        print(f"✓ Drugs with trials in Top 30: {len(top30_with_trials)}/30 ({len(top30_with_trials)/30*100:.1f}%)")
        results[f'{name}_drugs_with_trials'] = len(top30_with_trials)

        # Average trial count for matched drugs
        if len(top30_with_trials) > 0:
            trial_counts = []
            for drug_id in top30_with_trials['canonical_drug_id']:
                count = len(ct_matches[ct_matches['canonical_drug_id'] == drug_id])
                trial_counts.append(count)
            avg_trials = np.mean(trial_counts)
            print(f"✓ Avg trials per matched drug: {avg_trials:.1f}")
            results[f'{name}_avg_trials'] = avg_trials

    return results

def main():
    # Load clinical trials data
    studies = load_clinical_trials_data()

    if not studies:
        print("\n❌ Cannot proceed without clinical trials data!")
        return None

    # Extract interventions
    ct_interventions = extract_interventions(studies)

    if len(ct_interventions) == 0:
        print("\n❌ No interventions extracted!")
        return None

    # Load Top 30 with names
    print(f"\n{'─'*80}")
    print("LOADING TOP 30 DRUGS")
    print(f"{'─'*80}")

    top30_2b = pd.read_csv('results/lung_top30_phase2b_catboost_with_names.csv')
    top30_2c = pd.read_csv('results/lung_top30_phase2c_catboost_with_names.csv')
    unified = pd.read_csv('results/lung_top30_unified_2b_and_2c_with_names.csv')

    print(f"✓ Phase 2B: {len(top30_2b)} drugs")
    print(f"✓ Phase 2C: {len(top30_2c)} drugs")
    print(f"✓ Unified: {len(unified)} drugs")

    # Match GDSC to clinical trials
    ct_matches = match_gdsc_to_clinical_trials(unified, ct_interventions)

    if len(ct_matches) == 0:
        print("\n⚠️  No GDSC-Clinical Trials matches found!")

        results = {
            'ct_matched_drugs': 0,
            'ct_match_rate': 0.0,
            'note': 'No matches found'
        }

        with open('results/lung_clinical_trials_validation_results.json', 'w') as f:
            json.dump(results, f, indent=2)

        return results

    # Save matched drugs
    ct_matches.to_csv('results/lung_clinical_trials_matched_drugs.csv', index=False)
    print(f"\n✓ Saved: results/lung_clinical_trials_matched_drugs.csv")

    # Calculate metrics
    metrics = calculate_clinical_trial_metrics(top30_2b, top30_2c, ct_matches)

    if metrics:
        # Save metrics
        metrics['ct_matched_drugs'] = ct_matches['canonical_drug_id'].nunique()
        metrics['ct_match_rate'] = ct_matches['canonical_drug_id'].nunique() / len(unified)
        metrics['ct_total_trials'] = len(ct_matches)

        with open('results/lung_clinical_trials_validation_results.json', 'w') as f:
            json.dump(metrics, f, indent=2)

        print(f"\n{'='*80}")
        print("CLINICAL TRIALS VALIDATION COMPLETE")
        print(f"{'='*80}")
        print(f"✓ Saved: results/lung_clinical_trials_validation_results.json")

    return metrics

if __name__ == '__main__':
    main()
