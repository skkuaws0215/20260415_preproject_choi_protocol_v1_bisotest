"""
양수 Gain 앙상블 6개 과적합 분석
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
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
    """Load single model train and val metrics"""
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

    train_spearmans = [f['train']['spearman'] for f in fold_results]
    val_spearmans = [f['val']['spearman'] for f in fold_results]

    return {
        'train_spearman': np.mean(train_spearmans),
        'val_spearman': np.mean(val_spearmans),
        'gap': np.mean(train_spearmans) - np.mean(val_spearmans)
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

def analyze_overfitting():
    """Analyze overfitting for positive gain ensembles"""

    base_dir = Path(__file__).parent
    results_dir = base_dir / "results"
    data_dir = base_dir / "data"

    y_train = np.load(data_dir / "y_train.npy")

    print("="*200)
    print("양수 Gain 앙상블 6개 과적합 분석")
    print("="*200)

    # Positive gain ensembles (from previous analysis)
    positive_ensembles = [
        ('2A', 'Diversity', ['XGBoost', 'FTTransformer', 'ExtraTrees'], 'Weighted'),
        ('2A', 'Diversity', ['XGBoost', 'FTTransformer', 'ExtraTrees'], 'Simple'),
        ('2A', 'ML+DL_Mix', ['RandomForest', 'ResidualMLP', 'TabNet'], 'Weighted'),
        ('2A', 'ML+DL_Mix', ['RandomForest', 'ResidualMLP', 'TabNet'], 'Simple'),
        ('2C', 'ML+DL_Mix', ['RandomForest', 'ResidualMLP', 'TabNet'], 'Weighted'),
        ('2C', 'ML+DL_Mix', ['RandomForest', 'ResidualMLP', 'TabNet'], 'Simple'),
    ]

    results = []

    print("\n주의: 앙상블 Train 예측은 저장되어 있지 않으므로,")
    print("      각 모델의 Train Spearman을 가중 평균하여 추정합니다.")
    print("      이는 근사치이며, 실제값과 다를 수 있습니다.\n")

    for phase, combo_name, models, method in positive_ensembles:
        print(f"\n{'='*180}")
        print(f"[{phase} - {combo_name} ({method})]")
        print(f"구성: {' + '.join(models)}")
        print(f"{'='*180}")

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

        # Compute ensemble val spearman
        if method == 'Simple':
            ensemble_pred = ensemble_simple_average(oof_preds)
        else:  # Weighted
            weights = [individual_metrics[m]['val_spearman'] for m in models]
            ensemble_pred = ensemble_weighted_average(oof_preds, weights)

        ensemble_val_metrics = calculate_metrics(y_train, ensemble_pred)
        ensemble_val_spearman = ensemble_val_metrics['spearman']

        # Estimate ensemble train spearman
        # Method 1: Simple average of train spearmans
        if method == 'Simple':
            ensemble_train_spearman_est = np.mean([m['train_spearman'] for m in individual_metrics.values()])
        else:  # Weighted
            weights = [individual_metrics[m]['val_spearman'] for m in models]
            weights_array = np.array(weights)
            weights_array = weights_array / weights_array.sum()
            ensemble_train_spearman_est = np.average(
                [individual_metrics[m]['train_spearman'] for m in models],
                weights=weights_array
            )

        # Compute ensemble gap (estimated)
        ensemble_gap_est = ensemble_train_spearman_est - ensemble_val_spearman

        # Gap comparison
        gap_reduction = best_model_metrics['gap'] - ensemble_gap_est
        gap_reduction_pct = (gap_reduction / best_model_metrics['gap']) * 100

        print(f"\n[개별 모델 성능]")
        print(f"{'Model':<20} | {'Train Sp':>10} {'Val Sp':>10} {'Gap':>10}")
        print("-"*60)
        for model in models:
            m = individual_metrics[model]
            print(f"{model:<20} | {m['train_spearman']:10.4f} {m['val_spearman']:10.4f} {m['gap']:10.4f}")

        print(f"\n[앙상블 성능 (추정)]")
        print(f"  Train Spearman (est): {ensemble_train_spearman_est:.4f}")
        print(f"  Val Spearman:         {ensemble_val_spearman:.4f}")
        print(f"  Gap (est):            {ensemble_gap_est:.4f}")

        print(f"\n[최고 단일 모델 vs 앙상블]")
        print(f"  Best Single: {best_model_name}")
        print(f"    Train Sp: {best_model_metrics['train_spearman']:.4f}")
        print(f"    Val Sp:   {best_model_metrics['val_spearman']:.4f}")
        print(f"    Gap:      {best_model_metrics['gap']:.4f}")
        print(f"\n  Ensemble (est):")
        print(f"    Train Sp: {ensemble_train_spearman_est:.4f}")
        print(f"    Val Sp:   {ensemble_val_spearman:.4f}")
        print(f"    Gap:      {ensemble_gap_est:.4f}")

        print(f"\n[Gap 변화]")
        print(f"  Gap 감소: {gap_reduction:+.4f} ({gap_reduction_pct:+.2f}%)")

        if gap_reduction > 0:
            print(f"  ✅ 앙상블이 과적합을 완화했습니다 (Gap 감소)")
        elif gap_reduction < 0:
            print(f"  ❌ 앙상블이 과적합을 악화시켰습니다 (Gap 증가)")
        else:
            print(f"  ➖ Gap 변화 없음")

        # Store results
        results.append({
            'Phase': phase,
            'Combination': combo_name,
            'Method': method,
            'Ensemble_Train_Sp_Est': ensemble_train_spearman_est,
            'Ensemble_Val_Sp': ensemble_val_spearman,
            'Ensemble_Gap_Est': ensemble_gap_est,
            'Best_Single_Model': best_model_name,
            'Best_Single_Train_Sp': best_model_metrics['train_spearman'],
            'Best_Single_Val_Sp': best_model_metrics['val_spearman'],
            'Best_Single_Gap': best_model_metrics['gap'],
            'Gap_Reduction': gap_reduction,
            'Gap_Reduction_Pct': gap_reduction_pct,
            'Individual_Metrics': individual_metrics
        })

    return results

def print_comparison_table(results):
    """Print comprehensive comparison table"""

    print("\n" + "="*200)
    print("양수 Gain 앙상블 과적합 비교표")
    print("="*200)

    # Table 1: Main comparison
    print("\n" + "="*200)
    print("1. 앙상블 vs 최고 단일 모델 Gap 비교")
    print("="*200)

    print(f"\n{'Phase':<7} {'Combo':<15} {'Method':<8} | "
          f"{'Ens Train':>10} {'Ens Val':>10} {'Ens Gap':>10} | "
          f"{'Best Model':<20} {'Best Gap':>10} | {'Gap 감소':>10} {'감소율':>8}")
    print("-"*200)

    df = pd.DataFrame(results)

    for _, row in df.iterrows():
        print(f"{row['Phase']:<7} {row['Combination']:<15} {row['Method']:<8} | "
              f"{row['Ensemble_Train_Sp_Est']:10.4f} {row['Ensemble_Val_Sp']:10.4f} {row['Ensemble_Gap_Est']:10.4f} | "
              f"{row['Best_Single_Model']:<20} {row['Best_Single_Gap']:10.4f} | "
              f"{row['Gap_Reduction']:+10.4f} {row['Gap_Reduction_Pct']:+7.2f}%")

    # Table 2: Gap reduction ranking
    print("\n" + "="*200)
    print("2. Gap 감소 효과 순위")
    print("="*200)

    df_sorted = df.sort_values('Gap_Reduction', ascending=False)

    print(f"\n{'Rank':<5} {'Phase':<7} {'Combo':<15} {'Method':<8} | "
          f"{'Ens Gap':>10} {'Best Gap':>10} | {'Gap 감소':>10} {'감소율':>8}")
    print("-"*120)

    for rank, (_, row) in enumerate(df_sorted.iterrows(), 1):
        print(f"{rank:<5} {row['Phase']:<7} {row['Combination']:<15} {row['Method']:<8} | "
              f"{row['Ensemble_Gap_Est']:10.4f} {row['Best_Single_Gap']:10.4f} | "
              f"{row['Gap_Reduction']:+10.4f} {row['Gap_Reduction_Pct']:+7.2f}%")

    # Table 3: Individual model contribution
    print("\n" + "="*200)
    print("3. 조합 내 개별 모델 Gap 분포")
    print("="*200)

    for _, row in df.iterrows():
        print(f"\n{row['Phase']} - {row['Combination']} ({row['Method']})")
        print(f"{'Model':<20} | {'Train':>10} {'Val':>10} {'Gap':>10} | {'Gap vs Ens':>12}")
        print("-"*80)

        for model, metrics in row['Individual_Metrics'].items():
            gap_vs_ens = metrics['gap'] - row['Ensemble_Gap_Est']
            print(f"{model:<20} | {metrics['train_spearman']:10.4f} {metrics['val_spearman']:10.4f} "
                  f"{metrics['gap']:10.4f} | {gap_vs_ens:+12.4f}")

        avg_gap = np.mean([m['gap'] for m in row['Individual_Metrics'].values()])
        print(f"\n{'평균 Gap':<20} | {'':10} {'':10} {avg_gap:10.4f} | "
              f"{avg_gap - row['Ensemble_Gap_Est']:+12.4f}")

    # Table 4: Summary statistics
    print("\n" + "="*200)
    print("4. 종합 통계")
    print("="*200)

    print(f"\n전체 평균:")
    print(f"  앙상블 Gap (est):     {df['Ensemble_Gap_Est'].mean():.4f}")
    print(f"  최고 단일 모델 Gap:   {df['Best_Single_Gap'].mean():.4f}")
    print(f"  평균 Gap 감소:        {df['Gap_Reduction'].mean():+.4f} ({df['Gap_Reduction_Pct'].mean():+.2f}%)")

    print(f"\nGap 감소 효과:")
    print(f"  최대 Gap 감소: {df['Gap_Reduction'].max():+.4f} ({df.loc[df['Gap_Reduction'].idxmax(), 'Combination']} - "
          f"{df.loc[df['Gap_Reduction'].idxmax(), 'Phase']} - {df.loc[df['Gap_Reduction'].idxmax(), 'Method']})")
    print(f"  최소 Gap 감소: {df['Gap_Reduction'].min():+.4f} ({df.loc[df['Gap_Reduction'].idxmin(), 'Combination']} - "
          f"{df.loc[df['Gap_Reduction'].idxmin(), 'Phase']} - {df.loc[df['Gap_Reduction'].idxmin(), 'Method']})")

    n_reduced = sum(1 for x in df['Gap_Reduction'] if x > 0)
    n_increased = sum(1 for x in df['Gap_Reduction'] if x < 0)

    print(f"\n과적합 완화 성과:")
    print(f"  Gap 감소 (개선): {n_reduced}/{len(df)}")
    print(f"  Gap 증가 (악화): {n_increased}/{len(df)}")

    if n_reduced > n_increased:
        print(f"\n✅ 결론: 앙상블이 전반적으로 과적합을 완화했습니다")
    elif n_increased > n_reduced:
        print(f"\n❌ 결론: 앙상블이 전반적으로 과적합을 악화시켰습니다")
    else:
        print(f"\n➖ 결론: 앙상블의 과적합 완화 효과가 혼재되어 있습니다")

    # Table 5: Best for deployment
    print("\n" + "="*200)
    print("5. 배포용 추천 (Gap 기준)")
    print("="*200)

    best_gap_reduction = df.loc[df['Gap_Reduction'].idxmax()]

    print(f"\n최고 Gap 감소:")
    print(f"  {best_gap_reduction['Phase']} - {best_gap_reduction['Combination']} ({best_gap_reduction['Method']})")
    print(f"  앙상블 Gap (est): {best_gap_reduction['Ensemble_Gap_Est']:.4f}")
    print(f"  Gap 감소: {best_gap_reduction['Gap_Reduction']:+.4f} ({best_gap_reduction['Gap_Reduction_Pct']:+.2f}%)")
    print(f"  Val Spearman: {best_gap_reduction['Ensemble_Val_Sp']:.4f}")

    # Lowest ensemble gap
    lowest_gap = df.loc[df['Ensemble_Gap_Est'].idxmin()]

    print(f"\n최저 앙상블 Gap:")
    print(f"  {lowest_gap['Phase']} - {lowest_gap['Combination']} ({lowest_gap['Method']})")
    print(f"  앙상블 Gap (est): {lowest_gap['Ensemble_Gap_Est']:.4f}")
    print(f"  Val Spearman: {lowest_gap['Ensemble_Val_Sp']:.4f}")

def main():
    results = analyze_overfitting()
    print_comparison_table(results)

    print("\n" + "="*200)
    print("분석 완료!")
    print("="*200)

if __name__ == "__main__":
    main()
