#!/usr/bin/env python3
"""
Step 5: Ensemble - OOF-based Weighted Average
Baseline + FSimp 양쪽의 OOF predictions 를 활용한 앙상블 실험.

실험 구조:
  Tier 1: Cross-Category Best Mix (ML + DL + Graph)
  Tier 2: Phase-wise Best Mix (2A + 2B + 2C)
  Tier 3: 단일 Best (비교 기준)

출력:
  results/ensemble_20260422/ensemble_results.json
"""

import numpy as np
import json
from pathlib import Path
from itertools import combinations
from scipy.stats import spearmanr
from sklearn.model_selection import GroupKFold
import pandas as pd


def load_oof(oof_path):
    """OOF predictions 로드"""
    oof = np.load(oof_path)
    return oof


def compute_spearman(y_true, y_pred):
    """Spearman correlation 계산"""
    corr, _ = spearmanr(y_true, y_pred)
    return corr


def find_best_weights(oofs, y_true, n_steps=11):
    """
    2~3개 모델의 최적 가중치 탐색 (grid search).
    n_steps=11 -> 0.0, 0.1, 0.2, ..., 1.0
    """
    n_models = len(oofs)

    if n_models == 1:
        return [1.0], compute_spearman(y_true, oofs[0])

    best_score = -1
    best_weights = None

    if n_models == 2:
        for w1 in np.linspace(0, 1, n_steps):
            w2 = 1 - w1
            pred = w1 * oofs[0] + w2 * oofs[1]
            score = compute_spearman(y_true, pred)
            if score > best_score:
                best_score = score
                best_weights = [w1, w2]

    elif n_models == 3:
        for w1 in np.linspace(0, 1, n_steps):
            for w2 in np.linspace(0, 1 - w1, n_steps):
                w3 = 1 - w1 - w2
                if w3 < 0:
                    continue
                pred = w1 * oofs[0] + w2 * oofs[1] + w3 * oofs[2]
                score = compute_spearman(y_true, pred)
                if score > best_score:
                    best_score = score
                    best_weights = [w1, w2, w3]

    return best_weights, best_score


def evaluate_ensemble_cv(oofs, y, groups, weights):
    """
    가중치 적용 후 GroupKFold 로 재평가 (OOF 기반이라 이미 out-of-fold).
    OOF 자체가 이미 각 fold 의 validation prediction 이므로,
    전체 y 와 weighted OOF 의 correlation 이 앙상블 성능.
    """
    pred = sum(w * oof for w, oof in zip(weights, oofs))
    overall = compute_spearman(y, pred)
    return overall


