"""
Phase 2A GAT 모델 (MPS GPU) - Colon 버전
GraphSAGE는 별도 실행, GAT는 MPS 우선 시도

Original: Lung run_graph_gat_mps.py (274 lines)
Colon 변경점:
  1. Line 29: MPS 우선, OOM 시 CPU fallback
  2. Line 78: k=10 → k=7 (Colon 9,692 샘플 수 고려, GraphSAGE와 일관성)
  3. Line 248: oof_dir "lung_" → "colon_"
  4. Line 253: features_path Colon 경로
  5. Line 270: results_file "lung_" → "colon_"
  6. base_dir: scripts/의 상위 (data/, results/는 프로젝트 루트 기준)
"""

import numpy as np
import pandas as pd
from pathlib import Path
import sys
import json
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import NearestNeighbors

sys.path.insert(0, str(Path(__file__).parent))

from phase2_utils import calculate_metrics, save_results

try:
    import torch_geometric
    from torch_geometric.nn import GATConv
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


class GAT(nn.Module):
    """GAT (Graph Attention Network) for regression"""
    def __init__(self, input_dim, hidden_dim=128, num_heads=4, num_layers=2):
        super().__init__()
        self.convs = nn.ModuleList()

        # First layer
        self.convs.append(GATConv(input_dim, hidden_dim, heads=num_heads, dropout=0.2))

        # Hidden layers
        for _ in range(num_layers - 2):
            self.convs.append(GATConv(hidden_dim * num_heads, hidden_dim, heads=num_heads, dropout=0.2))

        # Last layer (single head)
        if num_layers > 1:
            self.convs.append(GATConv(hidden_dim * num_heads, hidden_dim, heads=1, dropout=0.2))

        self.fc = nn.Linear(hidden_dim, 1)
        self.dropout = nn.Dropout(0.2)

    def forward(self, x, edge_index):
        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)
            if i < len(self.convs) - 1:
                x = F.elu(x)
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


def train_evaluate_gat(X, y, groups, output_stem, oof_dir=None, k_neighbors=7):
    """
    GAT 모델 학습 및 평가 (GroupCV only, MPS with CPU fallback)
    Colon: k_neighbors=7 (Lung k=10에서 축소)
    """
    print(f"\n{'='*120}")
    print(f"GAT - GROUPCV (Drug-based split, device={device})")
    print(f"{'='*120}")

    global device

    try:
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
            model = GAT(input_dim).to(device)
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
            print(f"Restarting GAT on CPU...")

            # Retry on CPU
            return train_evaluate_gat(X, y, groups, output_stem, oof_dir, k_neighbors)
        else:
            raise e

    # Save OOF predictions
    if oof_dir:
        oof_file = oof_dir / "GAT.npy"
        np.save(oof_file, oof_predictions)
        print(f"\n  OOF predictions saved: {oof_file}")

    # Calculate average metrics
    train_sps = [f['train']['spearman'] for f in fold_results]
    val_sps = [f['val']['spearman'] for f in fold_results]

    print(f"\n  Average - Train: {np.mean(train_sps):.4f}, Val: {np.mean(val_sps):.4f}, Gap: {np.mean(train_sps) - np.mean(val_sps):+.4f}")

    results = {
        'model': 'GAT',
        'eval_mode': 'groupcv',
        'device': str(device),
        'fold_results': fold_results
    }

    return results


if __name__ == "__main__":
    # Colon 경로 - scripts/의 상위 (프로젝트 루트)
    base_dir = Path(__file__).parent.parent
    data_dir = base_dir / "data"
    results_dir = base_dir / "results"
    results_dir.mkdir(exist_ok=True)

    # Colon OOF dir
    oof_dir = results_dir / "colon_numeric_graph_v1_oof"
    oof_dir.mkdir(exist_ok=True)

    # Load data
    X = np.load(data_dir / "X_numeric.npy")
    y = np.load(data_dir / "y_train.npy")

    # Load groups - Colon features_slim.parquet
    features_path = base_dir / "fe_qc" / "20260420_colon_fe_v2" / "features_slim.parquet"
    df_meta = pd.read_parquet(features_path, columns=['canonical_drug_id'])
    groups = df_meta['canonical_drug_id'].values

    print(f"\nData: X_numeric.npy")
    print(f"X shape: {X.shape}")
    print(f"y shape: {y.shape}")
    print(f"Unique drugs: {len(np.unique(groups))}")

    # Run GAT with Colon k=7
    results = train_evaluate_gat(X, y, groups, "colon_numeric_graph_v1", oof_dir, k_neighbors=7)

    # Load existing results and merge (GraphSAGE may have written first)
    results_file = results_dir / "colon_numeric_graph_v1_groupcv.json"
    if results_file.exists():
        with open(results_file, 'r') as f:
            all_results = json.load(f)
        all_results['GAT'] = results
    else:
        all_results = {'GAT': results}

    save_results(all_results, results_file)

    print("\n" + "="*120)
    print("GAT Colon 완료!")
    print("="*120)
