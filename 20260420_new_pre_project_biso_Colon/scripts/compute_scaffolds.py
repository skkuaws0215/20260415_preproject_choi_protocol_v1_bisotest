"""
Murcko Scaffold 추출 (Task 1 — Scaffold Split용)

목적: 프로토콜 v2.3 Section 13 지표 #21 (Scaffold split) 충족
입력:
  - data/drug_features.parquet (canonical_smiles 포함)
  - fe_qc/20260420_colon_fe_v2/features/labels.parquet (pair 수준 매핑)
출력:
  - data/scaffold_groups.npy (9692,) — 각 pair의 scaffold integer ID
  - data/scaffold_mapping.json — {drug_id: scaffold_smiles, ...}
  - data/scaffold_stats.json — 통계 요약

Run:
  cd 20260420_new_pre_project_biso_Colon
  python3 scripts/compute_scaffolds.py
"""

import numpy as np
import pandas as pd
import json
from pathlib import Path
from collections import Counter
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit import RDLogger

# RDKit 경고 숨기기 (SMILES parsing warnings 많음)
RDLogger.DisableLog('rdApp.*')


def extract_scaffold(smiles):
    """
    SMILES → Murcko scaffold SMILES
    Returns: scaffold string or special marker
    """
    if pd.isna(smiles) or smiles == '':
        return 'NO_SMILES'

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return 'INVALID_SMILES'

    try:
        scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
        if not scaffold or scaffold == '':
            # 체인만 있는 작은 분자 (ring 없음)
            return 'EMPTY_SCAFFOLD'
        return scaffold
    except Exception as e:
        return f'ERROR_{type(e).__name__}'