def main():
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"

    # 결과 디렉토리
    ensemble_dir = base_dir / "results" / "ensemble_20260422"
    ensemble_dir.mkdir(parents=True, exist_ok=True)

    # y, groups 로드
    y = np.load(data_dir / "y_train.npy")
    features_path = base_dir / "fe_qc" / "20260420_colon_fe_v2" / "features_slim.parquet"
    df_meta = pd.read_parquet(features_path, columns=['canonical_drug_id'])
    groups = df_meta['canonical_drug_id'].values

    print(f"y shape: {y.shape}")
    print(f"Unique drugs: {len(np.unique(groups))}")

    # ============================================================
    # OOF 경로 매핑
    # ============================================================

    oof_map = {}

    # ML baseline
    for phase, stem in [("2A", "numeric"), ("2B", "numeric_smiles"), ("2C", "numeric_context_smiles")]:
        oof_dir = base_dir / "results" / "baseline_20260422_rerun" / f"colon_{stem}_ml_v1_oof"
        if oof_dir.exists():
            for npy in sorted(oof_dir.glob("*.npy")):
                model = npy.stem
                key = f"ML_baseline_{phase}_{model}"
                oof_map[key] = npy

    # ML fsimp
    for phase, stem in [("2A", "numeric"), ("2B", "numeric_smiles"), ("2C", "numeric_context_smiles")]:
        oof_dir = base_dir / "results" / "fsimp_top1000_20260422" / f"colon_{stem}_ml_v1_fsimp_top1000_oof"
        if oof_dir.exists():
            for npy in sorted(oof_dir.glob("*.npy")):
                model = npy.stem
                key = f"ML_fsimp_{phase}_{model}"
                oof_map[key] = npy

    # DL baseline
    for phase, stem in [("2A", "numeric"), ("2B", "numeric_smiles"), ("2C", "numeric_context_smiles")]:
        oof_dir = base_dir / "results" / f"colon_{stem}_dl_v1_oof"
        if oof_dir.exists():
            for npy in sorted(oof_dir.glob("*.npy")):
                model = npy.stem
                key = f"DL_baseline_{phase}_{model}"
                oof_map[key] = npy

    # DL fsimp
    for phase, stem in [("2A", "numeric"), ("2B", "numeric_smiles"), ("2C", "numeric_context_smiles")]:
        oof_dir = base_dir / "results" / "dl_fsimp_top1000_20260422" / f"colon_{stem}_dl_v1_fsimp_top1000_oof"
        if oof_dir.exists():
            for npy in sorted(oof_dir.glob("*.npy")):
                model = npy.stem
                key = f"DL_fsimp_{phase}_{model}"
                oof_map[key] = npy

    # Graph baseline
    for phase, stem in [("2A", "numeric"), ("2B", "numeric_smiles"), ("2C", "numeric_context_smiles")]:
        oof_dir = base_dir / "results" / f"colon_{stem}_graph_v1_oof"
        if oof_dir.exists():
            for npy in sorted(oof_dir.glob("*.npy")):
                model = npy.stem
                key = f"Graph_baseline_{phase}_{model}"
                oof_map[key] = npy

    # Graph fsimp
    for phase, stem in [("2A", "numeric"), ("2B", "numeric_smiles"), ("2C", "numeric_context_smiles")]:
        oof_dir = base_dir / "results" / "graph_fsimp_top1000_20260422" / f"colon_{stem}_graph_v1_fsimp_top1000_oof"
        if oof_dir.exists():
            for npy in sorted(oof_dir.glob("*.npy")):
                model = npy.stem
                key = f"Graph_fsimp_{phase}_{model}"
                oof_map[key] = npy

    print(f"\nTotal OOF files: {len(oof_map)}")
    print(f"Keys sample: {list(oof_map.keys())[:5]}")

    # ============================================================
    # 단일 모델 OOF 성능 (baseline)
    # ============================================================

    print("\n" + "=" * 100)
    print("단일 모델 OOF Spearman")
    print("=" * 100)

    single_results = {}
    for key, path in sorted(oof_map.items()):
        oof = load_oof(path)
        score = compute_spearman(y, oof)
        single_results[key] = score
        print(f"  {key:50s} {score:.4f}")

    # ============================================================
    # Tier 1: Cross-Category Best Mix (각 Phase 별)
    # ============================================================

    print("\n" + "=" * 100)
    print("Tier 1: Cross-Category Best Mix (ML + DL + Graph)")
    print("=" * 100)

    tier1_results = []

    for phase in ["2A", "2B", "2C"]:
        for variant in ["baseline", "fsimp"]:
            # 각 카테고리에서 OOF Spearman 최고 모델 선택
            ml_candidates = {k: v for k, v in single_results.items()
                             if k.startswith(f"ML_{variant}_{phase}_")}
            dl_candidates = {k: v for k, v in single_results.items()
                             if k.startswith(f"DL_{variant}_{phase}_")}
            graph_candidates = {k: v for k, v in single_results.items()
                                if k.startswith(f"Graph_{variant}_{phase}_")}

            if not ml_candidates or not dl_candidates or not graph_candidates:
                continue

            ml_best_key = max(ml_candidates, key=ml_candidates.get)
            dl_best_key = max(dl_candidates, key=dl_candidates.get)
            graph_best_key = max(graph_candidates, key=graph_candidates.get)

            oofs = [
                load_oof(oof_map[ml_best_key]),
                load_oof(oof_map[dl_best_key]),
                load_oof(oof_map[graph_best_key]),
            ]

            weights, score = find_best_weights(oofs, y)

            result = {
                "tier": "Tier1_CrossCategory",
                "phase": phase,
                "variant": variant,
                "models": [ml_best_key, dl_best_key, graph_best_key],
                "weights": [round(w, 2) for w in weights],
                "ensemble_spearman": round(score, 4),
                "individual_scores": [
                    round(single_results[ml_best_key], 4),
                    round(single_results[dl_best_key], 4),
                    round(single_results[graph_best_key], 4),
                ],
            }
            tier1_results.append(result)

            print(f"\n  [{phase} {variant}]")
            print(f"    ML:    {ml_best_key:40s} ({single_results[ml_best_key]:.4f})")
            print(f"    DL:    {dl_best_key:40s} ({single_results[dl_best_key]:.4f})")
            print(f"    Graph: {graph_best_key:40s} ({single_results[graph_best_key]:.4f})")
            print(f"    Weights: {weights}")
            print(f"    Ensemble: {score:.4f}")

    # ============================================================
    # Tier 1-B: Mixed variant (baseline ML + fsimp Graph 등)
    # ============================================================

    print("\n" + "=" * 100)
    print("Tier 1-B: Mixed Variant (baseline + fsimp 조합)")
    print("=" * 100)

    tier1b_results = []

    for phase in ["2A", "2B", "2C"]:
        # ML baseline + DL baseline + Graph fsimp (Graph 에 FS 가 가장 효과적이었으니)
        ml_candidates = {k: v for k, v in single_results.items()
                         if k.startswith(f"ML_baseline_{phase}_")}
        dl_candidates = {k: v for k, v in single_results.items()
                         if k.startswith(f"DL_baseline_{phase}_")}
        graph_candidates = {k: v for k, v in single_results.items()
                            if k.startswith(f"Graph_fsimp_{phase}_")}

        if not ml_candidates or not dl_candidates or not graph_candidates:
            continue

        ml_best_key = max(ml_candidates, key=ml_candidates.get)
        dl_best_key = max(dl_candidates, key=dl_candidates.get)
        graph_best_key = max(graph_candidates, key=graph_candidates.get)

        oofs = [
            load_oof(oof_map[ml_best_key]),
            load_oof(oof_map[dl_best_key]),
            load_oof(oof_map[graph_best_key]),
        ]

        weights, score = find_best_weights(oofs, y)

        result = {
            "tier": "Tier1B_MixedVariant",
            "phase": phase,
            "variant": "mixed",
            "models": [ml_best_key, dl_best_key, graph_best_key],
            "weights": [round(w, 2) for w in weights],
            "ensemble_spearman": round(score, 4),
            "individual_scores": [
                round(single_results[ml_best_key], 4),
                round(single_results[dl_best_key], 4),
                round(single_results[graph_best_key], 4),
            ],
        }
        tier1b_results.append(result)

        print(f"\n  [{phase} mixed]")
        print(f"    ML(base):    {ml_best_key:40s} ({single_results[ml_best_key]:.4f})")
        print(f"    DL(base):    {dl_best_key:40s} ({single_results[dl_best_key]:.4f})")
        print(f"    Graph(fsimp):{graph_best_key:40s} ({single_results[graph_best_key]:.4f})")
        print(f"    Weights: {weights}")
        print(f"    Ensemble: {score:.4f}")

    # ============================================================
    # Tier 2: Phase-wise Best Mix
    # ============================================================

    print("\n" + "=" * 100)
    print("Tier 2: Phase-wise Best Mix (2A + 2B + 2C)")
    print("=" * 100)

    tier2_results = []

    for variant in ["baseline", "fsimp"]:
        phase_bests = {}
        for phase in ["2A", "2B", "2C"]:
            candidates = {k: v for k, v in single_results.items()
                          if f"_{variant}_{phase}_" in k}
            if candidates:
                best_key = max(candidates, key=candidates.get)
                phase_bests[phase] = best_key

        if len(phase_bests) == 3:
            oofs = [load_oof(oof_map[phase_bests[p]]) for p in ["2A", "2B", "2C"]]
            weights, score = find_best_weights(oofs, y)

            result = {
                "tier": "Tier2_PhaseWise",
                "variant": variant,
                "models": [phase_bests[p] for p in ["2A", "2B", "2C"]],
                "weights": [round(w, 2) for w in weights],
                "ensemble_spearman": round(score, 4),
            }
            tier2_results.append(result)

            print(f"\n  [{variant}]")
            for p in ["2A", "2B", "2C"]:
                print(f"    {p}: {phase_bests[p]:50s} ({single_results[phase_bests[p]]:.4f})")
            print(f"    Weights: {weights}")
            print(f"    Ensemble: {score:.4f}")

    # ============================================================
    # Tier 3: 단일 Best (비교 기준)
    # ============================================================

    print("\n" + "=" * 100)
    print("Tier 3: 단일 Best")
    print("=" * 100)

    best_single_key = max(single_results, key=single_results.get)
    best_single_score = single_results[best_single_key]
    print(f"  {best_single_key}: {best_single_score:.4f}")

    # ============================================================
    # 최종 랭킹
    # ============================================================

    print("\n" + "=" * 100)
    print("최종 랭킹")
    print("=" * 100)

    all_results = []

    for r in tier1_results:
        all_results.append({
            "name": f"Tier1_{r['phase']}_{r['variant']}",
            "score": r["ensemble_spearman"],
            "tier": r["tier"],
            "detail": r,
        })

    for r in tier1b_results:
        all_results.append({
            "name": f"Tier1B_{r['phase']}_mixed",
            "score": r["ensemble_spearman"],
            "tier": r["tier"],
            "detail": r,
        })

    for r in tier2_results:
        all_results.append({
            "name": f"Tier2_{r['variant']}",
            "score": r["ensemble_spearman"],
            "tier": r["tier"],
            "detail": r,
        })

    all_results.append({
        "name": f"Tier3_single_{best_single_key}",
        "score": best_single_score,
        "tier": "Tier3_Single",
        "detail": {"model": best_single_key, "score": best_single_score},
    })

    all_results.sort(key=lambda x: x["score"], reverse=True)

    for i, r in enumerate(all_results, 1):
        marker = "🏆" if i == 1 else f"#{i}"
        print(f"  {marker:4s} {r['score']:.4f}  {r['name']}")

    # ============================================================
    # 결과 저장
    # ============================================================

    output = {
        "experiment": "Step 5 Ensemble",
        "date": "2026-04-22",
        "y_shape": list(y.shape),
        "n_oof_files": len(oof_map),
        "single_model_scores": single_results,
        "tier1_cross_category": tier1_results,
        "tier1b_mixed_variant": tier1b_results,
        "tier2_phase_wise": tier2_results,
        "tier3_single_best": {"model": best_single_key, "score": best_single_score},
        "final_ranking": [{"rank": i + 1, "name": r["name"], "score": r["score"]}
                          for i, r in enumerate(all_results)],
    }

    output_file = ensemble_dir / "ensemble_results.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n✅ 결과 저장: {output_file}")
    print(f"총 {len(all_results)} 앙상블 조합 실험 완료")


if __name__ == "__main__":
    main()
