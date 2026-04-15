"""
Phase 2 전체 종합 비교 분석 - 모든 데이터 포함
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import spearmanr

def load_all_results(results_dir):
    """ML + DL 모든 결과 로드"""
    phases = {
        '2A': {
            'ml': 'choi_numeric_ml_v1',
            'dl': 'choi_numeric_dl_v1'
        },
        '2B': {
            'ml': 'choi_numeric_smiles_ml_v1',
            'dl': 'choi_numeric_smiles_dl_v1'
        },
        '2C': {
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
    if result is None:
        return None
    if eval_mode == 'holdout':
        return result['test']['spearman']
    else:
        return np.mean([f['val']['spearman'] for f in result['fold_results']])

def extract_train_spearman(result, eval_mode):
    if result is None:
        return None
    if eval_mode == 'holdout':
        return result['train']['spearman']
    else:
        return np.mean([f['train']['spearman'] for f in result['fold_results']])

def extract_metric(result, eval_mode, split, metric):
    """Extract any metric from result"""
    if result is None:
        return None
    if eval_mode == 'holdout':
        return result[split][metric]
    else:
        return np.mean([f[split][metric] for f in result['fold_results']])

def extract_fold_std(result, eval_mode, split, metric):
    """Extract fold std"""
    if result is None or eval_mode == 'holdout':
        return None
    return np.std([f[split][metric] for f in result['fold_results']])

def table1_full_comparison(results):
    """1. 전체 비교표 (13모델 × 3입력셋 × 3평가방식)"""
    print("\n" + "="*200)
    print("1. 전체 비교표 (13개 모델 × 3개 입력셋 × 3개 평가방식) - Val Spearman")
    print("="*200)

    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']
    dl_models = ['FlatMLP', 'ResidualMLP', 'FTTransformer', 'CrossAttention', 'TabNet', 'WideDeep', 'TabTransformer']
    all_models = [(m, 'ML') for m in ml_models] + [(m, 'DL') for m in dl_models]

    phases = ['2A', '2B', '2C']
    eval_modes = ['holdout', '5foldcv', 'groupcv']

    # 데이터 수집
    eval_mode_names = {'holdout': 'HOLD', '5foldcv': '5FLD', 'groupcv': 'GRCV'}

    data = []
    for model, mtype in all_models:
        row = {'Model': model, 'Type': mtype}
        for phase in phases:
            for eval_mode in eval_modes:
                col_name = f"{phase}_{eval_mode_names[eval_mode]}"

                model_type_key = 'ml' if mtype == 'ML' else 'dl'
                if results[phase][model_type_key][eval_mode] and model in results[phase][model_type_key][eval_mode]:
                    val = extract_val_spearman(results[phase][model_type_key][eval_mode][model], eval_mode)
                    row[col_name] = val
                else:
                    row[col_name] = None
        data.append(row)

    df = pd.DataFrame(data)

    # 각 열의 최고값 찾기
    value_cols = [c for c in df.columns if c not in ['Model', 'Type']]
    best_vals = {}
    for col in value_cols:
        best_vals[col] = df[col].max()

    # 출력
    header_cols = ['Type', 'Model'] + value_cols
    print(f"\n{'Type':<4} {'Model':<20} | ", end='')
    for phase in phases:
        print(f"{'─── ' + phase + ' ───':^40} | ", end='')
    print()

    print(f"{'':4} {'':20} | ", end='')
    for phase in phases:
        print(f"{'HOLD':>12} {'5FLD':>12} {'GRCV':>12} | ", end='')
    print()
    print("-"*200)

    for _, row in df.iterrows():
        print(f"{row['Type']:<4} {row['Model']:<20} | ", end='')
        for phase in phases:
            for eval_mode in ['HOLD', '5FLD', 'GRCV']:
                col = f"{phase}_{eval_mode}"
                val = row[col]
                if pd.notna(val):
                    # 최고값이면 ★ 표시
                    marker = '★' if val == best_vals[col] else ' '
                    print(f"{val:11.4f}{marker} ", end='')
                else:
                    print(f"{'N/A':>12} ", end='')
            print("| ", end='')
        print()

    print("\n★ = 해당 열(입력셋×평가방식)에서 1위")

def table2_groupcv_detailed(results):
    """2. GroupCV 상세 (모든 메트릭)"""
    print("\n" + "="*200)
    print("2. GroupCV 상세 분석 (13개 모델 × 3개 입력셋) - 전체 메트릭")
    print("="*200)

    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']
    dl_models = ['FlatMLP', 'ResidualMLP', 'FTTransformer', 'CrossAttention', 'TabNet', 'WideDeep', 'TabTransformer']
    all_models = [(m, 'ML') for m in ml_models] + [(m, 'DL') for m in dl_models]

    phases = ['2A', '2B', '2C']
    metrics = ['spearman', 'pearson', 'r2', 'rmse', 'mae', 'kendall_tau']

    for phase in phases:
        print(f"\n{'='*200}")
        print(f"Phase {phase} - GroupCV")
        print(f"{'='*200}")

        # 데이터 수집
        data = []
        for model, mtype in all_models:
            row = {'Type': mtype, 'Model': model}

            model_type_key = 'ml' if mtype == 'ML' else 'dl'
            if results[phase][model_type_key]['groupcv'] and model in results[phase][model_type_key]['groupcv']:
                result = results[phase][model_type_key]['groupcv'][model]

                # Train metrics
                for metric in metrics:
                    row[f'Train_{metric}'] = extract_metric(result, 'groupcv', 'train', metric)

                # Val metrics
                for metric in metrics:
                    row[f'Val_{metric}'] = extract_metric(result, 'groupcv', 'val', metric)
                    row[f'Std_{metric}'] = extract_fold_std(result, 'groupcv', 'val', metric)

                # Gap (for spearman, pearson, r2)
                for metric in ['spearman', 'pearson', 'r2']:
                    if row[f'Train_{metric}'] is not None and row[f'Val_{metric}'] is not None:
                        row[f'Gap_{metric}'] = row[f'Train_{metric}'] - row[f'Val_{metric}']

            data.append(row)

        df = pd.DataFrame(data)

        # Val Spearman 기준 정렬 및 순위
        df['Rank'] = df['Val_spearman'].rank(ascending=False, method='min')
        df = df.sort_values('Val_spearman', ascending=False, na_position='last').reset_index(drop=True)

        # 출력 - Spearman
        print(f"\n[Spearman Correlation]")
        print(f"{'Rank':<5} {'Type':<4} {'Model':<20} | {'Train':>10} {'Val':>10} {'Std':>10} {'Gap':>10}")
        print("-"*80)
        for _, row in df.iterrows():
            if pd.notna(row['Val_spearman']):
                print(f"{int(row['Rank']):<5} {row['Type']:<4} {row['Model']:<20} | "
                      f"{row['Train_spearman']:10.4f} {row['Val_spearman']:10.4f} "
                      f"{row['Std_spearman']:10.4f} {row['Gap_spearman']:10.4f}")

        # 출력 - Pearson
        print(f"\n[Pearson Correlation]")
        print(f"{'Type':<4} {'Model':<20} | {'Train':>10} {'Val':>10} {'Std':>10} {'Gap':>10}")
        print("-"*80)
        for _, row in df.iterrows():
            if pd.notna(row['Val_pearson']):
                print(f"{row['Type']:<4} {row['Model']:<20} | "
                      f"{row['Train_pearson']:10.4f} {row['Val_pearson']:10.4f} "
                      f"{row['Std_pearson']:10.4f} {row['Gap_pearson']:10.4f}")

        # 출력 - R²
        print(f"\n[R² Score]")
        print(f"{'Type':<4} {'Model':<20} | {'Train':>10} {'Val':>10} {'Std':>10} {'Gap':>10}")
        print("-"*80)
        for _, row in df.iterrows():
            if pd.notna(row['Val_r2']):
                print(f"{row['Type']:<4} {row['Model']:<20} | "
                      f"{row['Train_r2']:10.4f} {row['Val_r2']:10.4f} "
                      f"{row['Std_r2']:10.4f} {row['Gap_r2']:10.4f}")

        # 출력 - RMSE, MAE
        print(f"\n[RMSE & MAE]")
        print(f"{'Type':<4} {'Model':<20} | {'RMSE_Train':>12} {'RMSE_Val':>12} {'RMSE_Std':>12} | {'MAE_Train':>12} {'MAE_Val':>12} {'MAE_Std':>12}")
        print("-"*130)
        for _, row in df.iterrows():
            if pd.notna(row['Val_rmse']):
                print(f"{row['Type']:<4} {row['Model']:<20} | "
                      f"{row['Train_rmse']:12.4f} {row['Val_rmse']:12.4f} {row['Std_rmse']:12.4f} | "
                      f"{row['Train_mae']:12.4f} {row['Val_mae']:12.4f} {row['Std_mae']:12.4f}")

        # 출력 - Kendall's Tau
        print(f"\n[Kendall's Tau]")
        print(f"{'Type':<4} {'Model':<20} | {'Train':>10} {'Val':>10} {'Std':>10}")
        print("-"*80)
        for _, row in df.iterrows():
            if pd.notna(row['Val_kendall_tau']):
                print(f"{row['Type']:<4} {row['Model']:<20} | "
                      f"{row['Train_kendall_tau']:10.4f} {row['Val_kendall_tau']:10.4f} "
                      f"{row['Std_kendall_tau']:10.4f}")

def table3_feature_effects(results):
    """3. 입력셋 효과 비교"""
    print("\n" + "="*200)
    print("3. 입력셋 피처 추가 효과 비교 (GroupCV Val Spearman)")
    print("="*200)

    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']
    dl_models = ['FlatMLP', 'ResidualMLP', 'FTTransformer', 'CrossAttention', 'TabNet', 'WideDeep', 'TabTransformer']

    print(f"\n{'='*200}")
    print("[ML Models - SMILES & Context 효과]")
    print(f"{'='*200}")
    print(f"{'Model':<20} | {'2A (Base)':>12} {'2B (+SMILES)':>12} {'2C (+Context)':>12} | {'A→B':>10} {'A→B %':>10} | {'B→C':>10} {'B→C %':>10} | {'A→C':>10} {'A→C %':>10}")
    print("-"*200)

    ml_ab, ml_bc, ml_ac = [], [], []
    for model in ml_models:
        scores = {}
        for phase, phase_name in [('2A', '2A'), ('2B', '2B'), ('2C', '2C')]:
            if results[phase]['ml']['groupcv'] and model in results[phase]['ml']['groupcv']:
                scores[phase] = extract_val_spearman(results[phase]['ml']['groupcv'][model], 'groupcv')
            else:
                scores[phase] = None

        a, b, c = scores['2A'], scores['2B'], scores['2C']
        ab = b - a if (a and b) else None
        bc = c - b if (b and c) else None
        ac = c - a if (a and c) else None

        ab_pct = (ab / a * 100) if (a and ab) else None
        bc_pct = (bc / b * 100) if (b and bc) else None
        ac_pct = (ac / a * 100) if (a and ac) else None

        if ab: ml_ab.append(ab)
        if bc: ml_bc.append(bc)
        if ac: ml_ac.append(ac)

        a_str = f"{a:12.4f}" if a else "         N/A"
        b_str = f"{b:12.4f}" if b else "         N/A"
        c_str = f"{c:12.4f}" if c else "         N/A"
        ab_str = f"{ab:+10.4f}" if ab else "       N/A"
        ab_pct_str = f"{ab_pct:+9.2f}%" if ab_pct else "       N/A"
        bc_str = f"{bc:+10.4f}" if bc else "       N/A"
        bc_pct_str = f"{bc_pct:+9.2f}%" if bc_pct else "       N/A"
        ac_str = f"{ac:+10.4f}" if ac else "       N/A"
        ac_pct_str = f"{ac_pct:+9.2f}%" if ac_pct else "       N/A"

        print(f"{model:<20} | {a_str} {b_str} {c_str} | {ab_str} {ab_pct_str} | {bc_str} {bc_pct_str} | {ac_str} {ac_pct_str}")

    print(f"\n{'ML 평균':<20} | {'':12} {'':12} {'':12} | "
          f"{np.mean(ml_ab):+10.4f} {np.mean(ml_ab)/0.52*100:+9.2f}% | "
          f"{np.mean(ml_bc):+10.4f} {np.mean(ml_bc)/0.48*100:+9.2f}% | "
          f"{np.mean(ml_ac):+10.4f} {np.mean(ml_ac)/0.52*100:+9.2f}%")
    print(f"{'ML 개선/악화':<20} |  | {sum(1 for x in ml_ab if x>0)}/{len(ml_ab)} 개선 | {sum(1 for x in ml_bc if x>0)}/{len(ml_bc)} 개선 | {sum(1 for x in ml_ac if x>0)}/{len(ml_ac)} 개선")

    print(f"\n{'='*200}")
    print("[DL Models - SMILES & Context 효과]")
    print(f"{'='*200}")
    print(f"{'Model':<20} | {'2A (Base)':>12} {'2B (+SMILES)':>12} {'2C (+Context)':>12} | {'A→B':>10} {'A→B %':>10} | {'B→C':>10} {'B→C %':>10} | {'A→C':>10} {'A→C %':>10}")
    print("-"*200)

    dl_ab, dl_bc, dl_ac = [], [], []
    for model in dl_models:
        scores = {}
        for phase, phase_name in [('2A', '2A'), ('2B', '2B'), ('2C', '2C')]:
            if results[phase]['dl']['groupcv'] and model in results[phase]['dl']['groupcv']:
                scores[phase] = extract_val_spearman(results[phase]['dl']['groupcv'][model], 'groupcv')
            else:
                scores[phase] = None

        a, b, c = scores['2A'], scores['2B'], scores['2C']
        ab = b - a if (a and b) else None
        bc = c - b if (b and c) else None
        ac = c - a if (a and c) else None

        ab_pct = (ab / a * 100) if (a and ab) else None
        bc_pct = (bc / b * 100) if (b and bc) else None
        ac_pct = (ac / a * 100) if (a and ac) else None

        if ab: dl_ab.append(ab)
        if bc: dl_bc.append(bc)
        if ac: dl_ac.append(ac)

        a_str = f"{a:12.4f}" if a else "         N/A"
        b_str = f"{b:12.4f}" if b else "         N/A"
        c_str = f"{c:12.4f}" if c else "         N/A"
        ab_str = f"{ab:+10.4f}" if ab else "       N/A"
        ab_pct_str = f"{ab_pct:+9.2f}%" if ab_pct else "       N/A"
        bc_str = f"{bc:+10.4f}" if bc else "       N/A"
        bc_pct_str = f"{bc_pct:+9.2f}%" if bc_pct else "       N/A"
        ac_str = f"{ac:+10.4f}" if ac else "       N/A"
        ac_pct_str = f"{ac_pct:+9.2f}%" if ac_pct else "       N/A"

        print(f"{model:<20} | {a_str} {b_str} {c_str} | {ab_str} {ab_pct_str} | {bc_str} {bc_pct_str} | {ac_str} {ac_pct_str}")

    print(f"\n{'DL 평균':<20} | {'':12} {'':12} {'':12} | "
          f"{np.mean(dl_ab):+10.4f} {np.mean(dl_ab)/0.52*100:+9.2f}% | "
          f"{np.mean(dl_bc):+10.4f} {np.mean(dl_bc)/0.54*100:+9.2f}% | "
          f"{np.mean(dl_ac):+10.4f} {np.mean(dl_ac)/0.52*100:+9.2f}%")
    print(f"{'DL 개선/악화':<20} |  | {sum(1 for x in dl_ab if x>0)}/{len(dl_ab)} 개선 | {sum(1 for x in dl_bc if x>0)}/{len(dl_bc)} 개선 | {sum(1 for x in dl_ac if x>0)}/{len(dl_ac)} 개선")

    print(f"\n{'='*200}")
    print("[ML vs DL 비교]")
    print(f"{'='*200}")
    print(f"{'효과':<20} | {'ML 평균':>12} {'DL 평균':>12} | {'차이 (DL-ML)':>15} | {'승자':>10}")
    print("-"*80)
    print(f"{'SMILES (A→B)':<20} | {np.mean(ml_ab):12.4f} {np.mean(dl_ab):12.4f} | {np.mean(dl_ab)-np.mean(ml_ab):15.4f} | {'DL' if np.mean(dl_ab) > np.mean(ml_ab) else 'ML':>10}")
    print(f"{'Context (B→C)':<20} | {np.mean(ml_bc):12.4f} {np.mean(dl_bc):12.4f} | {np.mean(dl_bc)-np.mean(ml_bc):15.4f} | {'DL' if np.mean(dl_bc) > np.mean(ml_bc) else 'ML':>10}")
    print(f"{'Total (A→C)':<20} | {np.mean(ml_ac):12.4f} {np.mean(dl_ac):12.4f} | {np.mean(dl_ac)-np.mean(ml_ac):15.4f} | {'DL' if np.mean(dl_ac) > np.mean(ml_ac) else 'ML':>10}")

def table4_gap_analysis(results):
    """4. Train-Val Gap 분석"""
    print("\n" + "="*200)
    print("4. Train-Val Gap 분석 (과적합/언더피팅 판별)")
    print("="*200)

    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']
    dl_models = ['FlatMLP', 'ResidualMLP', 'FTTransformer', 'CrossAttention', 'TabNet', 'WideDeep', 'TabTransformer']

    for phase in ['2A', '2B', '2C']:
        print(f"\n{'='*200}")
        print(f"Phase {phase} - GroupCV Gap 분석")
        print(f"{'='*200}")

        # ML
        print(f"\n[ML Models]")
        print(f"{'Model':<20} | {'Train_Sp':>10} {'Val_Sp':>10} {'Gap_Sp':>10} | {'Train_R²':>10} {'Val_R²':>10} {'Gap_R²':>10} | {'상태':>15}")
        print("-"*140)

        for model in ml_models:
            if results[phase]['ml']['groupcv'] and model in results[phase]['ml']['groupcv']:
                result = results[phase]['ml']['groupcv'][model]

                train_sp = extract_metric(result, 'groupcv', 'train', 'spearman')
                val_sp = extract_metric(result, 'groupcv', 'val', 'spearman')
                gap_sp = train_sp - val_sp if (train_sp and val_sp) else None

                train_r2 = extract_metric(result, 'groupcv', 'train', 'r2')
                val_r2 = extract_metric(result, 'groupcv', 'val', 'r2')
                gap_r2 = train_r2 - val_r2 if (train_r2 and val_r2) else None

                # 판별
                if gap_sp and gap_sp > 0.4:
                    status = "심각한 과적합"
                elif gap_sp and gap_sp > 0.3:
                    status = "과적합"
                elif gap_sp and gap_sp > 0.2:
                    status = "경미한 과적합"
                else:
                    status = "양호"

                print(f"{model:<20} | {train_sp:10.4f} {val_sp:10.4f} {gap_sp:10.4f} | "
                      f"{train_r2:10.4f} {val_r2:10.4f} {gap_r2:10.4f} | {status:>15}")

        # DL
        print(f"\n[DL Models]")
        print(f"{'Model':<20} | {'Train_Sp':>10} {'Val_Sp':>10} {'Gap_Sp':>10} | {'Train_R²':>10} {'Val_R²':>10} {'Gap_R²':>10} | {'상태':>15}")
        print("-"*140)

        for model in dl_models:
            if results[phase]['dl']['groupcv'] and model in results[phase]['dl']['groupcv']:
                result = results[phase]['dl']['groupcv'][model]

                train_sp = extract_metric(result, 'groupcv', 'train', 'spearman')
                val_sp = extract_metric(result, 'groupcv', 'val', 'spearman')
                gap_sp = train_sp - val_sp if (train_sp and val_sp) else None

                train_r2 = extract_metric(result, 'groupcv', 'train', 'r2')
                val_r2 = extract_metric(result, 'groupcv', 'val', 'r2')
                gap_r2 = train_r2 - val_r2 if (train_r2 and val_r2) else None

                # 판별
                if gap_sp and gap_sp > 0.4:
                    status = "심각한 과적합"
                elif gap_sp and gap_sp > 0.3:
                    status = "과적합"
                elif gap_sp and gap_sp > 0.2:
                    status = "경미한 과적합"
                else:
                    status = "양호"

                print(f"{model:<20} | {train_sp:10.4f} {val_sp:10.4f} {gap_sp:10.4f} | "
                      f"{train_r2:10.4f} {val_r2:10.4f} {gap_r2:10.4f} | {status:>15}")

def table5_oof_diversity(results_dir):
    """5. OOF Diversity Matrix (Phase 2C)"""
    print("\n" + "="*200)
    print("5. OOF Diversity Matrix - Phase 2C (최고 성능 입력셋) GroupCV")
    print("="*200)

    # OOF 파일 로드
    ml_oof_dir = results_dir / "choi_numeric_context_smiles_ml_v1_oof"
    dl_oof_dir = results_dir / "choi_numeric_context_smiles_dl_v1_oof"

    ml_models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']
    dl_models = ['FlatMLP', 'ResidualMLP', 'FTTransformer', 'CrossAttention', 'TabNet', 'WideDeep', 'TabTransformer']
    all_models = ml_models + dl_models

    # OOF 예측 로드
    oof_preds = {}
    for model in ml_models:
        oof_file = ml_oof_dir / f"{model}.npy"
        if oof_file.exists():
            oof_preds[f"ML:{model}"] = np.load(oof_file)

    for model in dl_models:
        oof_file = dl_oof_dir / f"{model}.npy"
        if oof_file.exists():
            oof_preds[f"DL:{model}"] = np.load(oof_file)

    if not oof_preds:
        print("\n⚠️  OOF 예측 파일을 찾을 수 없습니다.")
        return

    # 상관 행렬 계산
    model_names = list(oof_preds.keys())
    n_models = len(model_names)
    corr_matrix = np.zeros((n_models, n_models))

    for i, model1 in enumerate(model_names):
        for j, model2 in enumerate(model_names):
            if i == j:
                corr_matrix[i, j] = 1.0
            else:
                corr, _ = spearmanr(oof_preds[model1], oof_preds[model2])
                corr_matrix[i, j] = corr

    # 상관 행렬 출력
    print(f"\n[상관 행렬 - Spearman Correlation]")
    print(f"{'Model':<25} | ", end='')
    for name in model_names:
        print(f"{name.split(':')[1][:8]:>8} ", end='')
    print()
    print("-"*200)

    for i, name1 in enumerate(model_names):
        print(f"{name1:<25} | ", end='')
        for j, name2 in enumerate(model_names):
            if i == j:
                print(f"{'1.0000':>8} ", end='')
            else:
                print(f"{corr_matrix[i, j]:8.4f} ", end='')
        print()

    # 다양성 분석 - 낮은 상관 = 높은 다양성
    print(f"\n{'='*200}")
    print("[앙상블 다양성 분석 - 가장 다양한 조합 Top 10]")
    print(f"{'='*200}")
    print("낮은 상관계수 = 높은 다양성 = 좋은 앙상블 후보\n")

    # 모든 쌍의 평균 상관계수 계산
    pair_corrs = []
    for i in range(n_models):
        for j in range(i+1, n_models):
            pair_corrs.append((model_names[i], model_names[j], corr_matrix[i, j]))

    # 상관계수 낮은 순으로 정렬
    pair_corrs.sort(key=lambda x: x[2])

    print(f"{'Rank':<6} {'Model 1':<25} {'Model 2':<25} | {'Correlation':>12} | {'Diversity':>12}")
    print("-"*100)
    for rank, (m1, m2, corr) in enumerate(pair_corrs[:10], 1):
        diversity = 1 - corr
        print(f"{rank:<6} {m1:<25} {m2:<25} | {corr:12.4f} | {diversity:12.4f}")

    # 상관계수 높은 쌍 (중복 모델)
    print(f"\n{'='*200}")
    print("[높은 상관 쌍 - 중복 가능성 (Top 10)]")
    print(f"{'='*200}")

    high_corrs = sorted(pair_corrs, key=lambda x: x[2], reverse=True)[:10]
    print(f"{'Rank':<6} {'Model 1':<25} {'Model 2':<25} | {'Correlation':>12}")
    print("-"*80)
    for rank, (m1, m2, corr) in enumerate(high_corrs, 1):
        print(f"{rank:<6} {m1:<25} {m2:<25} | {corr:12.4f}")

    # 각 모델의 평균 상관계수
    print(f"\n{'='*200}")
    print("[모델별 평균 상관계수 - 독립성 지표]")
    print(f"{'='*200}")
    print("낮은 평균 상관 = 다른 모델들과 독립적 = 앙상블에 유용\n")

    avg_corrs = []
    for i, name in enumerate(model_names):
        # 자기 자신 제외한 평균 상관
        others = [corr_matrix[i, j] for j in range(n_models) if i != j]
        avg_corr = np.mean(others)
        avg_corrs.append((name, avg_corr))

    avg_corrs.sort(key=lambda x: x[1])

    print(f"{'Rank':<6} {'Model':<25} | {'Avg Correlation':>18} | {'독립성':>10}")
    print("-"*80)
    for rank, (name, avg_corr) in enumerate(avg_corrs, 1):
        independence = 1 - avg_corr
        print(f"{rank:<6} {name:<25} | {avg_corr:18.4f} | {independence:10.4f}")

def main():
    base_dir = Path(__file__).parent
    results_dir = base_dir / "results"

    print("="*200)
    print("Phase 2 전체 종합 비교 분석")
    print("="*200)

    # 결과 로드
    results = load_all_results(results_dir)

    # 1. 전체 비교표
    table1_full_comparison(results)

    # 2. GroupCV 상세
    table2_groupcv_detailed(results)

    # 3. 입력셋 효과
    table3_feature_effects(results)

    # 4. Gap 분석
    table4_gap_analysis(results)

    # 5. OOF Diversity
    table5_oof_diversity(results_dir)

    print("\n" + "="*200)
    print("전체 분석 완료!")
    print("="*200)

if __name__ == "__main__":
    main()
