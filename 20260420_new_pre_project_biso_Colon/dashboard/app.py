"""
Colon Drug Repurposing Pipeline Dashboard — Main App.

실행:
    cd <프로젝트 루트>
    streamlit run dashboard/app.py

탭 구조:
    Tab 1: 🏠 Overview              (구현 완료)
    Tab 2: 📥 Step 1-2 Data & QC    (placeholder)
    Tab 3: 🧬 Step 3 Feature Eng    (placeholder)
    Tab 4: 🤖 Step 4 Modeling       (placeholder — 다음 단계에서 구현)
    Tab 5: 🎯 Step 5 Ensemble       (placeholder)
    Tab 6: ✅ Step 6 Validation     (placeholder)
    Tab 7: 🔬 Comparison            (placeholder)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit 실행 시 PYTHONPATH 자동 설정을 위해 프로젝트 루트를 path 에 추가
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from dashboard.utils import (
    DISEASE,
    PROJECT_NAME,
    inject_global_css,
    render_header,
)
from dashboard.views import render_overview, render_step4


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit 페이지 설정 (최상단에 한 번만)
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title=f"{PROJECT_NAME} Pipeline Dashboard",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ─────────────────────────────────────────────────────────────────────────────
# 글로벌 스타일 + 헤더
# ─────────────────────────────────────────────────────────────────────────────

inject_global_css()
render_header()


# ─────────────────────────────────────────────────────────────────────────────
# 탭 구성 (7개)
# ─────────────────────────────────────────────────────────────────────────────

(
    tab_overview,
    tab_data_qc,
    tab_fe,
    tab_modeling,
    tab_ensemble,
    tab_validation,
    tab_compare,
) = st.tabs(
    [
        "🏠 Overview",
        "📥 Step 1-2 Data & QC",
        "🧬 Step 3 Feature Eng",
        "🤖 Step 4 Modeling",
        "🎯 Step 5 Ensemble",
        "✅ Step 6 Validation",
        "🔬 Comparison",
    ]
)


# ── Tab 1: Overview (구현 완료) ──────────────────────────────────────────────
with tab_overview:
    render_overview()


# ── Tab 2: Step 1-2 Data & QC ────────────────────────────────────────────────
with tab_data_qc:
    from dashboard.views.step2_data_qc import render_step2_data_qc
    render_step2_data_qc()


# ── Tab 3: Step 3 Feature Engineering ────────────────────────────────────────
with tab_fe:
    from dashboard.views.step3_fe import render_step3_fe
    render_step3_fe()


# ── Tab 4: Step 4 Modeling ───────────────────────────────────────────────────
with tab_modeling:
    render_step4()


# ── Tab 5: Step 5 Ensemble ──────────────────────────────────────────────────
with tab_ensemble:
    from dashboard.views.step5_ensemble import render_step5_ensemble
    render_step5_ensemble()


# ── Tab 6: Step 6-9 Integrated Results ─────────────────────────────────────
with tab_validation:
    from dashboard.views import step6_9_results
    step6_9_results.render()


# ── Tab 7: Comparison (placeholder) ─────────────────────────────────────────
with tab_compare:
    st.subheader("🔬 Comparison: Lung vs Colon vs STAD")
    st.info(
        "🚧 **Coming later** — 3개 암종 통합 비교 뷰.\n\n"
        "**전제 조건**:\n"
        "- 파서 암종 prefix 일반화 (`colon_*` → `{lung,colon,stad}_*`)\n"
        "- Lung Step 4 결과 재파싱\n"
        "- STAD Step 4 결과 완료 대기\n\n"
        "**현재 수치** (세션 요약 기준):\n"
        "- Lung 최고 (CatBoost 2C): **0.5030**\n"
        "- Colon 최고 (CatBoost 2B): **0.4881**\n"
        "- 차이: **-0.0149** (Lung 우세)\n\n"
        "자세한 계획은 `dashboard/TODO.md` 참조."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.caption(
    f"🧬 {PROJECT_NAME} Pipeline Dashboard · " f"{DISEASE} · " f"Built with Streamlit"
)
