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
from dashboard.views import render_overview


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


# ── Tab 2: Step 1-2 Data & QC (placeholder) ──────────────────────────────────
with tab_data_qc:
    st.subheader("📥 Step 1-2: Data Acquisition & QC")
    st.info(
        "🚧 **Coming soon** — Step 2 QC 리포트 8개 통합 뷰.\n\n"
        "**파싱 대상**:\n"
        "- `reports/step2_1_qc_report.txt`\n"
        "- `reports/step2_4_matching_report.json`\n"
        "- `reports/step2_5_drug_catalog_qc.json`\n"
        "- `reports/step2_5b_bridge_report.json`\n"
        "- `reports/step2_6_lincs_extract_report.json`\n"
        "- `reports/step2_7_lincs_aggregation_report.json`\n"
        "- `reports/step2_8_subtype_report.json`\n"
        "- `reports/step2_integrated_qc_report.json`\n\n"
        "자세한 계획은 `dashboard/TODO.md` 참조."
    )


# ── Tab 3: Step 3 Feature Engineering (placeholder) ─────────────────────────
with tab_fe:
    st.subheader("🧬 Step 3: Feature Engineering & Selection")
    st.info(
        "🚧 **Coming soon** — Step 3/3.5 FE 산출물 시각화.\n\n"
        "**파싱 대상**:\n"
        "- `fe_qc/20260420_colon_fe_v1/`\n"
        "- `fe_qc/20260420_colon_fe_v2/`\n\n"
        "자세한 계획은 `dashboard/TODO.md` 참조."
    )


# ── Tab 4: Step 4 Modeling (placeholder, 다음 단계에서 구현) ────────────────
with tab_modeling:
    st.subheader("🤖 Step 4: Modeling (핵심 탭)")
    st.info(
        "🚧 **Under active development** — 다음 구현 대상 (Phase 3).\n\n"
        "**포함될 섹션**:\n"
        "1. 전체 Ranking 테이블 (필터/정렬)\n"
        "2. 시각화 3종 (Bar / Heatmap / Box)\n"
        "3. Drug vs Scaffold Drop 분석\n"
        "4. 모델 드릴다운 (Fold별 상세)\n\n"
        "**데이터 준비 완료**: 129 experiments in 30 JSON files (Drug + Scaffold + 5-Fold)\n"
        "**Primary view**: Drug + Scaffold (90 experiments)"
    )
    st.markdown("---")
    st.markdown("**임시 요약** (Overview 탭 참조):")
    st.markdown(
        "- 🏆 **Best Drug Split**: CatBoost Phase 2B = 0.4881\n"
        "- 🏆 **Best Scaffold Split**: LightGBM Phase 2B = 0.4041\n"
        "- 💾 CSV: `reports/step4_parser_summary.csv`"
    )


# ── Tab 5: Step 5 Ensemble (placeholder) ────────────────────────────────────
with tab_ensemble:
    st.subheader("🎯 Step 5: Ensemble Analysis")
    st.info(
        "⏸️ **Pending** — Step 4 완료 후 착수 예정.\n\n"
        "**참고**: Lung 파이프라인의 `phase3_ensemble_analysis.py` 구조 재사용.\n"
        "**Lung 결과**: 양수 Gain 4/24 combinations\n\n"
        "자세한 계획은 `dashboard/TODO.md` 참조."
    )


# ── Tab 6: Step 6 External Validation (placeholder) ────────────────────────
with tab_validation:
    st.subheader("✅ Step 6: External Validation")
    st.info(
        "⏸️ **Pending** — Step 5 앙상블 완료 후 착수 예정.\n\n"
        "**검증 데이터셋** (옵션 B):\n"
        "- CPTAC-CRC\n"
        "- GSE39582\n"
        "- COSMIC-CRC\n"
        "- PRISM (CRC)\n"
        "- ClinicalTrials (CRC)\n\n"
        "자세한 계획은 `dashboard/TODO.md` 참조."
    )


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
