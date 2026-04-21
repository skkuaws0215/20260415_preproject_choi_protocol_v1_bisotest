"""
Graph 모델 전체 실행 (Drug Split) - Colon
Phase 2A/2B/2C × 2 Graph (GraphSAGE + GAT) = 6 실험

기존 Lung에서는 Phase 2A만 공식 스크립트로 제공됐으나,
Colon은 샘플 수 적어(9,692 vs 125,427) Phase 2B/2C도 실행 가능.

기존 run_graph_sage_mps.py의 train_evaluate_graphsage 함수와
run_graph_gat_mps.py의 train_evaluate_gat 함수를 import해서 재사용.

입력:
  - data/X_numeric.npy (Phase 2A)
  - data/X_numeric_smiles.npy (Phase 2B)
  - data/X_numeric_context_smiles.npy (Phase 2C)
  - data/y_train.npy
  - fe_qc/20260420_colon_fe_v2/features_slim.parquet (groups = canonical_drug_id)

출력:
  - results/colon_numeric_graph_v1_groupcv.json       (Phase 2A)
  - results/colon_numeric_smiles_graph_v1_groupcv.json       (Phase 2B)
  - results/colon_numeric_context_smiles_graph_v1_groupcv.json (Phase 2C)
  - results/colon_numeric_graph_v1_oof/GraphSAGE.npy, GAT.npy
  - results/colon_numeric_smiles_graph_v1_oof/GraphSAGE.npy, GAT.npy
  - results/colon_numeric_context_smiles_graph_v1_oof/GraphSAGE.npy, GAT.npy

Run:
  cd 20260420_new_pre_project_biso_Colon
  python3 scripts/run_graph_all.py 2>&1 | tee logs/colon_graph_all.log

예상 소요:
  - GraphSAGE × 3 Phase: ~20~30분
  - GAT × 3 Phase: ~30~40분
  - 총: ~50분~1시간
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


def run_graph_phase(input_file, output_stem, phase_name, k_neighbors=7):
    """
    하나의 입력셋(Phase)에 대해 GraphSAGE + GAT 실행
    """
    print("\n" + "=" * 120)
    print(f"{phase_name}: Graph Models (GraphSAGE + GAT, Drug Split)")
    print("=" * 120)

    # 경로 설정
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    results_dir = base_dir / "results"
    results_dir.mkdir(exist_ok=True)

    # OOF 디렉토리
    oof_dir = results_dir / f"{output_stem}_oof"
    oof_dir.mkdir(exist_ok=True)

    # 데이터 로드
    X = np.load(data_dir / input_file)
    y = np.load(data_dir / "y_train.npy")

    # Groups - canonical_drug_id 기반 (Drug split)
    features_path = base_dir / "fe_qc" / "20260420_colon_fe_v2" / "features_slim.parquet"
    df_meta = pd.read_parquet(features_path, columns=['canonical_drug_id'])
    groups = df_meta['canonical_drug_id'].values

    print(f"\nData: {input_file}")
    print(f"X shape: {X.shape}")
    print(f"y shape: {y.shape}")
    print(f"Unique drugs: {len(np.unique(groups))}")

    all_results = {}

    # 1. GraphSAGE
    print("\n" + "-" * 120)
    print(f"[1/2] GraphSAGE - {phase_name}")
    print("-" * 120)

    # 이미 OOF 파일 존재하면 건너뛰기 옵션
    sage_oof = oof_dir / "GraphSAGE.npy"
    if sage_oof.exists():
        print(f"  ⏭️  GraphSAGE OOF 이미 존재, 건너뜀: {sage_oof}")
    else:
        sage_results = train_evaluate_graphsage(
            X, y, groups, output_stem, oof_dir, k_neighbors=k_neighbors
        )
        all_results['GraphSAGE'] = sage_results

    # 2. GAT
    print("\n" + "-" * 120)
    print(f"[2/2] GAT - {phase_name}")
    print("-" * 120)

    gat_oof = oof_dir / "GAT.npy"
    if gat_oof.exists():
        print(f"  ⏭️  GAT OOF 이미 존재, 건너뜀: {gat_oof}")
    else:
        gat_results = train_evaluate_gat(
            X, y, groups, output_stem, oof_dir, k_neighbors=k_neighbors
        )
        all_results['GAT'] = gat_results

    # 결과 저장 (기존 파일과 merge)
    results_file = results_dir / f"{output_stem}_groupcv.json"
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
    print(f"{phase_name} Graph 완료 - 요약")
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


if __name__ == "__main__":
    print("\n" + "=" * 120)
    print("Graph Models 전체 실행 (Drug Split)")
    print("Colon: 9,692 samples, k=7 (Lung k=10 대비 축소)")
    print("=" * 120)

    # Phase 2A: numeric-only
    results_2a = run_graph_phase(
        input_file="X_numeric.npy",
        output_stem="colon_numeric_graph_v1",
        phase_name="Phase 2A",
        k_neighbors=7
    )

    # Phase 2B: numeric + SMILES
    results_2b = run_graph_phase(
        input_file="X_numeric_smiles.npy",
        output_stem="colon_numeric_smiles_graph_v1",
        phase_name="Phase 2B",
        k_neighbors=7
    )

    # Phase 2C: numeric + context + SMILES
    results_2c = run_graph_phase(
        input_file="X_numeric_context_smiles.npy",
        output_stem="colon_numeric_context_smiles_graph_v1",
        phase_name="Phase 2C",
        k_neighbors=7
    )

    print("\n" + "=" * 120)
    print("✅ 모든 Graph 실험 완료! (Drug Split)")
    print("=" * 120)
    print("\n다음 단계: Scaffold Split")
    print("  python3 scripts/compute_scaffolds.py  (아직 안 돌렸으면)")
    print("  python3 scripts/run_graph_scaffold_all.py")
