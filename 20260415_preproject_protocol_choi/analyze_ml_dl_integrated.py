"""
Phase 2A/2B/2C ML+DL 통합 비교 분석
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

def load_all_results(results_dir):
    """ML + DL 모든 결과 로드"""
    phases = {
        '2A_Numeric': {
            'ml': 'choi_numeric_ml_v1',
            'dl': 'choi_numeric_dl_v1'
        },
        '2B_Num+SMILES': {
            'ml': 'choi_numeric_smiles_ml_v1',
            'dl': 'choi_numeric_smiles_dl_v1'
        },
        '2C_Num+Ctx+SMILES': {
            'ml': 'choi_numeric_context_smiles_ml_v1',
            'dl': 'choi_numeric_context_smiles_dl_v1'
        }
    }

    results = {}
    for phase_name, stems in phases.items():
        results[phase_name] = {'ml': {}, 'dl': {}}

        for model_type, stem in stems.items():
            for eval_mode in ['holdout', '5foldcv', 'groupcv']:
                file_path = results_dir / f"{stem}_{eval_mode}.json"
                if file_path.exists():
                    with open(file_path) as f:
                        results[phase_name][model_type][eval_mode] = json.load(f)
                else:
                    results[phase_name][model_type][eval_mode] = None

    return results

def extract_val_spearman(result, eval_mode):
    """Val Spearman 추출"""
    if result is None:
        return None

    if eval_mode == 'holdout':
        return result['test']['spearman']
    else:
        val_sps = [f['val']['spearman'] for f in result['fold_results']]
        return np.mean(val_sps)

def extract_train_spearman(result, eval_mode):
    """Train Spearman 추출"""
    if result is None:
        return None

    if eval_mode == 'holdout':
        return result['train']['spearman']
    else:
        train_sps = [f['train']['spearman'] for f in result['fold_results']]
        return np.mean(train_sps)

def table1_ml_vs_dl_groupcv(results):
    """1. ML vs DL GroupCV 성능 비교 (입력셋별)"""
    print("\n" + "="*140)
    print("1. ML vs DL GroupCV Val Spearman 비교 (입력셋별)")
    print("="*140)

    phases = ['2A_Numeric', '2B_Num+SMILES', '2C_Num+Ctx+SMILES']

    # ML 모델들
    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']

    # DL 모델들
    dl_models = ['FlatMLP', 'ResidualMLP', 'FTTransformer', 'CrossAttention', 'TabNet', 'WideDeep', 'TabTransformer']

    for phase in phases:
        print(f"\n{phase}")
        print("-"*140)

        # ML 결과
        print("\n[ML Models]")
        ml_scores = []
        for model in ml_models:
            if results[phase]['ml']['groupcv'] and model in results[phase]['ml']['groupcv']:
                score = extract_val_spearman(results[phase]['ml']['groupcv'][model], 'groupcv')
                ml_scores.append((model, score))

        ml_scores.sort(key=lambda x: x[1] if x[1] is not None else -999, reverse=True)
        for rank, (model, score) in enumerate(ml_scores, 1):
            print(f"  {rank}. {model:<20} {score:.4f}")

        # DL 결과
        print("\n[DL Models]")
        dl_scores = []
        for model in dl_models:
            if results[phase]['dl']['groupcv'] and model in results[phase]['dl']['groupcv']:
                score = extract_val_spearman(results[phase]['dl']['groupcv'][model], 'groupcv')
                dl_scores.append((model, score))

        dl_scores.sort(key=lambda x: x[1] if x[1] is not None else -999, reverse=True)
        for rank, (model, score) in enumerate(dl_scores, 1):
            print(f"  {rank}. {model:<20} {score:.4f}")

        # 통계
        ml_vals = [s[1] for s in ml_scores if s[1] is not None]
        dl_vals = [s[1] for s in dl_scores if s[1] is not None]

        print(f"\n[통계]")
        print(f"  ML: Best={max(ml_vals):.4f}, Mean={np.mean(ml_vals):.4f}, Std={np.std(ml_vals):.4f}")
        print(f"  DL: Best={max(dl_vals):.4f}, Mean={np.mean(dl_vals):.4f}, Std={np.std(dl_vals):.4f}")

        # 최고 모델
        best_ml = ml_scores[0]
        best_dl = dl_scores[0]
        print(f"\n  🏆 Phase {phase} 최고 모델:")
        print(f"     ML: {best_ml[0]} ({best_ml[1]:.4f})")
        print(f"     DL: {best_dl[0]} ({best_dl[1]:.4f})")

        if best_ml[1] > best_dl[1]:
            print(f"     → ML 우세 (Δ = +{best_ml[1] - best_dl[1]:.4f})")
        else:
            print(f"     → DL 우세 (Δ = +{best_dl[1] - best_ml[1]:.4f})")

def table2_best_models_all_phases(results):
    """2. 전체 최고 모델 비교 (평가 방식별 × 입력셋별)"""
    print("\n" + "="*140)
    print("2. 전체 최고 성능 모델 (평가 방식별 × 입력셋별)")
    print("="*140)

    phases = ['2A_Numeric', '2B_Num+SMILES', '2C_Num+Ctx+SMILES']
    eval_modes = ['holdout', '5foldcv', 'groupcv']

    print(f"\n{'Phase':<25} | {'Holdout':>45} | {'5-Fold CV':>45} | {'GroupCV':>45}")
    print("-"*140)

    for phase in phases:
        row_data = [phase]

        for eval_mode in eval_modes:
            best_model = None
            best_score = -999
            best_type = None

            # ML 모델들 확인
            if results[phase]['ml'][eval_mode]:
                for model, result in results[phase]['ml'][eval_mode].items():
                    score = extract_val_spearman(result, eval_mode)
                    if score is not None and score > best_score:
                        best_score = score
                        best_model = model
                        best_type = 'ML'

            # DL 모델들 확인
            if results[phase]['dl'][eval_mode]:
                for model, result in results[phase]['dl'][eval_mode].items():
                    score = extract_val_spearman(result, eval_mode)
                    if score is not None and score > best_score:
                        best_score = score
                        best_model = model
                        best_type = 'DL'

            if best_model:
                row_data.append(f"{best_type}:{best_model} ({best_score:.4f})")
            else:
                row_data.append("N/A")

        print(f"{row_data[0]:<25} | {row_data[1]:>45} | {row_data[2]:>45} | {row_data[3]:>45}")

def table3_feature_effects(results):
    """3. 피처 추가 효과 비교 (ML vs DL)"""
    print("\n" + "="*140)
    print("3. 피처 추가 효과 (A→B: SMILES, B→C: Context) - GroupCV")
    print("="*140)

    phases = ['2A_Numeric', '2B_Num+SMILES', '2C_Num+Ctx+SMILES']

    for model_type in ['ml', 'dl']:
        print(f"\n[{model_type.upper()} Models]")
        print("-"*140)

        # 모델 리스트
        if model_type == 'ml':
            models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']
        else:
            models = ['FlatMLP', 'ResidualMLP', 'FTTransformer', 'CrossAttention', 'TabNet', 'WideDeep', 'TabTransformer']

        print(f"{'Model':<20} | {'2A':>10} | {'2B':>10} | {'2C':>10} | {'A→B':>10} | {'B→C':>10}")
        print("-"*140)

        ab_changes = []
        bc_changes = []

        for model in models:
            scores = {}
            for i, phase in enumerate(['2A_Numeric', '2B_Num+SMILES', '2C_Num+Ctx+SMILES']):
                if results[phase][model_type]['groupcv'] and model in results[phase][model_type]['groupcv']:
                    scores[phase] = extract_val_spearman(results[phase][model_type]['groupcv'][model], 'groupcv')
                else:
                    scores[phase] = None

            a = scores['2A_Numeric']
            b = scores['2B_Num+SMILES']
            c = scores['2C_Num+Ctx+SMILES']

            ab = b - a if (a is not None and b is not None) else None
            bc = c - b if (b is not None and c is not None) else None

            if ab is not None:
                ab_changes.append(ab)
            if bc is not None:
                bc_changes.append(bc)

            a_str = f"{a:10.4f}" if a is not None else "       N/A"
            b_str = f"{b:10.4f}" if b is not None else "       N/A"
            c_str = f"{c:10.4f}" if c is not None else "       N/A"
            ab_str = f"{ab:+10.4f}" if ab is not None else "       N/A"
            bc_str = f"{bc:+10.4f}" if bc is not None else "       N/A"

            print(f"{model:<20} | {a_str} | {b_str} | {c_str} | {ab_str} | {bc_str}")

        # 통계
        if ab_changes:
            print(f"\nSMILES 효과 (A→B): 평균={np.mean(ab_changes):+.4f}, 개선={sum(1 for x in ab_changes if x > 0)}/{len(ab_changes)}")
        if bc_changes:
            print(f"Context 효과 (B→C): 평균={np.mean(bc_changes):+.4f}, 개선={sum(1 for x in bc_changes if x > 0)}/{len(bc_changes)}")

def table4_gap_analysis(results):
    """4. Train-Val Gap 분석 (ML vs DL)"""
    print("\n" + "="*140)
    print("4. Train-Val Gap 분석 (GroupCV) - ML vs DL")
    print("="*140)

    phases = ['2A_Numeric', '2B_Num+SMILES', '2C_Num+Ctx+SMILES']

    for phase in phases:
        print(f"\n{phase}")
        print("-"*140)

        for model_type in ['ml', 'dl']:
            print(f"\n[{model_type.upper()}]")

            if model_type == 'ml':
                models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']
            else:
                models = ['FlatMLP', 'ResidualMLP', 'FTTransformer', 'CrossAttention', 'TabNet', 'WideDeep', 'TabTransformer']

            print(f"{'Model':<20} | {'Train':>10} | {'Val':>10} | {'Gap':>10}")
            print("-"*80)

            gaps = []
            for model in models:
                if results[phase][model_type]['groupcv'] and model in results[phase][model_type]['groupcv']:
                    train_sp = extract_train_spearman(results[phase][model_type]['groupcv'][model], 'groupcv')
                    val_sp = extract_val_spearman(results[phase][model_type]['groupcv'][model], 'groupcv')
                    gap = train_sp - val_sp if (train_sp is not None and val_sp is not None) else None

                    if gap is not None:
                        gaps.append(gap)

                    train_str = f"{train_sp:10.4f}" if train_sp is not None else "       N/A"
                    val_str = f"{val_sp:10.4f}" if val_sp is not None else "       N/A"
                    gap_str = f"{gap:10.4f}" if gap is not None else "       N/A"

                    print(f"{model:<20} | {train_str} | {val_str} | {gap_str}")

            if gaps:
                print(f"\n평균 Gap: {np.mean(gaps):.4f} (범위: {np.min(gaps):.4f} ~ {np.max(gaps):.4f})")

def table5_final_recommendations(results):
    """5. 최종 모델 추천"""
    print("\n" + "="*140)
    print("5. 최종 모델 추천")
    print("="*140)

    # GroupCV 기준으로 모든 모델 수집
    all_models = []

    for phase in ['2A_Numeric', '2B_Num+SMILES', '2C_Num+Ctx+SMILES']:
        for model_type in ['ml', 'dl']:
            if results[phase][model_type]['groupcv']:
                for model_name, model_result in results[phase][model_type]['groupcv'].items():
                    val_sp = extract_val_spearman(model_result, 'groupcv')
                    train_sp = extract_train_spearman(model_result, 'groupcv')
                    gap = train_sp - val_sp if (train_sp is not None and val_sp is not None) else None

                    all_models.append({
                        'Phase': phase,
                        'Type': model_type.upper(),
                        'Model': model_name,
                        'Val_Spearman': val_sp,
                        'Train_Spearman': train_sp,
                        'Gap': gap
                    })

    df = pd.DataFrame(all_models)
    df = df.sort_values('Val_Spearman', ascending=False).reset_index(drop=True)

    print("\nTop 10 모델 (GroupCV Val Spearman 기준)")
    print("-"*140)
    print(f"{'Rank':<6} {'Type':<5} {'Model':<20} {'Phase':<25} | {'Train':>10} {'Val':>10} {'Gap':>10}")
    print("-"*140)

    for idx, row in df.head(10).iterrows():
        rank = idx + 1
        print(f"{rank:<6} {row['Type']:<5} {row['Model']:<20} {row['Phase']:<25} | {row['Train_Spearman']:10.4f} {row['Val_Spearman']:10.4f} {row['Gap']:10.4f}")

    print("\n" + "="*140)
    print("추천 모델")
    print("="*140)

    # 최고 성능
    best = df.iloc[0]
    print(f"\n1. 최고 성능 (Val Spearman):")
    print(f"   → {best['Type']}:{best['Model']} ({best['Phase']}) - Val: {best['Val_Spearman']:.4f}")

    # Gap이 낮은 상위 모델
    top5 = df.head(5)
    best_stable = top5.loc[top5['Gap'].idxmin()]
    print(f"\n2. 최고 안정성 (Top 5 중 최소 Gap):")
    print(f"   → {best_stable['Type']}:{best_stable['Model']} ({best_stable['Phase']}) - Val: {best_stable['Val_Spearman']:.4f}, Gap: {best_stable['Gap']:.4f}")

    # ML 최고
    ml_best = df[df['Type'] == 'ML'].iloc[0]
    print(f"\n3. ML 최고:")
    print(f"   → {ml_best['Model']} ({ml_best['Phase']}) - Val: {ml_best['Val_Spearman']:.4f}")

    # DL 최고
    dl_best = df[df['Type'] == 'DL'].iloc[0]
    print(f"\n4. DL 최고:")
    print(f"   → {dl_best['Model']} ({dl_best['Phase']}) - Val: {dl_best['Val_Spearman']:.4f}")

def main():
    base_dir = Path(__file__).parent
    results_dir = base_dir / "results"

    print("="*140)
    print("Phase 2A/2B/2C ML+DL 통합 비교 분석")
    print("="*140)

    # 결과 로드
    results = load_all_results(results_dir)

    # 분석 테이블 생성
    table1_ml_vs_dl_groupcv(results)
    table2_best_models_all_phases(results)
    table3_feature_effects(results)
    table4_gap_analysis(results)
    table5_final_recommendations(results)

    print("\n" + "="*140)
    print("분석 완료!")
    print("="*140)

if __name__ == "__main__":
    main()
