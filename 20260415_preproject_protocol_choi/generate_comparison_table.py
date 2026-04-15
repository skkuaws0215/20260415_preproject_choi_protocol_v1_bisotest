"""
전체 결과 비교표 생성
평가 방식 3가지 × 입력셋 3가지 × 모델별 Spearman 비교
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

def load_results(results_dir, output_stems, eval_modes):
    """모든 결과 로드"""
    all_results = {}

    for stem in output_stems:
        all_results[stem] = {}
        for mode in eval_modes:
            result_file = results_dir / f"{stem}_{mode}.json"
            if result_file.exists():
                with open(result_file) as f:
                    all_results[stem][mode] = json.load(f)
            else:
                all_results[stem][mode] = None

    return all_results


def extract_spearman(result, eval_mode):
    """결과에서 Spearman 추출"""
    if result is None:
        return None

    if eval_mode == 'holdout':
        return result['test']['spearman']
    else:
        # fold 평균
        val_sps = [f['val']['spearman'] for f in result['fold_results']]
        return np.mean(val_sps)


def generate_comparison_table(results_dir):
    """비교표 생성"""
    print("="*140)
    print("전체 결과 비교표")
    print("="*140)

    output_stems = [
        'choi_numeric_ml_v1',
        'choi_numeric_smiles_ml_v1',
        'choi_numeric_context_smiles_ml_v1'
    ]

    eval_modes = ['holdout', '5foldcv', 'groupcv']

    # 결과 로드
    all_results = load_results(Path(results_dir), output_stems, eval_modes)

    # 입력셋별로 표 생성
    input_set_names = {
        'choi_numeric_ml_v1': 'Numeric-only',
        'choi_numeric_smiles_ml_v1': 'Numeric+SMILES',
        'choi_numeric_context_smiles_ml_v1': 'Numeric+Context+SMILES'
    }

    for stem, input_name in input_set_names.items():
        print(f"\n{'='*140}")
        print(f"입력셋: {input_name}")
        print(f"{'='*140}")

        # 모델 목록
        if all_results[stem]['holdout'] is not None:
            models = list(all_results[stem]['holdout'].keys())
        else:
            continue

        # 표 생성
        print(f"\n{'Model':20s} | {'Holdout':>12} | {'5-Fold CV':>12} | {'GroupCV (3-fold)':>18}")
        print("-" * 140)

        for model in models:
            row = [model]

            for mode in eval_modes:
                if all_results[stem][mode] and model in all_results[stem][mode]:
                    spearman = extract_spearman(all_results[stem][mode][model], mode)
                    row.append(f"{spearman:.4f}" if spearman is not None else "N/A")
                else:
                    row.append("N/A")

            print(f"{row[0]:20s} | {row[1]:>12s} | {row[2]:>12s} | {row[3]:>18s}")

    # 평가 방식별 비교 (모든 입력셋)
    for mode in eval_modes:
        print(f"\n{'='*140}")
        print(f"평가 방식: {mode.upper()}")
        print(f"{'='*140}")

        # 입력셋별로 모델 성능 비교
        print(f"\n{'Model':20s} | {'Numeric':>12} | {'Numeric+SMILES':>15} | {'Numeric+Ctx+SMILES':>20} | {'Best':>10}")
        print("-" * 140)

        # 모델 목록
        if all_results[output_stems[0]][mode] is not None:
            models = list(all_results[output_stems[0]][mode].keys())
        else:
            continue

        for model in models:
            row = [model]
            spearman_values = []

            for stem in output_stems:
                if all_results[stem][mode] and model in all_results[stem][mode]:
                    spearman = extract_spearman(all_results[stem][mode][model], mode)
                    row.append(f"{spearman:.4f}" if spearman is not None else "N/A")
                    spearman_values.append(spearman if spearman is not None else 0)
                else:
                    row.append("N/A")
                    spearman_values.append(0)

            # Best
            best_idx = np.argmax(spearman_values)
            best_stem = ['Num', 'Num+S', 'Num+C+S'][best_idx]
            row.append(best_stem)

            print(f"{row[0]:20s} | {row[1]:>12s} | {row[2]:>15s} | {row[3]:>20s} | {row[4]:>10s}")

    # 종합 순위
    print(f"\n{'='*140}")
    print(f"종합 순위 (GroupCV 기준)")
    print(f"{'='*140}")

    # GroupCV 결과만 모아서 정렬
    rankings = []
    for stem in output_stems:
        if all_results[stem]['groupcv'] is not None:
            for model, result in all_results[stem]['groupcv'].items():
                spearman = extract_spearman(result, 'groupcv')
                if spearman is not None:
                    rankings.append({
                        'model': model,
                        'input_set': input_set_names[stem],
                        'spearman': spearman
                    })

    # 정렬
    rankings.sort(key=lambda x: x['spearman'], reverse=True)

    print(f"\n{'Rank':>6} | {'Model':20s} | {'Input Set':25s} | {'Spearman':>12}")
    print("-" * 140)

    for rank, item in enumerate(rankings[:20], 1):  # Top 20
        print(f"{rank:6d} | {item['model']:20s} | {item['input_set']:25s} | {item['spearman']:12.4f}")


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    results_dir = base_dir / "results"

    generate_comparison_table(results_dir)
