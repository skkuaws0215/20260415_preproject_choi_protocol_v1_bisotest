"""
Phase 3: 앙상블 확장 분석 - 추가 지표
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

def load_val_spearman_and_gap(results_dir, phase, model):
    """Load GroupCV Val Spearman and Gap for a model"""
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
    val_spearmans = [f['val']['spearman'] for f in fold_results]
    train_spearmans = [f['train']['spearman'] for f in fold_results]

    avg_val = np.mean(val_spearmans)
    avg_train = np.mean(train_spearmans)
    gap = avg_train - avg_val

    return avg_val, gap

def compute_improvement_rates(oof_preds, y_true, ensemble_pred):
    """Compute improvement rate for each individual model vs ensemble"""
    improvement_rates = {}

    ensemble_metrics = calculate_metrics(y_true, ensemble_pred)

    for model, pred in oof_preds.items():
        model_metrics = calculate_metrics(y_true, pred)
        improvement = (ensemble_metrics['spearman'] - model_metrics['spearman']) / model_metrics['spearman'] * 100
        improvement_rates[model] = {
            'model_spearman': model_metrics['spearman'],
            'improvement_pct': improvement
        }

    return improvement_rates, ensemble_metrics

def compute_error_overlap(oof_preds, y_true, top_pct=10):
    """Compute error overlap - percentage of samples where all models have high error"""
    n_samples = len(y_true)
    top_n = int(n_samples * top_pct / 100)

    # Compute errors for each model
    errors = {}
    for model, pred in oof_preds.items():
        errors[model] = np.abs(pred - y_true)

    # Get top error sample indices for each model
    top_error_indices = {}
    for model, err in errors.items():
        top_indices = np.argsort(err)[-top_n:]
        top_error_indices[model] = set(top_indices)

    # Compute overlap
    all_models = list(oof_preds.keys())
    n_models = len(all_models)

    # Find samples that are in top error for all models
    overlap_set = top_error_indices[all_models[0]]
    for model in all_models[1:]:
        overlap_set = overlap_set.intersection(top_error_indices[model])

    overlap_rate = len(overlap_set) / top_n * 100

    # Find samples that are in top error for at least 2 models
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
    """Compute prediction consensus - rank agreement across models"""
    # Convert predictions to ranks
    ranks = {}
    for model, pred in oof_preds.items():
        # Higher prediction = higher rank
        ranks[model] = rankdata(-pred, method='average')  # Negative for descending

    n_samples = len(list(oof_preds.values())[0])
    models = list(oof_preds.keys())
    n_models = len(models)

    # Compute pairwise rank correlations
    rank_corrs = []
    for i in range(n_models):
        for j in range(i+1, n_models):
            corr, _ = spearmanr(ranks[models[i]], ranks[models[j]])
            rank_corrs.append(corr)

    avg_rank_corr = np.mean(rank_corrs)

    # Compute variance in ranks for each sample
    rank_matrix = np.array([ranks[m] for m in models])
    rank_std = np.std(rank_matrix, axis=0)
    avg_rank_std = np.mean(rank_std)

    # Top 10% high-confidence predictions (low rank variance)
    top_n = int(n_samples * 0.1)
    low_variance_indices = np.argsort(rank_std)[:top_n]

    # Average ensemble prediction for high-confidence samples
    ensemble_pred = np.mean([oof_preds[m] for m in models], axis=0)
    avg_pred_high_confidence = np.mean(ensemble_pred[low_variance_indices])

    return {
        'avg_rank_correlation': avg_rank_corr,
        'avg_rank_std': avg_rank_std,
        'high_confidence_avg_pred': avg_pred_high_confidence,
        'high_confidence_indices': low_variance_indices
    }

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

def run_ensemble_extended():
    """Run extended ensemble analysis with all metrics"""
    base_dir = Path(__file__).parent
    results_dir = base_dir / "results"
    data_dir = base_dir / "data"

    y_train = np.load(data_dir / "y_train.npy")

    print("="*200)
    print("Phase 3: 앙상블 확장 분석 - 전체 지표")
    print("="*200)

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

    all_extended_results = []

    for phase in ['2A', '2B', '2C']:
        print(f"\n{'='*200}")
        print(f"Phase {phase}")
        print(f"{'='*200}")

        for combo_name, models in combinations[phase].items():
            print(f"\n{'-'*200}")
            print(f"[{combo_name}] {' + '.join(models)}")
            print(f"{'-'*200}")

            # Load OOF predictions
            oof_preds = load_oof_predictions(results_dir, phase, models)

            # Load individual model metrics
            val_spearmans = {}
            gaps = {}
            for model in models:
                val_sp, gap = load_val_spearman_and_gap(results_dir, phase, model)
                val_spearmans[model] = val_sp
                gaps[model] = gap

            # Best single model
            best_single_model = max(val_spearmans.items(), key=lambda x: x[1])
            best_single_gap = gaps[best_single_model[0]]

            # Simple Average Ensemble
            ensemble_pred_simple = ensemble_simple_average(oof_preds)

            # Extended metrics
            improvement_simple, metrics_simple = compute_improvement_rates(oof_preds, y_train, ensemble_pred_simple)
            error_overlap_simple = compute_error_overlap(oof_preds, y_train, top_pct=10)
            consensus_simple = compute_consensus_score(oof_preds)

            # Diversity
            models_list = list(oof_preds.keys())
            n = len(models_list)
            corr_sum = 0
            for i in range(n):
                for j in range(i+1, n):
                    corr, _ = spearmanr(oof_preds[models_list[i]], oof_preds[models_list[j]])
                    corr_sum += corr
            avg_corr = corr_sum / (n * (n - 1) / 2)
            diversity = 1 - avg_corr

            gain_simple = metrics_simple['spearman'] - best_single_model[1]

            result_simple = {
                'Phase': phase,
                'Combination': combo_name,
                'Models': ' + '.join(models),
                'Method': 'Simple',
                'Val_Spearman': metrics_simple['spearman'],
                'Ensemble_Gain': gain_simple,
                'Diversity': diversity,
                'Error_Overlap': error_overlap_simple['full_overlap_rate'],
                'Partial_Overlap': error_overlap_simple['partial_overlap_rate'],
                'Consensus': consensus_simple['avg_rank_correlation'],
                'Rank_Std': consensus_simple['avg_rank_std'],
                'Best_Single': best_single_model[1],
                'Best_Single_Gap': best_single_gap,
                'Improvement_Rates': improvement_simple
            }
            all_extended_results.append(result_simple)

            print(f"\n[Simple Average]")
            print(f"  Ensemble Spearman: {metrics_simple['spearman']:.4f}")
            print(f"  Ensemble Gain: {gain_simple:+.4f} ({gain_simple/best_single_model[1]*100:+.2f}%)")
            print(f"\n  개별 모델 대비 개선율:")
            for model in models:
                imp = improvement_simple[model]
                print(f"    {model:<20}: {imp['model_spearman']:.4f} → {imp['improvement_pct']:+7.2f}%")
            print(f"\n  Prediction Diversity: {diversity:.4f}")
            print(f"  Error Overlap (Top 10%): {error_overlap_simple['full_overlap_rate']:.2f}% ({error_overlap_simple['n_full_overlap']}/{int(len(y_train)*0.1)} samples)")
            print(f"  Partial Error Overlap (≥2 models): {error_overlap_simple['partial_overlap_rate']:.2f}%")
            print(f"  Consensus Score (Rank Corr): {consensus_simple['avg_rank_correlation']:.4f}")
            print(f"  Avg Rank Std: {consensus_simple['avg_rank_std']:.2f}")
            print(f"\n  Best Single: {best_single_model[0]} (Spearman={best_single_model[1]:.4f}, Gap={best_single_gap:.4f})")

            # Weighted Average (for custom only)
            is_custom = combo_name in ['Diversity', 'ML+DL_Mix']

            if is_custom:
                weights = [val_spearmans[m] for m in models]
                ensemble_pred_weighted = ensemble_weighted_average(oof_preds, weights)

                improvement_weighted, metrics_weighted = compute_improvement_rates(oof_preds, y_train, ensemble_pred_weighted)
                error_overlap_weighted = compute_error_overlap(oof_preds, y_train, top_pct=10)
                consensus_weighted = compute_consensus_score(oof_preds)

                gain_weighted = metrics_weighted['spearman'] - best_single_model[1]

                result_weighted = {
                    'Phase': phase,
                    'Combination': combo_name,
                    'Models': ' + '.join(models),
                    'Method': 'Weighted',
                    'Val_Spearman': metrics_weighted['spearman'],
                    'Ensemble_Gain': gain_weighted,
                    'Diversity': diversity,
                    'Error_Overlap': error_overlap_weighted['full_overlap_rate'],
                    'Partial_Overlap': error_overlap_weighted['partial_overlap_rate'],
                    'Consensus': consensus_weighted['avg_rank_correlation'],
                    'Rank_Std': consensus_weighted['avg_rank_std'],
                    'Best_Single': best_single_model[1],
                    'Best_Single_Gap': best_single_gap,
                    'Improvement_Rates': improvement_weighted
                }
                all_extended_results.append(result_weighted)

                print(f"\n[Weighted Average]")
                print(f"  Weights: {', '.join([f'{m}={val_spearmans[m]:.4f}' for m in models])}")
                print(f"  Ensemble Spearman: {metrics_weighted['spearman']:.4f}")
                print(f"  Ensemble Gain: {gain_weighted:+.4f} ({gain_weighted/best_single_model[1]*100:+.2f}%)")
                print(f"\n  개별 모델 대비 개선율:")
                for model in models:
                    imp = improvement_weighted[model]
                    print(f"    {model:<20}: {imp['model_spearman']:.4f} → {imp['improvement_pct']:+7.2f}%")

    return all_extended_results

def print_extended_comparison_tables(all_results):
    """Print extended comparison tables"""

    print("\n" + "="*200)
    print("확장 지표 종합 비교표")
    print("="*200)

    # Table 1: Full metrics table
    print("\n" + "="*200)
    print("1. 전체 확장 메트릭 비교")
    print("="*200)

    print(f"\n{'Phase':<7} {'Combo':<20} {'Method':<8} | {'Spearman':>10} {'Gain':>10} {'Gain%':>8} | {'Diversity':>10} {'ErrOvlp':>10} {'Consensus':>10} {'RankStd':>10}")
    print("-"*200)

    df = pd.DataFrame(all_results)
    df = df.sort_values('Val_Spearman', ascending=False)

    for _, row in df.iterrows():
        gain_pct = (row['Ensemble_Gain'] / row['Best_Single']) * 100
        print(f"{row['Phase']:<7} {row['Combination']:<20} {row['Method']:<8} | "
              f"{row['Val_Spearman']:10.4f} {row['Ensemble_Gain']:+10.4f} {gain_pct:+7.2f}% | "
              f"{row['Diversity']:10.4f} {row['Error_Overlap']:9.2f}% {row['Consensus']:10.4f} {row['Rank_Std']:10.2f}")

    # Table 2: Improvement Rates Detail
    print("\n" + "="*200)
    print("2. 개별 모델 대비 개선율 상세")
    print("="*200)

    for _, row in df.head(5).iterrows():
        print(f"\n{row['Phase']} - {row['Combination']} ({row['Method']})")
        print(f"  Ensemble: {row['Val_Spearman']:.4f}, Gain: {row['Ensemble_Gain']:+.4f}")
        print(f"  개별 모델 개선:")
        for model, imp in row['Improvement_Rates'].items():
            print(f"    {model:<20}: {imp['model_spearman']:.4f} → {imp['improvement_pct']:+7.2f}%")

    # Table 3: Error Overlap Analysis
    print("\n" + "="*200)
    print("3. Error Overlap 분석 (높을수록 모델들이 같은 실수 반복)")
    print("="*200)

    df_sorted_overlap = df.sort_values('Error_Overlap', ascending=False)
    print(f"\n{'Phase':<7} {'Combo':<20} {'Method':<8} | {'Full Overlap':>12} {'Partial Overlap':>16} | {'Diversity':>10} {'Spearman':>10}")
    print("-"*120)

    for _, row in df_sorted_overlap.iterrows():
        print(f"{row['Phase']:<7} {row['Combination']:<20} {row['Method']:<8} | "
              f"{row['Error_Overlap']:11.2f}% {row['Partial_Overlap']:15.2f}% | "
              f"{row['Diversity']:10.4f} {row['Val_Spearman']:10.4f}")

    print(f"\n  상관 (Error Overlap vs Diversity): {spearmanr(df['Error_Overlap'], df['Diversity'])[0]:.4f}")
    print(f"  상관 (Error Overlap vs Spearman): {spearmanr(df['Error_Overlap'], df['Val_Spearman'])[0]:.4f}")

    # Table 4: Consensus Score Analysis
    print("\n" + "="*200)
    print("4. Consensus Score 분석 (높을수록 모델 간 예측 순위 일치)")
    print("="*200)

    df_sorted_consensus = df.sort_values('Consensus', ascending=False)
    print(f"\n{'Phase':<7} {'Combo':<20} {'Method':<8} | {'Consensus':>10} {'Rank Std':>10} | {'Diversity':>10} {'Spearman':>10}")
    print("-"*120)

    for _, row in df_sorted_consensus.iterrows():
        print(f"{row['Phase']:<7} {row['Combination']:<20} {row['Method']:<8} | "
              f"{row['Consensus']:10.4f} {row['Rank_Std']:10.2f} | "
              f"{row['Diversity']:10.4f} {row['Val_Spearman']:10.4f}")

    print(f"\n  상관 (Consensus vs Diversity): {spearmanr(df['Consensus'], df['Diversity'])[0]:.4f}")
    print(f"  상관 (Consensus vs Spearman): {spearmanr(df['Consensus'], df['Val_Spearman'])[0]:.4f}")

    # Table 5: Optimal Balance
    print("\n" + "="*200)
    print("5. 최적 균형 분석")
    print("="*200)

    # Positive gain only
    df_positive_gain = df[df['Ensemble_Gain'] > 0]

    if len(df_positive_gain) > 0:
        print(f"\n양수 Gain 앙상블 ({len(df_positive_gain)}개):")
        print(f"\n{'Phase':<7} {'Combo':<20} {'Method':<8} | {'Gain':>10} {'Diversity':>10} {'ErrOvlp':>10} {'Consensus':>10}")
        print("-"*120)

        for _, row in df_positive_gain.iterrows():
            print(f"{row['Phase']:<7} {row['Combination']:<20} {row['Method']:<8} | "
                  f"{row['Ensemble_Gain']:+10.4f} {row['Diversity']:10.4f} "
                  f"{row['Error_Overlap']:9.2f}% {row['Consensus']:10.4f}")

        print(f"\n  평균 Gain: {df_positive_gain['Ensemble_Gain'].mean():+.4f}")
        print(f"  평균 Diversity: {df_positive_gain['Diversity'].mean():.4f}")
        print(f"  평균 Error Overlap: {df_positive_gain['Error_Overlap'].mean():.2f}%")
        print(f"  평균 Consensus: {df_positive_gain['Consensus'].mean():.4f}")
    else:
        print("\n  양수 Gain을 보이는 앙상블이 없습니다.")

    # Best overall
    print(f"\n🏆 최종 추천:")
    best = df.iloc[0]
    gain_pct = (best['Ensemble_Gain'] / best['Best_Single']) * 100
    print(f"\n  {best['Phase']} - {best['Combination']} ({best['Method']})")
    print(f"  구성: {best['Models']}")
    print(f"  Val Spearman: {best['Val_Spearman']:.4f}")
    print(f"  Ensemble Gain: {best['Ensemble_Gain']:+.4f} ({gain_pct:+.2f}%)")
    print(f"  Diversity: {best['Diversity']:.4f}")
    print(f"  Error Overlap: {best['Error_Overlap']:.2f}%")
    print(f"  Consensus: {best['Consensus']:.4f}")
    print(f"  Rank Std: {best['Rank_Std']:.2f}")

def main():
    all_results = run_ensemble_extended()
    print_extended_comparison_tables(all_results)

    print("\n" + "="*200)
    print("확장 분석 완료!")
    print("="*200)

if __name__ == "__main__":
    main()
