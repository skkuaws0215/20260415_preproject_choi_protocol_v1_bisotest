"""
Phase 3 앙상블 종합 비교 분석 - 대시보드용 완전판
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import spearmanr, pearsonr, kendalltau, rankdata
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import sys

sys.path.insert(0, str(Path(__file__).parent))
from phase2_utils import calculate_metrics

def load_oof_predictions(results_dir, phase, models):
    """Load OOF predictions for specified models"""
    phase_stems = {
        '2A': {'ml': 'choi_numeric_ml_v1', 'dl': 'choi_numeric_dl_v1'},
        '2B': {'ml': 'choi_numeric_smiles_ml_v1', 'dl': 'choi_numeric_smiles_dl_v1'},
        '2C': {'ml': 'choi_numeric_context_smiles_ml_v1', 'dl': 'choi_numeric_context_smiles_dl_v1'}
    }

    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']

    oof_preds = {}
    for model in models:
        if model in ml_models:
            oof_dir = results_dir / f"{phase_stems[phase]['ml']}_oof"
        else:
            oof_dir = results_dir / f"{phase_stems[phase]['dl']}_oof"

        oof_file = oof_dir / f"{model}.npy"
        if oof_file.exists():
            oof_preds[model] = np.load(oof_file)
        else:
            raise FileNotFoundError(f"OOF file not found: {oof_file}")

    return oof_preds

def load_single_model_metrics(results_dir, phase, model):
    """Load all metrics for a single model from GroupCV"""
    phase_stems = {
        '2A': {'ml': 'choi_numeric_ml_v1', 'dl': 'choi_numeric_dl_v1'},
        '2B': {'ml': 'choi_numeric_smiles_ml_v1', 'dl': 'choi_numeric_smiles_dl_v1'},
        '2C': {'ml': 'choi_numeric_context_smiles_ml_v1', 'dl': 'choi_numeric_context_smiles_dl_v1'}
    }

    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']

    if model in ml_models:
        result_file = results_dir / f"{phase_stems[phase]['ml']}_groupcv.json"
    else:
        result_file = results_dir / f"{phase_stems[phase]['dl']}_groupcv.json"

    with open(result_file) as f:
        results = json.load(f)

    fold_results = results[model]['fold_results']

    metrics = {}
    for metric in ['spearman', 'pearson', 'r2', 'rmse', 'mae', 'kendall_tau']:
        val_vals = [f['val'][metric] for f in fold_results]
        train_vals = [f['train'][metric] for f in fold_results]

        metrics[f'val_{metric}'] = np.mean(val_vals)
        metrics[f'train_{metric}'] = np.mean(train_vals)
        metrics[f'gap_{metric}'] = np.mean(train_vals) - np.mean(val_vals)

    return metrics

def ensemble_simple_average(oof_preds):
    """Simple average ensemble"""
    preds_array = np.array(list(oof_preds.values()))
    return np.mean(preds_array, axis=0)

def ensemble_weighted_average(oof_preds, weights):
    """Weighted average ensemble"""
    preds_array = np.array(list(oof_preds.values()))
    weights_array = np.array(weights)
    weights_array = weights_array / weights_array.sum()
    return np.average(preds_array, axis=0, weights=weights_array)

def compute_diversity_metrics(oof_preds):
    """Compute diversity-related metrics"""
    models = list(oof_preds.keys())
    n = len(models)

    # Pairwise correlations
    corr_matrix = np.zeros((n, n))
    for i, m1 in enumerate(models):
        for j, m2 in enumerate(models):
            if i == j:
                corr_matrix[i, j] = 1.0
            else:
                corr, _ = spearmanr(oof_preds[m1], oof_preds[m2])
                corr_matrix[i, j] = corr

    # Average pairwise correlation
    avg_corr = (corr_matrix.sum() - n) / (n * (n - 1))
    diversity = 1 - avg_corr

    return {
        'corr_matrix': corr_matrix,
        'avg_corr': avg_corr,
        'diversity': diversity,
        'models': models
    }

def compute_error_overlap(oof_preds, y_true, top_pct=10):
    """Compute error overlap"""
    n_samples = len(y_true)
    top_n = int(n_samples * top_pct / 100)

    errors = {}
    for model, pred in oof_preds.items():
        errors[model] = np.abs(pred - y_true)

    top_error_indices = {}
    for model, err in errors.items():
        top_indices = np.argsort(err)[-top_n:]
        top_error_indices[model] = set(top_indices)

    all_models = list(oof_preds.keys())
    overlap_set = top_error_indices[all_models[0]]
    for model in all_models[1:]:
        overlap_set = overlap_set.intersection(top_error_indices[model])

    overlap_rate = len(overlap_set) / top_n * 100

    partial_overlap_count = 0
    for i in range(n_samples):
        count = sum(1 for model in all_models if i in top_error_indices[model])
        if count >= 2:
            partial_overlap_count += 1

    partial_overlap_rate = partial_overlap_count / n_samples * 100

    return {
        'full_overlap_rate': overlap_rate,
        'partial_overlap_rate': partial_overlap_rate,
        'n_full_overlap': len(overlap_set),
        'n_partial_overlap': partial_overlap_count
    }

def compute_consensus_score(oof_preds):
    """Compute prediction consensus"""
    ranks = {}
    for model, pred in oof_preds.items():
        ranks[model] = rankdata(-pred, method='average')

    models = list(oof_preds.keys())
    n_models = len(models)

    rank_corrs = []
    for i in range(n_models):
        for j in range(i+1, n_models):
            corr, _ = spearmanr(ranks[models[i]], ranks[models[j]])
            rank_corrs.append(corr)

    avg_rank_corr = np.mean(rank_corrs)

    rank_matrix = np.array([ranks[m] for m in models])
    rank_std = np.std(rank_matrix, axis=0)
    avg_rank_std = np.mean(rank_std)

    return {
        'avg_rank_correlation': avg_rank_corr,
        'avg_rank_std': avg_rank_std
    }

def compute_improvement_rates(oof_preds, y_true, ensemble_pred):
    """Compute improvement rate for each model"""
    ensemble_metrics = calculate_metrics(y_true, ensemble_pred)

    improvement_rates = {}
    for model, pred in oof_preds.items():
        model_metrics = calculate_metrics(y_true, pred)
        improvement = (ensemble_metrics['spearman'] - model_metrics['spearman']) / model_metrics['spearman'] * 100
        improvement_rates[model] = {
            'model_spearman': model_metrics['spearman'],
            'improvement_pct': improvement
        }

    return improvement_rates

def run_full_ensemble_analysis():
    """Run complete ensemble analysis"""

    base_dir = Path(__file__).parent
    results_dir = base_dir / "results"
    data_dir = base_dir / "data"

    y_train = np.load(data_dir / "y_train.npy")

    combinations = {
        '2A': {
            'Protocol_WCF': ['WideDeep', 'CrossAttention', 'FlatMLP'],
            'Diversity': ['XGBoost', 'FTTransformer', 'ExtraTrees'],
            'ML+DL_Mix': ['RandomForest', 'ResidualMLP', 'TabNet']
        },
        '2B': {
            'Protocol_FRC': ['FlatMLP', 'ResidualMLP', 'CrossAttention'],
            'Diversity': ['XGBoost', 'FTTransformer', 'ExtraTrees'],
            'ML+DL_Mix': ['RandomForest', 'ResidualMLP', 'TabNet']
        },
        '2C': {
            'Protocol_FRC': ['FlatMLP', 'ResidualMLP', 'CrossAttention'],
            'Protocol_FWC': ['FlatMLP', 'WideDeep', 'CrossAttention'],
            'Diversity': ['XGBoost', 'FTTransformer', 'ExtraTrees'],
            'ML+DL_Mix': ['RandomForest', 'ResidualMLP', 'TabNet']
        }
    }

    all_results = []

    for phase in ['2A', '2B', '2C']:
        for combo_name, models in combinations[phase].items():
            # Load OOF predictions
            oof_preds = load_oof_predictions(results_dir, phase, models)

            # Load individual model metrics
            individual_metrics = {}
            for model in models:
                individual_metrics[model] = load_single_model_metrics(results_dir, phase, model)

            # Find best single model
            best_single = max(individual_metrics.items(),
                            key=lambda x: x[1]['val_spearman'])
            best_model_name = best_single[0]
            best_model_metrics = best_single[1]

            # Compute diversity metrics
            diversity_info = compute_diversity_metrics(oof_preds)

            # Simple Average
            ensemble_pred_simple = ensemble_simple_average(oof_preds)
            ensemble_metrics_simple = calculate_metrics(y_train, ensemble_pred_simple)
            improvement_simple = compute_improvement_rates(oof_preds, y_train, ensemble_pred_simple)
            error_overlap_simple = compute_error_overlap(oof_preds, y_train, top_pct=10)
            consensus_simple = compute_consensus_score(oof_preds)

            gain_simple = ensemble_metrics_simple['spearman'] - best_model_metrics['val_spearman']

            result_simple = {
                'Phase': phase,
                'Combination': combo_name,
                'Models': ' + '.join(models),
                'Method': 'Simple',
                'Val_Spearman': ensemble_metrics_simple['spearman'],
                'Val_Pearson': ensemble_metrics_simple['pearson'],
                'Val_R2': ensemble_metrics_simple['r2'],
                'Val_RMSE': ensemble_metrics_simple['rmse'],
                'Val_MAE': ensemble_metrics_simple['mae'],
                'Val_Kendall': ensemble_metrics_simple['kendall_tau'],
                'Best_Single_Model': best_model_name,
                'Best_Single_Spearman': best_model_metrics['val_spearman'],
                'Best_Single_Gap': best_model_metrics['gap_spearman'],
                'Ensemble_Gain': gain_simple,
                'Diversity': diversity_info['diversity'],
                'Avg_Corr': diversity_info['avg_corr'],
                'Error_Overlap': error_overlap_simple['full_overlap_rate'],
                'Partial_Overlap': error_overlap_simple['partial_overlap_rate'],
                'Consensus': consensus_simple['avg_rank_correlation'],
                'Rank_Std': consensus_simple['avg_rank_std'],
                'Individual_Metrics': individual_metrics,
                'Improvement_Rates': improvement_simple,
                'Corr_Matrix': diversity_info['corr_matrix'],
                'Model_Names': diversity_info['models']
            }
            all_results.append(result_simple)

            # Weighted Average (for custom combinations only)
            is_custom = combo_name in ['Diversity', 'ML+DL_Mix']

            if is_custom:
                weights = [individual_metrics[m]['val_spearman'] for m in models]
                ensemble_pred_weighted = ensemble_weighted_average(oof_preds, weights)
                ensemble_metrics_weighted = calculate_metrics(y_train, ensemble_pred_weighted)
                improvement_weighted = compute_improvement_rates(oof_preds, y_train, ensemble_pred_weighted)
                error_overlap_weighted = compute_error_overlap(oof_preds, y_train, top_pct=10)
                consensus_weighted = compute_consensus_score(oof_preds)

                gain_weighted = ensemble_metrics_weighted['spearman'] - best_model_metrics['val_spearman']

                result_weighted = {
                    'Phase': phase,
                    'Combination': combo_name,
                    'Models': ' + '.join(models),
                    'Method': 'Weighted',
                    'Val_Spearman': ensemble_metrics_weighted['spearman'],
                    'Val_Pearson': ensemble_metrics_weighted['pearson'],
                    'Val_R2': ensemble_metrics_weighted['r2'],
                    'Val_RMSE': ensemble_metrics_weighted['rmse'],
                    'Val_MAE': ensemble_metrics_weighted['mae'],
                    'Val_Kendall': ensemble_metrics_weighted['kendall_tau'],
                    'Best_Single_Model': best_model_name,
                    'Best_Single_Spearman': best_model_metrics['val_spearman'],
                    'Best_Single_Gap': best_model_metrics['gap_spearman'],
                    'Ensemble_Gain': gain_weighted,
                    'Diversity': diversity_info['diversity'],
                    'Avg_Corr': diversity_info['avg_corr'],
                    'Error_Overlap': error_overlap_weighted['full_overlap_rate'],
                    'Partial_Overlap': error_overlap_weighted['partial_overlap_rate'],
                    'Consensus': consensus_weighted['avg_rank_correlation'],
                    'Rank_Std': consensus_weighted['avg_rank_std'],
                    'Individual_Metrics': individual_metrics,
                    'Improvement_Rates': improvement_weighted,
                    'Corr_Matrix': diversity_info['corr_matrix'],
                    'Model_Names': diversity_info['models']
                }
                all_results.append(result_weighted)

    return all_results

def print_table1_full_comparison(all_results):
    """1. 전체 앙상블 비교표"""
    print("\n" + "="*200)
    print("1. 전체 앙상블 비교표 (16개 실험)")
    print("="*200)

    df = pd.DataFrame(all_results)
    df['Rank'] = df['Val_Spearman'].rank(ascending=False, method='min')
    df = df.sort_values('Val_Spearman', ascending=False).reset_index(drop=True)

    print(f"\n{'Rank':<5} {'Phase':<7} {'Combo':<20} {'Method':<8} | "
          f"{'Spearman':>10} {'Pearson':>10} {'R²':>10} {'RMSE':>10} {'MAE':>10} {'Kendall':>10} | "
          f"{'Gain':>10} {'Gain%':>8}")
    print("-"*200)

    for _, row in df.iterrows():
        gain_pct = (row['Ensemble_Gain'] / row['Best_Single_Spearman']) * 100
        print(f"{int(row['Rank']):<5} {row['Phase']:<7} {row['Combination']:<20} {row['Method']:<8} | "
              f"{row['Val_Spearman']:10.4f} {row['Val_Pearson']:10.4f} {row['Val_R2']:10.4f} "
              f"{row['Val_RMSE']:10.4f} {row['Val_MAE']:10.4f} {row['Val_Kendall']:10.4f} | "
              f"{row['Ensemble_Gain']:+10.4f} {gain_pct:+7.2f}%")

def print_table2_ensemble_metrics(all_results):
    """2. 앙상블 전용 지표 전체"""
    print("\n" + "="*200)
    print("2. 앙상블 전용 지표 전체")
    print("="*200)

    df = pd.DataFrame(all_results)
    df['Rank'] = df['Val_Spearman'].rank(ascending=False, method='min')
    df = df.sort_values('Val_Spearman', ascending=False)

    print(f"\n{'Rank':<5} {'Phase':<7} {'Combo':<20} {'Method':<8} | "
          f"{'Diversity':>10} {'AvgCorr':>10} {'ErrOvlp%':>10} {'PartOvlp%':>10} {'Consensus':>10} {'RankStd':>10}")
    print("-"*180)

    for idx, row in df.iterrows():
        print(f"{int(row['Rank']):<5} {row['Phase']:<7} {row['Combination']:<20} {row['Method']:<8} | "
              f"{row['Diversity']:10.4f} {row['Avg_Corr']:10.4f} {row['Error_Overlap']:9.2f}% "
              f"{row['Partial_Overlap']:9.2f}% {row['Consensus']:10.4f} {row['Rank_Std']:10.2f}")

    # Show correlation matrices for top 3
    print("\n" + "="*200)
    print("조합 내 모델별 OOF 상관 행렬 (Top 3 앙상블)")
    print("="*200)

    for idx, row in df.head(3).iterrows():
        print(f"\n[{int(row['Rank'])}위] "
              f"{row['Phase']} - {row['Combination']} ({row['Method']})")
        print(f"  구성: {row['Models']}")

        models = row['Model_Names']
        corr_matrix = row['Corr_Matrix']

        print(f"\n  {'Model':<20} | ", end='')
        for m in models:
            print(f"{m[:10]:>10} ", end='')
        print()
        print(f"  {'-'*80}")

        for i, m1 in enumerate(models):
            print(f"  {m1:<20} | ", end='')
            for j, m2 in enumerate(models):
                if i == j:
                    print(f"{'1.0000':>10} ", end='')
                else:
                    print(f"{corr_matrix[i, j]:10.4f} ", end='')
            print()

def print_table3_improvement_rates(all_results):
    """3. 개별 모델 대비 개선율 전체"""
    print("\n" + "="*200)
    print("3. 개별 모델 대비 개선율 전체 (16개 앙상블)")
    print("="*200)

    df = pd.DataFrame(all_results)
    df['Rank'] = df['Val_Spearman'].rank(ascending=False, method='min')
    df = df.sort_values('Val_Spearman', ascending=False)

    for idx, row in df.iterrows():
        print(f"\n[{int(row['Rank'])}위] {row['Phase']} - {row['Combination']} ({row['Method']})")
        print(f"  Ensemble: {row['Val_Spearman']:.4f}, Gain: {row['Ensemble_Gain']:+.4f}")

        imp_rates = row['Improvement_Rates']
        improvements = [(m, imp['improvement_pct']) for m, imp in imp_rates.items()]
        improvements.sort(key=lambda x: x[1], reverse=True)

        print(f"  개별 모델 개선율:")
        for model, imp_pct in improvements:
            print(f"    {model:<20}: {imp_rates[model]['model_spearman']:.4f} → {imp_pct:+7.2f}%")

        best_imp = max(improvements, key=lambda x: x[1])
        worst_imp = min(improvements, key=lambda x: x[1])
        print(f"  → 최고 개선: {best_imp[0]} ({best_imp[1]:+.2f}%)")
        print(f"  → 최저 개선: {worst_imp[0]} ({worst_imp[1]:+.2f}%)")

def print_table4_gap_analysis(all_results):
    """4. Gap 변화 분석"""
    print("\n" + "="*200)
    print("4. Gap 변화 분석 (앙상블 vs 단일 최고 모델)")
    print("="*200)
    print("\n주의: 앙상블은 Train 예측이 없으므로 Gap을 직접 계산할 수 없습니다.")
    print("      대신 조합 내 최고 단일 모델의 Gap과 비교하여 일반화 능력을 추정합니다.\n")

    df = pd.DataFrame(all_results)
    df['Rank'] = df['Val_Spearman'].rank(ascending=False, method='min')
    df = df.sort_values('Val_Spearman', ascending=False)

    print(f"{'Rank':<5} {'Phase':<7} {'Combo':<20} {'Method':<8} | "
          f"{'Best Model':<20} {'Best Gap':>10} | {'Ens Spr':>10} | {'Gap 추정':>12}")
    print("-"*160)

    for idx, row in df.iterrows():
        rank = int(row['Rank'])

        # Gap estimation: if ensemble performs better than best single,
        # it likely has smaller gap (better generalization)
        gap_estimate = "개선 예상" if row['Ensemble_Gain'] > 0 else "악화 예상"

        print(f"{rank:<5} {row['Phase']:<7} {row['Combination']:<20} {row['Method']:<8} | "
              f"{row['Best_Single_Model']:<20} {row['Best_Single_Gap']:10.4f} | "
              f"{row['Val_Spearman']:10.4f} | {gap_estimate:>12}")

    print("\n해석:")
    print("  - Ensemble Gain > 0 → Gap 개선 예상 (앙상블이 과적합 완화)")
    print("  - Ensemble Gain < 0 → Gap 악화 예상 (앙상블 효과 없음)")

def print_table5_positive_gain_detail(all_results):
    """5. 양수 Gain 앙상블 상세"""
    print("\n" + "="*200)
    print("5. 양수 Gain 앙상블 상세 (6개)")
    print("="*200)

    df = pd.DataFrame(all_results)
    df['Rank'] = df['Val_Spearman'].rank(ascending=False, method='min')
    positive_gain = df[df['Ensemble_Gain'] > 0].sort_values('Ensemble_Gain', ascending=False)

    print(f"\n총 {len(positive_gain)}개 앙상블이 양수 Gain을 보였습니다.\n")

    for idx, row in positive_gain.iterrows():
        rank = int(row['Rank'])

        print(f"\n{'='*180}")
        print(f"[{rank}위] {row['Phase']} - {row['Combination']} ({row['Method']})")
        print(f"{'='*180}")

        print(f"\n구성: {row['Models']}")

        print(f"\n[앙상블 성능]")
        print(f"  Spearman: {row['Val_Spearman']:.4f}")
        print(f"  Pearson:  {row['Val_Pearson']:.4f}")
        print(f"  R²:       {row['Val_R2']:.4f}")
        print(f"  RMSE:     {row['Val_RMSE']:.4f}")
        print(f"  MAE:      {row['Val_MAE']:.4f}")
        print(f"  Kendall:  {row['Val_Kendall']:.4f}")

        print(f"\n[앙상블 효과]")
        print(f"  Ensemble Gain: {row['Ensemble_Gain']:+.4f} ({row['Ensemble_Gain']/row['Best_Single_Spearman']*100:+.2f}%)")
        print(f"  Best Single: {row['Best_Single_Model']} ({row['Best_Single_Spearman']:.4f})")

        print(f"\n[다양성 지표]")
        print(f"  Diversity: {row['Diversity']:.4f}")
        print(f"  Avg Corr: {row['Avg_Corr']:.4f}")
        print(f"  Error Overlap: {row['Error_Overlap']:.2f}%")
        print(f"  Consensus: {row['Consensus']:.4f}")

        print(f"\n[조합 내 모델별 성능]")
        print(f"  {'Model':<20} | {'Val Spr':>10} {'Train Spr':>10} {'Gap':>10} | {'Improvement':>12}")
        print(f"  {'-'*80}")

        for model, metrics in row['Individual_Metrics'].items():
            imp = row['Improvement_Rates'][model]['improvement_pct']
            print(f"  {model:<20} | {metrics['val_spearman']:10.4f} {metrics['train_spearman']:10.4f} "
                  f"{metrics['gap_spearman']:10.4f} | {imp:+11.2f}%")

def print_table6_protocol_vs_custom(all_results):
    """6. 프로토콜 vs 커스텀 비교"""
    print("\n" + "="*200)
    print("6. 프로토콜 조합 vs 커스텀 조합 비교")
    print("="*200)

    df = pd.DataFrame(all_results)

    protocol_combos = ['Protocol_WCF', 'Protocol_FRC', 'Protocol_FWC']
    custom_combos = ['Diversity', 'ML+DL_Mix']

    for phase in ['2A', '2B', '2C']:
        print(f"\n{'='*180}")
        print(f"Phase {phase}")
        print(f"{'='*180}")

        df_phase = df[df['Phase'] == phase]

        # Protocol results
        print(f"\n[프로토콜 조합]")
        df_protocol = df_phase[df_phase['Combination'].isin(protocol_combos)]

        if len(df_protocol) > 0:
            print(f"{'Combo':<20} {'Method':<8} | {'Spearman':>10} {'Gain':>10} | {'Diversity':>10} {'Consensus':>10}")
            print("-"*100)

            for _, row in df_protocol.iterrows():
                print(f"{row['Combination']:<20} {row['Method']:<8} | "
                      f"{row['Val_Spearman']:10.4f} {row['Ensemble_Gain']:+10.4f} | "
                      f"{row['Diversity']:10.4f} {row['Consensus']:10.4f}")

        # Custom results
        print(f"\n[커스텀 조합]")
        df_custom = df_phase[df_phase['Combination'].isin(custom_combos)]

        if len(df_custom) > 0:
            print(f"{'Combo':<20} {'Method':<8} | {'Spearman':>10} {'Gain':>10} | {'Diversity':>10} {'Consensus':>10}")
            print("-"*100)

            for _, row in df_custom.iterrows():
                print(f"{row['Combination']:<20} {row['Method']:<8} | "
                      f"{row['Val_Spearman']:10.4f} {row['Ensemble_Gain']:+10.4f} | "
                      f"{row['Diversity']:10.4f} {row['Consensus']:10.4f}")

        # Comparison
        if len(df_protocol) > 0 and len(df_custom) > 0:
            best_protocol = df_protocol.loc[df_protocol['Val_Spearman'].idxmax()]
            best_custom = df_custom.loc[df_custom['Val_Spearman'].idxmax()]

            print(f"\n{phase} 최고:")
            print(f"  프로토콜: {best_protocol['Combination']} ({best_protocol['Method']}) - {best_protocol['Val_Spearman']:.4f}")
            print(f"  커스텀:   {best_custom['Combination']} ({best_custom['Method']}) - {best_custom['Val_Spearman']:.4f}")

            if best_custom['Val_Spearman'] > best_protocol['Val_Spearman']:
                diff = best_custom['Val_Spearman'] - best_protocol['Val_Spearman']
                print(f"  → 커스텀 우세 (+{diff:.4f})")
            else:
                diff = best_protocol['Val_Spearman'] - best_custom['Val_Spearman']
                print(f"  → 프로토콜 우세 (+{diff:.4f})")

def print_table7_final_ranking(all_results, results_dir):
    """7. 최종 순위표 (단일 모델 Top5 + 앙상블 Top5)"""
    print("\n" + "="*200)
    print("7. 최종 통합 순위표 - 단일 모델 Top 5 + 앙상블 Top 5")
    print("="*200)

    # Load single model results
    single_models = []

    for phase in ['2A', '2B', '2C']:
        phase_stems = {
            '2A': {'ml': 'choi_numeric_ml_v1', 'dl': 'choi_numeric_dl_v1'},
            '2B': {'ml': 'choi_numeric_smiles_ml_v1', 'dl': 'choi_numeric_smiles_dl_v1'},
            '2C': {'ml': 'choi_numeric_context_smiles_ml_v1', 'dl': 'choi_numeric_context_smiles_dl_v1'}
        }

        for model_type in ['ml', 'dl']:
            result_file = results_dir / f"{phase_stems[phase][model_type]}_groupcv.json"

            with open(result_file) as f:
                results = json.load(f)

            for model_name, model_data in results.items():
                fold_results = model_data['fold_results']
                val_spearman = np.mean([f['val']['spearman'] for f in fold_results])
                train_spearman = np.mean([f['train']['spearman'] for f in fold_results])
                gap = train_spearman - val_spearman

                single_models.append({
                    'Type': 'Single',
                    'Phase': phase,
                    'Model': f"{model_type.upper()}:{model_name}",
                    'Val_Spearman': val_spearman,
                    'Gap': gap
                })

    # Get ensemble results
    df_ensemble = pd.DataFrame(all_results)
    df_ensemble['Type'] = 'Ensemble'
    df_ensemble['Model'] = df_ensemble['Combination'] + ' (' + df_ensemble['Method'] + ')'
    df_ensemble['Gap'] = None  # Ensembles don't have train predictions

    # Combine
    df_single = pd.DataFrame(single_models)

    # Select top 5 from each
    top5_single = df_single.nlargest(5, 'Val_Spearman')
    top5_ensemble = df_ensemble.nlargest(5, 'Val_Spearman')

    print(f"\n{'='*180}")
    print("단일 모델 Top 5")
    print(f"{'='*180}")
    print(f"{'Rank':<5} {'Phase':<7} {'Model':<40} | {'Val Spearman':>12} {'Gap':>10}")
    print("-"*100)

    for rank, (_, row) in enumerate(top5_single.iterrows(), 1):
        print(f"{rank:<5} {row['Phase']:<7} {row['Model']:<40} | {row['Val_Spearman']:12.4f} {row['Gap']:10.4f}")

    print(f"\n{'='*180}")
    print("앙상블 Top 5")
    print(f"{'='*180}")
    print(f"{'Rank':<5} {'Phase':<7} {'Model':<50} | {'Val Spearman':>12} {'Gain':>10}")
    print("-"*110)

    for rank, (_, row) in enumerate(top5_ensemble.iterrows(), 1):
        print(f"{rank:<5} {row['Phase']:<7} {row['Model']:<50} | {row['Val_Spearman']:12.4f} {row['Ensemble_Gain']:+10.4f}")

    # Overall best
    print(f"\n{'='*180}")
    print("전체 최고")
    print(f"{'='*180}")

    best_single = df_single.loc[df_single['Val_Spearman'].idxmax()]
    best_ensemble = df_ensemble.loc[df_ensemble['Val_Spearman'].idxmax()]

    print(f"\n🥇 단일 모델 최고:")
    print(f"   {best_single['Phase']} - {best_single['Model']}")
    print(f"   Val Spearman: {best_single['Val_Spearman']:.4f}")
    print(f"   Gap: {best_single['Gap']:.4f}")

    print(f"\n🥇 앙상블 최고:")
    print(f"   {best_ensemble['Phase']} - {best_ensemble['Model']}")
    print(f"   Val Spearman: {best_ensemble['Val_Spearman']:.4f}")
    print(f"   Ensemble Gain: {best_ensemble['Ensemble_Gain']:+.4f}")

    if best_single['Val_Spearman'] > best_ensemble['Val_Spearman']:
        diff = best_single['Val_Spearman'] - best_ensemble['Val_Spearman']
        print(f"\n✅ 결론: 단일 모델이 앙상블보다 {diff:.4f} 더 우수")
        print(f"   → 최종 추천: {best_single['Phase']} - {best_single['Model']}")
    else:
        diff = best_ensemble['Val_Spearman'] - best_single['Val_Spearman']
        print(f"\n✅ 결론: 앙상블이 단일 모델보다 {diff:.4f} 더 우수")
        print(f"   → 최종 추천: {best_ensemble['Phase']} - {best_ensemble['Model']}")

def main():
    base_dir = Path(__file__).parent
    results_dir = base_dir / "results"

    print("="*200)
    print("Phase 3 앙상블 종합 비교 분석 - 대시보드용 완전판")
    print("="*200)

    # Run full analysis
    all_results = run_full_ensemble_analysis()

    # Print all tables
    print_table1_full_comparison(all_results)
    print_table2_ensemble_metrics(all_results)
    print_table3_improvement_rates(all_results)
    print_table4_gap_analysis(all_results)
    print_table5_positive_gain_detail(all_results)
    print_table6_protocol_vs_custom(all_results)
    print_table7_final_ranking(all_results, results_dir)

    print("\n" + "="*200)
    print("전체 분석 완료!")
    print("="*200)

if __name__ == "__main__":
    main()
