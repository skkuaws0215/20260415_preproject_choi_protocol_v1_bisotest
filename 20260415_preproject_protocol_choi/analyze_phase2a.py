"""
Phase 2A (X_numeric) ML + DL 종합 비교 분석
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from itertools import combinations

def load_all_results(results_dir):
    """모든 결과 파일 로드"""
    results = {}

    # ML 결과
    with open(results_dir / "choi_numeric_ml_v1_holdout.json") as f:
        ml_holdout = json.load(f)
    with open(results_dir / "choi_numeric_ml_v1_5foldcv.json") as f:
        ml_5fold = json.load(f)
    with open(results_dir / "choi_numeric_ml_v1_groupcv.json") as f:
        ml_groupcv = json.load(f)

    # DL 결과
    with open(results_dir / "choi_numeric_dl_v1_holdout.json") as f:
        dl_holdout = json.load(f)
    with open(results_dir / "choi_numeric_dl_v1_5foldcv.json") as f:
        dl_5fold = json.load(f)
    with open(results_dir / "choi_numeric_dl_v1_groupcv.json") as f:
        dl_groupcv = json.load(f)

    results['ml'] = {
        'holdout': ml_holdout,
        '5foldcv': ml_5fold,
        'groupcv': ml_groupcv
    }

    results['dl'] = {
        'holdout': dl_holdout,
        '5foldcv': dl_5fold,
        'groupcv': dl_groupcv
    }

    return results

def extract_val_spearman(result, eval_mode):
    """Val Spearman 추출"""
    if eval_mode == 'holdout':
        return result['test']['spearman']
    else:
        # 5foldcv 또는 groupcv: fold 평균
        val_sps = [f['val']['spearman'] for f in result['fold_results']]
        return np.mean(val_sps)

def table1_evaluation_comparison(results):
    """1. 평가 방식별 × 모델별 Val Spearman 비교표"""
    print("\n" + "="*140)
    print("1. 평가 방식별 Val Spearman 비교 (ML 6개 + DL 7개 = 13개 모델)")
    print("="*140)

    # ML 모델
    ml_models = list(results['ml']['holdout'].keys())
    # DL 모델
    dl_models = list(results['dl']['holdout'].keys())

    all_models = [(m, 'ML') for m in ml_models] + [(m, 'DL') for m in dl_models]

    # 데이터 수집
    data = []
    for model_name, model_type in all_models:
        row = {'Model': f"{model_name} ({model_type})", 'Type': model_type}

        skip_model = False
        for eval_mode in ['holdout', '5foldcv', 'groupcv']:
            if model_type == 'ML':
                if model_name in results['ml'][eval_mode]:
                    result = results['ml'][eval_mode][model_name]
                    spearman = extract_val_spearman(result, eval_mode)
                    row[eval_mode] = spearman
                else:
                    row[eval_mode] = None
                    skip_model = True
            else:
                if model_name in results['dl'][eval_mode]:
                    result = results['dl'][eval_mode][model_name]
                    spearman = extract_val_spearman(result, eval_mode)
                    row[eval_mode] = spearman
                else:
                    # GroupCV에 없으면 스킵 (FlatMLP, ResidualMLP)
                    if eval_mode == 'groupcv':
                        row[eval_mode] = None
                    else:
                        skip_model = True

        if not skip_model or row.get('holdout') is not None:
            data.append(row)

    df = pd.DataFrame(data)

    # 각 평가 방식별 순위 (None 제외)
    for eval_mode in ['holdout', '5foldcv', 'groupcv']:
        df[f'{eval_mode}_rank'] = df[eval_mode].rank(ascending=False, method='min', na_option='keep')

    # GroupCV 기준 정렬 (None은 마지막)
    df = df.sort_values('groupcv', ascending=False, na_position='last').reset_index(drop=True)

    # 출력
    print(f"\n{'Rank':<6} {'Model':<35} {'Type':<5} | {'Holdout':>10} {'Rank':>5} | {'5-Fold CV':>10} {'Rank':>5} | {'GroupCV':>10} {'Rank':>5}")
    print("-" * 140)

    for idx, row in df.iterrows():
        rank = idx + 1

        # Format values and ranks (handle None)
        holdout_val = f"{row['holdout']:10.4f}" if pd.notna(row['holdout']) else "       N/A"
        holdout_rank = f"{int(row['holdout_rank']):5d}" if pd.notna(row['holdout_rank']) else "   - "

        foldcv_val = f"{row['5foldcv']:10.4f}" if pd.notna(row['5foldcv']) else "       N/A"
        foldcv_rank = f"{int(row['5foldcv_rank']):5d}" if pd.notna(row['5foldcv_rank']) else "   - "

        groupcv_val = f"{row['groupcv']:10.4f}" if pd.notna(row['groupcv']) else "       N/A"
        groupcv_rank = f"{int(row['groupcv_rank']):5d}" if pd.notna(row['groupcv_rank']) else "   - "

        print(f"{rank:<6} {row['Model']:<35} {row['Type']:<5} | "
              f"{holdout_val} {holdout_rank} | "
              f"{foldcv_val} {foldcv_rank} | "
              f"{groupcv_val} {groupcv_rank}")

    return df

def table2_groupcv_details(results, df_comparison):
    """2. GroupCV 기준 상세 결과"""
    print("\n" + "="*140)
    print("2. GroupCV 상세 결과 (전체 지표)")
    print("="*140)

    # Top 5 모델만
    top5 = df_comparison.head(5)

    for idx, row in top5.iterrows():
        model_full = row['Model']
        model_type = row['Type']
        # 모델명 추출 (괄호 제거)
        model_name = model_full.split(' (')[0]

        print(f"\n{'='*140}")
        print(f"#{idx+1}: {model_full} - GroupCV Val Spearman: {row['groupcv']:.4f}")
        print(f"{'='*140}")

        if model_type == 'ML':
            result = results['ml']['groupcv'][model_name]
        else:
            result = results['dl']['groupcv'][model_name]

        # Fold별 결과
        print(f"\n{'Fold':<6} | {'Train Sp':>10} {'Val Sp':>10} {'Gap':>10} | {'Pearson':>10} {'R²':>10} {'RMSE':>10} {'MAE':>10} {'Kendall':>10}")
        print("-" * 140)

        for fold in result['fold_results']:
            fold_num = fold['fold']
            train_sp = fold['train']['spearman']
            val_sp = fold['val']['spearman']
            gap = train_sp - val_sp

            val_metrics = fold['val']
            print(f"{fold_num:<6} | {train_sp:10.4f} {val_sp:10.4f} {gap:10.4f} | "
                  f"{val_metrics['pearson']:10.4f} "
                  f"{val_metrics['r2']:10.4f} "
                  f"{val_metrics['rmse']:10.4f} "
                  f"{val_metrics['mae']:10.4f} "
                  f"{val_metrics['kendall_tau']:10.4f}")

        # 통계
        val_sps = [f['val']['spearman'] for f in result['fold_results']]
        gaps = [f['train']['spearman'] - f['val']['spearman'] for f in result['fold_results']]

        print("-" * 140)
        print(f"{'Mean':<6} | {np.mean([f['train']['spearman'] for f in result['fold_results']]):10.4f} "
              f"{np.mean(val_sps):10.4f} {np.mean(gaps):10.4f}")
        print(f"{'Std':<6} |            {np.std(val_sps):10.4f} {np.std(gaps):10.4f}")

        # Overfitting check
        overfit = result['overfitting_check']
        print(f"\nOverfitting: {overfit['n_overfitting_folds']}/3 folds, Max Gap: {overfit['max_gap']:.4f}")

        # Stability check
        stability = result['stability_check']
        print(f"Stability: Std={stability['val_spearman_std']:.4f}, {'Unstable' if stability['unstable'] else 'Stable'}")

def table3_ml_vs_dl(results, df_comparison):
    """3. ML vs DL 비교 요약"""
    print("\n" + "="*140)
    print("3. ML vs DL 비교 요약")
    print("="*140)

    ml_data = df_comparison[df_comparison['Type'] == 'ML']
    dl_data = df_comparison[df_comparison['Type'] == 'DL']

    print(f"\n{'Metric':<20} | {'ML (6 models)':>20} | {'DL (7 models)':>20} | {'Winner':>10}")
    print("-" * 140)

    for eval_mode in ['holdout', '5foldcv', 'groupcv']:
        # Filter out None values
        ml_values = ml_data[eval_mode].dropna()
        dl_values = dl_data[eval_mode].dropna()

        if len(ml_values) == 0 or len(dl_values) == 0:
            continue

        ml_mean = ml_values.mean()
        ml_std = ml_values.std()
        ml_max = ml_values.max()
        ml_max_model = ml_data.loc[ml_values.idxmax(), 'Model'].split(' (')[0]

        dl_mean = dl_values.mean()
        dl_std = dl_values.std()
        dl_max = dl_values.max()
        dl_max_model = dl_data.loc[dl_values.idxmax(), 'Model'].split(' (')[0]

        print(f"\n{eval_mode.upper()}:")
        print(f"{'  평균 ± std':<20} | {ml_mean:8.4f} ± {ml_std:6.4f} | {dl_mean:8.4f} ± {dl_std:6.4f} | "
              f"{'ML' if ml_mean > dl_mean else 'DL'}")
        print(f"{'  최고 성능':<20} | {ml_max:8.4f} ({ml_max_model:9s}) | {dl_max:8.4f} ({dl_max_model:12s}) | "
              f"{'ML' if ml_max > dl_max else 'DL'}")

    # 종합 승자
    print(f"\n{'='*140}")
    print("종합 평가:")

    for eval_mode, name in [('holdout', 'Holdout'), ('5foldcv', '5-Fold CV'), ('groupcv', 'GroupCV (실제 성능)')]:
        ml_vals = ml_data[eval_mode].dropna()
        dl_vals = dl_data[eval_mode].dropna()
        if len(ml_vals) > 0 and len(dl_vals) > 0:
            winner = 'ML' if ml_vals.mean() > dl_vals.mean() else 'DL'
            print(f"  - {name}: {winner} 우세 (ML={ml_vals.mean():.4f} vs DL={dl_vals.mean():.4f})")

    top_model = df_comparison[df_comparison['groupcv'].notna()].iloc[0]['Model']
    print(f"  - 최고 단일 모델 (GroupCV): {top_model}")

def table4_diversity_matrix(results_dir):
    """4. 앙상블 예비 분석 - Diversity Matrix"""
    print("\n" + "="*140)
    print("4. 앙상블 예비 분석 - OOF 예측 다양성 (GroupCV)")
    print("="*140)

    # OOF 파일 로드
    oof_dir = results_dir / "choi_numeric_ml_v1_oof"

    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']

    oof_predictions = {}
    for model in ml_models:
        oof_file = oof_dir / f"{model}.npy"
        if oof_file.exists():
            oof_predictions[model] = np.load(oof_file)

    # DL OOF도 추가
    dl_oof_dir = results_dir / "choi_numeric_dl_v1_oof"
    dl_models = ['FlatMLP', 'ResidualMLP', 'FTTransformer', 'CrossAttention', 'TabNet', 'WideDeep', 'TabTransformer']

    for model in dl_models:
        oof_file = dl_oof_dir / f"{model}.npy"
        if oof_file.exists():
            oof_predictions[f"DL_{model}"] = np.load(oof_file)

    # 상관 행렬 계산
    model_names = list(oof_predictions.keys())
    n_models = len(model_names)
    corr_matrix = np.zeros((n_models, n_models))

    for i, model1 in enumerate(model_names):
        for j, model2 in enumerate(model_names):
            if i == j:
                corr_matrix[i, j] = 1.0
            else:
                pred1 = oof_predictions[model1]
                pred2 = oof_predictions[model2]
                corr = np.corrcoef(pred1, pred2)[0, 1]
                corr_matrix[i, j] = corr

    # 상관 행렬 출력 (요약)
    print(f"\n상관 행렬 (OOF 예측 간 Pearson 상관):")
    print(f"\n{'Model':<20}", end='')
    for name in model_names[:8]:  # 처음 8개만
        short_name = name[:10]
        print(f"{short_name:>10}", end='')
    print()
    print("-" * 140)

    for i, name1 in enumerate(model_names[:8]):
        short_name1 = name1[:20]
        print(f"{short_name1:<20}", end='')
        for j in range(min(8, len(model_names))):
            print(f"{corr_matrix[i, j]:10.4f}", end='')
        print()

    # 다양성이 높은 조합 찾기 (상관이 낮은 조합)
    print(f"\n{'='*140}")
    print("다양성이 높은 모델 조합 Top 10 (상관이 낮음 = 높은 다양성)")
    print("="*140)

    pairs = []
    for i in range(n_models):
        for j in range(i+1, n_models):
            corr = corr_matrix[i, j]
            pairs.append((model_names[i], model_names[j], corr))

    # 상관이 낮은 순으로 정렬
    pairs.sort(key=lambda x: x[2])

    print(f"\n{'Rank':<6} {'Model 1':<25} {'Model 2':<25} {'Correlation':>12} {'Diversity':>10}")
    print("-" * 140)

    for rank, (m1, m2, corr) in enumerate(pairs[:10], 1):
        diversity = 1 - abs(corr)
        print(f"{rank:<6} {m1:<25} {m2:<25} {corr:12.4f} {diversity:10.4f}")

    # 3개 조합 추천
    print(f"\n{'='*140}")
    print("앙상블 추천 조합 (3개 모델)")
    print("="*140)

    # 간단한 휴리스틱: 상위 성능 모델 중에서 다양성 높은 조합
    # ML Top 3 + DL Top 3 에서 조합
    top_ml = ['CatBoost', 'LightGBM', 'RandomForest']
    top_dl = ['DL_TabTransformer', 'DL_WideDeep', 'DL_FlatMLP']

    top_candidates = top_ml + top_dl
    top_candidates = [m for m in top_candidates if m in model_names]

    best_combos = []
    for combo in combinations(top_candidates, 3):
        indices = [model_names.index(m) for m in combo]
        avg_corr = np.mean([corr_matrix[i, j] for i in indices for j in indices if i != j])
        best_combos.append((combo, avg_corr, 1 - avg_corr))

    best_combos.sort(key=lambda x: x[1])  # 낮은 상관 = 높은 다양성

    print(f"\n{'Rank':<6} {'Model 1':<20} {'Model 2':<20} {'Model 3':<20} {'Avg Corr':>10} {'Diversity':>10}")
    print("-" * 140)

    for rank, (combo, avg_corr, diversity) in enumerate(best_combos[:3], 1):
        print(f"{rank:<6} {combo[0]:<20} {combo[1]:<20} {combo[2]:<20} {avg_corr:10.4f} {diversity:10.4f}")

def main():
    base_dir = Path(__file__).parent
    results_dir = base_dir / "results"

    print("="*140)
    print("Phase 2A (X_numeric) 종합 비교 분석")
    print("="*140)

    # 결과 로드
    results = load_all_results(results_dir)

    # 1. 평가 방식별 비교
    df_comparison = table1_evaluation_comparison(results)

    # 2. GroupCV 상세 결과
    table2_groupcv_details(results, df_comparison)

    # 3. ML vs DL 비교
    table3_ml_vs_dl(results, df_comparison)

    # 4. Diversity 분석
    table4_diversity_matrix(results_dir)

    print("\n" + "="*140)
    print("분석 완료!")
    print("="*140)

if __name__ == "__main__":
    main()
