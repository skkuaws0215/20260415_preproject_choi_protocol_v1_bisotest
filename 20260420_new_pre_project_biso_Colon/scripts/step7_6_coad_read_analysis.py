#!/usr/bin/env python3
"""
Step 7.6: COAD vs READ 분리 분석

TCGA coadread_tcga_pan_can_atlas_2018 발현 데이터에서
Top 15 약물의 타겟 유전자가 COAD vs READ 에서 발현 차이가 있는지 분석.

방법:
  1. TCGA mRNA (592 samples) 로드
  2. TCGA clinical 에서 COAD/READ 분류
  3. Top 15 약물 타겟 유전자 추출
  4. COAD vs READ 발현 비교 (t-test)
  5. 약물별 COAD/READ 추천 적합성 판단

입력:
  - results/colon_final_top15.csv
  - curated_data/cbioportal/coadread_tcga_pan_can_atlas_2018/data_mrna_seq_v2_rsem.txt
  - curated_data/cbioportal/coadread_tcga_pan_can_atlas_2018/data_clinical_patient.txt
  - data/colon_subtype_metadata.parquet

출력:
  - results/colon_coad_read_analysis.json
  - results/colon_coad_read_drug_recommendations.csv
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


def load_top15(results_dir):
    """Top 15 약물 로드"""
    df = pd.read_csv(results_dir / "colon_final_top15.csv")
    print(f"  Top 15 loaded: {len(df)} drugs")
    return df


def extract_targets(top15):
    """약물별 타겟 추출"""
    name_col = "drug_name" if "drug_name" in top15.columns else "DRUG_NAME"
    target_col = "target" if "target" in top15.columns else "TARGET"

    drug_targets = {}
    all_genes = set()

    for _, row in top15.iterrows():
        drug = row[name_col]
        target_str = str(row.get(target_col, ""))
        if not target_str or target_str == "nan":
            continue

        genes = []
        for t in target_str.replace(";", ",").replace("/", ",").split(","):
            t = t.strip().upper()
            if t and len(t) >= 2 and t not in [
                "BROAD",
                "SPECTRUM",
                "KINASE",
                "INHIBITOR",
                "MICROTUBULE",
                "DESTABILISER",
                "DNA",
                "RNA",
            ]:
                genes.append(t)
                all_genes.add(t)

        drug_targets[drug] = genes

    print(f"  Drugs with targets: {len(drug_targets)}")
    print(f"  Unique genes: {len(all_genes)}")
    return drug_targets, sorted(all_genes)


def load_tcga_clinical(tcga_dir):
    """TCGA clinical + subtype 매핑"""
    clinical_path = tcga_dir / "data_clinical_patient.txt"
    df = pd.read_csv(clinical_path, sep="\t", comment="#")
    print(f"  TCGA clinical: {len(df)} patients")
    print(f"  Columns: {list(df.columns[:10])}")
    return df


def load_subtype_metadata(data_dir):
    """subtype metadata (COAD/READ 분류)"""
    path = data_dir / "colon_subtype_metadata.parquet"
    if not path.exists():
        print(f"  WARNING: {path} not found")
        return None

    df = pd.read_parquet(path)
    print(f"  Subtype metadata: {len(df)} samples")
    print(f"  primary_site: {df['primary_site'].value_counts().to_dict()}")
    return df


def load_tcga_mrna(tcga_dir):
    """TCGA mRNA 발현 데이터 로드"""
    mrna_path = tcga_dir / "data_mrna_seq_v2_rsem.txt"
    if not mrna_path.exists():
        print(f"  ERROR: {mrna_path} not found")
        return None

    df = pd.read_csv(mrna_path, sep="\t")
    gene_col = "Hugo_Symbol" if "Hugo_Symbol" in df.columns else df.columns[0]
    sample_cols = [c for c in df.columns if c not in ["Hugo_Symbol", "Entrez_Gene_Id"]]

    print(f"  TCGA mRNA: {len(df)} genes × {len(sample_cols)} samples")
    return df, gene_col, sample_cols


def map_samples_to_subtype(sample_cols, subtype_df, clinical_df):
    """mRNA 샘플 ID 를 COAD/READ 로 매핑"""
    # TCGA sample ID 는 보통 "TCGA-XX-XXXX-01" 형식
    # subtype metadata 의 sample_id 도 TCGA 형식

    # 먼저 subtype metadata 에서 매핑 시도
    sample_to_type = {}

    if subtype_df is not None and "sample_id" in subtype_df.columns and "primary_site" in subtype_df.columns:
        for _, row in subtype_df.iterrows():
            sid = str(row["sample_id"])
            site = row["primary_site"]
            if site in ["COAD", "READ"]:
                # TCGA ID 에서 앞 12자리 (patient level)
                patient_id = sid[:12] if len(sid) >= 12 else sid
                sample_to_type[patient_id] = site
                sample_to_type[sid] = site

    # mRNA 샘플을 COAD/READ 로 분류
    coad_samples = []
    read_samples = []
    unmatched = []

    for sample in sample_cols:
        # 샘플 ID 에서 patient ID 추출 (앞 12자리)
        patient_id = sample[:12] if len(sample) >= 12 else sample

        if patient_id in sample_to_type:
            if sample_to_type[patient_id] == "COAD":
                coad_samples.append(sample)
            elif sample_to_type[patient_id] == "READ":
                read_samples.append(sample)
        elif sample in sample_to_type:
            if sample_to_type[sample] == "COAD":
                coad_samples.append(sample)
            elif sample_to_type[sample] == "READ":
                read_samples.append(sample)
        else:
            unmatched.append(sample)

    print(f"  COAD samples: {len(coad_samples)}")
    print(f"  READ samples: {len(read_samples)}")
    print(f"  Unmatched: {len(unmatched)}")

    return coad_samples, read_samples


def compare_expression(mrna_df, gene_col, target_genes, coad_samples, read_samples):
    """COAD vs READ 타겟 유전자 발현 비교"""
    results = []

    available_genes = set(mrna_df[gene_col].dropna().str.upper())

    for gene in target_genes:
        if gene not in available_genes:
            continue

        gene_row = mrna_df[mrna_df[gene_col].str.upper() == gene]
        if len(gene_row) == 0:
            continue

        # COAD 발현
        coad_values = gene_row[coad_samples].values.flatten()
        coad_values = coad_values[~np.isnan(coad_values)]

        # READ 발현
        read_values = gene_row[read_samples].values.flatten()
        read_values = read_values[~np.isnan(read_values)]

        if len(coad_values) < 5 or len(read_values) < 5:
            continue

        # t-test
        t_stat, p_value = stats.ttest_ind(coad_values, read_values, equal_var=False)

        # 효과 크기 (Cohen's d)
        pooled_std = np.sqrt((np.std(coad_values) ** 2 + np.std(read_values) ** 2) / 2)
        cohens_d = (np.mean(coad_values) - np.mean(read_values)) / pooled_std if pooled_std > 0 else 0

        # 발현 방향
        if p_value < 0.05:
            if np.mean(coad_values) > np.mean(read_values):
                direction = "COAD_higher"
            else:
                direction = "READ_higher"
        else:
            direction = "No_difference"

        results.append(
            {
                "gene": gene,
                "coad_mean": round(float(np.mean(coad_values)), 4),
                "coad_median": round(float(np.median(coad_values)), 4),
                "coad_std": round(float(np.std(coad_values)), 4),
                "coad_n": len(coad_values),
                "read_mean": round(float(np.mean(read_values)), 4),
                "read_median": round(float(np.median(read_values)), 4),
                "read_std": round(float(np.std(read_values)), 4),
                "read_n": len(read_values),
                "t_statistic": round(float(t_stat), 4),
                "p_value": round(float(p_value), 6),
                "cohens_d": round(float(cohens_d), 4),
                "direction": direction,
                "significant": p_value < 0.05,
            }
        )

    return results


def drug_level_recommendations(drug_targets, expression_results):
    """약물별 COAD/READ 추천"""
    gene_results = {r["gene"]: r for r in expression_results}

    recommendations = []

    for drug, genes in drug_targets.items():
        drug_genes = []
        coad_score = 0
        read_score = 0
        n_sig = 0

        for gene in genes:
            if gene in gene_results:
                r = gene_results[gene]
                drug_genes.append(r)
                if r["significant"]:
                    n_sig += 1
                    if r["direction"] == "COAD_higher":
                        coad_score += abs(r["cohens_d"])
                    elif r["direction"] == "READ_higher":
                        read_score += abs(r["cohens_d"])

        # 추천 판정
        if not drug_genes:
            recommendation = "Unknown"
            detail = "No target gene expression data"
        elif n_sig == 0:
            recommendation = "Both"
            detail = "No significant COAD/READ difference in target expression"
        elif coad_score > read_score * 1.5:
            recommendation = "COAD_preferred"
            detail = f"Target genes higher in COAD (effect={coad_score:.2f} vs {read_score:.2f})"
        elif read_score > coad_score * 1.5:
            recommendation = "READ_preferred"
            detail = f"Target genes higher in READ (effect={read_score:.2f} vs {coad_score:.2f})"
        else:
            recommendation = "Both"
            detail = f"Similar effect (COAD={coad_score:.2f}, READ={read_score:.2f})"

        recommendations.append(
            {
                "drug": drug,
                "recommendation": recommendation,
                "detail": detail,
                "n_targets_analyzed": len(drug_genes),
                "n_significant": n_sig,
                "coad_score": round(coad_score, 4),
                "read_score": round(read_score, 4),
            }
        )

    return recommendations


def main():
    base_dir = Path(__file__).parent.parent
    results_dir = base_dir / "results"
    tcga_dir = base_dir / "curated_data" / "cbioportal" / "coadread_tcga_pan_can_atlas_2018"
    data_dir = base_dir / "data"

    print("=" * 80)
    print("Step 7.6: COAD vs READ Differential Analysis")
    print("=" * 80)

    # 1. Top 15
    print("\n[1] Top 15 로드")
    top15 = load_top15(results_dir)

    # 2. 타겟 추출
    print("\n[2] 타겟 유전자 추출")
    drug_targets, all_genes = extract_targets(top15)

    # 3. TCGA clinical
    print("\n[3] TCGA clinical 로드")
    clinical = load_tcga_clinical(tcga_dir)

    # 4. Subtype metadata
    print("\n[4] Subtype metadata 로드")
    subtype = load_subtype_metadata(data_dir)

    # 5. TCGA mRNA
    print("\n[5] TCGA mRNA 발현 데이터 로드")
    result = load_tcga_mrna(tcga_dir)
    if result is None:
        return
    mrna_df, gene_col, sample_cols = result

    # 6. 샘플 → COAD/READ 매핑
    print("\n[6] 샘플 COAD/READ 매핑")
    coad_samples, read_samples = map_samples_to_subtype(sample_cols, subtype, clinical)

    if len(coad_samples) < 10 or len(read_samples) < 10:
        print(f"  WARNING: Insufficient samples (COAD={len(coad_samples)}, READ={len(read_samples)})")
        print("  Minimum 10 per group required")

    # 7. COAD vs READ 발현 비교
    print("\n[7] COAD vs READ 발현 비교")
    expression_results = compare_expression(mrna_df, gene_col, all_genes, coad_samples, read_samples)
    print(f"  Analyzed: {len(expression_results)} genes")

    sig_count = sum(1 for r in expression_results if r["significant"])
    print(f"  Significant (p<0.05): {sig_count}/{len(expression_results)}")

    for r in expression_results:
        sig_icon = "⭐" if r["significant"] else "  "
        print(
            f"  {sig_icon} {r['gene']:15s} COAD={r['coad_mean']:>10.2f} READ={r['read_mean']:>10.2f} "
            f"p={r['p_value']:.4f} d={r['cohens_d']:+.3f} → {r['direction']}"
        )

    # 8. 약물별 추천
    print("\n[8] 약물별 COAD/READ 추천")
    recommendations = drug_level_recommendations(drug_targets, expression_results)

    for rec in recommendations:
        icon = (
            "🔵"
            if rec["recommendation"] == "COAD_preferred"
            else "🔴"
            if rec["recommendation"] == "READ_preferred"
            else "🟢"
            if rec["recommendation"] == "Both"
            else "⚪"
        )
        print(f"  {icon} {rec['drug']:25s} → {rec['recommendation']:15s} ({rec['detail']})")

    # 9. 저장
    print("\n[9] 저장")

    analysis = {
        "step": "Step 7.6 COAD vs READ Analysis",
        "disease": "colorectal cancer",
        "tcga_samples": {"coad": len(coad_samples), "read": len(read_samples)},
        "genes_analyzed": len(expression_results),
        "genes_significant": sig_count,
        "expression_results": expression_results,
        "drug_recommendations": recommendations,
        "summary": {
            "coad_preferred": sum(1 for r in recommendations if r["recommendation"] == "COAD_preferred"),
            "read_preferred": sum(1 for r in recommendations if r["recommendation"] == "READ_preferred"),
            "both": sum(1 for r in recommendations if r["recommendation"] == "Both"),
            "unknown": sum(1 for r in recommendations if r["recommendation"] == "Unknown"),
        },
    }

    json_path = results_dir / "colon_coad_read_analysis.json"
    with open(json_path, "w") as f:
        json.dump(analysis, f, indent=2, default=str)
    print(f"  ✅ {json_path}")

    rec_df = pd.DataFrame(recommendations)
    csv_path = results_dir / "colon_coad_read_drug_recommendations.csv"
    rec_df.to_csv(csv_path, index=False)
    print(f"  ✅ {csv_path}")

    # 10. 요약
    print("\n" + "=" * 80)
    print("COAD vs READ Analysis Summary")
    print("=" * 80)
    print(f"  TCGA samples: COAD {len(coad_samples)}, READ {len(read_samples)}")
    print(f"  Genes analyzed: {len(expression_results)}")
    print(f"  Significant (p<0.05): {sig_count}")
    print()
    print("  Drug recommendations:")
    print(f"    🔵 COAD preferred: {analysis['summary']['coad_preferred']}")
    print(f"    🔴 READ preferred: {analysis['summary']['read_preferred']}")
    print(f"    🟢 Both: {analysis['summary']['both']}")
    print(f"    ⚪ Unknown: {analysis['summary']['unknown']}")

    print("\n✅ Step 7.6 완료!")


if __name__ == "__main__":
    main()
