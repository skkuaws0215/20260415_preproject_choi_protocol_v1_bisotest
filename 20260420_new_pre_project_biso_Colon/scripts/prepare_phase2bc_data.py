"""
Phase 2B/2C 데이터 준비 - Colon 버전
- Phase 2B: SMILES features 추가 (64-bit Morgan FP)
- Phase 2C: Context features 추가 (64-dim hash-based embedding)

Original: Lung prepare_phase2bc_data.py (180 lines)
Colon 변경점:
  1. base_dir: Colon 프로젝트 루트로 변경
  2. features_slim.parquet 경로: fe_qc/20260420_colon_fe_v2/ 하위
  3. drug_features.parquet 경로: data/ 하위 (Lung과 동일하게 전제)

전제조건:
  - data/X_numeric.npy (Phase 2A 입력) 가 이미 생성되어 있어야 함
  - data/y_train.npy 가 이미 생성되어 있어야 함
  - data/drug_features.parquet 에 canonical_smiles 컬럼 존재
"""

import numpy as np
import pandas as pd
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import AllChem, Descriptors
from collections import Counter
import json

def smiles_to_fingerprint(smiles, radius=2, n_bits=64):
    """SMILES를 Morgan Fingerprint로 변환 (64-bit)"""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return np.zeros(n_bits)
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, radius, nBits=n_bits)
        return np.array(fp)
    except:
        return np.zeros(n_bits)


def tokenize_smiles(smiles, max_len=256):
    """
    SMILES를 토큰 ID로 변환
    간단한 character-level tokenization
    """
    # Character vocabulary (SMILES에서 자주 사용되는 문자들)
    chars = ['<PAD>', '<START>', '<END>', '<UNK>',
             'C', 'c', 'O', 'N', 'n', 'S', 's', 'F', 'Cl', 'Br', 'I',
             '(', ')', '[', ']', '=', '#', '@', '+', '-', '/', '\\',
             '1', '2', '3', '4', '5', '6', '7', '8', '9', '0']

    char_to_idx = {c: i for i, c in enumerate(chars)}

    # Tokenize
    tokens = [char_to_idx.get('<START>', 1)]

    if smiles and isinstance(smiles, str):
        for char in smiles[:max_len-2]:  # Reserve space for START and END
            tokens.append(char_to_idx.get(char, char_to_idx['<UNK>']))

    tokens.append(char_to_idx.get('<END>', 2))

    # Pad to max_len
    while len(tokens) < max_len:
        tokens.append(char_to_idx.get('<PAD>', 0))

    return np.array(tokens[:max_len])


def create_context_features(df_features, df_drugs):
    """
    Context features 생성 (Phase 2C용)
    drug_id hash 기반 64-dim 임베딩 (placeholder)
    """
    context_dim = 64
    drug_to_context = {}

    for drug_id in df_drugs['canonical_drug_id']:
        # 간단한 해시 기반 임베딩
        np.random.seed(hash(str(drug_id)) % 2**32)
        drug_to_context[drug_id] = np.random.randn(context_dim) * 0.1

    return drug_to_context


print("="*120)
print("Phase 2B/2C 데이터 생성 (Colon)")
print("="*120)

# Colon 경로 - scripts/ 상위를 base로
base_dir = Path(__file__).parent.parent   # 20260420_new_pre_project_biso_Colon/
data_dir = base_dir / "data"

# Colon features_slim.parquet 경로
features_slim_path = base_dir / "fe_qc" / "20260420_colon_fe_v2" / "features_slim.parquet"

# Load data
print("\n1. 데이터 로드...")
X_numeric = np.load(data_dir / "X_numeric.npy")
y_train = np.load(data_dir / "y_train.npy")
df_features = pd.read_parquet(features_slim_path, columns=['sample_id', 'canonical_drug_id'])
df_drugs = pd.read_parquet(data_dir / "drug_features.parquet")

print(f"   X_numeric: {X_numeric.shape}")
print(f"   Unique drugs: {df_features['canonical_drug_id'].nunique()}")

