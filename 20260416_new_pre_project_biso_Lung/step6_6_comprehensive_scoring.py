#!/usr/bin/env python3
"""
Step 6.6: Comprehensive Scoring & Final Ranking
- Integrate all validation results (PRISM, Clinical Trials, COSMIC, CPTAC)
- Calculate multi-objective scores
- Generate final drug ranking with confidence scores
"""

import sys
import json
from pathlib import Path

_LUNG = Path(__file__).resolve().parent
if str(_LUNG) not in sys.path:
    sys.path.insert(0, str(_LUNG))

import pandas as pd
import numpy as np

from step6_validation_context import Step6ValidationContext


def load_all_validation_results(ctx: Step6ValidationContext):
    """Load all validation results."""

    print("="*80)
    print("STEP 6.6: COMPREHENSIVE SCORING & FINAL RANKING")
    print("="*80)

    results = {}

    # Load PRISM results
    prism_file = ctx.results_json("prism_validation_results")
    if prism_file.exists():
        with open(prism_file, "r", encoding="utf-8") as f:
            results["prism"] = json.load(f)
        print(f"✓ Loaded PRISM results ({prism_file})")

    # Load Clinical Trials results
    ct_file = ctx.results_json("clinical_trials_validation_results")
    if ct_file.exists():
        with open(ct_file, "r", encoding="utf-8") as f:
            results["clinical_trials"] = json.load(f)
        print(f"✓ Loaded Clinical Trials results ({ct_file})")

    # Load COSMIC results
    cosmic_file = ctx.results_json("cosmic_validation_results")
    if cosmic_file.exists():
        with open(cosmic_file, "r", encoding="utf-8") as f:
            results["cosmic"] = json.load(f)
        print(f"✓ Loaded COSMIC results ({cosmic_file})")

    # Load CPTAC results
    cptac_file = ctx.results_json("cptac_validation_results")
    if cptac_file.exists():
        with open(cptac_file, "r", encoding="utf-8") as f:
            results["cptac"] = json.load(f)
        print(f"✓ Loaded CPTAC results ({cptac_file})")

    ctx.merge_step_sources(
        "6.6_scoring_inputs",
        [f"loaded_result_keys={list(results.keys())}"],
    )
    return results


def load_validation_matches(ctx: Step6ValidationContext):
    """Load detailed validation matches for each drug."""

    print(f"\n{'─'*80}")
    print("LOADING VALIDATION MATCHES")
    print(f"{'─'*80}")

    matches = {}

    # PRISM matches
    prism_file = ctx.results_csv("prism_matched_drugs")
    if prism_file.exists():
        df_prism = pd.read_csv(prism_file)
        prism_drugs = set(df_prism["canonical_drug_id"].unique())
        matches["prism"] = prism_drugs
        print(f"✓ PRISM: {len(prism_drugs)} drugs ({prism_file})")

    # Clinical Trials matches
    ct_file = ctx.results_csv("clinical_trials_matched_drugs")
    if ct_file.exists():
        df_ct = pd.read_csv(ct_file)
        ct_drugs = set(df_ct["canonical_drug_id"].unique())
        matches["clinical_trials"] = ct_drugs
        print(f"✓ Clinical Trials: {len(ct_drugs)} drugs ({ct_file})")

        # Count trials per drug
        trial_counts = df_ct.groupby("canonical_drug_id").size().to_dict()
        matches["clinical_trials_counts"] = trial_counts

    # COSMIC matches
    cosmic_file = ctx.results_csv("cosmic_matched_drugs")
    if cosmic_file.exists():
        df_cosmic = pd.read_csv(cosmic_file)
        cosmic_drugs = set(df_cosmic["canonical_drug_id"].unique())
        matches["cosmic"] = cosmic_drugs
        print(f"✓ COSMIC: {len(cosmic_drugs)} drugs ({cosmic_file})")

        # Count actionability records per drug
        cosmic_counts = df_cosmic.groupby("canonical_drug_id").size().to_dict()
        matches["cosmic_counts"] = cosmic_counts

    # CPTAC matches
    cptac_file = ctx.results_csv("cptac_target_expression_stats")
    if cptac_file.exists():
        df_cptac = pd.read_csv(cptac_file)
        cptac_drugs = set(df_cptac["canonical_drug_id"].unique())
        matches["cptac"] = cptac_drugs
        print(f"✓ CPTAC: {len(cptac_drugs)} drugs ({cptac_file})")

        # Get mean expression per drug
        cptac_expr = df_cptac.groupby("canonical_drug_id")["mean_expression"].mean().to_dict()
        matches["cptac_expression"] = cptac_expr

    return matches

