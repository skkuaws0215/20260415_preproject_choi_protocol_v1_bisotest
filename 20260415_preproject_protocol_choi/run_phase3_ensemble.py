"""
Phase 3: 앙상블 실행
- 프로토콜 기본 조합 + 커스텀 조합
- Simple Average + Weighted Average
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import spearmanr, pearsonr, kendalltau
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
import sys

sys.path.insert(0, str(Path(__file__).parent))
from phase2_utils import calculate_metrics

def load_oof_predictions(results_dir, phase, models):
    """Load OOF predictions for specified models"""

    # Phase to directory stem mapping
    phase_stems = {
        '2A': {'ml': 'choi_numeric_ml_v1', 'dl': 'choi_numeric_dl_v1'},
        '2B': {'ml': 'choi_numeric_smiles_ml_v1', 'dl': 'choi_numeric_smiles_dl_v1'},
        '2C': {'ml': 'choi_numeric_context_smiles_ml_v1', 'dl': 'choi_numeric_context_smiles_dl_v1'}
    }

    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']

    oof_preds = {}
    for model in models:
        # Determine if ML or DL
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

def load_val_spearman(results_dir, phase, model):
    """Load GroupCV Val Spearman for a model"""

    phase_stems = {
        '2A': {'ml': 'choi_numeric_ml_v1', 'dl': 'choi_numeric_dl_v1'},
        '2B': {'ml': 'choi_numeric_smiles_ml_v1', 'dl': 'choi_numeric_smiles_dl_v1'},
        '2C': {'ml': 'choi_numeric_context_smiles_ml_v1', 'dl': 'choi_numeric_context_smiles_dl_v1'}
    }

    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']

    # Determine if ML or DL
    if model in ml_models:
        result_file = results_dir / f"{phase_stems[phase]['ml']}_groupcv.json"
    else:
        result_file = results_dir / f"{phase_stems[phase]['dl']}_groupcv.json"

    with open(result_file) as f:
        results = json.load(f)

    # Calculate average val spearman across folds
    val_spearmans = [fold['val']['spearman'] for fold in results[model]['fold_results']]
    return np.mean(val_spearmans)

def compute_oof_correlations(oof_preds):
    """Compute pairwise Spearman correlations between OOF predictions"""
    models = list(oof_preds.keys())
    n = len(models)
    corr_matrix = np.zeros((n, n))

    for i, m1 in enumerate(models):
        for j, m2 in enumerate(models):
            if i == j:
                corr_matrix[i, j] = 1.0
            else:
                corr, _ = spearmanr(oof_preds[m1], oof_preds[m2])
                corr_matrix[i, j] = corr

    return models, corr_matrix

def ensemble_simple_average(oof_preds):
    """Simple average ensemble"""
    preds_array = np.array(list(oof_preds.values()))
    return np.mean(preds_array, axis=0)

def ensemble_weighted_average(oof_preds, weights):
    """Weighted average ensemble"""
    preds_array = np.array(list(oof_preds.values()))
    weights_array = np.array(weights)
    weights_array = weights_array / weights_array.sum()  # Normalize

    return np.average(preds_array, axis=0, weights=weights_array)

def run_ensemble_combinations():
    """Run all ensemble combinations"""

    base_dir = Path(__file__).parent
    results_dir = base_dir / "results"
    data_dir = base_dir / "data"

    # Load y_train
    y_train = np.load(data_dir / "y_train.npy")

    print("="*200)
    print("Phase 3: 앙상블 실행")
    print("="*200)

    # Define combinations
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
        print(f"\n{'='*200}")
        print(f"Phase {phase} - 앙상블")
        print(f"{'='*200}\n")

        for combo_name, models in combinations[phase].items():
            print(f"\n{'-'*200}")
            print(f"조합: {combo_name} ({' + '.join(models)})")
            print(f"{'-'*200}")

            # Load OOF predictions
            oof_preds = load_oof_predictions(results_dir, phase, models)

            # Load individual model val spearmans for weights
            val_spearmans = {}
            for model in models:
                val_spearmans[model] = load_val_spearman(results_dir, phase, model)

            # Compute diversity
            model_names, corr_matrix = compute_oof_correlations(oof_preds)

            # Average pairwise correlation (excluding diagonal)
            n = len(model_names)
            avg_corr = (corr_matrix.sum() - n) / (n * (n - 1))
            diversity = 1 - avg_corr

            # Best single model in this combination
            best_single_model = max(val_spearmans.items(), key=lambda x: x[1])

            # Simple Average
            ensemble_pred_simple = ensemble_simple_average(oof_preds)
            metrics_simple = calculate_metrics(y_train, ensemble_pred_simple)

            gain_simple = metrics_simple['spearman'] - best_single_model[1]

            result_simple = {
                'Phase': phase,
                'Combination': combo_name,
                'Models': ' + '.join(models),
                'Method': 'Simple Avg',
                'Val_Spearman': metrics_simple['spearman'],
                'Val_Pearson': metrics_simple['pearson'],
                'Val_R2': metrics_simple['r2'],
                'Val_RMSE': metrics_simple['rmse'],
                'Val_MAE': metrics_simple['mae'],
                'Val_Kendall': metrics_simple['kendall_tau'],
                'Best_Single': best_single_model[1],
                'Best_Single_Model': best_single_model[0],
                'Ensemble_Gain': gain_simple,
                'Avg_Corr': avg_corr,
                'Diversity': diversity
            }
            all_results.append(result_simple)

            print(f"\n[Simple Average]")
            print(f"  Val Spearman: {metrics_simple['spearman']:.4f}")
            print(f"  Val Pearson:  {metrics_simple['pearson']:.4f}")
            print(f"  Val R²:       {metrics_simple['r2']:.4f}")
            print(f"  Val RMSE:     {metrics_simple['rmse']:.4f}")
            print(f"  Val MAE:      {metrics_simple['mae']:.4f}")
            print(f"  Val Kendall:  {metrics_simple['kendall_tau']:.4f}")
            print(f"  Best Single:  {best_single_model[0]} ({best_single_model[1]:.4f})")
            print(f"  Ensemble Gain: {gain_simple:+.4f}")
            print(f"  Diversity:    {diversity:.4f}")

            # Weighted Average (only for custom combinations)
            is_custom = combo_name in ['Diversity', 'ML+DL_Mix']

            if is_custom:
                weights = [val_spearmans[m] for m in models]
                ensemble_pred_weighted = ensemble_weighted_average(oof_preds, weights)
                metrics_weighted = calculate_metrics(y_train, ensemble_pred_weighted)

                gain_weighted = metrics_weighted['spearman'] - best_single_model[1]

                result_weighted = {
                    'Phase': phase,
                    'Combination': combo_name,
                    'Models': ' + '.join(models),
                    'Method': 'Weighted Avg',
                    'Val_Spearman': metrics_weighted['spearman'],
                    'Val_Pearson': metrics_weighted['pearson'],
                    'Val_R2': metrics_weighted['r2'],
                    'Val_RMSE': metrics_weighted['rmse'],
                    'Val_MAE': metrics_weighted['mae'],
                    'Val_Kendall': metrics_weighted['kendall_tau'],
                    'Best_Single': best_single_model[1],
                    'Best_Single_Model': best_single_model[0],
                    'Ensemble_Gain': gain_weighted,
                    'Avg_Corr': avg_corr,
                    'Diversity': diversity
                }
                all_results.append(result_weighted)

                print(f"\n[Weighted Average] (weights by Val Spearman)")
                for model in models:
                    print(f"  {model}: {val_spearmans[model]:.4f}")
                print(f"  Val Spearman: {metrics_weighted['spearman']:.4f}")
                print(f"  Val Pearson:  {metrics_weighted['pearson']:.4f}")
                print(f"  Val R²:       {metrics_weighted['r2']:.4f}")
                print(f"  Val RMSE:     {metrics_weighted['rmse']:.4f}")
                print(f"  Val MAE:      {metrics_weighted['mae']:.4f}")
                print(f"  Val Kendall:  {metrics_weighted['kendall_tau']:.4f}")
                print(f"  Ensemble Gain: {gain_weighted:+.4f}")

            # Show pairwise correlations
            print(f"\n[OOF 상관 행렬]")
            print(f"  {'Model':<20} | ", end='')
            for m in model_names:
                print(f"{m[:10]:>10} ", end='')
            print()
            print(f"  {'-'*80}")
            for i, m1 in enumerate(model_names):
                print(f"  {m1:<20} | ", end='')
                for j, m2 in enumerate(model_names):
                    if i == j:
                        print(f"{'1.0000':>10} ", end='')
                    else:
                        print(f"{corr_matrix[i, j]:>10.4f} ", end='')
                print()
            print(f"  평균 상관: {avg_corr:.4f}, Diversity: {diversity:.4f}")

    return all_results

def print_comparison_tables(all_results):
    """Print comprehensive comparison tables"""

    df = pd.DataFrame(all_results)

    print("\n" + "="*200)
    print("Phase 3 앙상블 전체 비교표")
    print("="*200)

    # Table 1: All ensembles sorted by Val Spearman
    print("\n" + "="*200)
    print("1. 전체 앙상블 성능 순위 (Val Spearman 기준)")
    print("="*200)

    df_sorted = df.sort_values('Val_Spearman', ascending=False).reset_index(drop=True)

    print(f"\n{'Rank':<5} {'Phase':<7} {'Combination':<20} {'Method':<13} | {'Spearman':>10} {'Pearson':>10} {'R²':>10} {'RMSE':>10} {'MAE':>10} | {'Gain':>10} {'Diversity':>10}")
    print("-"*200)

    for idx, row in df_sorted.iterrows():
        rank = idx + 1
        print(f"{rank:<5} {row['Phase']:<7} {row['Combination']:<20} {row['Method']:<13} | "
              f"{row['Val_Spearman']:10.4f} {row['Val_Pearson']:10.4f} {row['Val_R2']:10.4f} "
              f"{row['Val_RMSE']:10.4f} {row['Val_MAE']:10.4f} | "
              f"{row['Ensemble_Gain']:+10.4f} {row['Diversity']:10.4f}")

    # Table 2: Phase별 비교
    print("\n" + "="*200)
    print("2. Phase별 최고 앙상블")
    print("="*200)

    for phase in ['2A', '2B', '2C']:
        df_phase = df[df['Phase'] == phase].sort_values('Val_Spearman', ascending=False)
        best = df_phase.iloc[0]

        print(f"\n{phase} 최고: {best['Combination']} ({best['Method']}) - Spearman {best['Val_Spearman']:.4f} (Gain: {best['Ensemble_Gain']:+.4f})")
        print(f"  구성: {best['Models']}")
        print(f"  Best Single: {best['Best_Single_Model']} ({best['Best_Single']:.4f})")

    # Table 3: Simple vs Weighted 비교
    print("\n" + "="*200)
    print("3. Simple Average vs Weighted Average 비교 (커스텀 조합)")
    print("="*200)

    custom_combos = df[df['Combination'].isin(['Diversity', 'ML+DL_Mix'])]

    for phase in ['2A', '2B', '2C']:
        for combo in ['Diversity', 'ML+DL_Mix']:
            df_combo = custom_combos[(custom_combos['Phase'] == phase) & (custom_combos['Combination'] == combo)]

            if len(df_combo) == 2:
                simple = df_combo[df_combo['Method'] == 'Simple Avg'].iloc[0]
                weighted = df_combo[df_combo['Method'] == 'Weighted Avg'].iloc[0]

                diff = weighted['Val_Spearman'] - simple['Val_Spearman']
                winner = "Weighted" if diff > 0 else "Simple" if diff < 0 else "동일"

                print(f"\n{phase} - {combo}:")
                print(f"  Simple:   {simple['Val_Spearman']:.4f}")
                print(f"  Weighted: {weighted['Val_Spearman']:.4f}")
                print(f"  차이:     {diff:+.4f} → {winner} 우세")

    # Table 4: Ensemble Gain 분석
    print("\n" + "="*200)
    print("4. Ensemble Gain 분석")
    print("="*200)

    print(f"\n{'Phase':<7} {'Combination':<20} {'Method':<13} | {'Best Single':>12} {'Ensemble':>12} {'Gain':>12} | {'Gain %':>10}")
    print("-"*150)

    for _, row in df_sorted.iterrows():
        gain_pct = (row['Ensemble_Gain'] / row['Best_Single']) * 100
        print(f"{row['Phase']:<7} {row['Combination']:<20} {row['Method']:<13} | "
              f"{row['Best_Single']:12.4f} {row['Val_Spearman']:12.4f} {row['Ensemble_Gain']:+12.4f} | "
              f"{gain_pct:+9.2f}%")

    print(f"\n평균 Gain: {df['Ensemble_Gain'].mean():+.4f} ({(df['Ensemble_Gain'].mean() / df['Best_Single'].mean()) * 100:+.2f}%)")
    print(f"최대 Gain: {df['Ensemble_Gain'].max():+.4f} ({(df.loc[df['Ensemble_Gain'].idxmax(), 'Combination'])} - {df.loc[df['Ensemble_Gain'].idxmax(), 'Phase']} - {df.loc[df['Ensemble_Gain'].idxmax(), 'Method']})")
    print(f"최소 Gain: {df['Ensemble_Gain'].min():+.4f} ({(df.loc[df['Ensemble_Gain'].idxmin(), 'Combination'])} - {df.loc[df['Ensemble_Gain'].idxmin(), 'Phase']} - {df.loc[df['Ensemble_Gain'].idxmin(), 'Method']})")

    # Table 5: Diversity vs Performance
    print("\n" + "="*200)
    print("5. Diversity vs Performance 관계")
    print("="*200)

    print(f"\n{'Combination':<20} {'Phase':<7} {'Method':<13} | {'Diversity':>10} {'Spearman':>10} {'Gain':>10}")
    print("-"*100)

    df_div_sorted = df.sort_values('Diversity', ascending=False)
    for _, row in df_div_sorted.iterrows():
        print(f"{row['Combination']:<20} {row['Phase']:<7} {row['Method']:<13} | "
              f"{row['Diversity']:10.4f} {row['Val_Spearman']:10.4f} {row['Ensemble_Gain']:+10.4f}")

    # Correlation between diversity and gain
    corr_div_gain, _ = spearmanr(df['Diversity'], df['Ensemble_Gain'])
    print(f"\nDiversity-Gain 상관계수: {corr_div_gain:.4f}")

    # Table 6: 최종 추천
    print("\n" + "="*200)
    print("6. 최종 앙상블 추천")
    print("="*200)

    # 최고 성능
    best_overall = df_sorted.iloc[0]
    print(f"\n🥇 최고 성능 앙상블:")
    print(f"   {best_overall['Phase']} - {best_overall['Combination']} ({best_overall['Method']})")
    print(f"   구성: {best_overall['Models']}")
    print(f"   Val Spearman: {best_overall['Val_Spearman']:.4f}")
    print(f"   Ensemble Gain: {best_overall['Ensemble_Gain']:+.4f} ({(best_overall['Ensemble_Gain']/best_overall['Best_Single']*100):+.2f}%)")

    # 최고 Gain
    best_gain_idx = df['Ensemble_Gain'].idxmax()
    best_gain = df.loc[best_gain_idx]
    print(f"\n🥈 최고 Ensemble Gain:")
    print(f"   {best_gain['Phase']} - {best_gain['Combination']} ({best_gain['Method']})")
    print(f"   구성: {best_gain['Models']}")
    print(f"   Val Spearman: {best_gain['Val_Spearman']:.4f}")
    print(f"   Ensemble Gain: {best_gain['Ensemble_Gain']:+.4f} ({(best_gain['Ensemble_Gain']/best_gain['Best_Single']*100):+.2f}%)")

    # 최고 Diversity
    best_div_idx = df['Diversity'].idxmax()
    best_div = df.loc[best_div_idx]
    print(f"\n🥉 최고 Diversity:")
    print(f"   {best_div['Phase']} - {best_div['Combination']} ({best_div['Method']})")
    print(f"   구성: {best_div['Models']}")
    print(f"   Diversity: {best_div['Diversity']:.4f}")
    print(f"   Val Spearman: {best_div['Val_Spearman']:.4f}")
    print(f"   Ensemble Gain: {best_div['Ensemble_Gain']:+.4f}")

def main():
    # Run all ensembles
    all_results = run_ensemble_combinations()

    # Print comparison tables
    print_comparison_tables(all_results)

    print("\n" + "="*200)
    print("Phase 3 앙상블 완료!")
    print("="*200)

if __name__ == "__main__":
    main()
