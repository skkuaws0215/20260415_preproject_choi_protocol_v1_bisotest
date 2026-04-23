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
# 탭 구성 (10개)
# ─────────────────────────────────────────────────────────────────────────────

(
    tab1,
    tab2,
    tab3,
    tab4,
    tab5,
    tab6,
    tab7,
    tab8,
    tab9,
    tab10,
) = st.tabs(
    [
        "🏠 Overview",
        "📥 Step 1-2 Data & QC",
        "🧬 Step 3 Feature Eng",
        "🤖 Step 4 Modeling",
        "🎯 Step 5 Ensemble",
        "✅ Step 6 Validation",
        "💊 Step 7 ADMET",
        "🕸️ Step 8 KG",
        "📝 Step 9 LLM",
        "🔬 Comparison",
    ]
)


# ── Tab 1: Overview (구현 완료) ──────────────────────────────────────────────
with tab1:
    render_overview()


# ── Tab 2: Step 1-2 Data & QC ────────────────────────────────────────────────
with tab2:
    from dashboard.views.step2_data_qc import render_step2_data_qc
    render_step2_data_qc()


# ── Tab 3: Step 3 Feature Engineering ────────────────────────────────────────
with tab3:
    from dashboard.views.step3_fe import render_step3_fe
    render_step3_fe()


# ── Tab 4: Step 4 Modeling ───────────────────────────────────────────────────
with tab4:
    render_step4()


# ── Tab 5: Step 5 Ensemble ──────────────────────────────────────────────────
with tab5:
    from dashboard.views.step5_ensemble import render_step5_ensemble
    render_step5_ensemble()


# ── Tab 6: Step 6 Validation ────────────────────────────────────────────────
with tab6:
    from dashboard.views import step6_validation
    step6_validation.render()


# ── Tab 7: Step 7 ADMET ─────────────────────────────────────────────────────
with tab7:
    from dashboard.views import step7_admet
    step7_admet.render()


# ── Tab 8: Step 8 Knowledge Graph ───────────────────────────────────────────
with tab8:
    from dashboard.views import step8_knowledge_graph
    step8_knowledge_graph.render()


# ── Tab 9: Step 9 LLM ────────────────────────────────────────────────────────
with tab9:
    from dashboard.views import step9_llm
    step9_llm.render()


# ── Tab 10: Comparison ───────────────────────────────────────────────────────
with tab10:
    st.subheader("🔬 Cross-Disease Comparison")
    from dashboard.views import step8_knowledge_graph
    step8_knowledge_graph.render()


# ─────────────────────────────────────────────────────────────────────────────
# Footer
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("---")
st.caption(
    f"🧬 {PROJECT_NAME} Pipeline Dashboard · " f"{DISEASE} · " f"Built with Streamlit"
)