def calculate_drug_scores(top30_2b, top30_2c, matches):
    """Calculate comprehensive scores for each drug."""

    print(f"\n{'─'*80}")
    print("CALCULATING COMPREHENSIVE SCORES")
    print(f"{'─'*80}")

    # Combine Top 30 from both phases
    all_drugs = pd.concat([
        top30_2b[['canonical_drug_id', 'DRUG_NAME', 'TARGET', 'rank', 'pred_ic50_mean']].assign(phase='2B'),
        top30_2c[['canonical_drug_id', 'DRUG_NAME', 'TARGET', 'rank', 'pred_ic50_mean']].assign(phase='2C')
    ])

    # Get unique drugs
    unique_drugs = all_drugs.drop_duplicates(subset=['canonical_drug_id'])

    scores = []

    for idx, row in unique_drugs.iterrows():
        drug_id = row['canonical_drug_id']
        drug_name = row['DRUG_NAME']

        score_dict = {
            'canonical_drug_id': drug_id,
            'drug_name': drug_name,
            'target': row['TARGET']
        }

        # Get ranks from both phases
        rank_2b = top30_2b[top30_2b['canonical_drug_id'] == drug_id]['rank'].values
        rank_2c = top30_2c[top30_2c['canonical_drug_id'] == drug_id]['rank'].values

        score_dict['in_2b'] = len(rank_2b) > 0
        score_dict['in_2c'] = len(rank_2c) > 0
        score_dict['rank_2b'] = rank_2b[0] if len(rank_2b) > 0 else None
        score_dict['rank_2c'] = rank_2c[0] if len(rank_2c) > 0 else None

        # Calculate prediction score (lower rank = higher score)
        pred_scores = []
        if len(rank_2b) > 0:
            pred_scores.append(1.0 / rank_2b[0])
        if len(rank_2c) > 0:
            pred_scores.append(1.0 / rank_2c[0])
        score_dict['prediction_score'] = np.mean(pred_scores) if len(pred_scores) > 0 else 0

        # Validation scores
        score_dict['prism_validated'] = drug_id in matches.get('prism', set())
        score_dict['clinical_trials_validated'] = drug_id in matches.get('clinical_trials', set())
        score_dict['cosmic_validated'] = drug_id in matches.get('cosmic', set())
        score_dict['cptac_validated'] = drug_id in matches.get('cptac', set())

        # Validation counts
        score_dict['n_clinical_trials'] = matches.get('clinical_trials_counts', {}).get(drug_id, 0)
        score_dict['n_cosmic_records'] = matches.get('cosmic_counts', {}).get(drug_id, 0)
        score_dict['target_expression'] = matches.get('cptac_expression', {}).get(drug_id, 0)

        # Total validation score
        validation_count = sum([
            score_dict['prism_validated'],
            score_dict['clinical_trials_validated'],
            score_dict['cosmic_validated'],
            score_dict['cptac_validated']
        ])
        score_dict['validation_score'] = validation_count / 4.0  # 0 to 1

        # Multi-objective score (weighted combination)
        # Prediction: 40%, Validation: 30%, Clinical Trials: 20%, Expression: 10%
        multi_obj_score = (
            0.40 * score_dict['prediction_score'] +
            0.30 * score_dict['validation_score'] +
            0.20 * min(score_dict['n_clinical_trials'] / 100.0, 1.0) +
            0.10 * min(score_dict['target_expression'] / 1000.0, 1.0)
        )
        score_dict['multi_objective_score'] = multi_obj_score

        # Confidence score (how well validated)
        confidence = validation_count * 25  # 0 to 100%
        score_dict['confidence'] = confidence

        scores.append(score_dict)

    df_scores = pd.DataFrame(scores)

    # Sort by multi-objective score
    df_scores = df_scores.sort_values('multi_objective_score', ascending=False).reset_index(drop=True)
    df_scores['final_rank'] = np.arange(1, len(df_scores) + 1)

    print(f"✓ Calculated scores for {len(df_scores)} drugs")

    return df_scores