# Merge to get SMILES for each sample
print("\n2. SMILES 매칭...")
df_merged = df_features.merge(df_drugs[['canonical_drug_id', 'canonical_smiles']], on='canonical_drug_id', how='left')
print(f"   Merged: {len(df_merged)} samples")
print(f"   SMILES 있는 샘플: {df_merged['canonical_smiles'].notna().sum()} ({df_merged['canonical_smiles'].notna().mean()*100:.1f}%)")

# Generate SMILES features
print("\n3. SMILES Fingerprints 생성 (64-bit)...")
smiles_fps = []
for idx, smiles in enumerate(df_merged['canonical_smiles']):
    if pd.isna(smiles):
        smiles_fps.append(np.zeros(64))  # Zero for missing SMILES
    else:
        smiles_fps.append(smiles_to_fingerprint(smiles, n_bits=64))

    if (idx + 1) % 1000 == 0:
        print(f"   Progress: {idx + 1}/{len(df_merged)}")

smiles_fps = np.array(smiles_fps, dtype=np.float32)
print(f"   SMILES fingerprints: {smiles_fps.shape}")

# Create X_numeric_smiles
X_numeric_smiles = np.concatenate([X_numeric, smiles_fps], axis=1)
print(f"   X_numeric_smiles: {X_numeric_smiles.shape}")

# Generate SMILES tokens
print("\n4. SMILES Tokens 생성 (256 tokens)...")
smiles_tokens = []
for idx, smiles in enumerate(df_merged['canonical_smiles']):
    if pd.isna(smiles):
        smiles_tokens.append(np.zeros(256, dtype=np.int32))  # Pad for missing
    else:
        smiles_tokens.append(tokenize_smiles(smiles, max_len=256))

    if (idx + 1) % 1000 == 0:
        print(f"   Progress: {idx + 1}/{len(df_merged)}")

smiles_tokens = np.array(smiles_tokens, dtype=np.int32)
print(f"   smiles_token_ids: {smiles_tokens.shape}")

# Generate context features
print("\n5. Context Features 생성 (64-dim)...")
drug_to_context = create_context_features(df_features, df_drugs)

context_features = []
for drug_id in df_merged['canonical_drug_id']:
    context_features.append(drug_to_context.get(drug_id, np.zeros(64)))

context_features = np.array(context_features, dtype=np.float32)
print(f"   context_codes: {context_features.shape}")

# Create X_numeric_context_smiles
X_numeric_context_smiles = np.concatenate([X_numeric, context_features, smiles_fps], axis=1)
print(f"   X_numeric_context_smiles: {X_numeric_context_smiles.shape}")

# Save files
print("\n6. 파일 저장...")
np.save(data_dir / "X_numeric_smiles.npy", X_numeric_smiles)
print(f"   ✓ X_numeric_smiles.npy saved ({X_numeric_smiles.shape})")

np.save(data_dir / "smiles_token_ids.npy", smiles_tokens)
print(f"   ✓ smiles_token_ids.npy saved ({smiles_tokens.shape})")

np.save(data_dir / "context_codes.npy", context_features)
print(f"   ✓ context_codes.npy saved ({context_features.shape})")

np.save(data_dir / "X_numeric_context_smiles.npy", X_numeric_context_smiles)
print(f"   ✓ X_numeric_context_smiles.npy saved ({X_numeric_context_smiles.shape})")

# Save context vocab (for reference)
context_vocab = {
    'context_dim': 64,
    'description': 'Drug context embeddings (hash-based)',
    'num_drugs': len(drug_to_context)
}
with open(data_dir / "context_vocab.json", 'w') as f:
    json.dump(context_vocab, f, indent=2)
print(f"   ✓ context_vocab.json saved")

# Summary
print("\n" + "="*120)
print("완료!")
print("="*120)
print(f"Phase 2A: X_numeric             {X_numeric.shape}")
print(f"Phase 2B: X_numeric_smiles      {X_numeric_smiles.shape}  (+{X_numeric_smiles.shape[1] - X_numeric.shape[1]} features)")
print(f"Phase 2C: X_numeric_context_smiles {X_numeric_context_smiles.shape}  (+{X_numeric_context_smiles.shape[1] - X_numeric.shape[1]} features)")
print(f"\nSMILES 커버리지: {df_merged['canonical_smiles'].notna().mean()*100:.1f}%")
print(f"SMILES 없는 샘플은 zero padding 처리됨")
print("="*120)
