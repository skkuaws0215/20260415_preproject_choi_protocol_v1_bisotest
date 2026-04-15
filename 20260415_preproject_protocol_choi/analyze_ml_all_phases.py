"""
Phase 2A/2B/2C ML 전체 결과 비교 분석
"""
import json
import numpy as np
import pandas as pd
from pathlib import Path

def load_ml_results(results_dir):
    """모든 ML 결과 로드"""
    phases = {
        '2A_Numeric': 'choi_numeric_ml_v1',
        '2B_Num+SMILES': 'choi_numeric_smiles_ml_v1',
        '2C_Num+Ctx+SMILES': 'choi_numeric_context_smiles_ml_v1'
    }

    results = {}
    for phase_name, stem in phases.items():
        results[phase_name] = {}
        for eval_mode in ['holdout', '5foldcv', 'groupcv']:
            file_path = results_dir / f"{stem}_{eval_mode}.json"
            if file_path.exists():
                with open(file_path) as f:
                    results[phase_name][eval_mode] = json.load(f)
            else:
                results[phase_name][eval_mode] = None

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

def table1_input_model_comparison(results):
    """1. 입력셋 × ML 모델 × GroupCV Val Spearman 비교"""
    print("\n" + "="*140)
    print("1. 입력셋별 × ML 모델별 GroupCV Val Spearman 비교")
    print("="*140)

    phases = ['2A_Numeric', '2B_Num+SMILES', '2C_Num+Ctx+SMILES']
    models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']

    # 데이터 수집
    data = []
    for model in models:
        row = {'Model': model}

        for phase in phases:
            if results[phase]['groupcv'] and model in results[phase]['groupcv']:
                spearman = extract_val_spearman(results[phase]['groupcv'][model], 'groupcv')
                row[phase] = spearman
            else:
                row[phase] = None

        # SMILES 효과 (A→B)
        if row['2A_Numeric'] is not None and row['2B_Num+SMILES'] is not None:
            row['A→B'] = row['2B_Num+SMILES'] - row['2A_Numeric']
        else:
            row['A→B'] = None

        # Context 효과 (B→C)
        if row['2B_Num+SMILES'] is not None and row['2C_Num+Ctx+SMILES'] is not None:
            row['B→C'] = row['2C_Num+Ctx+SMILES'] - row['2B_Num+SMILES']
        else:
            row['B→C'] = None

        data.append(row)

    df = pd.DataFrame(data)

    # 각 Phase별 순위
    for phase in phases:
        df[f'{phase}_rank'] = df[phase].rank(ascending=False, method='min', na_option='keep')

    # Phase 2C 기준 정렬
    df = df.sort_values('2C_Num+Ctx+SMILES', ascending=False, na_position='last').reset_index(drop=True)

    # 출력
    print(f"\n{'Rank':<6} {'Model':<20} | {'2A_Numeric':>12} {'R':>3} | {'2B_Num+SMILES':>12} {'R':>3} | {'2C_Num+Ctx+SMILES':>12} {'R':>3} | {'A→B':>8} | {'B→C':>8}")
    print("-"*140)

    for idx, row in df.iterrows():
        rank = idx + 1

        a_val = f"{row['2A_Numeric']:12.4f}" if pd.notna(row['2A_Numeric']) else "         N/A"
        a_rank = f"{int(row['2A_Numeric_rank']):3d}" if pd.notna(row['2A_Numeric_rank']) else "  -"

        b_val = f"{row['2B_Num+SMILES']:12.4f}" if pd.notna(row['2B_Num+SMILES']) else "         N/A"
        b_rank = f"{int(row['2B_Num+SMILES_rank']):3d}" if pd.notna(row['2B_Num+SMILES_rank']) else "  -"

        c_val = f"{row['2C_Num+Ctx+SMILES']:12.4f}" if pd.notna(row['2C_Num+Ctx+SMILES']) else "         N/A"
        c_rank = f"{int(row['2C_Num+Ctx+SMILES_rank']):3d}" if pd.notna(row['2C_Num+Ctx+SMILES_rank']) else "  -"

        ab_change = f"{row['A→B']:8.4f}" if pd.notna(row['A→B']) else "     N/A"
        bc_change = f"{row['B→C']:8.4f}" if pd.notna(row['B→C']) else "     N/A"

        # 변화량 표시
        ab_arrow = " ↑" if pd.notna(row['A→B']) and row['A→B'] > 0 else (" ↓" if pd.notna(row['A→B']) and row['A→B'] < 0 else "")
        bc_arrow = " ↑" if pd.notna(row['B→C']) and row['B→C'] > 0 else (" ↓" if pd.notna(row['B→C']) and row['B→C'] < 0 else "")

        print(f"{rank:<6} {row['Model']:<20} | {a_val} {a_rank} | {b_val} {b_rank} | {c_val} {c_rank} | {ab_change}{ab_arrow} | {bc_change}{bc_arrow}")

    # 통계
    print("\n" + "="*140)
    print("피처 추가 효과 통계")
    print("="*140)

    valid_ab = df['A→B'].dropna()
    valid_bc = df['B→C'].dropna()

    print(f"\nSMILES 추가 효과 (A→B):")
    print(f"  평균: {valid_ab.mean():+.4f}")
    print(f"  중앙값: {valid_ab.median():+.4f}")
    print(f"  범위: {valid_ab.min():+.4f} ~ {valid_ab.max():+.4f}")
    print(f"  개선 모델: {(valid_ab > 0).sum()}/{len(valid_ab)}")

    print(f"\nContext 추가 효과 (B→C):")
    print(f"  평균: {valid_bc.mean():+.4f}")
    print(f"  중앙값: {valid_bc.median():+.4f}")
    print(f"  범위: {valid_bc.min():+.4f} ~ {valid_bc.max():+.4f}")
    print(f"  개선 모델: {(valid_bc > 0).sum()}/{len(valid_bc)}")

    return df