def print_final_ranking(df_scores):
    """Print final ranking."""

    print(f"\n{'='*80}")
    print("FINAL DRUG RANKING (Top 20)")
    print(f"{'='*80}")

    top20 = df_scores.head(20)

    display_cols = ['final_rank', 'drug_name', 'multi_objective_score', 'confidence',
                    'prism_validated', 'clinical_trials_validated', 'cosmic_validated', 'cptac_validated',
                    'n_clinical_trials', 'rank_2b', 'rank_2c']

    print(top20[display_cols].to_string(index=False))

    # Summary statistics
    print(f"\n{'='*80}")
    print("SUMMARY STATISTICS")
    print(f"{'='*80}")

    print(f"\nValidation Coverage:")
    print(f"  ✓ PRISM validated: {df_scores['prism_validated'].sum()}/{len(df_scores)} ({df_scores['prism_validated'].mean()*100:.1f}%)")
    print(f"  ✓ Clinical Trials validated: {df_scores['clinical_trials_validated'].sum()}/{len(df_scores)} ({df_scores['clinical_trials_validated'].mean()*100:.1f}%)")
    print(f"  ✓ COSMIC validated: {df_scores['cosmic_validated'].sum()}/{len(df_scores)} ({df_scores['cosmic_validated'].mean()*100:.1f}%)")
    print(f"  ✓ CPTAC validated: {df_scores['cptac_validated'].sum()}/{len(df_scores)} ({df_scores['cptac_validated'].mean()*100:.1f}%)")

    print(f"\nConfidence Distribution:")
    print(f"  ✓ High (75-100%): {len(df_scores[df_scores['confidence'] >= 75])}")
    print(f"  ✓ Medium (50-75%): {len(df_scores[(df_scores['confidence'] >= 50) & (df_scores['confidence'] < 75)])}")
    print(f"  ✓ Low (25-50%): {len(df_scores[(df_scores['confidence'] >= 25) & (df_scores['confidence'] < 50)])}")
    print(f"  ✓ Very Low (0-25%): {len(df_scores[df_scores['confidence'] < 25])}")

def main(argv=None):
    ctx = Step6ValidationContext.load(argv)
    for p in (ctx.top30_2b, ctx.top30_2c):
        if not p.exists():
            raise FileNotFoundError(f"Required input missing: {p}")

    # Load all validation results
    validation_results = load_all_validation_results(ctx)
    validation_matches = load_validation_matches(ctx)

    # Load Top 30
    print(f"\n{'─'*80}")
    print("LOADING TOP 30 DRUGS")
    print(f"{'─'*80}")

    top30_2b = pd.read_csv(ctx.top30_2b)
    top30_2c = pd.read_csv(ctx.top30_2c)

    print(f"✓ Phase 2B: {len(top30_2b)} drugs ({ctx.top30_2b})")
    print(f"✓ Phase 2C: {len(top30_2c)} drugs ({ctx.top30_2c})")

    # Calculate comprehensive scores
    df_scores = calculate_drug_scores(top30_2b, top30_2c, validation_matches)

    # Save results
    out_rank = ctx.results_csv("final_drug_ranking_with_scores")
    out_rank.parent.mkdir(parents=True, exist_ok=True)
    df_scores.to_csv(out_rank, index=False)
    print(f"\n✓ Saved: {out_rank}")

    # Print final ranking
    print_final_ranking(df_scores)

    # Save summary
    summary = {
        'total_drugs': len(df_scores),
        'validation_sources': len(validation_results),
        'avg_confidence': float(df_scores['confidence'].mean()),
        'avg_validation_score': float(df_scores['validation_score'].mean()),
        'high_confidence_drugs': int(len(df_scores[df_scores['confidence'] >= 75])),
        'top_10_drugs': df_scores.head(10)[['drug_name', 'multi_objective_score', 'confidence']].to_dict('records')
    }

    with open(ctx.results_json("final_ranking_summary"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n✓ Saved: {ctx.results_json('final_ranking_summary')}")

    print(f"\n{'='*80}")
    print("COMPREHENSIVE SCORING COMPLETE")
    print(f"{'='*80}")

    return df_scores, summary

if __name__ == '__main__':
    main(sys.argv[1:])
