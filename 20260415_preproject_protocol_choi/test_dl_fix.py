"""
DL 버그 수정 후 빠른 검증 - FlatMLP Holdout만 테스트
"""
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from phase2_utils import calculate_metrics

# PyTorch 설정
if torch.backends.mps.is_available():
    device = torch.device('mps')
    print(f"Using device: MPS (Metal Performance Shaders)")
else:
    device = torch.device('cpu')
    print(f"Using device: CPU")

# FlatMLP 모델
class FlatMLP(nn.Module):
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

# 학습 함수 (수정 버전)
def train_dl_model_fixed(model, train_loader, val_loader, train_loader_no_shuffle, epochs=30, lr=0.001):
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr)

    model.train()
    for epoch in range(epochs):
        total_loss = 0
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)

            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        if epoch % 5 == 0:
            print(f"  Epoch {epoch+1}: Loss = {total_loss:.4f}")

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

# 데이터 로드
base_dir = Path(__file__).parent
data_dir = base_dir / "data"

X = np.load(data_dir / "X_numeric.npy")
y = np.load(data_dir / "y_train.npy")

print("="*140)
print("DL 버그 수정 검증 - FlatMLP Holdout 테스트")
print("="*140)
print(f"\nData: X shape = {X.shape}")

# Holdout split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# DataLoader
train_dataset = TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(y_train))
test_dataset = TensorDataset(torch.FloatTensor(X_test), torch.FloatTensor(y_test))

train_loader = DataLoader(train_dataset, batch_size=128, shuffle=True)
train_loader_no_shuffle = DataLoader(train_dataset, batch_size=128, shuffle=False)  # 수정!
test_loader = DataLoader(test_dataset, batch_size=128)

# 모델 학습
print("\n학습 중 (30 epochs)...")
model = FlatMLP(X.shape[1]).to(device)
train_pred, test_pred = train_dl_model_fixed(model, train_loader, test_loader, train_loader_no_shuffle, epochs=30)

# 메트릭 계산
train_metrics = calculate_metrics(y_train, train_pred)
test_metrics = calculate_metrics(y_test, test_pred)

print("\n" + "="*140)
print("결과")
print("="*140)

print(f"\n{'Metric':<20} | {'Train':>12} | {'Test':>12} | {'Gap':>12}")
print("-"*140)

for metric in ['spearman', 'pearson', 'r2', 'rmse', 'mae', 'kendall_tau']:
    train_val = train_metrics[metric]
    test_val = test_metrics[metric]
    gap = train_val - test_val

    print(f"{metric:<20} | {train_val:12.4f} | {test_val:12.4f} | {gap:12.4f}")

print("\n" + "="*140)
print("✅ 수정 성공 여부 확인:")
print("="*140)

if train_metrics['spearman'] > 0.5:
    print(f"✅  Train Spearman = {train_metrics['spearman']:.4f} > 0.5 (정상!)")
else:
    print(f"❌  Train Spearman = {train_metrics['spearman']:.4f} < 0.5 (여전히 문제)")

if train_metrics['r2'] > 0:
    print(f"✅  Train R² = {train_metrics['r2']:.4f} > 0 (정상!)")
else:
    print(f"❌  Train R² = {train_metrics['r2']:.4f} < 0 (여전히 문제)")

print("\n수정 전 예상값: Train Spearman ≈ 0.01, Train R² ≈ -0.81")
print("수정 후 예상값: Train Spearman > 0.8,   Train R² > 0.7")
