"""
DL Scaffold Split 기반 DL 모델 재실행 - Colon (Task 1)
Phase 2A/2B/2C × 7 DL = 21 실험

프로토콜 v2.3 Section 13 지표 #21 (Scaffold split) 충족 시도 (DL 범위).

기존 run_dl_all.py의 train_evaluate_dl 함수를 재사용하되,
groups 파라미터만 canonical_drug_id → scaffold_id로 교체.
eval_mode는 groupcv 고정 (scaffold split은 GroupCV만 의미 있음).

입력:
  - data/X_numeric.npy, X_numeric_smiles.npy, X_numeric_context_smiles.npy
  - data/y_train.npy
  - data/scaffold_groups.npy (compute_scaffolds.py에서 생성)

출력:
  - results/colon_numeric_dl_v1_scaffoldcv.json (Phase 2A)
  - results/colon_numeric_smiles_dl_v1_scaffoldcv.json (Phase 2B)
  - results/colon_numeric_context_smiles_dl_v1_scaffoldcv.json (Phase 2C)
  - results/colon_numeric_dl_v1_scaffold_oof/*.npy (7 파일)
  - results/colon_numeric_smiles_dl_v1_scaffold_oof/*.npy (7 파일)
  - results/colon_numeric_context_smiles_dl_v1_scaffold_oof/*.npy (7 파일)

Run:
  cd 20260420_new_pre_project_biso_Colon
  python3 scripts/run_dl_scaffold_all.py 2>&1 | tee logs/colon_dl_scaffold.log

전제: compute_scaffolds.py + run_dl_all.py 완료

예상 소요:
  - 7 DL × 3 Phase × 3-fold = 63 fold
  - MPS 활용: ~1.5~2시간 (epochs=50)
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent))

# 기존 run_dl_all.py의 함수 + 모델 클래스 import
from run_dl_all import (
    train_evaluate_dl,
    FlatMLP, ResidualMLP, FTTransformer, CrossAttention,
    TabNet, WideDeep, TabTransformer
)
from phase2_utils import save_results


def run_dl_scaffold_phase(
    input_file,
    output_stem,
    phase_name,
    fs_top_k=None,
    out_suffix="",
    experiment_dir=None,
):
    """
    하나의 입력셋(Phase)에 대해 Scaffold split으로 DL 7개 모델 실행
    """
    print("\n" + "=" * 120)
    print(f"{phase_name}: DL Models (Scaffold Split)")
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

    # Scaffold groups 로드
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
    print(f"Unique scaffolds: {len(np.unique(scaffold_groups))}")

    # DL 모델 정의 (run_dl_all.py와 동일)
    models = {
        'FlatMLP': FlatMLP,
        'ResidualMLP': ResidualMLP,
        'FTTransformer': FTTransformer,
        'CrossAttention': CrossAttention,
        'TabNet': TabNet,
        'WideDeep': WideDeep,
        'TabTransformer': TabTransformer
    }

    # Scaffold split: GroupCV만 수행 (holdout/5foldcv는 scaffold split으로 의미 없음)
    all_results = {}

    for model_name, model_class in models.items():
        # OOF 파일 이미 존재하면 건너뛰기
        oof_file = oof_dir / f"{model_name}.npy"
        if oof_file.exists():
            print(f"\n{'='*120}")
            print(f"⏭️  {model_name} - Scaffold GroupCV: OOF 이미 존재, 건너뜀")
            print(f"{'='*120}")
            continue

        results = train_evaluate_dl(
            X, y, scaffold_groups,        # ← groups를 scaffold로 교체
            model_name, model_class,
            eval_mode='groupcv',           # GroupKFold 3-fold
            output_stem=f"{output_stem}_scaffold",
            oof_dir=oof_dir,
            fs_top_k=fs_top_k,
            out_suffix=out_suffix,
        )
        all_results[model_name] = results

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
    print(f"{phase_name} DL Scaffold 완료 - 요약")
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


def compare_dl_drug_vs_scaffold(output_stem):
    """
    DL 모델의 Drug split vs Scaffold split 비교
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

    for model_name in drug_results:
        if model_name not in scaffold_results:
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
        experiment_dir = "dl_scaffold_baseline_20260422_rerun"
    else:
        experiment_dir = f"dl_scaffold_fsimp_top{fs_top_k}_20260422"

    print(
        f"Experiment: fs_top_k={fs_top_k}, out_suffix='{out_suffix}', "
        f"experiment_dir='{experiment_dir}'"
    )
    # ============================================================

    print("\n" + "=" * 120)
    print("Task 1: DL Scaffold Split")
    print("=" * 120)

    # Phase 2A: numeric-only
    results_2a = run_dl_scaffold_phase(
        input_file="X_numeric.npy",
        output_stem="colon_numeric_dl_v1",
        phase_name="Phase 2A",
        fs_top_k=fs_top_k, out_suffix=out_suffix, experiment_dir=experiment_dir,
    )

    # Phase 2B: numeric + SMILES
    results_2b = run_dl_scaffold_phase(
        input_file="X_numeric_smiles.npy",
        output_stem="colon_numeric_smiles_dl_v1",
        phase_name="Phase 2B",
        fs_top_k=fs_top_k, out_suffix=out_suffix, experiment_dir=experiment_dir,
    )

    # Phase 2C: numeric + context + SMILES
    results_2c = run_dl_scaffold_phase(
        input_file="X_numeric_context_smiles.npy",
        output_stem="colon_numeric_context_smiles_dl_v1",
        phase_name="Phase 2C",
        fs_top_k=fs_top_k, out_suffix=out_suffix, experiment_dir=experiment_dir,
    )

    print("\n✅ DL Scaffold Split 완료!")