def table2_eval_mode_comparison(results):
    """2. 평가 방식별 비교"""
    print("\n" + "="*140)
    print("2. 평가 방식별 최고 성능 모델 (입력셋별)")
    print("="*140)

    phases = ['2A_Numeric', '2B_Num+SMILES', '2C_Num+Ctx+SMILES']
    eval_modes = ['holdout', '5foldcv', 'groupcv']

    print(f"\n{'Phase':<25} | {'Holdout':>30} | {'5-Fold CV':>30} | {'GroupCV':>30}")
    print("-"*140)

    for phase in phases:
        row_data = [phase]

        for eval_mode in eval_modes:
            if results[phase][eval_mode]:
                # 최고 모델 찾기
                best_model = None
                best_score = -999

                for model, result in results[phase][eval_mode].items():
                    score = extract_val_spearman(result, eval_mode)
                    if score is not None and score > best_score:
                        best_score = score
                        best_model = model

                row_data.append(f"{best_model} ({best_score:.4f})")
            else:
                row_data.append("N/A")

        print(f"{row_data[0]:<25} | {row_data[1]:>30} | {row_data[2]:>30} | {row_data[3]:>30}")

def table3_gap_analysis(results):
    """3. Train-Val Gap 분석"""
    print("\n" + "="*140)
    print("3. Train-Val Gap 분석 (GroupCV)")
    print("="*140)

    phases = ['2A_Numeric', '2B_Num+SMILES', '2C_Num+Ctx+SMILES']
    models = ['LightGBM', 'LightGBM_DART', 'XGBoost', 'CatBoost', 'RandomForest', 'ExtraTrees']

    print(f"\n{'Model':<20} | {'2A_Numeric':>20} | {'2B_Num+SMILES':>20} | {'2C_Num+Ctx+SMILES':>20}")
    print(f"{'':20} | {'Train':>9} {'Val':>9} {'Gap':>9} | {'Train':>9} {'Val':>9} {'Gap':>9} | {'Train':>9} {'Val':>9} {'Gap':>9}")
    print("-"*140)

    for model in models:
        row = [model]

        for phase in phases:
            if results[phase]['groupcv'] and model in results[phase]['groupcv']:
                train_sp = extract_train_spearman(results[phase]['groupcv'][model], 'groupcv')
                val_sp = extract_val_spearman(results[phase]['groupcv'][model], 'groupcv')
                gap = train_sp - val_sp if (train_sp is not None and val_sp is not None) else None

                train_str = f"{train_sp:9.4f}" if train_sp is not None else "      N/A"
                val_str = f"{val_sp:9.4f}" if val_sp is not None else "      N/A"
                gap_str = f"{gap:9.4f}" if gap is not None else "      N/A"

                row.append(f"{train_str} {val_str} {gap_str}")
            else:
                row.append(f"{'N/A':>9} {'N/A':>9} {'N/A':>9}")

        print(f"{row[0]:<20} | {row[1]} | {row[2]} | {row[3]}")

    # Gap 통계
    print("\n" + "="*140)
    print("Gap 통계 (입력셋별 평균)")
    print("="*140)

    for phase in phases:
        if results[phase]['groupcv']:
            gaps = []
            for model in models:
                if model in results[phase]['groupcv']:
                    train_sp = extract_train_spearman(results[phase]['groupcv'][model], 'groupcv')
                    val_sp = extract_val_spearman(results[phase]['groupcv'][model], 'groupcv')
                    if train_sp is not None and val_sp is not None:
                        gaps.append(train_sp - val_sp)

            if gaps:
                print(f"\n{phase}:")
                print(f"  평균 Gap: {np.mean(gaps):.4f}")
                print(f"  최소 Gap: {np.min(gaps):.4f}")
                print(f"  최대 Gap: {np.max(gaps):.4f}")

def main():
    base_dir = Path(__file__).parent
    results_dir = base_dir / "results"

    print("="*140)
    print("Phase 2A/2B/2C ML 전체 결과 비교 분석")
    print("="*140)

    # 결과 로드
    results = load_ml_results(results_dir)

    # 완료 여부 확인
    missing = []
    for phase in ['2A_Numeric', '2B_Num+SMILES', '2C_Num+Ctx+SMILES']:
        for eval_mode in ['holdout', '5foldcv', 'groupcv']:
            if results[phase][eval_mode] is None:
                missing.append(f"{phase} {eval_mode}")

    if missing:
        print(f"\n⚠️  경고: 다음 결과 파일이 없습니다:")
        for m in missing:
            print(f"  - {m}")
        print()

    # 1. 입력셋 × 모델 비교
    df_comparison = table1_input_model_comparison(results)

    # 2. 평가 방식별 비교
    table2_eval_mode_comparison(results)

    # 3. Gap 분석
    table3_gap_analysis(results)

    print("\n" + "="*140)
    print("분석 완료!")
    print("="*140)

if __name__ == "__main__":
    main()
