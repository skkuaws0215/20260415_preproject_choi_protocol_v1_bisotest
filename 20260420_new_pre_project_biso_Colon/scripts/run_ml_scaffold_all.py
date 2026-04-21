"""
Scaffold Split 기반 ML 재실행 (Task 1)

목적: 프로토콜 v2.3 Section 13 지표 #21 충족
기존 run_ml_all.py의 train_evaluate_ml 함수를 재사용하되,
groups 파라미터를 canonical_drug_id → scaffold_id로 교체.

입력:
  - data/X_numeric.npy, X_numeric_smiles.npy, X_numeric_context_smiles.npy
  - data/y_train.npy
  - data/scaffold_groups.npy (compute_scaffolds.py에서 생성)

출력:
  - results/colon_numeric_ml_v1_scaffoldcv.json
  - results/colon_numeric_smiles_ml_v1_scaffoldcv.json
  - results/colon_numeric_context_smiles_ml_v1_scaffoldcv.json
  - results/colon_numeric_ml_v1_scaffold_oof/*.npy (18 파일: 6 모델 × 3 Phase)
  - results/colon_numeric_smiles_ml_v1_scaffold_oof/*.npy
  - results/colon_numeric_context_smiles_ml_v1_scaffold_oof/*.npy

Run:
  cd 20260420_new_pre_project_biso_Colon
  python3 scripts/run_ml_scaffold_all.py

전제: compute_scaffolds.py 먼저 실행
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).parent))

# 기존 run_ml_all.py의 함수 재사용
from run_ml_all import train_evaluate_ml
from phase2_utils import save_results

from lightgbm import LGBMRegressor
from xgboost import XGBRegressor
from catboost import CatBoostRegressor
from sklearn.ensemble import RandomForestRegressor, ExtraTreesRegressor


def run_scaffold_phase(input_file, output_stem, phase_name):
    """
    하나의 입력셋에 대해 Scaffold split으로 ML 6개 모델 실행
    """
    print("\n" + "=" * 120)
    print(f"{phase_name}: Scaffold Split ML Models")
    print("=" * 120)

    # 경로 설정
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    results_dir = base_dir / "results"
    results_dir.mkdir(exist_ok=True)

    # Scaffold OOF 디렉토리 (기존 drug split과 구분)
    oof_dir = results_dir / f"{output_stem}_scaffold_oof"
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
    print(f"Unique scaffolds in pairs: {len(np.unique(scaffold_groups))}")

    # 모델 정의 (run_ml_all.py와 동일)
    models = {
        'LightGBM': lambda: LGBMRegressor(random_state=42, verbose=-1, n_jobs=-1),
        'LightGBM_DART': lambda: LGBMRegressor(boosting_type='dart', random_state=42, verbose=-1, n_jobs=-1),
        'XGBoost': lambda: XGBRegressor(random_state=42, verbosity=0, n_jobs=-1),
        'CatBoost': lambda: CatBoostRegressor(random_state=42, verbose=0),
        'RandomForest': lambda: RandomForestRegressor(random_state=42, n_jobs=-1),
        'ExtraTrees': lambda: ExtraTreesRegressor(random_state=42, n_jobs=-1)
    }

    # Scaffold split은 groupcv 평가 모드만 사용 (holdout/5foldcv는 의미 없음)
    all_results = {}

    for model_name, model_class in models.items():
        results = train_evaluate_ml(
            X, y, scaffold_groups,     # ← groups를 scaffold로 교체
            model_name, model_class,
            eval_mode='groupcv',        # GroupKFold 3-fold, groups=scaffold
            output_stem=f"{output_stem}_scaffold",
            oof_dir=oof_dir
        )
        all_results[model_name] = results

    # 결과 저장 (파일명에 'scaffoldcv' 표기)
    output_file = results_dir / f"{output_stem}_scaffoldcv.json"
    save_results(all_results, output_file)
    print(f"\n✓ Saved: {output_file}")

    # 중간 요약
    print("\n" + "=" * 120)
    print(f"{phase_name} (Scaffold Split) 완료 - 중간 요약")
    print("=" * 120)
    print(f"{'Model':20s} | {'Val Spearman':>13s} | {'Gap':>10s}")
    print("-" * 60)

    for model_name, result in all_results.items():
        val_sps = [f['val']['spearman'] for f in result['fold_results']]
        train_sps = [f['train']['spearman'] for f in result['fold_results']]
        val_mean = np.mean(val_sps)
        gap = np.mean(train_sps) - val_mean
        print(f"{model_name:20s} | {val_mean:13.4f} | {gap:+10.4f}")

    return all_results


def compare_with_drug_split(output_stem):
    """
    Drug split (기존 GroupCV) vs Scaffold split 비교
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
        drug_val = np.mean([f['val']['spearman'] for f in drug_results[model_name]['fold_results']])
        if model_name not in scaffold_results:
            continue
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
    print("\n" + "=" * 120)
    print("Task 1: Scaffold Split 기반 ML 실험")
    print("프로토콜 v2.3 Section 13 지표 #21 충족 시도")
    print("=" * 120)

    # Phase 2A: numeric-only
    results_2a = run_scaffold_phase(
        input_file="X_numeric.npy",
        output_stem="colon_numeric_ml_v1",
        phase_name="Phase 2A"
    )

    # Phase 2B: numeric + SMILES
    results_2b = run_scaffold_phase(
        input_file="X_numeric_smiles.npy",
        output_stem="colon_numeric_smiles_ml_v1",
        phase_name="Phase 2B"
    )

    # Phase 2C: numeric + context + SMILES
    results_2c = run_scaffold_phase(
        input_file="X_numeric_context_smiles.npy",
        output_stem="colon_numeric_context_smiles_ml_v1",
        phase_name="Phase 2C"
    )

    # Drug split vs Scaffold split 비교
    print("\n" + "=" * 120)
    print("Drug Split vs Scaffold Split 비교 (기존 GroupCV vs 신규 ScaffoldCV)")
    print("=" * 120)

    for phase_name, stem in [
        ('Phase 2A', 'colon_numeric_ml_v1'),
        ('Phase 2B', 'colon_numeric_smiles_ml_v1'),
        ('Phase 2C', 'colon_numeric_context_smiles_ml_v1'),
    ]:
        print(f"\n[{phase_name}]")
        compare_with_drug_split(stem)

    print("\n" + "=" * 120)
    print("✅ Scaffold Split 완료!")
    print("=" * 120)
    print("\n판정 기준:")
    print("  🟢 Drop < 0.05:    scaffold 독립적, 일반화 능력 우수")
    print("  🟡 Drop 0.05~0.15: 중간 의존, 업계 평균 수준")
    print("  🔴 Drop > 0.15:    scaffold 암기 심함, 새 chemotype 예측 어려움")
