"""
Phase 2A GraphSAGE 모델 (MPS GPU) - Colon 버전
GAT는 별도 실행, GraphSAGE는 MPS 우선 시도

Original: Lung run_graph_sage_mps.py (258 lines)
Colon 변경점:
  1. Line 29: CPU 강제 → MPS/CUDA/CPU 자동 선택 복원 (OOM 시 CPU fallback 유지)
  2. Line 108: k=10 → k=7 (Colon 9,692 샘플 수 고려)
  3. Line 204: oof_dir "lung_" → "colon_"
  4. Line 213: features_path Colon 경로
  5. Line 234: results_file "lung_" → "colon_"
  6. base_dir: scripts/의 상위
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import json
import torch
import torch.nn as nn
import torch.nn.functional as F
import lightgbm as lgb
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import NearestNeighbors

sys.path.insert(0, str(Path(__file__).parent))

from phase2_utils import calculate_metrics, save_results

try:
    import torch_geometric
    from torch_geometric.nn import SAGEConv
    from torch_geometric.data import Data
    print(f"PyTorch Geometric {torch_geometric.__version__} loaded")
except ImportError:
    print("ERROR: PyTorch Geometric not installed")
    sys.exit(1)

# Device - Colon: MPS 우선 시도, OOM 발생 시 CPU fallback
if torch.backends.mps.is_available():
    device = torch.device('mps')
    print(f"Using device: MPS (will fallback to CPU on OOM)")
elif torch.cuda.is_available():
    device = torch.device('cuda')
    print(f"Using device: CUDA")
else:
    device = torch.device('cpu')
    print(f"Using device: CPU")
print(f"Device: {device}")


def build_knn_graph(X, k=7):
    """
    KNN 그래프 생성
    각 샘플을 k개의 가장 가까운 이웃과 연결
    Colon: k=7 (Lung k=10에서 샘플 수 감소에 맞춰 축소)
    """
    print(f"Building KNN graph with k={k}...")
    nbrs = NearestNeighbors(n_neighbors=k+1, algorithm='auto', n_jobs=-1).fit(X)
    distances, indices = nbrs.kneighbors(X)

    # Edge list 생성 (자기 자신 제외)
    edge_list = []
    for i in range(len(X)):
        for j in range(1, k+1):  # Skip self (index 0)
            edge_list.append([i, indices[i, j]])

    edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()
    print(f"Graph created: {len(X)} nodes, {edge_index.shape[1]} edges")

    return edge_index


class GraphSAGE(nn.Module):
    """GraphSAGE for regression"""
    def __init__(self, input_dim, hidden_dim=128, num_layers=2):
        super().__init__()
        self.convs = nn.ModuleList()
        self.convs.append(SAGEConv(input_dim, hidden_dim))
        for _ in range(num_layers - 1):
            self.convs.append(SAGEConv(hidden_dim, hidden_dim))

        self.fc = nn.Linear(hidden_dim, 1)
        self.dropout = nn.Dropout(0.2)

    def forward(self, x, edge_index):
        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)
            if i < len(self.convs) - 1:
                x = F.relu(x)
                x = self.dropout(x)

        return self.fc(x).squeeze()


def train_graph_model(model, data, train_mask, optimizer, criterion):
    """Train for one epoch"""
    model.train()
    optimizer.zero_grad()

    out = model(data.x, data.edge_index)
    loss = criterion(out[train_mask], data.y[train_mask])

    loss.backward()
    optimizer.step()

    return loss.item()


def evaluate_graph_model(model, data, mask):
    """Evaluate model"""
    model.eval()
    with torch.no_grad():
        out = model(data.x, data.edge_index)
        pred = out[mask].cpu().numpy()
        true = data.y[mask].cpu().numpy()

    return pred, true


def train_evaluate_graphsage(
    X,
    y,
    groups,
    output_stem,
    oof_dir=None,
    k_neighbors=7,
    fs_top_k=None,
):
    """
    GraphSAGE 모델 학습 및 평가 (GroupCV only, MPS 우선)
    """
    print(f"\n{'='*120}")
    print(f"GraphSAGE - GROUPCV (Drug-based split, k={k_neighbors})")
    print(f"{'='*120}")

    global device

    try:
        # --- Global Importance-based FS (Graph 특수: fold 밖에서 전체 X 로 계산) ---
        if fs_top_k is not None and fs_top_k < X.shape[1]:
            fs_model = lgb.LGBMRegressor(
                n_estimators=100,
                learning_rate=0.1,
                random_state=42,
                verbose=-1,
                num_threads=-1,
            )
            fs_model.fit(X, y)
            importance = fs_model.feature_importances_
            top_indices = np.argsort(importance)[-fs_top_k:]
            X = X[:, top_indices]
            print(f"  FS applied: -> {X.shape[1]} features (top {fs_top_k})")
        # ---------------------------------------------------------

        # Build KNN graph
        edge_index = build_knn_graph(X, k=k_neighbors)

        # Prepare data
        x_tensor = torch.FloatTensor(X).to(device)
        y_tensor = torch.FloatTensor(y).to(device)

        # GroupCV
        gkf = GroupKFold(n_splits=3)
        fold_results = []
        oof_predictions = np.zeros(len(y))

        for fold_idx, (train_idx, val_idx) in enumerate(gkf.split(X, y, groups), 1):
            print(f"\n  Fold {fold_idx}/3")

            # Create train and val masks
            train_mask = torch.zeros(len(y), dtype=torch.bool)
            val_mask = torch.zeros(len(y), dtype=torch.bool)
            train_mask[train_idx] = True
            val_mask[val_idx] = True

            # Create graph data
            data = Data(x=x_tensor, edge_index=edge_index, y=y_tensor).to(device)

            # Initialize model
            input_dim = X.shape[1]
            model = GraphSAGE(input_dim).to(device)
            optimizer = torch.optim.Adam(model.parameters(), lr=0.001, weight_decay=1e-5)
            criterion = nn.MSELoss()

            # Training
            best_val_loss = float('inf')
            patience = 20
            patience_counter = 0

            for epoch in range(200):  # Max 200 epochs
                train_loss = train_graph_model(model, data, train_mask, optimizer, criterion)

                # Validation
                val_pred, val_true = evaluate_graph_model(model, data, val_mask)
                val_loss = np.mean((val_pred - val_true) ** 2)

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                    # Save best predictions
                    best_val_pred = val_pred.copy()
                else:
                    patience_counter += 1

                if patience_counter >= patience:
                    print(f"    Early stopping at epoch {epoch+1}")
                    break

            # Get train predictions
            train_pred, train_true = evaluate_graph_model(model, data, train_mask)

            # Calculate metrics
            train_metrics = calculate_metrics(train_true, train_pred)
            val_metrics = calculate_metrics(val_true, best_val_pred)

            print(f"    Train Spearman: {train_metrics['spearman']:.4f}")
            print(f"    Val   Spearman: {val_metrics['spearman']:.4f}")

            fold_results.append({
                'fold': fold_idx,
                'train': train_metrics,
                'val': val_metrics
            })

            # Save OOF predictions
            oof_predictions[val_idx] = best_val_pred

    except RuntimeError as e:
        if "out of memory" in str(e).lower() or "oom" in str(e).lower():
            print(f"\n⚠️  MPS/CUDA OOM detected! Switching to CPU...")
            device = torch.device('cpu')
            print(f"Restarting GraphSAGE on CPU...")

            # Retry on CPU
            return train_evaluate_graphsage(
                X, y, groups, output_stem, oof_dir, k_neighbors, fs_top_k=fs_top_k
            )
        else:
            raise e

    # Save OOF predictions
    if oof_dir:
        oof_file = oof_dir / "GraphSAGE.npy"
        np.save(oof_file, oof_predictions)
        print(f"\n  OOF predictions saved: {oof_file}")

    # Calculate average metrics
    train_sps = [f['train']['spearman'] for f in fold_results]
    val_sps = [f['val']['spearman'] for f in fold_results]

    print(f"\n  Average - Train: {np.mean(train_sps):.4f}, Val: {np.mean(val_sps):.4f}, Gap: {np.mean(train_sps) - np.mean(val_sps):+.4f}")

    results = {
        'model': 'GraphSAGE',
        'eval_mode': 'groupcv',
        'device': str(device),
        'k_neighbors': k_neighbors,
        'fold_results': fold_results
    }

    return results


if __name__ == "__main__":
    # ============================================================
    # Experiment configuration
    # ============================================================
    # fs_top_k = None
    fs_top_k = 1000
    out_suffix = f"_fsimp_top{fs_top_k}" if fs_top_k is not None else ""
    if fs_top_k is None:
        experiment_dir = "graph_baseline_20260422_rerun"
    else:
        experiment_dir = f"graph_fsimp_top{fs_top_k}_20260422"

    print(
        f"Experiment: fs_top_k={fs_top_k}, out_suffix='{out_suffix}', "
        f"experiment_dir='{experiment_dir}'"
    )
    # ============================================================

    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    if experiment_dir:
        results_dir = base_dir / "results" / experiment_dir
    else:
        results_dir = base_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Load shared labels
    y = np.load(data_dir / "y_train.npy")

    # Load groups - Colon features_slim.parquet
    features_path = base_dir / "fe_qc" / "20260420_colon_fe_v2" / "features_slim.parquet"
    df_meta = pd.read_parquet(features_path, columns=['canonical_drug_id'])
    groups = df_meta['canonical_drug_id'].values

    # ─── Phase 2A ───
    print("\n" + "=" * 120)
    print("Phase 2A: numeric-only")
    print("=" * 120)

    X = np.load(data_dir / "X_numeric.npy")
    print(f"X shape: {X.shape}")

    oof_dir = results_dir / f"colon_numeric_graph_v1{out_suffix}_oof"
    oof_dir.mkdir(exist_ok=True)

    results = train_evaluate_graphsage(
        X, y, groups, "colon_numeric_graph_v1", oof_dir, k_neighbors=7, fs_top_k=fs_top_k
    )

    results_file = results_dir / f"colon_numeric_graph_v1{out_suffix}_groupcv.json"
    if results_file.exists():
        with open(results_file, 'r') as f:
            all_results = json.load(f)
        all_results['GraphSAGE'] = results
    else:
        all_results = {'GraphSAGE': results}

    from phase2_utils import save_results
    save_results(all_results, results_file)

    # ─── Phase 2B ───
    print("\n" + "="*120)
    print("Phase 2B: numeric + SMILES")
    print("="*120)

    X_2b = np.load(data_dir / "X_numeric_smiles.npy")
    print(f"X shape: {X_2b.shape}")

    oof_dir_2b = results_dir / f"colon_numeric_smiles_graph_v1{out_suffix}_oof"
    oof_dir_2b.mkdir(exist_ok=True)

    results_2b = train_evaluate_graphsage(
        X_2b, y, groups, "colon_numeric_smiles_graph_v1", oof_dir_2b, k_neighbors=7, fs_top_k=fs_top_k
    )

    results_file_2b = results_dir / f"colon_numeric_smiles_graph_v1{out_suffix}_groupcv.json"
    if results_file_2b.exists():
        with open(results_file_2b, 'r') as f:
            all_results_2b = json.load(f)
        all_results_2b['GraphSAGE'] = results_2b
    else:
        all_results_2b = {'GraphSAGE': results_2b}
    save_results(all_results_2b, results_file_2b)

    # ─── Phase 2C ───
    print("\n" + "="*120)
    print("Phase 2C: numeric + context + SMILES")
    print("="*120)

    X_2c = np.load(data_dir / "X_numeric_context_smiles.npy")
    print(f"X shape: {X_2c.shape}")

    oof_dir_2c = results_dir / f"colon_numeric_context_smiles_graph_v1{out_suffix}_oof"
    oof_dir_2c.mkdir(exist_ok=True)

    results_2c = train_evaluate_graphsage(
        X_2c, y, groups, "colon_numeric_context_smiles_graph_v1", oof_dir_2c, k_neighbors=7, fs_top_k=fs_top_k
    )

    results_file_2c = results_dir / f"colon_numeric_context_smiles_graph_v1{out_suffix}_groupcv.json"
    if results_file_2c.exists():
        with open(results_file_2c, 'r') as f:
            all_results_2c = json.load(f)
        all_results_2c['GraphSAGE'] = results_2c
    else:
        all_results_2c = {'GraphSAGE': results_2c}
    save_results(all_results_2c, results_file_2c)

    print(f"\n✅ GraphSAGE 전체 완료! (Phase 2A/2B/2C)")
