"""
대시보드 전역 상수.

- 경로
- 모델 분류 (ML/DL/Graph)
- Phase 매핑
- Split 매핑
- 색상 팔레트 (Lung 대시보드 참고)

수정 시 주의: 이 파일만 바꾸면 모든 뷰에 반영됨.
"""

from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# 경로 (프로젝트 루트 기준)
# ─────────────────────────────────────────────────────────────────────────────
# dashboard/utils/constants.py → 프로젝트 루트는 2단계 상위
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs"
FE_QC_DIR = PROJECT_ROOT / "fe_qc"
CURATED_DATA_DIR = PROJECT_ROOT / "curated_data"  # 규칙 1: 읽기 전용

# 타 프로젝트 (Lung/STAD 비교용)
WORKSPACE_ROOT = PROJECT_ROOT.parent
LUNG_DIR = WORKSPACE_ROOT / "20260416_new_pre_project_biso_Lung"
STAD_DIR = WORKSPACE_ROOT / "20260421_new_pre_project_biso_STAD"

# ─────────────────────────────────────────────────────────────────────────────
# 프로젝트 메타
# ─────────────────────────────────────────────────────────────────────────────
PROJECT_NAME = "Colon"
DISEASE = "Colorectal Cancer (COAD+READ)"
PROTOCOL_VERSION = "v3.1"

# ─────────────────────────────────────────────────────────────────────────────
# Step 4 실험 차원
# ─────────────────────────────────────────────────────────────────────────────

# Phase 매핑 (파일명 키 ↔ 표시 이름)
PHASE_MAP = {
    "numeric": "Phase 2A",
    "numeric_smiles": "Phase 2B",
    "numeric_context_smiles": "Phase 2C",
}

PHASE_ORDER = ["Phase 2A", "Phase 2B", "Phase 2C"]

# 파일명 suffix → Split 이름
SPLIT_MAP = {
    "groupcv": "Drug Split",
    "scaffoldcv": "Scaffold Split",
    "5foldcv": "5-Fold CV",
    "holdout": "Holdout",
}

SPLIT_ORDER = ["Drug Split", "Scaffold Split", "5-Fold CV", "Holdout"]

# 주로 볼 split (Step 4 핵심)
PRIMARY_SPLITS = ["Drug Split", "Scaffold Split"]

# Category (파일명 키 ↔ 표시 이름)
CATEGORY_MAP = {
    "ml": "ML",
    "dl": "DL",
    "graph": "Graph",
}

CATEGORY_ORDER = ["ML", "DL", "Graph"]

# 모델 카테고리 분류 (파서가 JSON에서 자동 감지하므로 참고용)
# Lung generate_final_comprehensive_report.py 기반
ML_MODELS = [
    "LightGBM",
    "LightGBM_DART",
    "XGBoost",
    "CatBoost",
    "RandomForest",
    "ExtraTrees",
]

DL_MODELS = [
    "FlatMLP",
    "ResidualMLP",
    "TabNet",
    "TabTransformer",
    "FTTransformer",
    "WideDeep",
    "CrossAttention",
]

GRAPH_MODELS = [
    "GraphSAGE",
    "GAT",
]

ALL_MODELS = ML_MODELS + DL_MODELS + GRAPH_MODELS


def get_model_category(model_name: str) -> str:
    """모델 이름 → 카테고리 반환."""
    if model_name in ML_MODELS:
        return "ML"
    if model_name in DL_MODELS:
        return "DL"
    if model_name in GRAPH_MODELS:
        return "Graph"
    return "Unknown"


# ─────────────────────────────────────────────────────────────────────────────
# 색상 팔레트 (Lung 대시보드 gradient 참고)
# ─────────────────────────────────────────────────────────────────────────────
COLORS = {
    "primary": "#667eea",       # Lung gradient start
    "secondary": "#764ba2",     # Lung gradient end
    "success": "#10b981",       # green
    "warning": "#f59e0b",       # amber
    "danger": "#ef4444",        # red
    "neutral": "#6b7280",       # gray
    "bg_light": "#f8f9fa",
}

# Split 별 색상 (차트용)
SPLIT_COLORS = {
    "Drug Split": "#667eea",
    "Scaffold Split": "#f59e0b",
    "5-Fold CV": "#10b981",
    "Holdout": "#ef4444",
}

# Category 별 색상
CATEGORY_COLORS = {
    "ML": "#667eea",
    "DL": "#764ba2",
    "Graph": "#10b981",
}

# Phase 별 색상
PHASE_COLORS = {
    "Phase 2A": "#667eea",
    "Phase 2B": "#764ba2",
    "Phase 2C": "#10b981",
}

# ─────────────────────────────────────────────────────────────────────────────
# 임계값 (프로토콜 기준)
# ─────────────────────────────────────────────────────────────────────────────
OVERFITTING_THRESHOLD = 0.15   # train-val gap
STABILITY_THRESHOLD = 0.05     # val std across folds

# ─────────────────────────────────────────────────────────────────────────────
# Step 파이프라인 상태 (Overview 탭용)
# ─────────────────────────────────────────────────────────────────────────────
PIPELINE_STEPS = [
    {"id": "step1", "name": "Step 1: Raw -> Parquet", "status": "done"},
    {"id": "step2", "name": "Step 2: QC (10 sub-steps)", "status": "done"},
    {"id": "step3", "name": "Step 3: Feature Engineering", "status": "done"},
    {"id": "step3_5", "name": "Step 3.5: Feature Selection", "status": "done"},
    {"id": "step4", "name": "Step 4: Modeling", "status": "in_progress"},
    {"id": "step5", "name": "Step 5: Ensemble", "status": "pending"},
    {"id": "step6", "name": "Step 6: External Validation", "status": "pending"},
]

STATUS_ICONS = {
    "done": "✅",
    "in_progress": "🔄",
    "pending": "⏸️",
    "failed": "❌",
}

STATUS_LABELS = {
    "done": "완료",
    "in_progress": "진행 중",
    "pending": "대기",
    "failed": "실패",
}
