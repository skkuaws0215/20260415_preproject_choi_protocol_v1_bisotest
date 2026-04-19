#!/usr/bin/env python3
"""
최종 종합 보고서 생성
- Phase 2 전체 지표
- Phase 3 앙상블 결과
- 최종 추천
"""

import json
import numpy as np
from pathlib import Path
from scipy.stats import spearmanr

# Load ensemble results
def load_oof(phase, model_name):
    """Load OOF predictions"""
    phase_map = {
        '2A': 'lung_numeric',
        '2B': 'lung_numeric_smiles',
        '2C': 'lung_numeric_context_smiles'
    }

    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']

    if model_name == 'GAT':
        oof_dir = Path(__file__).parent / "results" / "lung_numeric_graph_v1_oof"
    elif model_name in ml_models:
        oof_dir = Path(__file__).parent / "results" / f"{phase_map[phase]}_ml_v1_oof"
    else:
        oof_dir = Path(__file__).parent / "results" / f"{phase_map[phase]}_dl_v1_oof"

    oof_file = oof_dir / f"{model_name}.npy"
    if oof_file.exists():
        return np.load(oof_file)
    return None

y_train = np.load(Path(__file__).parent / "data" / "y_train.npy")

# Single model scores (Phase 2C)
single_model_scores = {
    'CatBoost': 0.5030,
    'ResidualMLP': 0.4277,
    'XGBoost': 0.4235,
    'TabTransformer': 0.4186,
    'LightGBM_DART': 0.4142,
    'FlatMLP': 0.4122,
    'LightGBM': 0.4062,
    'TabNet': 0.4063,
    'FTTransformer': 0.4018,
    'CrossAttention': 0.3841,
    'WideDeep': 0.3149,
    'RandomForest': 0.2822
}

# Best ensemble (Phase 2A)
best_ensemble_2a = {
    'name': 'Mixed Weighted',
    'models': ['CatBoost', 'ResidualMLP', 'TabNet'],
    'score': 0.4797,
    'gain': 0.0033
}

# Best ensemble (Phase 2C)
best_ensemble_2c_mixed = {
    'name': 'Mixed Weighted',
    'models': ['CatBoost', 'ResidualMLP', 'TabNet'],
    'score': 0.4855,
    'gain': -0.0175
}

best_ensemble_2c_dl = {
    'name': 'DL_Top3 Weighted',
    'models': ['ResidualMLP', 'TabTransformer', 'TabNet'],
    'score': 0.4290,
    'gain': 0.0013
}

print("=" * 200)
print("최종 종합 보고서 - Lung Cancer Drug Repurposing")
print("=" * 200)

print("\n" + "=" * 200)
print("1. Phase 2 단일 모델 최종 순위 (Phase 2C GroupCV)")
print("=" * 200)
print(f"\n{'Rank':>4s} | {'Model':20s} | {'Type':6s} | {'Spearman':>10s} | {'비고':40s}")
print("-" * 200)

sorted_models = sorted(single_model_scores.items(), key=lambda x: x[1], reverse=True)
for rank, (model, score) in enumerate(sorted_models, 1):
    model_type = 'ML' if model in ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees'] else 'DL'
    note = ""
    if rank == 1:
        note = "⭐ 전체 최고 - 대부분 앙상블보다 우수"
    elif model == 'RandomForest':
        note = "Phase 2C에서 급격한 성능 저하"

    print(f"{rank:>4d} | {model:20s} | {model_type:6s} | {score:10.4f} | {note:40s}")

print("\n" + "=" * 200)
print("2. Phase 3 앙상블 최종 결과 (양수 Gain만)")
print("=" * 200)
print(f"\n{'Rank':>4s} | {'Phase':6s} | {'Ensemble':15s} | {'Method':10s} | {'Spearman':>10s} | "
      f"{'Best Single':>12s} | {'Gain':>10s} | {'Models':50s}")
print("-" * 200)

positive_gains = [
    ('2A', 'Mixed', 'Weighted', 0.4797, 0.4765, 0.0033, 'CatBoost+ResidualMLP+TabNet'),
    ('2A', 'Mixed', 'Simple', 0.4790, 0.4765, 0.0025, 'CatBoost+ResidualMLP+TabNet'),
    ('2C', 'DL_Top3', 'Weighted', 0.4290, 0.4277, 0.0013, 'ResidualMLP+TabTransformer+TabNet'),
    ('2C', 'DL_Top3', 'Simple', 0.4290, 0.4277, 0.0012, 'ResidualMLP+TabTransformer+TabNet'),
]

