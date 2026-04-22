"""
dashboard.utils — 상수, 스타일, 헬퍼.

사용 예:
    from dashboard.utils import (
        PROJECT_ROOT, RESULTS_DIR,
        COLORS, PHASE_MAP,
        inject_global_css, render_header,
    )
"""

# constants
from dashboard.utils.constants import (
    # 경로
    CURATED_DATA_DIR,
    DATA_DIR,
    FE_QC_DIR,
    LOGS_DIR,
    LUNG_DIR,
    PROJECT_ROOT,
    REPORTS_DIR,
    RESULTS_DIR,
    STAD_DIR,
    WORKSPACE_ROOT,
    # 메타
    DISEASE,
    PROJECT_NAME,
    PROTOCOL_VERSION,
    # 매핑
    CATEGORY_MAP,
    CATEGORY_ORDER,
    PHASE_MAP,
    PHASE_ORDER,
    PRIMARY_SPLITS,
    SPLIT_MAP,
    SPLIT_ORDER,
    # 모델
    ALL_MODELS,
    DL_MODELS,
    GRAPH_MODELS,
    ML_MODELS,
    get_model_category,
    # 색상
    CATEGORY_COLORS,
    COLORS,
    PHASE_COLORS,
    SPLIT_COLORS,
    # 임계값
    OVERFITTING_THRESHOLD,
    STABILITY_THRESHOLD,
    # 파이프라인
    PIPELINE_STEPS,
    STATUS_ICONS,
    STATUS_LABELS,
)

# styles
from dashboard.utils.styles import (
    GLOBAL_CSS,
    inject_global_css,
    render_header,
    render_metric_card,
    render_step_badge,
)

__all__ = [
    # 경로
    "PROJECT_ROOT",
    "DATA_DIR",
    "RESULTS_DIR",
    "REPORTS_DIR",
    "LOGS_DIR",
    "FE_QC_DIR",
    "CURATED_DATA_DIR",
    "WORKSPACE_ROOT",
    "LUNG_DIR",
    "STAD_DIR",
    # 메타
    "PROJECT_NAME",
    "DISEASE",
    "PROTOCOL_VERSION",
    # 매핑
    "PHASE_MAP",
    "PHASE_ORDER",
    "SPLIT_MAP",
    "SPLIT_ORDER",
    "PRIMARY_SPLITS",
    "CATEGORY_MAP",
    "CATEGORY_ORDER",
    # 모델
    "ML_MODELS",
    "DL_MODELS",
    "GRAPH_MODELS",
    "ALL_MODELS",
    "get_model_category",
    # 색상
    "COLORS",
    "SPLIT_COLORS",
    "CATEGORY_COLORS",
    "PHASE_COLORS",
    # 임계값
    "OVERFITTING_THRESHOLD",
    "STABILITY_THRESHOLD",
    # 파이프라인
    "PIPELINE_STEPS",
    "STATUS_ICONS",
    "STATUS_LABELS",
    # 스타일
    "GLOBAL_CSS",
    "inject_global_css",
    "render_header",
    "render_metric_card",
    "render_step_badge",
]
