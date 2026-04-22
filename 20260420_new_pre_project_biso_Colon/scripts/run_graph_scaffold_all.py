"""
Graph Scaffold Split 기반 Graph 모델 재실행 - Colon (Task 1)
Phase 2A/2B/2C × 2 Graph (GraphSAGE + GAT) = 6 실험

프로토콜 v2.3 Section 13 지표 #21 (Scaffold split) 충족 시도 (Graph 범위).

기존 run_graph_sage_mps.py, run_graph_gat_mps.py의 함수를 import하되,
groups 파라미터만 canonical_drug_id → scaffold_id로 교체.

입력:
  - data/X_numeric.npy, X_numeric_smiles.npy, X_numeric_context_smiles.npy
  - data/y_train.npy
  - data/scaffold_groups.npy (compute_scaffolds.py에서 생성)

출력:
  - results/colon_numeric_graph_v1_scaffoldcv.json
  - results/colon_numeric_smiles_graph_v1_scaffoldcv.json
  - results/colon_numeric_context_smiles_graph_v1_scaffoldcv.json
  - results/colon_numeric_graph_v1_scaffold_oof/*.npy
  - results/colon_numeric_smiles_graph_v1_scaffold_oof/*.npy
  - results/colon_numeric_context_smiles_graph_v1_scaffold_oof/*.npy

Run:
  cd 20260420_new_pre_project_biso_Colon
  python3 scripts/run_graph_scaffold_all.py 2>&1 | tee logs/colon_graph_scaffold.log

전제: compute_scaffolds.py 먼저 실행

예상 소요:
  - GraphSAGE × 3 Phase: ~20~30분
  - GAT × 3 Phase: ~30~40분
  - 총: ~50분~1시간

주의:
  Scaffold split + Graph 조합은 KNN graph가 scaffold 경계를 넘을 수 있음.
  즉 val 노드의 이웃 중 일부가 train 노드 → 약간의 정보 누출 가능.
  이 문제는 Graph 모델의 transductive 특성 때문이며, 기존 drug split에서도
  동일하게 발생하므로 상대적 비교는 유효함.
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent))

# 기존 스크립트의 함수 import
from run_graph_sage_mps import train_evaluate_graphsage
from run_graph_gat_mps import train_evaluate_gat
from phase2_utils import save_results


def run_graph_scaffold_phase(
    input_file,
    output_stem,
    phase_name,
    k_neighbors=7,
    fs_top_k=None,
    out_suffix="",
    experiment_dir=None,
):
    """
    하나의 입력셋(Phase)에 대해 Scaffold split으로 GraphSAGE + GAT 실행
    """
    print("\n" + "=" * 120)
    print(f"{phase_name}: Graph Models (GraphSAGE + GAT, SCAFFOLD Split)")
    print("=" * 120)

    # 경로 설정
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    if experiment_dir:
        results_dir = base_dir / "results" / experiment_dir
    else:
        results_dir = base_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Scaffold OOF 디렉토리 (기존 drug split과 구분)
    oof_dir = results_dir / f"{output_stem}{out_suffix}_scaffold_oof"
    oof_dir.mkdir(exist_ok=True)

    # 데이터 로드
    X = np.load(data_dir / input_file)
    y = np.load(data_dir / "y_train.npy")

    # Scaffold groups 로드 (Drug groups 대체)
    scaffold_groups_path = data_dir / "scaffold_groups.npy"
    if not scaffold_groups_path.exists():
        print(f"❌ ERROR: {scaffold_groups_path} 없음")
        print(f"   먼저 실행: python3 scripts/compute_scaffolds.py")
        sys.exit(1)

    scaffold_groups = np.load(scaffold_groups_path)

    print(f"\nData: {input_file}")
    print(f"X shape: {X.shape}")
    print(f"y shape: {y.shape}")
    print(f"Scaffold groups: {scaffold_groups.shape}")
    print(f"Unique scaffolds in pairs: {len(np.unique(scaffold_groups))}")

    all_results = {}

    # 1. GraphSAGE (scaffold)
    print("\n" + "-" * 120)
    print(f"[1/2] GraphSAGE - {phase_name} (Scaffold)")
    print("-" * 120)

    sage_oof = oof_dir / "GraphSAGE.npy"
    if sage_oof.exists():
        print(f"  ⏭️  GraphSAGE Scaffold OOF 이미 존재, 건너뜀")
    else:
        # train_evaluate_graphsage의 groups 파라미터를 scaffold_groups로 교체
        sage_results = train_evaluate_graphsage(
            X, y, scaffold_groups,        # ← scaffold로 교체
            f"{output_stem}_scaffold", oof_dir,
            k_neighbors=k_neighbors,
            fs_top_k=fs_top_k,
        )
        all_results['GraphSAGE'] = sage_results

    # 2. GAT (scaffold)
    print("\n" + "-" * 120)
    print(f"[2/2] GAT - {phase_name} (Scaffold)")
    print("-" * 120)

    gat_oof = oof_dir / "GAT.npy"
    if gat_oof.exists():
        print(f"  ⏭️  GAT Scaffold OOF 이미 존재, 건너뜀")
    else:
        gat_results = train_evaluate_gat(
            X, y, scaffold_groups,         # ← scaffold로 교체
            f"{output_stem}_scaffold", oof_dir,
            k_neighbors=k_neighbors,
            fs_top_k=fs_top_k,
        )
        all_results['GAT'] = gat_results

    # 결과 저장 (scaffoldcv 표기)
    results_file = results_dir / f"{output_stem}{out_suffix}_scaffoldcv.json"
    if results_file.exists():
        with open(results_file, 'r') as f:
            existing = json.load(f)
        existing.update(all_results)
        all_results = existing

    if all_results:
        save_results(all_results, results_file)
        print(f"\n✓ Saved: {results_file}")

    # Phase 요약
    print("\n" + "=" * 120)
    print(f"{phase_name} Graph Scaffold 완료 - 요약")
    print("=" * 120)
    print(f"{'Model':20s} | {'Val Spearman':>13s} | {'Gap':>10s}")
    print("-" * 50)

    for model_name, result in all_results.items():
        if 'fold_results' not in result:
            continue
        val_sps = [f['val']['spearman'] for f in result['fold_results']]
        train_sps = [f['train']['spearman'] for f in result['fold_results']]
        val_mean = np.mean(val_sps)
        gap = np.mean(train_sps) - val_mean
        print(f"{model_name:20s} | {val_mean:13.4f} | {gap:+10.4f}")

    return all_results


def compare_graph_drug_vs_scaffold(output_stem):
    """
    Graph 모델의 Drug split vs Scaffold split 비교
    """
    base_dir = Path(__file__).parent.parent
    results_dir = base_dir / "results"

    drug_path = results_dir / f"{output_stem}_groupcv.json"
    scaffold_path = results_dir / f"{output_stem}_scaffoldcv.json"

    if not drug_path.exists() or not scaffold_path.exists():
        print(f"  ⚠️  비교 파일 부족. {drug_path.name} or {scaffold_path.name} 없음")
        return

    with open(drug_path) as f:
        drug_results = json.load(f)
    with open(scaffold_path) as f:
        scaffold_results = json.load(f)

    print(f"\n  {'Model':20s} | {'Drug Sp':>8s} | {'Scaffold Sp':>12s} | {'Drop':>8s} | {'Drop %':>8s}")
    print(f"  {'-'*65}")

    for model_name in ['GraphSAGE', 'GAT']:
        if model_name not in drug_results or model_name not in scaffold_results:
            continue

        drug_val = np.mean([f['val']['spearman'] for f in drug_results[model_name]['fold_results']])
        scaffold_val = np.mean([f['val']['spearman'] for f in scaffold_results[model_name]['fold_results']])
        drop = drug_val - scaffold_val
        drop_pct = (drop / drug_val * 100) if drug_val != 0 else 0

        marker = ''
        if drop > 0.15:
            marker = ' 🔴 scaffold 의존 심함'
        elif drop > 0.05:
            marker = ' 🟡 중간 의존'
        else:
            marker = ' 🟢 scaffold 독립적'

        print(f"  {model_name:20s} | {drug_val:8.4f} | {scaffold_val:12.4f} | "
              f"{drop:+8.4f} | {drop_pct:+7.1f}%{marker}")


if __name__ == "__main__":
    # ============================================================
    # Experiment configuration
    # ============================================================
    # fs_top_k = None
    fs_top_k = 1000
    out_suffix = f"_fsimp_top{fs_top_k}" if fs_top_k is not None else ""
    if fs_top_k is None:
        experiment_dir = "graph_scaffold_baseline_20260422_rerun"
    else:
        experiment_dir = f"graph_scaffold_fsimp_top{fs_top_k}_20260422"

    print(
        f"Experiment: fs_top_k={fs_top_k}, out_suffix='{out_suffix}', "
        f"experiment_dir='{experiment_dir}'"
    )
    # ============================================================

    print("\n" + "=" * 120)
    print("Task 1: Graph Scaffold Split")
    print("=" * 120)

    # Phase 2A: numeric-only
    results_2a = run_graph_scaffold_phase(
        "X_numeric.npy", "colon_numeric_graph_v1", "Phase 2A",
        k_neighbors=7, fs_top_k=fs_top_k, out_suffix=out_suffix, experiment_dir=experiment_dir,
    )

    # Phase 2B: numeric + SMILES
    results_2b = run_graph_scaffold_phase(
        "X_numeric_smiles.npy", "colon_numeric_smiles_graph_v1", "Phase 2B",
        k_neighbors=7, fs_top_k=fs_top_k, out_suffix=out_suffix, experiment_dir=experiment_dir,
    )

    # Phase 2C: numeric + context + SMILES
    results_2c = run_graph_scaffold_phase(
        "X_numeric_context_smiles.npy", "colon_numeric_context_smiles_graph_v1", "Phase 2C",
        k_neighbors=7, fs_top_k=fs_top_k, out_suffix=out_suffix, experiment_dir=experiment_dir,
    )
    print("\n✅ Graph Scaffold Split 완료!")
