"""
Phase 2 DL 모델 전체 실행 (기본 하이퍼파라미터) - Colon 버전
3가지 평가 방식: Holdout, 5-Fold CV, GroupCV

Original: Lung run_dl_all.py (436 lines)
Colon 변경점:
  1. epochs=30 → epochs=50 (Lung은 샘플 많아 30으로 줄였으나 Colon은 작아 충분한 학습 필요)
  2. TabTransformer 5foldcv early stop 제거 (BRCA 기준 < 0.57, Colon과 무관)
  3. Line 323: features_path Colon 경로
  4. Line 370/373/376: output_stem choi_ → colon_
  5. base_dir: scripts/의 상위 (data/, results/는 프로젝트 루트 기준)
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split, KFold, GroupKFold
import lightgbm as lgb

sys.path.insert(0, str(Path(__file__).parent))

from phase2_utils import calculate_metrics, save_results
from data_validation import check_overfitting, check_stability

# PyTorch 설정 - MPS (Apple Silicon GPU) 우선 사용
if torch.backends.mps.is_available():
    device = torch.device('mps')
    print(f"Using device: MPS (Metal Performance Shaders)")
elif torch.cuda.is_available():
    device = torch.device('cuda')
    print(f"Using device: CUDA")
else:
    device = torch.device('cpu')
    print(f"Using device: CPU")

print(f"Device: {device}")

# ============================================================================
# DL 모델 정의
# ============================================================================

class FlatMLP(nn.Module):
    """단순 MLP"""
    def __init__(self, input_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 1)
        )

    def forward(self, x):
        return self.net(x).squeeze()


class ResidualMLP(nn.Module):
    """Residual connection이 있는 MLP"""
    def __init__(self, input_dim):
        super().__init__()
        self.input_layer = nn.Linear(input_dim, 512)

        self.block1 = nn.Sequential(
            nn.Linear(512, 512),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(512, 512)
        )

        self.block2 = nn.Sequential(
            nn.Linear(512, 256),
            nn.ReLU(),
            nn.Dropout(0.2)
        )

        self.output_layer = nn.Linear(256, 1)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.relu(self.input_layer(x))
        x = self.relu(x + self.block1(x))  # Residual
        x = self.block2(x)
        return self.output_layer(x).squeeze()


class FTTransformer(nn.Module):
    """간단한 Transformer 기반 모델"""
    def __init__(self, input_dim):
        super().__init__()
        self.embedding = nn.Linear(input_dim, 256)
        encoder_layer = nn.TransformerEncoderLayer(d_model=256, nhead=4, dim_feedforward=512, batch_first=True)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
        self.fc = nn.Linear(256, 1)

    def forward(self, x):
        x = self.embedding(x).unsqueeze(1)  # (batch, 1, 256)
        x = self.transformer(x)
        x = x.squeeze(1)
        return self.fc(x).squeeze()


class CrossAttention(nn.Module):
    """Cross Attention 모델"""
    def __init__(self, input_dim):
        super().__init__()
        self.embed = nn.Linear(input_dim, 256)
        self.attention = nn.MultiheadAttention(256, num_heads=4, batch_first=True)
        self.fc = nn.Sequential(
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Linear(128, 1)
        )

    def forward(self, x):
        x = self.embed(x).unsqueeze(1)
        attn_out, _ = self.attention(x, x, x)
        x = attn_out.squeeze(1)
        return self.fc(x).squeeze()


class TabNet(nn.Module):
    """간단한 TabNet 스타일"""
    def __init__(self, input_dim):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, 256)
        self.fc2 = nn.Linear(256, 128)
        self.fc3 = nn.Linear(128, 1)
        self.bn1 = nn.BatchNorm1d(256)
        self.bn2 = nn.BatchNorm1d(128)

    def forward(self, x):
        x = torch.relu(self.bn1(self.fc1(x)))
        x = torch.relu(self.bn2(self.fc2(x)))
        return self.fc3(x).squeeze()


class WideDeep(nn.Module):
    """Wide & Deep 모델"""
    def __init__(self, input_dim):
        super().__init__()
        # Wide
        self.wide = nn.Linear(input_dim, 1, bias=False)

        # Deep
        self.deep = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 1)
        )

    def forward(self, x):
        wide_out = self.wide(x)
        deep_out = self.deep(x)
        return (wide_out + deep_out).squeeze()


class TabTransformer(nn.Module):
    """Tab Transformer"""
    def __init__(self, input_dim):
        super().__init__()
        self.embedding = nn.Linear(input_dim, 128)
        encoder_layer = nn.TransformerEncoderLayer(d_model=128, nhead=4, dim_feedforward=256, batch_first=True)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
        self.fc = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1)
        )

    def forward(self, x):
        x = self.embedding(x).unsqueeze(1)
        x = self.transformer(x).squeeze(1)
        return self.fc(x).squeeze()


# ============================================================================
# 학습 함수
# ============================================================================

def train_dl_model(model, train_loader, val_loader, train_loader_no_shuffle, epochs=50, lr=0.001):
    """DL 모델 학습"""
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    model.train()
    for epoch in range(epochs):
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)

            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()

    # 평가 모드
    model.eval()
    with torch.no_grad():
        # Train 예측 (버그 수정: shuffle=False 사용)
        train_preds = []
        for batch_X, batch_y in train_loader_no_shuffle:
            batch_X = batch_X.to(device)
            preds = model(batch_X).cpu().numpy()
            train_preds.extend(preds)

        # Val 예측
        val_preds = []
        for batch_X, batch_y in val_loader:
            batch_X = batch_X.to(device)
            preds = model(batch_X).cpu().numpy()
            val_preds.extend(preds)

    return np.array(train_preds), np.array(val_preds)


def train_evaluate_dl(
    X,
    y,
    groups,
    model_name,
    model_class,
    eval_mode,
    output_stem,
    oof_dir=None,
    fs_top_k=None,
    out_suffix="",
):
    """DL 모델 학습 및 평가"""
    print(f"\n{'='*120}")
    print(f"{model_name} - {eval_mode.upper()}")
    print(f"{'='*120}")

    input_dim = X.shape[1]

    if eval_mode == 'holdout':
        # Holdout
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # DataLoader
        train_dataset = TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(y_train))
        test_dataset = TensorDataset(torch.FloatTensor(X_test), torch.FloatTensor(y_test))

        train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True)
        train_loader_no_shuffle = DataLoader(train_dataset, batch_size=128, shuffle=False)  # 버그 수정
        test_loader = DataLoader(test_dataset, batch_size=128)

        # 모델 학습 - Colon: epochs=50
        model = model_class(input_dim).to(device)
        train_pred, test_pred = train_dl_model(model, train_loader, test_loader, train_loader_no_shuffle, epochs=50)

        train_metrics = calculate_metrics(y_train, train_pred)
        test_metrics = calculate_metrics(y_test, test_pred)

        results = {
            'model': model_name,
            'eval_mode': 'holdout',
            'train': train_metrics,
            'test': test_metrics,
            'gap': {
                'spearman': train_metrics['spearman'] - test_metrics['spearman'],
                'rmse': train_metrics['rmse'] - test_metrics['rmse']
            }
        }

        print(f"  Train Spearman: {train_metrics['spearman']:.4f}")
        print(f"  Test  Spearman: {test_metrics['spearman']:.4f}")

    elif eval_mode == '5foldcv':
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        fold_results = []

        for fold_idx, (train_idx, val_idx) in enumerate(kf.split(X), 1):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # --- Fold-internal Importance-based FS ---
            if fs_top_k is not None and fs_top_k < X_train.shape[1]:
                fs_model = lgb.LGBMRegressor(
                    n_estimators=100,
                    learning_rate=0.1,
                    random_state=42,
                    verbose=-1,
                    num_threads=-1,
                )
                fs_model.fit(X_train, y_train)
                importance = fs_model.feature_importances_
                top_indices = np.argsort(importance)[-fs_top_k:]
                X_train = X_train[:, top_indices]
                X_val = X_val[:, top_indices]
            # -----------------------------------------

            train_dataset = TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(y_train))
            val_dataset = TensorDataset(torch.FloatTensor(X_val), torch.FloatTensor(y_val))

            train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True)
            train_loader_no_shuffle = DataLoader(train_dataset, batch_size=128, shuffle=False)  # 버그 수정
            val_loader = DataLoader(val_dataset, batch_size=128)

            # Colon: epochs=50
            input_dim = X_train.shape[1]  # FS 후 feature 수 반영
            model = model_class(input_dim).to(device)
            train_pred, val_pred = train_dl_model(model, train_loader, val_loader, train_loader_no_shuffle, epochs=50)

            train_metrics = calculate_metrics(y_train, train_pred)
            val_metrics = calculate_metrics(y_val, val_pred)

            fold_results.append({
                'fold': fold_idx,
                'train': train_metrics,
                'val': val_metrics
            })

            print(f"  Fold {fold_idx}: Val Spearman={val_metrics['spearman']:.4f}")

            # TabTransformer early stop 제거 (Colon에서는 비교 위해 full fold 실행)

        overfitting_check = check_overfitting(fold_results)
        stability_check = check_stability(fold_results)

        results = {
            'model': model_name,
            'eval_mode': '5foldcv',
            'fold_results': fold_results,
            'overfitting_check': overfitting_check,
            'stability_check': stability_check
        }

    else:  # groupcv
        gkf = GroupKFold(n_splits=3)
        fold_results = []
        oof_predictions = np.zeros(len(y))

        for fold_idx, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups=groups), 1):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            # --- Fold-internal Importance-based FS ---
            if fs_top_k is not None and fs_top_k < X_train.shape[1]:
                fs_model = lgb.LGBMRegressor(
                    n_estimators=100,
                    learning_rate=0.1,
                    random_state=42,
                    verbose=-1,
                    num_threads=-1,
                )
                fs_model.fit(X_train, y_train)
                importance = fs_model.feature_importances_
                top_indices = np.argsort(importance)[-fs_top_k:]
                X_train = X_train[:, top_indices]
                X_val = X_val[:, top_indices]
            # -----------------------------------------

            train_dataset = TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(y_train))
            val_dataset = TensorDataset(torch.FloatTensor(X_val), torch.FloatTensor(y_val))

            train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True)
            train_loader_no_shuffle = DataLoader(train_dataset, batch_size=128, shuffle=False)  # 버그 수정
            val_loader = DataLoader(val_dataset, batch_size=128)

            # Colon: epochs=50
            input_dim = X_train.shape[1]  # FS 후 feature 수 반영
            model = model_class(input_dim).to(device)
            train_pred, val_pred = train_dl_model(model, train_loader, val_loader, train_loader_no_shuffle, epochs=50)

            oof_predictions[val_idx] = val_pred

            train_metrics = calculate_metrics(y_train, train_pred)
            val_metrics = calculate_metrics(y_val, val_pred)

            fold_results.append({
                'fold': fold_idx,
                'train': train_metrics,
                'val': val_metrics
            })

            print(f"  Fold {fold_idx}: Val Spearman={val_metrics['spearman']:.4f}")

        if oof_dir:
            np.save(oof_dir / f"{model_name}.npy", oof_predictions)

        overfitting_check = check_overfitting(fold_results)
        stability_check = check_stability(fold_results)

        results = {
            'model': model_name,
            'eval_mode': 'groupcv',
            'fold_results': fold_results,
            'overfitting_check': overfitting_check,
            'stability_check': stability_check
        }

    return results


def run_phase_dl(
    input_file,
    output_stem,
    phase_name,
    fs_top_k=None,
    out_suffix="",
    experiment_dir=None,
):
    """하나의 입력셋에 대해 DL 모델 전체 실행"""
    print("\n" + "="*120)
    print(f"{phase_name}: DL Models")
    print("="*120)

    # Colon 경로
    base_dir = Path(__file__).parent.parent   # 20260420_new_pre_project_biso_Colon/
    data_dir = base_dir / "data"
    if experiment_dir:
        results_dir = base_dir / "results" / experiment_dir
    else:
        results_dir = base_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    oof_dir = results_dir / f"{output_stem}{out_suffix}_oof"
    oof_dir.mkdir(exist_ok=True)

    X = np.load(data_dir / input_file)
    y = np.load(data_dir / "y_train.npy")

    # Colon features_slim.parquet 경로
    features_path = base_dir / "fe_qc" / "20260420_colon_fe_v2" / "features_slim.parquet"
    df_meta = pd.read_parquet(features_path, columns=['canonical_drug_id'])
    groups = df_meta['canonical_drug_id'].values

    print(f"\nData: {input_file}")
    print(f"X shape: {X.shape}")

    models = {
        'FlatMLP': FlatMLP,
        'ResidualMLP': ResidualMLP,
        'FTTransformer': FTTransformer,
        'CrossAttention': CrossAttention,
        'TabNet': TabNet,
        'WideDeep': WideDeep,
        'TabTransformer': TabTransformer
    }

    eval_modes = ['holdout', '5foldcv', 'groupcv']
    all_results = {mode: {} for mode in eval_modes}

    for model_name, model_class in models.items():
        for eval_mode in eval_modes:
            oof_dir_arg = oof_dir if eval_mode == 'groupcv' else None

            # OOF 파일이 이미 존재하면 건너뛰기 (GroupCV만)
            if eval_mode == 'groupcv' and oof_dir:
                oof_file = oof_dir / f"{model_name}.npy"
                if oof_file.exists():
                    print(f"\n{'='*120}")
                    print(f"⏭️  {model_name} - GroupCV: OOF 파일 이미 존재, 건너뜀")
                    print(f"{'='*120}")
                    continue

            results = train_evaluate_dl(
                X, y, groups,
                model_name, model_class,
                eval_mode, output_stem,
                oof_dir=oof_dir_arg,
                fs_top_k=fs_top_k,
                out_suffix=out_suffix,
            )

            all_results[eval_mode][model_name] = results

    for eval_mode in eval_modes:
        output_file = results_dir / f"{output_stem}{out_suffix}_{eval_mode}.json"
        save_results(all_results[eval_mode], output_file)

    print("\n" + "="*120)
    print(f"{phase_name} DL 완료")
    print("="*120)

    return all_results


if __name__ == "__main__":
    # ============================================================
    # Experiment configuration
    # ============================================================
    # fs_top_k = None            # Baseline (기존과 동일)
    fs_top_k = 1000              # Fold-internal importance FS, Top 1000

    out_suffix = f"_fsimp_top{fs_top_k}" if fs_top_k is not None else ""

    if fs_top_k is None:
        experiment_dir = "dl_baseline_20260422_rerun"
    else:
        experiment_dir = f"dl_fsimp_top{fs_top_k}_20260422"

    print(
        f"Experiment: fs_top_k={fs_top_k}, "
        f"out_suffix='{out_suffix}', "
        f"experiment_dir='{experiment_dir}'"
    )
    # ============================================================

    # Phase 2A
    run_phase_dl(
        "X_numeric.npy", "colon_numeric_dl_v1", "Phase 2A",
        fs_top_k=fs_top_k, out_suffix=out_suffix, experiment_dir=experiment_dir,
    )

    # Phase 2B
    run_phase_dl(
        "X_numeric_smiles.npy", "colon_numeric_smiles_dl_v1", "Phase 2B",
        fs_top_k=fs_top_k, out_suffix=out_suffix, experiment_dir=experiment_dir,
    )

    # Phase 2C
    run_phase_dl(
        "X_numeric_context_smiles.npy", "colon_numeric_context_smiles_dl_v1", "Phase 2C",
        fs_top_k=fs_top_k, out_suffix=out_suffix, experiment_dir=experiment_dir,
    )

    print("\n전체 DL 학습 완료!")
