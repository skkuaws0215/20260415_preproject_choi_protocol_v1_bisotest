"""
Phase 2A vs 2C 커스텀 앙상블 비교 분석
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import spearmanr, rankdata
import sys

sys.path.insert(0, str(Path(__file__).parent))
from phase2_utils import calculate_metrics

def load_oof_predictions(results_dir, phase, models):
    """Load OOF predictions"""
    phase_stems = {
        '2A': {'ml': 'choi_numeric_ml_v1', 'dl': 'choi_numeric_dl_v1'},
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
        oof_preds[model] = np.load(oof_file)

    return oof_preds

def load_single_model_metrics(results_dir, phase, model):
    """Load single model GroupCV metrics"""
    phase_stems = {
        '2A': {'ml': 'choi_numeric_ml_v1', 'dl': 'choi_numeric_dl_v1'},
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
    val_spearmans = [f['val']['spearman'] for f in fold_results]
    return np.mean(val_spearmans)

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

def compute_diversity(oof_preds):
    """Compute diversity metrics"""
    models = list(oof_preds.keys())
    n = len(models)

    corr_sum = 0
    for i in range(n):
        for j in range(i+1, n):
            corr, _ = spearmanr(oof_preds[models[i]], oof_preds[models[j]])
            corr_sum += corr

    avg_corr = corr_sum / (n * (n - 1) / 2)
    diversity = 1 - avg_corr
    return diversity, avg_corr

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
    return overlap_rate

def compute_consensus(oof_preds):
    """Compute consensus score"""
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
    return avg_rank_corr

def analyze_custom_ensembles():
    """Analyze custom ensembles for 2A vs 2C"""

    base_dir = Path(__file__).parent
    results_dir = base_dir / "results"
    data_dir = base_dir / "data"

    y_train = np.load(data_dir / "y_train.npy")

    print("="*180)
    print("Phase 2A vs 2C 커스텀 앙상블 비교 분석")
    print("="*180)

    combinations = {
        'Diversity': ['XGBoost', 'FTTransformer', 'ExtraTrees'],
        'ML+DL_Mix': ['RandomForest', 'ResidualMLP', 'TabNet']
    }

    all_results = []

    for combo_name, models in combinations.items():
        print(f"\n{'='*180}")
        print(f"조합: {combo_name} ({' + '.join(models)})")
        print(f"{'='*180}")

        for phase in ['2A', '2C']:
            print(f"\n{'-'*180}")
            print(f"Phase {phase}")
            print(f"{'-'*180}")

            # Load OOF predictions
            oof_preds = load_oof_predictions(results_dir, phase, models)

            # Load individual model val spearmans for weights
            val_spearmans = {}
            for model in models:
                val_spearmans[model] = load_single_model_metrics(results_dir, phase, model)

            # Best single model
            best_single = max(val_spearmans.items(), key=lambda x: x[1])
            best_model_name = best_single[0]
            best_model_spearman = best_single[1]

            # Compute metrics
            diversity, avg_corr = compute_diversity(oof_preds)
            error_overlap = compute_error_overlap(oof_preds, y_train, top_pct=10)
            consensus = compute_consensus(oof_preds)

            # Simple Average
            ensemble_pred_simple = ensemble_simple_average(oof_preds)
            metrics_simple = calculate_metrics(y_train, ensemble_pred_simple)
            gain_simple = metrics_simple['spearman'] - best_model_spearman

            print(f"\n[Simple Average]")
            print(f"  Val Spearman: {metrics_simple['spearman']:.4f}")
            print(f"  Best Single:  {best_model_name} ({best_model_spearman:.4f})")
            print(f"  Gain:         {gain_simple:+.4f} ({gain_simple/best_model_spearman*100:+.2f}%)")
            print(f"  Diversity:    {diversity:.4f}")
            print(f"  Error Overlap: {error_overlap:.2f}%")
            print(f"  Consensus:    {consensus:.4f}")

            all_results.append({
                'Combination': combo_name,
                'Phase': phase,
                'Method': 'Simple',
                'Val_Spearman': metrics_simple['spearman'],
                'Best_Single': best_model_spearman,
                'Best_Single_Model': best_model_name,
                'Gain': gain_simple,
                'Gain_Pct': gain_simple / best_model_spearman * 100,
                'Diversity': diversity,
                'Avg_Corr': avg_corr,
                'Error_Overlap': error_overlap,
                'Consensus': consensus,
                'Val_Spearmans': val_spearmans
            })

            # Weighted Average
            weights = [val_spearmans[m] for m in models]
            ensemble_pred_weighted = ensemble_weighted_average(oof_preds, weights)
            metrics_weighted = calculate_metrics(y_train, ensemble_pred_weighted)
            gain_weighted = metrics_weighted['spearman'] - best_model_spearman

            print(f"\n[Weighted Average]")
            print(f"  Weights: {', '.join([f'{m}={val_spearmans[m]:.4f}' for m in models])}")
            print(f"  Val Spearman: {metrics_weighted['spearman']:.4f}")
            print(f"  Gain:         {gain_weighted:+.4f} ({gain_weighted/best_model_spearman*100:+.2f}%)")

            all_results.append({
                'Combination': combo_name,
                'Phase': phase,
                'Method': 'Weighted',
                'Val_Spearman': metrics_weighted['spearman'],
                'Best_Single': best_model_spearman,
                'Best_Single_Model': best_model_name,
                'Gain': gain_weighted,
                'Gain_Pct': gain_weighted / best_model_spearman * 100,
                'Diversity': diversity,
                'Avg_Corr': avg_corr,
                'Error_Overlap': error_overlap,
                'Consensus': consensus,
                'Val_Spearmans': val_spearmans
            })

    return all_results

def print_comparison_tables(all_results):
    """Print comparison tables"""

    df = pd.DataFrame(all_results)

    print("\n" + "="*180)
    print("Phase 2A vs 2C 커스텀 앙상블 비교표")
    print("="*180)

    # Table 1: Side-by-side comparison
    print("\n" + "="*180)
    print("1. 전체 비교표 (2A vs 2C)")
    print("="*180)

    print(f"\n{'Combo':<15} {'Method':<8} {'Phase':<7} | {'Val Spr':>10} {'Best Sgl':>10} {'Gain':>10} {'Gain%':>8} | "
          f"{'Diversity':>10} {'AvgCorr':>10} {'ErrOvlp':>10} {'Consensus':>10}")
    print("-"*180)

    df_sorted = df.sort_values(['Combination', 'Method', 'Phase'])
    for _, row in df_sorted.iterrows():
        print(f"{row['Combination']:<15} {row['Method']:<8} {row['Phase']:<7} | "
              f"{row['Val_Spearman']:10.4f} {row['Best_Single']:10.4f} {row['Gain']:+10.4f} {row['Gain_Pct']:+7.2f}% | "
              f"{row['Diversity']:10.4f} {row['Avg_Corr']:10.4f} {row['Error_Overlap']:9.2f}% {row['Consensus']:10.4f}")

    # Table 2: Direct comparison for each combination
    print("\n" + "="*180)
    print("2. 조합별 2A vs 2C 직접 비교")
    print("="*180)

    for combo in ['Diversity', 'ML+DL_Mix']:
        print(f"\n{'-'*180}")
        print(f"[{combo}]")
        print(f"{'-'*180}")

        df_combo = df[df['Combination'] == combo]

        for method in ['Simple', 'Weighted']:
            print(f"\n{method} Average:")

            df_method = df_combo[df_combo['Method'] == method]

            row_2a = df_method[df_method['Phase'] == '2A'].iloc[0]
            row_2c = df_method[df_method['Phase'] == '2C'].iloc[0]

            print(f"\n{'Metric':<20} | {'2A':>12} {'2C':>12} | {'차이 (2C-2A)':>15} {'우세':>10}")
            print("-"*80)

            metrics = [
                ('Val Spearman', 'Val_Spearman'),
                ('Gain', 'Gain'),
                ('Diversity', 'Diversity'),
                ('Error Overlap', 'Error_Overlap'),
                ('Consensus', 'Consensus')
            ]

            for label, key in metrics:
                val_2a = row_2a[key]
                val_2c = row_2c[key]
                diff = val_2c - val_2a

                if label == 'Error Overlap':
                    # Lower is better
                    winner = '2C' if diff < 0 else '2A'
                else:
                    # Higher is better
                    winner = '2C' if diff > 0 else '2A'

                if label == 'Error Overlap':
                    print(f"{label:<20} | {val_2a:11.2f}% {val_2c:11.2f}% | {diff:+14.2f}% {winner:>10}")
                else:
                    print(f"{label:<20} | {val_2a:12.4f} {val_2c:12.4f} | {diff:+15.4f} {winner:>10}")

            # Individual model comparison
            print(f"\n개별 모델 Val Spearman:")
            print(f"{'Model':<20} | {'2A':>12} {'2C':>12} | {'차이':>12}")
            print("-"*70)

            models = list(row_2a['Val_Spearmans'].keys())
            for model in models:
                val_2a = row_2a['Val_Spearmans'][model]
                val_2c = row_2c['Val_Spearmans'][model]
                diff = val_2c - val_2a
                print(f"{model:<20} | {val_2a:12.4f} {val_2c:12.4f} | {diff:+12.4f}")

    # Table 3: Best configuration
    print("\n" + "="*180)
    print("3. 최고 성능 구성")
    print("="*180)

    best_overall = df.loc[df['Val_Spearman'].idxmax()]

    print(f"\n전체 최고:")
    print(f"  조합: {best_overall['Combination']}")
    print(f"  Phase: {best_overall['Phase']}")
    print(f"  방법: {best_overall['Method']}")
    print(f"  Val Spearman: {best_overall['Val_Spearman']:.4f}")
    print(f"  Gain: {best_overall['Gain']:+.4f} ({best_overall['Gain_Pct']:+.2f}%)")
    print(f"  Diversity: {best_overall['Diversity']:.4f}")
    print(f"  Error Overlap: {best_overall['Error_Overlap']:.2f}%")
    print(f"  Consensus: {best_overall['Consensus']:.4f}")

    # Best per combination
    print(f"\n조합별 최고:")
    for combo in ['Diversity', 'ML+DL_Mix']:
        df_combo = df[df['Combination'] == combo]
        best = df_combo.loc[df_combo['Val_Spearman'].idxmax()]

        print(f"\n  {combo}:")
        print(f"    Phase {best['Phase']} - {best['Method']}: {best['Val_Spearman']:.4f} (Gain: {best['Gain']:+.4f})")

    # 2A vs 2C summary
    print(f"\n" + "="*180)
    print("4. 2A vs 2C 종합 결과")
    print("="*180)

    df_2a = df[df['Phase'] == '2A']
    df_2c = df[df['Phase'] == '2C']

    print(f"\n평균 성능:")
    print(f"  2A - Val Spearman: {df_2a['Val_Spearman'].mean():.4f}")
    print(f"  2C - Val Spearman: {df_2c['Val_Spearman'].mean():.4f}")
    print(f"  차이: {df_2c['Val_Spearman'].mean() - df_2a['Val_Spearman'].mean():+.4f}")

    print(f"\n평균 Gain:")
    print(f"  2A: {df_2a['Gain'].mean():+.4f}")
    print(f"  2C: {df_2c['Gain'].mean():+.4f}")

    print(f"\n평균 Diversity:")
    print(f"  2A: {df_2a['Diversity'].mean():.4f}")
    print(f"  2C: {df_2c['Diversity'].mean():.4f}")

    print(f"\n평균 Error Overlap:")
    print(f"  2A: {df_2a['Error_Overlap'].mean():.2f}%")
    print(f"  2C: {df_2c['Error_Overlap'].mean():.2f}%")

    wins_2a = sum(1 for i in range(len(df_2a)) if df_2a.iloc[i]['Val_Spearman'] > df_2c.iloc[i]['Val_Spearman'])
    wins_2c = len(df_2a) - wins_2a

    print(f"\n승패:")
    print(f"  2A 승리: {wins_2a}/{len(df_2a)}")
    print(f"  2C 승리: {wins_2c}/{len(df_2c)}")

    if wins_2c > wins_2a:
        print(f"\n✅ 결론: Phase 2C (Numeric+Context+SMILES)가 2A보다 우수")
    elif wins_2a > wins_2c:
        print(f"\n✅ 결론: Phase 2A (Numeric-only)가 2C보다 우수")
    else:
        print(f"\n✅ 결론: 2A와 2C가 동등")

def main():
    all_results = analyze_custom_ensembles()
    print_comparison_tables(all_results)

    print("\n" + "="*180)
    print("분석 완료!")
    print("="*180)

if __name__ == "__main__":
    main()