def main():
    # 경로 설정 - scripts/의 상위 (프로젝트 루트)
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    features_dir = base_dir / "fe_qc" / "20260420_colon_fe_v2" / "features"

    print("=" * 100)
    print("Murcko Scaffold 추출 (Task 1: Scaffold Split 준비)")
    print("=" * 100)

    # 1. Drug-level SMILES → scaffold 매핑
    print("\n[1] Drug-level scaffold 추출")
    df_drugs = pd.read_parquet(data_dir / "drug_features.parquet")
    print(f"  drug_features.parquet shape: {df_drugs.shape}")

    drug_to_scaffold = {}
    for _, row in df_drugs.iterrows():
        did = str(row['canonical_drug_id'])
        smi = row.get('canonical_smiles', None)
        drug_to_scaffold[did] = extract_scaffold(smi)

    # 2. Unique scaffold → integer ID
    unique_scaffolds = sorted(set(drug_to_scaffold.values()))
    scaffold_to_id = {s: i for i, s in enumerate(unique_scaffolds)}

    # 3. 통계
    scaffold_counts = Counter(drug_to_scaffold.values())
    print(f"  Total drugs: {len(drug_to_scaffold)}")
    print(f"  Unique scaffolds: {len(unique_scaffolds)}")
    print(f"\n  카테고리별 drug 수:")
    categories = {
        'NO_SMILES': scaffold_counts.get('NO_SMILES', 0),
        'INVALID_SMILES': scaffold_counts.get('INVALID_SMILES', 0),
        'EMPTY_SCAFFOLD': scaffold_counts.get('EMPTY_SCAFFOLD', 0),
    }
    error_count = sum(v for k, v in scaffold_counts.items() if k.startswith('ERROR_'))
    categories['ERROR'] = error_count
    valid_scaffolds = len(unique_scaffolds) - sum(1 for k in scaffold_counts if k in ['NO_SMILES', 'INVALID_SMILES', 'EMPTY_SCAFFOLD'] or k.startswith('ERROR_'))
    categories['valid_unique_scaffolds'] = valid_scaffolds

    for k, v in categories.items():
        print(f"    {k:30s}: {v}")

    # 4. 상위 10개 scaffold
    print(f"\n  Top 10 scaffolds (drug 수 기준):")
    for scaffold, cnt in scaffold_counts.most_common(10):
        display = scaffold[:80] + '...' if len(scaffold) > 80 else scaffold
        print(f"    [{cnt:3d} drugs] {display}")

    # 5. Pair-level 매핑
    print("\n[2] Pair-level scaffold ID 매핑")
    df_labels = pd.read_parquet(features_dir / "labels.parquet")
    print(f"  labels.parquet shape: {df_labels.shape}")

    scaffold_ids = np.array([
        scaffold_to_id[drug_to_scaffold[str(did)]]
        for did in df_labels['canonical_drug_id']
    ], dtype=np.int32)

    print(f"  scaffold_groups: {scaffold_ids.shape}, dtype={scaffold_ids.dtype}")
    print(f"  Min ID: {scaffold_ids.min()}, Max ID: {scaffold_ids.max()}")
    print(f"  Unique IDs in pairs: {len(np.unique(scaffold_ids))}")

    # 6. Pair-level 분포 (3-fold 적정성 평가)
    print("\n[3] Pair-level scaffold 분포 (3-fold 적정성 평가)")
    pair_counts = Counter(scaffold_ids)
    sorted_counts = sorted(pair_counts.values(), reverse=True)

    print(f"  Total pairs: {len(scaffold_ids)}")
    print(f"  Scaffolds with pairs: {len(pair_counts)}")
    print(f"  Max pairs per scaffold: {sorted_counts[0] if sorted_counts else 0}")
    print(f"  Min pairs per scaffold: {sorted_counts[-1] if sorted_counts else 0}")
    print(f"  Median pairs per scaffold: {sorted_counts[len(sorted_counts)//2] if sorted_counts else 0}")

    # 3-fold 불균형 체크
    target_fold_size = len(scaffold_ids) / 3
    largest_scaffold_pairs = sorted_counts[0] if sorted_counts else 0
    imbalance_ratio = largest_scaffold_pairs / target_fold_size
    print(f"\n  3-fold 목표 크기: ~{target_fold_size:.0f} pairs/fold")
    print(f"  가장 큰 scaffold: {largest_scaffold_pairs} pairs ({imbalance_ratio*100:.1f}% of fold)")

    if imbalance_ratio > 0.5:
        print(f"  ⚠️  경고: 단일 scaffold가 fold의 {imbalance_ratio*100:.1f}% → 불균형 심함")
        print(f"      → GroupKFold가 해당 scaffold를 하나의 fold에 몰아넣음")
        print(f"      → 결과 해석 시 주의 필요")
    else:
        print(f"  ✅ 양호: 단일 scaffold가 fold의 {imbalance_ratio*100:.1f}% 이하")

    # 7. 저장
    print("\n[4] 파일 저장")

    # scaffold_groups.npy
    np.save(data_dir / "scaffold_groups.npy", scaffold_ids)
    print(f"  ✓ Saved: data/scaffold_groups.npy ({scaffold_ids.nbytes/1024:.1f} KB)")

    # scaffold_mapping.json
    mapping_data = {
        'drug_to_scaffold': drug_to_scaffold,
        'scaffold_to_id': scaffold_to_id,
    }
    with open(data_dir / "scaffold_mapping.json", 'w') as f:
        json.dump(mapping_data, f, indent=2)
    print(f"  ✓ Saved: data/scaffold_mapping.json")

    # scaffold_stats.json
    stats = {
        'total_drugs': len(drug_to_scaffold),
        'unique_scaffolds': len(unique_scaffolds),
        'valid_unique_scaffolds': valid_scaffolds,
        'categories': categories,
        'total_pairs': int(len(scaffold_ids)),
        'scaffolds_in_pairs': len(pair_counts),
        'pairs_per_scaffold': {
            'max': sorted_counts[0] if sorted_counts else 0,
            'min': sorted_counts[-1] if sorted_counts else 0,
            'median': sorted_counts[len(sorted_counts)//2] if sorted_counts else 0,
            'mean': float(np.mean(sorted_counts)) if sorted_counts else 0,
        },
        'imbalance': {
            'largest_scaffold_pairs': largest_scaffold_pairs,
            'target_fold_size': target_fold_size,
            'imbalance_ratio': float(imbalance_ratio),
        },
        'top10_scaffolds_by_drug_count': [
            {'scaffold': s, 'drug_count': c}
            for s, c in scaffold_counts.most_common(10)
        ]
    }
    with open(data_dir / "scaffold_stats.json", 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"  ✓ Saved: data/scaffold_stats.json")

    print("\n" + "=" * 100)
    print("완료!")
    print("=" * 100)
    print(f"  다음 단계: python3 scripts/run_ml_scaffold_all.py")


if __name__ == "__main__":
    main()
