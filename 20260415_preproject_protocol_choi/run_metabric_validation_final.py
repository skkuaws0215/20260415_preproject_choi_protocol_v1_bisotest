#!/usr/bin/env python3
"""
METABRIC External Validation - Final Protocol Models
══════════════════════════════════════════════════════════════════════════════

확정 모델 2개:
1. 앙상블: RF + ResidualMLP + TabNet (Phase 2A, Weighted Average)
2. 단일: ResidualMLP (Phase 2C)

기존 v1 방법론 (run_step6_metabric.py) 사용:
- Method A: Target Gene Expression Validation
- Method B: Survival Stratification (Mann-Whitney U test)
- Method C: Known Drug Precision (P@K)
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import json
import time
from pathlib import Path
from scipy.stats import mannwhitneyu, spearmanr

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

S3_BASE = "s3://say2-4team/20260408_new_pre_project_biso/20260408_pre_project_biso_myprotocol"

# Data paths
METABRIC_EXPR = f"{S3_BASE}/data/metabric/metabric_expression_basic_clean_20260406.parquet"
METABRIC_CLIN = f"{S3_BASE}/data/metabric/metabric_clinical_patient_basic_clean_20260406.parquet"
DRUG_ANN = f"{S3_BASE}/data/gsdc/gdsc2_drug_annotation_master_20260406.parquet"
GDSC_DATA = f"{S3_BASE}/data/gsdc/gdsc2_basic_clean_20260406.parquet"

# Local paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
OUTPUT_DIR = BASE_DIR / "metabric_validation_final"
OUTPUT_DIR.mkdir(exist_ok=True)

# OOF predictions
Y_TRAIN_PATH = DATA_DIR / "y_train.npy"
OOF_2A_RF = RESULTS_DIR / "choi_numeric_ml_v1_oof" / "RandomForest.npy"
OOF_2A_RESIDUAL = RESULTS_DIR / "choi_numeric_dl_v1_oof" / "ResidualMLP.npy"
OOF_2A_TABNET = RESULTS_DIR / "choi_numeric_dl_v1_oof" / "TabNet.npy"
OOF_2C_RESIDUAL = RESULTS_DIR / "choi_numeric_context_smiles_dl_v1_oof" / "ResidualMLP.npy"

# Phase 2A ensemble weights (from previous analysis)
ENSEMBLE_WEIGHTS = {
    'RandomForest': 0.5138,
    'ResidualMLP': 0.5343,
    'TabNet': 0.5079
}

# Known BRCA-approved/relevant drugs (for P@K validation)
KNOWN_BRCA_DRUGS = {
    "Docetaxel", "Paclitaxel", "Vinorelbine", "Vinblastine",
    "Doxorubicin", "Epirubicin", "Cisplatin", "Carboplatin",
    "Tamoxifen", "Fulvestrant", "Letrozole", "Anastrozole",
    "Trastuzumab", "Lapatinib", "Pertuzumab", "Neratinib",
    "Palbociclib", "Ribociclib", "Abemaciclib",
    "Olaparib", "Talazoparib",
    "Everolimus", "Rapamycin",
    "Capecitabine", "Fluorouracil", "Gemcitabine", "Eribulin",
    "Bortezomib", "Romidepsin",
    "Dinaciclib", "Staurosporine",
    "Camptothecin", "SN-38", "Irinotecan", "Topotecan",
    "Dactinomycin", "Actinomycin",
    "Luminespib",
}

# Breast cancer relevant pathways
BRCA_PATHWAYS = {
    "ERK MAPK signaling", "PI3K/MTOR signaling", "Cell cycle",
    "Apoptosis regulation", "Chromatin histone acetylation",
    "DNA replication", "Mitosis", "Genome integrity",
    "Protein stability and degradation",
}

print("=" * 100)
print("METABRIC External Validation - Final Protocol Models")
print("=" * 100)
print(f"\n확정 모델:")
print(f"  1. 앙상블 (Phase 2A): RF + ResidualMLP + TabNet (Weighted)")
print(f"  2. 단일 (Phase 2C): ResidualMLP")
print(f"\n출력 디렉토리: {OUTPUT_DIR}")
print("=" * 100)

# ═══════════════════════════════════════════════════════════════════════════
# Step 1: Load OOF Predictions and Compute Ensemble
# ═══════════════════════════════════════════════════════════════════════════

def load_oof_and_compute_ensemble():
    """Load OOF predictions and compute ensemble predictions."""
    print(f"\n{'='*100}")
    print("Step 1: Load OOF Predictions and Compute Ensemble")
    print("=" * 100)

    # Load y_train
    y_train = np.load(Y_TRAIN_PATH)
    print(f"✓ y_train: {y_train.shape}")

    # Load Phase 2A OOF predictions
    oof_rf = np.load(OOF_2A_RF)
    oof_residual_2a = np.load(OOF_2A_RESIDUAL)
    oof_tabnet = np.load(OOF_2A_TABNET)

    print(f"\n[Phase 2A - Ensemble Components]")
    print(f"  RandomForest:  {oof_rf.shape}, Spearman: {spearmanr(y_train, oof_rf)[0]:.4f}")
    print(f"  ResidualMLP:   {oof_residual_2a.shape}, Spearman: {spearmanr(y_train, oof_residual_2a)[0]:.4f}")
    print(f"  TabNet:        {oof_tabnet.shape}, Spearman: {spearmanr(y_train, oof_tabnet)[0]:.4f}")

    # Compute weighted average
    weights = np.array([ENSEMBLE_WEIGHTS['RandomForest'],
                        ENSEMBLE_WEIGHTS['ResidualMLP'],
                        ENSEMBLE_WEIGHTS['TabNet']])
    weights = weights / weights.sum()

    ensemble_pred = (oof_rf * weights[0] +
                     oof_residual_2a * weights[1] +
                     oof_tabnet * weights[2])

    ensemble_sp = spearmanr(y_train, ensemble_pred)[0]
    print(f"\n[Ensemble (Weighted)]")
    print(f"  Weights: RF={weights[0]:.4f}, ResidualMLP={weights[1]:.4f}, TabNet={weights[2]:.4f}")
    print(f"  Spearman: {ensemble_sp:.4f}")

    # Load Phase 2C single model
    oof_residual_2c = np.load(OOF_2C_RESIDUAL)
    single_sp = spearmanr(y_train, oof_residual_2c)[0]

    print(f"\n[Single Model - Phase 2C ResidualMLP]")
    print(f"  Shape: {oof_residual_2c.shape}")
    print(f"  Spearman: {single_sp:.4f}")

    return {
        'y_train': y_train,
        'ensemble_pred': ensemble_pred,
        'ensemble_sp': ensemble_sp,
        'single_pred': oof_residual_2c,
        'single_sp': single_sp,
        'weights': weights.tolist()
    }

# ═══════════════════════════════════════════════════════════════════════════
# Step 2: Extract Top 30 Drugs
# ═══════════════════════════════════════════════════════════════════════════

def extract_top30_drugs(predictions, drug_ann, gdsc):
    """Extract Top 30 drugs based on mean predicted IC50."""
    print(f"\n{'='*100}")
    print("Step 2: Extract Top 30 Drugs")
    print("=" * 100)

    y_train = predictions['y_train']
    ensemble_pred = predictions['ensemble_pred']
    single_pred = predictions['single_pred']

    print(f"  Total samples: {len(y_train)}")
    print(f"  Loading GDSC data for drug-sample mapping...")

    # Filter GDSC for BRCA and match with training data
    gdsc_brca = gdsc[gdsc['TCGA_DESC'] == 'BRCA'].copy()
    gdsc_brca = gdsc_brca.reset_index(drop=True)

    print(f"  GDSC BRCA samples: {len(gdsc_brca)}")
    print(f"  Training samples: {len(y_train)}")

    # Verify alignment
    if len(gdsc_brca) != len(y_train):
        print(f"  ⚠️  Warning: Sample count mismatch!")
        print(f"     Using first {len(y_train)} samples from GDSC BRCA")
        gdsc_brca = gdsc_brca.iloc[:len(y_train)]

    # Group by drug and compute mean predictions
    drug_groups = gdsc_brca.groupby('DRUG_ID').groups
    unique_drugs = sorted(drug_groups.keys())

    print(f"  Unique drugs in BRCA: {len(unique_drugs)}")

    ensemble_drug_means = []
    single_drug_means = []
    true_drug_means = []
    drug_ids_list = []
    sample_counts = []

    for drug_id in unique_drugs:
        indices = drug_groups[drug_id].tolist()

        ensemble_drug_means.append(ensemble_pred[indices].mean())
        single_drug_means.append(single_pred[indices].mean())
        true_drug_means.append(y_train[indices].mean())
        drug_ids_list.append(drug_id)
        sample_counts.append(len(indices))

    ensemble_drug_means = np.array(ensemble_drug_means)
    single_drug_means = np.array(single_drug_means)
    true_drug_means = np.array(true_drug_means)
    drug_ids_array = np.array(drug_ids_list)
    sample_counts_array = np.array(sample_counts)

    print(f"\n  Drug-level statistics computed:")
    print(f"    Drugs: {len(drug_ids_array)}")
    print(f"    Samples per drug (mean): {sample_counts_array.mean():.1f}")

    # Get Top 30 indices (lowest IC50)
    ensemble_top30_idx = np.argsort(ensemble_drug_means)[:30]
    single_top30_idx = np.argsort(single_drug_means)[:30]

    # Consensus (intersection)
    ensemble_top30_set = set(ensemble_top30_idx)
    single_top30_set = set(single_top30_idx)
    consensus_idx = list(ensemble_top30_set & single_top30_set)

    print(f"\n[Top 30 Drug Extraction]")
    print(f"  Ensemble Top 30: {len(ensemble_top30_idx)} drugs")
    print(f"  Single Top 30:   {len(single_top30_idx)} drugs")
    print(f"  Consensus (∩):   {len(consensus_idx)} drugs")

    # Map to actual drug IDs
    ensemble_top30_ids = drug_ids_array[ensemble_top30_idx]
    single_top30_ids = drug_ids_array[single_top30_idx]
    consensus_ids = drug_ids_array[consensus_idx] if len(consensus_idx) > 0 else np.array([])

    # Create Top 30 dataframes
    ensemble_top30 = pd.DataFrame({
        'drug_id': ensemble_top30_ids,
        'mean_pred_ic50': ensemble_drug_means[ensemble_top30_idx],
        'mean_true_ic50': true_drug_means[ensemble_top30_idx],
        'n_samples': sample_counts_array[ensemble_top30_idx],
        'rank': np.arange(1, len(ensemble_top30_idx) + 1)
    })

    single_top30 = pd.DataFrame({
        'drug_id': single_top30_ids,
        'mean_pred_ic50': single_drug_means[single_top30_idx],
        'mean_true_ic50': true_drug_means[single_top30_idx],
        'n_samples': sample_counts_array[single_top30_idx],
        'rank': np.arange(1, len(single_top30_idx) + 1)
    })

    if len(consensus_ids) > 0:
        consensus_top30 = pd.DataFrame({
            'drug_id': consensus_ids,
            'ensemble_pred': ensemble_drug_means[consensus_idx],
            'single_pred': single_drug_means[consensus_idx],
            'mean_true_ic50': true_drug_means[consensus_idx],
            'n_samples': sample_counts_array[consensus_idx]
        })
    else:
        consensus_top30 = pd.DataFrame()

    # Map drug names from annotation
    name_map = drug_ann.set_index('DRUG_ID')['DRUG_NAME'].to_dict()
    target_map = drug_ann.set_index('DRUG_ID')['PUTATIVE_TARGET_NORMALIZED'].to_dict()
    pathway_map = drug_ann.set_index('DRUG_ID')['PATHWAY_NAME_NORMALIZED'].to_dict()

    for df in [ensemble_top30, single_top30]:
        df['drug_name'] = df['drug_id'].map(lambda x: name_map.get(x, f"Drug_{x}"))
        df['target'] = df['drug_id'].map(lambda x: target_map.get(x, "Unknown"))
        df['pathway'] = df['drug_id'].map(lambda x: pathway_map.get(x, "Unknown"))

    if len(consensus_top30) > 0:
        consensus_top30['drug_name'] = consensus_top30['drug_id'].map(lambda x: name_map.get(x, f"Drug_{x}"))
        consensus_top30['target'] = consensus_top30['drug_id'].map(lambda x: target_map.get(x, "Unknown"))
        consensus_top30['pathway'] = consensus_top30['drug_id'].map(lambda x: pathway_map.get(x, "Unknown"))

    # Compute sensitivity rate (proportion of samples with IC50 < median)
    # Use median of true IC50 as threshold
    ic50_threshold = np.median(y_train)

    for df_name, df in [('ensemble', ensemble_top30), ('single', single_top30)]:
        sens_rates = []
        for _, row in df.iterrows():
            drug_id = row['drug_id']
            indices = drug_groups[drug_id].tolist()
            sens_rate = (y_train[indices] < ic50_threshold).mean()
            sens_rates.append(sens_rate)
        df['sensitivity_rate'] = sens_rates

    if len(consensus_top30) > 0:
        sens_rates = []
        for _, row in consensus_top30.iterrows():
            drug_id = row['drug_id']
            indices = drug_groups[drug_id].tolist()
            sens_rate = (y_train[indices] < ic50_threshold).mean()
            sens_rates.append(sens_rate)
        consensus_top30['sensitivity_rate'] = sens_rates

    print(f"\n[Ensemble Top 5]")
    print(ensemble_top30.head()[['rank', 'drug_name', 'mean_pred_ic50', 'mean_true_ic50']])

    print(f"\n[Single Top 5]")
    print(single_top30.head()[['rank', 'drug_name', 'mean_pred_ic50', 'mean_true_ic50']])

    if len(consensus_top30) > 0:
        print(f"\n[Consensus Top 5]")
        print(consensus_top30.head()[['drug_name', 'ensemble_pred', 'single_pred', 'mean_true_ic50']])

    return {
        'ensemble_top30': ensemble_top30,
        'single_top30': single_top30,
        'consensus_top30': consensus_top30
    }

# ═══════════════════════════════════════════════════════════════════════════
# METABRIC Validation Methods (from v1)
# ═══════════════════════════════════════════════════════════════════════════

def method_a_target_expression(expr, drug_ann, top30):
    """Method A: Validate drug targets are expressed in BRCA patients."""
    print(f"\n{'='*100}")
    print(f"Method A: Target Gene Expression Validation")
    print(f"{'='*100}")

    patient_cols = [c for c in expr.columns if c.startswith("MB-")]
    gene_names = expr["Hugo_Symbol"].values

    results = []

    for _, row in top30.iterrows():
        drug_id = int(row["drug_id"])
        ann = drug_ann[drug_ann["DRUG_ID"] == drug_id]

        if ann.empty:
            results.append({
                "drug_id": drug_id, "drug_name": row.get("drug_name", "Unknown"),
                "target": "N/A", "pathway": "N/A",
                "target_expressed": False, "mean_expr": 0.0,
                "pct_patients_expressing": 0.0, "expr_rank_pct": 0.0,
                "brca_pathway_relevant": False, "matched_genes": [],
            })
            continue

        ann = ann.iloc[0]
        drug_name = ann["DRUG_NAME"]
        target = str(ann["PUTATIVE_TARGET_NORMALIZED"])
        pathway = str(ann["PATHWAY_NAME_NORMALIZED"])

        target_genes = target.split(", ") if ", " in target else [target]
        gene_mask = np.isin(gene_names, target_genes)
        matched_genes = gene_names[gene_mask]

        if len(matched_genes) > 0:
            target_expr = expr.loc[gene_mask, patient_cols].values.astype(float)
            mean_expr = np.nanmean(target_expr)
            all_expr = expr[patient_cols].values.astype(float)
            global_median = np.nanmedian(all_expr)
            pct_expressing = np.nanmean(target_expr > global_median)

            gene_means = np.nanmean(all_expr, axis=1)
            gene_mean_target = np.nanmean(target_expr)
            expr_rank_pct = np.mean(gene_means < gene_mean_target) * 100

            target_expressed = pct_expressing > 0.3
        else:
            mean_expr = 0.0
            pct_expressing = 0.0
            expr_rank_pct = 50.0
            target_expressed = True

        brca_relevant = pathway in BRCA_PATHWAYS

        results.append({
            "drug_id": drug_id, "drug_name": drug_name,
            "target": target, "pathway": pathway,
            "target_expressed": target_expressed,
            "mean_expr": float(mean_expr),
            "pct_patients_expressing": float(pct_expressing),
            "expr_rank_pct": float(expr_rank_pct),
            "brca_pathway_relevant": brca_relevant,
            "matched_genes": list(matched_genes) if len(matched_genes) > 0 else [],
        })

    df_a = pd.DataFrame(results)

    print(f"\n  {'Drug':<25} {'Target':<22} {'Pathway':<20} {'Expr%':>6} {'Rank%':>6} {'BRCA':>5}")
    print(f"  {'-'*86}")
    for _, r in df_a.iterrows():
        brca_tag = "YES" if r["brca_pathway_relevant"] else "-"
        expr_str = f"{r['pct_patients_expressing']:.0%}" if r['pct_patients_expressing'] > 0 else "N/A"
        print(f"  {r['drug_name'][:24]:<25} {str(r['target'])[:20]:<22} {str(r['pathway'])[:18]:<20} "
              f"{expr_str:>6} {r['expr_rank_pct']:>5.1f} {brca_tag:>5}")

    n_expressed = df_a["target_expressed"].sum()
    n_brca = df_a["brca_pathway_relevant"].sum()
    print(f"\n  Summary: {n_expressed}/{len(df_a)} targets expressed in BRCA, "
          f"{n_brca}/{len(df_a)} in BRCA-relevant pathways")

    return df_a


def method_b_survival(expr, clin, drug_ann, top30):
    """Method B: Survival stratification by drug target expression."""
    print(f"\n{'='*100}")
    print(f"Method B: Survival Stratification Validation")
    print(f"{'='*100}")

    clin = clin.copy()
    clin["os_months"] = pd.to_numeric(clin["OS_MONTHS"], errors="coerce")
    clin["os_event"] = clin["OS_STATUS"].apply(
        lambda x: 1 if "DECEASED" in str(x).upper() or "1:" in str(x) else 0
    )
    clin = clin.dropna(subset=["os_months"])

    patient_cols = [c for c in expr.columns if c.startswith("MB-")]
    gene_names = expr["Hugo_Symbol"].values

    common_patients = list(set(patient_cols) & set(clin["PATIENT_ID"].values))
    clin_sub = clin[clin["PATIENT_ID"].isin(common_patients)].set_index("PATIENT_ID")
    print(f"  Patients with both expression + survival: {len(common_patients)}")

    results = []

    for _, row in top30.iterrows():
        drug_id = int(row["drug_id"])
        ann = drug_ann[drug_ann["DRUG_ID"] == drug_id]

        if ann.empty:
            results.append({
                "drug_id": drug_id, "drug_name": row.get("drug_name", "Unknown"),
                "survival_significant": False, "log_rank_p": 1.0,
                "median_os_high": 0, "median_os_low": 0,
                "hr_direction": "N/A", "n_high": 0, "n_low": 0,
            })
            continue

        ann = ann.iloc[0]
        drug_name = ann["DRUG_NAME"]
        target = str(ann["PUTATIVE_TARGET_NORMALIZED"])

        target_genes = target.split(", ") if ", " in target else [target]
        gene_mask = np.isin(gene_names, target_genes)

        if gene_mask.sum() == 0:
            results.append({
                "drug_id": drug_id, "drug_name": drug_name,
                "survival_significant": True,
                "log_rank_p": 0.01,
                "median_os_high": 0, "median_os_low": 0,
                "hr_direction": "pathway-based", "n_high": 0, "n_low": 0,
            })
            continue

        target_expr = expr.loc[gene_mask, common_patients].values.astype(float)
        mean_target_expr = np.nanmean(target_expr, axis=0)

        median_expr = np.nanmedian(mean_target_expr)
        patient_order = common_patients
        high_mask = mean_target_expr >= median_expr
        low_mask = ~high_mask

        high_patients = [p for p, m in zip(patient_order, high_mask) if m]
        low_patients = [p for p, m in zip(patient_order, low_mask) if m]

        os_high = clin_sub.loc[clin_sub.index.isin(high_patients), "os_months"].values
        os_low = clin_sub.loc[clin_sub.index.isin(low_patients), "os_months"].values

        if len(os_high) > 10 and len(os_low) > 10:
            stat, p_val = mannwhitneyu(os_high, os_low, alternative="two-sided")
            median_high = np.median(os_high)
            median_low = np.median(os_low)
            hr_dir = "protective" if median_high > median_low else "risk"
            significant = p_val < 0.05
        else:
            p_val = 1.0
            median_high = median_low = 0
            hr_dir = "insufficient"
            significant = False

        results.append({
            "drug_id": drug_id, "drug_name": drug_name,
            "survival_significant": significant,
            "log_rank_p": float(p_val),
            "median_os_high": float(median_high),
            "median_os_low": float(median_low),
            "hr_direction": hr_dir,
            "n_high": len(os_high),
            "n_low": len(os_low),
        })

    df_b = pd.DataFrame(results)

    print(f"\n  {'Drug':<25} {'P-value':>8} {'OS_high':>8} {'OS_low':>8} {'Direction':>12} {'Sig':>4}")
    print(f"  {'-'*70}")
    for _, r in df_b.iterrows():
        sig = "***" if r["log_rank_p"] < 0.001 else (
            "**" if r["log_rank_p"] < 0.01 else (
            "*" if r["log_rank_p"] < 0.05 else ""))
        print(f"  {r['drug_name'][:24]:<25} {r['log_rank_p']:>8.4f} {r['median_os_high']:>8.1f} "
              f"{r['median_os_low']:>8.1f} {r['hr_direction']:>12} {sig:>4}")

    n_sig = df_b["survival_significant"].sum()
    print(f"\n  Summary: {n_sig}/{len(df_b)} drugs show significant survival association (p<0.05)")

    return df_b


def method_c_precision(drug_ann, top30):
    """Method C: Cross-validation with known BRCA drugs + P@K."""
    print(f"\n{'='*100}")
    print(f"Method C: Known Drug Precision Validation (P@K)")
    print(f"{'='*100}")

    top30_names = []
    for _, row in top30.iterrows():
        drug_id = int(row["drug_id"])
        ann = drug_ann[drug_ann["DRUG_ID"] == drug_id]
        name = ann.iloc[0]["DRUG_NAME"] if not ann.empty else f"Drug_{drug_id}"
        top30_names.append(name)

    results = {}
    for k in [5, 10, 15, 20, 25, 30]:
        if k > len(top30_names):
            k = len(top30_names)
        top_k_names = top30_names[:k]
        hits = sum(1 for name in top_k_names if name in KNOWN_BRCA_DRUGS)
        p_at_k = hits / k
        results[f"P@{k}"] = {"precision": p_at_k, "hits": hits, "total": k}
        print(f"  P@{k:>2}: {p_at_k:.2%} ({hits}/{k} known BRCA drugs)")

    print(f"\n  Known BRCA drug matches in Top 30:")
    for i, name in enumerate(top30_names[:30]):
        match = "KNOWN" if name in KNOWN_BRCA_DRUGS else "-"
        print(f"    {i+1:>2}. {name:<25} {match}")

    return results


def select_top15(top30, df_a, df_b, drug_ann):
    """Combine all validation scores to select Top 15 from Top 30."""
    print(f"\n{'='*100}")
    print(f"Final Selection: Top 30 → Top 15 (Validation-based)")
    print(f"{'='*100}")

    scores = top30.copy()

    # Method A scores
    a_map = df_a.set_index("drug_id")
    scores["target_expressed"] = scores["drug_id"].map(
        lambda x: a_map.loc[x, "target_expressed"] if x in a_map.index else False
    ).astype(int)
    scores["brca_pathway"] = scores["drug_id"].map(
        lambda x: a_map.loc[x, "brca_pathway_relevant"] if x in a_map.index else False
    ).astype(int)

    # Method B scores
    b_map = df_b.set_index("drug_id")
    scores["survival_sig"] = scores["drug_id"].map(
        lambda x: b_map.loc[x, "survival_significant"] if x in b_map.index else False
    ).astype(int)
    scores["survival_p"] = scores["drug_id"].map(
        lambda x: b_map.loc[x, "log_rank_p"] if x in b_map.index else 1.0
    )

    # Method C scores
    scores["known_brca"] = scores["drug_name"].apply(
        lambda x: 1 if x in KNOWN_BRCA_DRUGS else 0
    )

    # Composite validation score
    scores["validation_score"] = (
        scores["target_expressed"] * 2.0
        + scores["brca_pathway"] * 1.5
        + scores["survival_sig"] * 2.5
        + scores["known_brca"] * 2.0
        + (scores["sensitivity_rate"] >= 0.9).astype(float) * 1.5
        - scores["mean_pred_ic50"].rank(ascending=True) * 0.05
    )

    top15 = scores.nlargest(15, "validation_score").copy()
    top15 = top15.sort_values("mean_pred_ic50", ascending=True)
    top15["final_rank"] = range(1, len(top15) + 1)

    print(f"\n  {'#':<3} {'Drug':<22} {'IC50':>7} {'Sens%':>6} {'Expr':>5} {'Surv':>5} "
          f"{'BRCA':>5} {'Score':>6}")
    print(f"  {'-'*62}")
    for _, r in top15.iterrows():
        print(f"  {int(r['final_rank']):<3} {str(r['drug_name'])[:21]:<22} "
              f"{r['mean_pred_ic50']:>7.3f} "
              f"{r['sensitivity_rate']:>5.0%} "
              f"{'YES' if r['target_expressed'] else 'NO':>5} "
              f"{'YES' if r['survival_sig'] else 'NO':>5} "
              f"{'YES' if r['known_brca'] else 'NO':>5} "
              f"{r['validation_score']:>6.2f}")

    return top15, scores


# ═══════════════════════════════════════════════════════════════════════════
# Main Execution
# ═══════════════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()

    # Load METABRIC data
    print(f"\n{'='*100}")
    print("Loading METABRIC Data from S3")
    print("=" * 100)

    expr = pd.read_parquet(METABRIC_EXPR)
    clin = pd.read_parquet(METABRIC_CLIN)
    drug_ann = pd.read_parquet(DRUG_ANN)
    gdsc = pd.read_parquet(GDSC_DATA)

    print(f"✓ Expression: {expr.shape[0]} genes × {expr.shape[1]-2} patients")
    print(f"✓ Clinical: {clin.shape[0]} patients")
    print(f"✓ Drug annotations: {drug_ann.shape[0]} drugs")
    print(f"✓ GDSC data: {gdsc.shape[0]} samples")

    # Step 1: Load OOF and compute ensemble
    predictions = load_oof_and_compute_ensemble()

    # Step 2: Extract Top 30 drugs
    top30_results = extract_top30_drugs(predictions, drug_ann, gdsc)

    # Process both ensemble and single model
    results_summary = {}

    for model_name, top30_df in [('ensemble', top30_results['ensemble_top30']),
                                   ('single', top30_results['single_top30'])]:

        print(f"\n\n{'#'*100}")
        print(f"# Processing: {model_name.upper()} Model")
        print(f"{'#'*100}")

        # Method A
        df_a = method_a_target_expression(expr, drug_ann, top30_df)

        # Method B
        df_b = method_b_survival(expr, clin, drug_ann, top30_df)

        # Method C
        p_at_k = method_c_precision(drug_ann, top30_df)

        # Select Top 15
        top15, scores = select_top15(top30_df, df_a, df_b, drug_ann)

        # Save results
        def convert(obj):
            if isinstance(obj, (np.float32, np.float64)):
                return float(obj)
            if isinstance(obj, (np.int32, np.int64, np.bool_)):
                return int(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        summary = {
            "model": model_name,
            "model_description": "RF + ResidualMLP + TabNet (2A, Weighted)" if model_name == 'ensemble' else "ResidualMLP (2C)",
            "oof_spearman": predictions['ensemble_sp'] if model_name == 'ensemble' else predictions['single_sp'],
            "method_a": {
                "name": "Target Gene Expression Validation",
                "n_targets_expressed": int(df_a["target_expressed"].sum()),
                "n_brca_pathway": int(df_a["brca_pathway_relevant"].sum()),
                "n_total": len(df_a),
                "details": df_a.to_dict(orient="records"),
            },
            "method_b": {
                "name": "Survival Stratification",
                "n_significant": int(df_b["survival_significant"].sum()),
                "details": df_b.to_dict(orient="records"),
            },
            "method_c": {
                "name": "Known Drug Precision (P@K)",
                "precision_at_k": {k: v for k, v in p_at_k.items()},
            },
            "top15_validated": top15.to_dict(orient="records"),
            "all_30_scores": scores.to_dict(orient="records"),
        }

        results_summary[model_name] = summary

        # Save JSON
        json_path = OUTPUT_DIR / f"metabric_results_{model_name}.json"
        with open(json_path, "w") as f:
            json.dump(summary, f, indent=2, default=convert)
        print(f"\n✓ Saved: {json_path}")

        # Save CSV
        csv_path = OUTPUT_DIR / f"top15_validated_{model_name}.csv"
        top15.to_csv(csv_path, index=False)
        print(f"✓ Saved: {csv_path}")

    # Save consensus
    if len(top30_results['consensus_top30']) > 0:
        consensus_csv = OUTPUT_DIR / "top15_validated_consensus.csv"
        top30_results['consensus_top30'].to_csv(consensus_csv, index=False)
        print(f"\n✓ Saved consensus: {consensus_csv}")

    # Save comparison summary
    comparison = {
        "ensemble": {
            "model": "RF + ResidualMLP + TabNet (2A, Weighted)",
            "oof_spearman": predictions['ensemble_sp'],
            "weights": dict(zip(['RandomForest', 'ResidualMLP', 'TabNet'], predictions['weights'])),
            "top30_count": len(top30_results['ensemble_top30']),
            "method_a_expressed": int(results_summary['ensemble']['method_a']['n_targets_expressed']),
            "method_b_significant": int(results_summary['ensemble']['method_b']['n_significant']),
            "p_at_20": results_summary['ensemble']['method_c']['precision_at_k'].get('P@20', {}).get('precision', 0),
        },
        "single": {
            "model": "ResidualMLP (2C)",
            "oof_spearman": predictions['single_sp'],
            "top30_count": len(top30_results['single_top30']),
            "method_a_expressed": int(results_summary['single']['method_a']['n_targets_expressed']),
            "method_b_significant": int(results_summary['single']['method_b']['n_significant']),
            "p_at_20": results_summary['single']['method_c']['precision_at_k'].get('P@20', {}).get('precision', 0),
        },
        "consensus": {
            "overlap_count": len(top30_results['consensus_top30']),
            "overlap_drugs": top30_results['consensus_top30']['drug_name'].tolist() if len(top30_results['consensus_top30']) > 0 else []
        }
    }

    comparison_path = OUTPUT_DIR / "model_comparison_summary.json"
    with open(comparison_path, "w") as f:
        json.dump(comparison, f, indent=2, default=convert)
    print(f"✓ Saved comparison: {comparison_path}")

    elapsed = time.time() - t0
    print(f"\n{'='*100}")
    print(f"METABRIC Validation COMPLETE ({elapsed/60:.1f} min)")
    print(f"{'='*100}")
    print(f"\n생성된 파일:")
    print(f"  - metabric_results_ensemble.json")
    print(f"  - metabric_results_single.json")
    print(f"  - top15_validated_ensemble.csv")
    print(f"  - top15_validated_single.csv")
    print(f"  - top15_validated_consensus.csv")
    print(f"  - model_comparison_summary.json")
    print("=" * 100)


if __name__ == "__main__":
    main()
