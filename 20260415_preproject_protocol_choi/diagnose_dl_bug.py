"""
DL Train 예측 순서 버그 진단
"""
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from sklearn.model_selection import train_test_split
from scipy.stats import spearmanr
from pathlib import Path

# 간단한 MLP 모델
class SimpleMLP(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 1)
        )

    def forward(self, x):
        return self.net(x).squeeze()

# 데이터 로드
base_dir = Path(__file__).parent
data_dir = base_dir / "data"

X = np.load(data_dir / "X_numeric.npy")
y = np.load(data_dir / "y_train.npy")

# Holdout split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print("="*140)
print("DL Train 예측 순서 버그 진단")
print("="*140)
print(f"\nData: X_train shape = {X_train.shape}, y_train shape = {y_train.shape}")
print(f"y_train first 10 values: {y_train[:10]}")

# 디바이스 설정
device = torch.device('mps' if torch.backends.mps.is_available() else 'cpu')
print(f"Device: {device}")

# ============================================================================
# 버그 재현: shuffle=True로 예측 수집
# ============================================================================

print("\n" + "="*140)
print("1. 버그 재현: shuffle=True 사용")
print("="*140)

# DataLoader with shuffle=True (버그 버전)
train_dataset = TensorDataset(torch.FloatTensor(X_train), torch.FloatTensor(y_train))
train_loader_shuffled = DataLoader(train_dataset, batch_size=128, shuffle=True)

# 모델 학습
model = SimpleMLP(X_train.shape[1]).to(device)
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

model.train()
print("\n학습 중 (5 epochs)...")
for epoch in range(5):
    total_loss = 0
    for batch_X, batch_y in train_loader_shuffled:
        batch_X, batch_y = batch_X.to(device), batch_y.to(device)

        optimizer.zero_grad()
        outputs = model(batch_X)
        loss = criterion(outputs, batch_y)
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    if epoch % 1 == 0:
        print(f"  Epoch {epoch+1}: Loss = {total_loss:.4f}")

# 예측 수집 (버그 버전 - shuffled loader 사용)
model.eval()
train_preds_shuffled = []
train_targets_from_loader = []

with torch.no_grad():
    for batch_X, batch_y in train_loader_shuffled:
        batch_X = batch_X.to(device)
        preds = model(batch_X).cpu().numpy()
        train_preds_shuffled.extend(preds)
        train_targets_from_loader.extend(batch_y.numpy())

train_preds_shuffled = np.array(train_preds_shuffled)
train_targets_from_loader = np.array(train_targets_from_loader)

# 원본 y_train과 비교 (버그!)
spearman_bug, _ = spearmanr(y_train, train_preds_shuffled)
r2_bug = 1 - np.sum((y_train - train_preds_shuffled)**2) / np.sum((y_train - y_train.mean())**2)

# Loader에서 수집한 target과 비교 (정상)
spearman_correct, _ = spearmanr(train_targets_from_loader, train_preds_shuffled)
r2_correct = 1 - np.sum((train_targets_from_loader - train_preds_shuffled)**2) / np.sum((train_targets_from_loader - train_targets_from_loader.mean())**2)

print("\n예측 수집 완료:")
print(f"  원본 y_train first 10: {y_train[:10]}")
print(f"  Loader의 target first 10: {train_targets_from_loader[:10]}")
print(f"  예측값 first 10: {train_preds_shuffled[:10]}")

print(f"\n⚠️  버그 버전 (y_train vs train_preds):")
print(f"     Spearman: {spearman_bug:.4f}")
print(f"     R²: {r2_bug:.4f}")

print(f"\n✅  정상 버전 (loader targets vs train_preds):")
print(f"     Spearman: {spearman_correct:.4f}")
print(f"     R²: {r2_correct:.4f}")

# ============================================================================
# 수정 버전: shuffle=False로 예측 수집
# ============================================================================

print("\n" + "="*140)
print("2. 수정 버전: shuffle=False 사용")
print("="*140)

# Non-shuffled loader for prediction
train_loader_no_shuffle = DataLoader(train_dataset, batch_size=128, shuffle=False)

train_preds_fixed = []
with torch.no_grad():
    for batch_X, batch_y in train_loader_no_shuffle:
        batch_X = batch_X.to(device)
        preds = model(batch_X).cpu().numpy()
        train_preds_fixed.extend(preds)

train_preds_fixed = np.array(train_preds_fixed)

# 원본 y_train과 비교 (이제 순서 일치!)
spearman_fixed, _ = spearmanr(y_train, train_preds_fixed)
r2_fixed = 1 - np.sum((y_train - train_preds_fixed)**2) / np.sum((y_train - y_train.mean())**2)

print(f"\n✅  수정 버전 (y_train vs train_preds_fixed):")
print(f"     Spearman: {spearman_fixed:.4f}")
print(f"     R²: {r2_fixed:.4f}")

# ============================================================================
# 결과 비교
# ============================================================================

print("\n" + "="*140)
print("결과 비교")
print("="*140)

print(f"\n{'방법':<40} | {'Spearman':>12} | {'R²':>12} | {'상태':>10}")
print("-"*140)
print(f"{'버그 (shuffled loader + 원본 y)':<40} | {spearman_bug:12.4f} | {r2_bug:12.4f} | {'❌ WRONG':>10}")
print(f"{'정상 (loader targets 사용)':<40} | {spearman_correct:12.4f} | {r2_correct:12.4f} | {'✅ OK':>10}")
print(f"{'수정 (non-shuffled loader)':<40} | {spearman_fixed:12.4f} | {r2_fixed:12.4f} | {'✅ OK':>10}")

print("\n" + "="*140)
print("결론: shuffle=True인 loader로 예측 수집 후 원본 y_train과 비교하면 순서 불일치 발생!")
print("="*140)