for rank, (phase, ens, method, score, best_single, gain, models) in enumerate(positive_gains, 1):
    print(f"{rank:>4d} | {phase:6s} | {ens:15s} | {method:10s} | {score:10.4f} | "
          f"{best_single:12.4f} | {gain:+10.4f} | {models:50s}")

print("\n" + "=" * 200)
print("3. 최종 추천")
print("=" * 200)

print("\n[추천 1] 단일 모델: Phase 2C CatBoost")
print("-" * 200)
print(f"  GroupCV Spearman: 0.5030")
print(f"  이유:")
print(f"    - 전체 Phase에서 1위 (0.4765 → 0.4823 → 0.5030)")
print(f"    - Context 추가 효과 유일하게 긍정적 (+0.0207)")
print(f"    - 대부분의 앙상블보다 우수")
print(f"    - 단순하고 해석 가능")
print(f"    - 과적합 Gap 0.4140 (다른 모델 대비 낮음)")

print("\n[추천 2] 앙상블 (제한적 효과): Phase 2A Mixed Weighted")
print("-" * 200)
print(f"  GroupCV Spearman: 0.4797")
print(f"  Gain: +0.0033")
print(f"  구성: CatBoost + ResidualMLP + TabNet (가중 평균)")
print(f"  이유:")
print(f"    - 유일하게 의미있는 양수 Gain")
print(f"    - ML(CatBoost) + DL(ResidualMLP, TabNet) 혼합")
print(f"    - Diversity 0.7559 (적절한 다양성)")
print(f"    - Error Overlap 0.6553 (낮음)")
print(f"  주의:")
print(f"    - Phase 2B/2C에서는 음수 Gain")
print(f"    - 복잡도 증가 대비 성능 향상 미미")

print("\n[추천 3] DL 앙상블 (Phase 2C): DL_Top3 Weighted")
print("-" * 200)
print(f"  GroupCV Spearman: 0.4290")
print(f"  Gain: +0.0013")
print(f"  구성: ResidualMLP + TabTransformer + TabNet (가중 평균)")
print(f"  이유:")
print(f"    - Phase 2C에서 양수 Gain")
print(f"    - 순수 DL 모델 조합")
print(f"    - 높은 Diversity (0.8569)")
print(f"  주의:")
print(f"    - Gain 매우 작음 (+0.0013)")
print(f"    - 단일 ResidualMLP와 거의 동일")

print("\n" + "=" * 200)
print("4. 결론 및 해석")
print("=" * 200)

print("""
약물 재창출(Drug Repurposing) Lung Cancer 파이프라인 결과:

1. **단일 모델의 우수성**:
   - CatBoost가 압도적 성능 (0.5030)
   - 앙상블의 제한적 효과 (24개 중 4개만 양수 Gain)

2. **입력 특성 효과**:
   - SMILES 추가 (2A→2B): 대부분 부정적 또는 무효과
   - Context 추가 (2B→2C): CatBoost만 긍정적 (+0.0207)

3. **약물 단위 일반화의 어려움**:
   - 모든 모델이 심각한 과적합 (Gap > 0.15)
   - Train Spearman 0.8~0.9, Val Spearman 0.3~0.5
   - Train/Val Ratio 1.8~2.8

4. **앙상블 실패 원인**:
   - 높은 모델 간 상관 (Diversity 0.7~0.9)
   - 유사한 오류 패턴 (Error Overlap 0.6~0.8)
   - CatBoost의 압도적 성능으로 다른 모델 추가 시 희석

5. **최종 권장사항**:
   ✅ **Phase 2C CatBoost 단일 모델 사용**
   - 간단하고 효과적
   - 해석 가능성 높음
   - 배포 및 유지보수 용이

   ❌ 앙상블 사용 비권장
   - 복잡도 증가 대비 성능 향상 미미
   - 계산 비용 증가
   - 해석 어려움
""")

print("\n" + "=" * 200)
print("✅ 최종 종합 보고서 생성 완료!")
print("=" * 200)
